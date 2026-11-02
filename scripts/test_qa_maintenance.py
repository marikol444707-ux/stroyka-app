"""Pure fake connections. No DB library/application imports or SQL execution."""
import ast
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock
from scripts.qa_maintenance import maintain, Journal, TARGET


class Result:
    def __init__(self, value): self.value = value
    def scalar(self): return self.value
    def one(self): return self.value
    def all(self): return self.value


class Connection:
    def __init__(self, name, pid):
        self.ident = (name, 50 if name == 'stroyka_qa' else 5, 'cluster', '172.18.0.2', 5432, pid)
        self.calls = []
        self.allow = True
        self.sessions = []
        self.fail = None
        self.superuser = True
        self.tx = MagicMock(is_active=True)
        self.options = {'isolation_level': 'AUTOCOMMIT'}
    def rollback(self): pass
    def begin(self): return self.tx
    def get_execution_options(self): return self.options
    def exec_driver_sql(self, sql, params=None, **kwargs):
        self.calls.append((sql, params))
        if self.fail and self.fail in sql: raise RuntimeError('synthetic failure')
        if 'SELECT current_database()' in sql: return Result(self.ident)
        if 'pg_try_advisory_lock' in sql: return Result(True)
        if 'SELECT rolsuper' in sql: return Result(self.superuser)
        if 'SELECT datallowconn' in sql: return Result(self.allow)
        if 'ALLOW_CONNECTIONS false' in sql: self.allow = False
        if 'ALLOW_CONNECTIONS true' in sql: self.allow = True
        if 'FROM pg_stat_activity' in sql: return Result(list(self.sessions))
        if 'pg_terminate_backend' in sql:
            self.sessions = [row for row in self.sessions if row[0] != params[0]]
            return Result(True)
        if 'SELECT version_num' in sql: return Result([(TARGET,)])
        return Result(0)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.c = Connection('postgres', 1)
        self.w = Connection('stroyka_qa', 2)
        self.j = MagicMock()
        self.up = MagicMock()
    def run_case(self):
        return maintain(self.c, self.w, service_database='postgres', expected_host='172.18.0.2',
                        statements=('CREATE TABLE synthetic(id int)',), upgrade=self.up, journal=self.j)
    def test_one_work_connection_and_restore(self):
        self.c.sessions = [(3, 'client backend')]
        self.run_case()
        self.up.assert_called_once_with(self.w)
        self.w.tx.commit.assert_called_once()
        self.assertTrue(self.c.allow)
        self.assertIn(('SELECT pg_terminate_backend(%s, 5000)', (3,)), self.c.calls)
        self.assertTrue(any(x.kwargs.get('phase') == 'before_gate' for x in self.j.record.call_args_list))
    def test_wrong_cluster_no_gate(self):
        self.w.ident = (*self.w.ident[:2], 'other', *self.w.ident[3:])
        with self.assertRaises(ValueError): self.run_case()
        self.assertFalse(any('ALTER DATABASE' in sql for sql, _ in self.c.calls))
    def test_insufficient_privileges_no_gate(self):
        self.c.superuser = False
        with self.assertRaises(ValueError): self.run_case()
        self.assertTrue(self.c.allow)
        self.up.assert_not_called()
    def test_already_closed_not_reopened(self):
        self.c.allow = False
        with self.assertRaises(ValueError): self.run_case()
        self.assertFalse(self.c.allow)
    def test_journal_failure_prevents_gate(self):
        self.j.record.side_effect = OSError('synthetic')
        with self.assertRaises(OSError): self.run_case()
        self.assertFalse(any('ALTER DATABASE' in sql for sql, _ in self.c.calls))
    def test_background_worker_not_terminated(self):
        self.c.sessions = [(9, 'logical replication worker')]
        with self.assertRaises(ValueError): self.run_case()
        self.assertFalse(any('pg_terminate_backend' in sql for sql, _ in self.c.calls))
        self.assertTrue(self.c.allow)
    def test_upgrade_failure_rolls_back_before_reopen(self):
        self.up.side_effect = RuntimeError('synthetic')
        with self.assertRaises(RuntimeError): self.run_case()
        self.w.tx.rollback.assert_called_once()
        self.w.tx.commit.assert_not_called()
        self.assertTrue(self.c.allow)
    def test_interrupt_rolls_back(self):
        self.up.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_case()
        self.w.tx.rollback.assert_called_once()
        self.assertTrue(self.c.allow)
    def test_commit_loss_does_not_claim_rollback_or_reopen(self):
        self.w.tx.commit.side_effect = RuntimeError('lost response')
        with self.assertRaises(RuntimeError): self.run_case()
        self.assertFalse(self.c.allow)
        self.assertTrue(any(x.kwargs.get('recovery_required') for x in self.j.record.call_args_list))
    def test_rollback_failure_leaves_closed(self):
        self.up.side_effect = RuntimeError('synthetic')
        self.w.tx.rollback.side_effect = RuntimeError('lost connection')
        with self.assertRaises(RuntimeError): self.run_case()
        self.assertFalse(self.c.allow)
    def test_restore_failure_propagates(self):
        self.c.fail = 'ALLOW_CONNECTIONS true'
        with self.assertRaises(RuntimeError): self.run_case()
        self.assertFalse(self.c.allow)
    def test_journal_exclusive_and_private(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'journal.jsonl'
            j = Journal(p)
            j.record(phase='test')
            j.close()
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): Journal(p)
    def test_env_uses_supplied_connection_without_engine_or_config_import(self):
        tree = ast.parse(Path('migrations/env.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_migrations_online')
        context, factory = MagicMock(), MagicMock()
        supplied = object()
        scope = dict(config=SimpleNamespace(attributes={'connection': supplied}), context=context,
                     target_metadata=None, create_engine=factory)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<pure function>', 'exec'), scope)
        scope['run_migrations_online']()
        context.configure.assert_called_once_with(connection=supplied, target_metadata=None)
        factory.assert_not_called()
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.module == 'backend.db' for n in tree.body))
    def test_env_normal_path_still_opens_engine(self):
        tree = ast.parse(Path('migrations/env.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_migrations_online')
        context, factory = MagicMock(), MagicMock()
        scope = dict(config=SimpleNamespace(attributes={}), context=context, target_metadata=None,
                     create_engine=factory, _database_url=lambda:'synthetic', pool=SimpleNamespace(NullPool='pool'))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<pure function>', 'exec'), scope)
        scope['run_migrations_online']()
        factory.assert_called_once_with('synthetic', poolclass='pool')

    def test_wrong_database_no_gate(self):
        self.w.ident = ('production', *self.w.ident[1:])
        with self.assertRaises(ValueError): self.run_case()
        self.assertFalse(any('ALTER DATABASE' in sql for sql, _ in self.c.calls))

    def test_termination_failure_restores_without_schema_writes(self):
        self.c.sessions = [(3, 'client backend')]
        self.c.fail = 'pg_terminate_backend'
        with self.assertRaises(RuntimeError): self.run_case()
        self.assertTrue(self.c.allow)
        self.assertFalse(any('DROP SCHEMA' in sql for sql, _ in self.w.calls))

    def test_graph_has_no_direct_connection_or_transaction_escape(self):
        revisions = {}
        for path in Path('migrations/versions').glob('*.py'):
            tree = ast.parse(path.read_text())
            values = {}
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('revision', 'down_revision'):
                    values[node.targets[0].id] = ast.literal_eval(node.value)
            revisions[values['revision']] = values['down_revision']
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = ast.unparse(node.func).split('.')[-1]
                    self.assertNotIn(name, ('connect', 'get_db', 'create_engine', 'commit', 'autocommit_block'), str(path))
        visited = set()
        current = TARGET
        while current:
            self.assertNotIn(current, visited)
            visited.add(current)
            current = revisions[current]
        self.assertEqual(visited, set(revisions))

    def test_preflight_connections_only_reads_and_checks_privileges(self):
        from scripts.qa_maintenance import preflight_connections
        evidence=preflight_connections(self.c,self.w,service_database='postgres',expected_host='172.18.0.2')
        self.assertEqual(evidence['database_oid'],50)
        for sql,params in self.c.calls+self.w.calls:
            self.assertTrue(sql.startswith('SELECT') or sql=='SET TRANSACTION READ ONLY',sql)
        self.c.superuser=False
        with self.assertRaises(ValueError):
            preflight_connections(self.c,self.w,service_database='postgres',expected_host='172.18.0.2')
        self.assertTrue(self.c.allow)


class ParameterDispatchConnection(Connection):
    """Model SQLAlchemy's omitted-parameter {} and DBAPI formatting branch.

    No driver, SQL execution or database connection. The formatter rejects literal
    percent with a parameter object, instead of silently accepting every string.
    """
    def __init__(self, name, pid, *, drop_option=False):
        super().__init__(name, pid)
        self.dispatches = []
        self.drop_option = drop_option

    def exec_driver_sql(self, sql, params=None, **kwargs):
        effective = {} if params is None else params
        no_parameters = kwargs.get('execution_options', {}).get('no_parameters', False)
        if self.drop_option:
            no_parameters = False
        arguments = (sql,) if no_parameters and not effective else (sql, effective)
        self.dispatches.append(arguments)
        if len(arguments) == 2:
            # Models the formatter trigger, not the exact psycopg2 error wording.
            sql % effective
        return super().exec_driver_sql(sql, params, **kwargs)


class PercentDispatchRegressionTests(unittest.TestCase):
    def connections(self, *, drop_option=False):
        return (ParameterDispatchConnection('postgres', 1),
                ParameterDispatchConnection('stroyka_qa', 2, drop_option=drop_option))

    def preflight(self, c, w):
        from scripts.qa_maintenance import preflight_connections
        return preflight_connections(c, w, service_database='postgres', expected_host='172.18.0.2')

    def maintenance(self, c, w):
        return maintain(c, w, service_database='postgres', expected_host='172.18.0.2',
                        statements=("SELECT 'synthetic%literal'",), upgrade=MagicMock(), journal=MagicMock())

    def test_old_dispatch_fails_in_both_catalog_checks(self):
        for operation in (self.preflight, self.maintenance):
            with self.subTest(operation=operation.__name__):
                c, w = self.connections(drop_option=True)
                with self.assertRaises((ValueError, TypeError)):
                    operation(c, w)
                self.assertIn("NOT LIKE 'pg_%'", w.dispatches[-1][0])
                self.assertEqual(w.dispatches[-1][1], {})
                self.assertFalse(any('DROP SCHEMA' in args[0] for args in w.dispatches))

    def test_preflight_catalog_omits_dbapi_parameters_only_per_query(self):
        c, w = self.connections()
        self.preflight(c, w)
        catalog = [args for args in w.dispatches if 'pg_namespace' in args[0]]
        self.assertEqual(len(catalog), 1)
        self.assertEqual(len(catalog[0]), 1)
        self.assertTrue(any(len(args) == 2 and args[1] == (50, 'stroyka_qa') for args in c.dispatches))
        self.assertTrue(any(len(args) == 2 and args[1] == {} for args in w.dispatches))

    def test_maintenance_catalog_and_schema_batch_omit_parameters(self):
        c, w = self.connections()
        self.maintenance(c, w)
        percent_calls = [args for args in w.dispatches if '%' in args[0]]
        self.assertEqual(len(percent_calls), 2)
        self.assertTrue(all(len(args) == 1 for args in percent_calls))
        self.assertTrue(any(len(args) == 2 and args[1] == ('stroyka_qa',) for args in c.dispatches))
        w.tx.commit.assert_called_once()

    def test_static_literal_percent_scan_in_qa_tooling(self):
        checked = []
        for path in sorted(Path('scripts').glob('qa_*.py')):
            for node in ast.walk(ast.parse(path.read_text())):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'exec_driver_sql' and node.args
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    continue
                sql = node.args[0].value
                if '%' not in sql or len(node.args) > 1:
                    continue
                options = next((k.value for k in node.keywords if k.arg == 'execution_options'), None)
                self.assertIsNotNone(options, f'{path}:{node.lineno}')
                self.assertIs(ast.literal_eval(options).get('no_parameters'), True)
                checked.append((str(path), node.lineno))
        self.assertEqual(len(checked), 2)


class NetworkIdentityConnection(Connection):
    """Model documented PostgreSQL inet::text versus host(inet) output.

    Rows preserve psycopg2 scalar types: str database/system ID/address and int
    OID/port/PID. No SQL or real driver runs in this model.
    """
    def __init__(self, name, pid, address='172.18.0.2'):
        super().__init__(name, pid)
        self.ident = (*self.ident[:2], '7612345678901234567', address, 5432, pid)

    def exec_driver_sql(self, sql, params=None, **kwargs):
        if 'SELECT current_database()' in sql:
            self.calls.append((sql, params))
            row = list(self.ident)
            if 'inet_server_addr()::text' in sql:
                if row[3] is not None:
                    row[3] += '/128' if ':' in row[3] else '/32'
            elif 'host(inet_server_addr())' not in sql:
                raise AssertionError('Unmodelled address conversion')
            return Result(tuple(row))
        return super().exec_driver_sql(sql, params, **kwargs)


class NetworkIdentityRegressionTests(unittest.TestCase):
    def preflight(self, c, w, expected='172.18.0.2'):
        from scripts.qa_maintenance import preflight_connections
        return preflight_connections(c, w, service_database='postgres', expected_host=expected)

    def test_old_cast_adds_mask_fixed_identity_matches_exact_host(self):
        from scripts.qa_maintenance import identity
        c = NetworkIdentityConnection('postgres', 1)
        w = NetworkIdentityConnection('stroyka_qa', 2)
        # Old projection fails despite the SAME cluster, address and port.
        identity(c)
        old_sql = c.calls[-1][0].replace('host(inet_server_addr())', 'inet_server_addr()::text')
        old_c, old_w = c.exec_driver_sql(old_sql).one(), w.exec_driver_sql(old_sql).one()
        self.assertEqual(old_c[2:5], old_w[2:5])
        self.assertEqual(old_c[3], '172.18.0.2/32')
        self.assertNotEqual(old_c[3], '172.18.0.2')
        result = self.preflight(c, w)
        self.assertEqual(result['server_address'], '172.18.0.2')
        self.assertEqual(result['database_oid'], 50)
        self.assertEqual(c.ident[1], 5)  # Different database OIDs are expected.
        self.assertIs(type(result['server_port']), int)
        self.assertIs(type(result['system_identifier']), str)

    def test_same_projection_used_during_maintenance_and_restore(self):
        c = NetworkIdentityConnection('postgres', 1)
        w = NetworkIdentityConnection('stroyka_qa', 2)
        maintain(c, w, service_database='postgres', expected_host='172.18.0.2',
                 statements=(), upgrade=MagicMock(), journal=MagicMock())
        w.tx.commit.assert_called_once()
        self.assertTrue(c.allow)
        for sql, _ in c.calls + w.calls:
            if 'SELECT current_database()' in sql:
                self.assertIn('host(inet_server_addr())', sql)
                self.assertNotIn('inet_server_addr()::text', sql)

    def test_real_identity_mismatches_remain_rejected(self):
        cases = [(2, 'other-cluster'), (3, '172.18.0.99'), (4, 5433),
                 (4, '5432'), (3, None)]
        for index, value in cases:
            with self.subTest(index=index, value=value):
                c = NetworkIdentityConnection('postgres', 1)
                w = NetworkIdentityConnection('stroyka_qa', 2)
                row = list(w.ident); row[index] = value; w.ident = tuple(row)
                with self.assertRaisesRegex(ValueError, '^QA server identity mismatch$'):
                    self.preflight(c, w)
                self.assertFalse(any('ALTER DATABASE' in sql for sql, _ in c.calls))
        c = NetworkIdentityConnection('postgres', 1, '172.18.0.99')
        w = NetworkIdentityConnection('stroyka_qa', 2, '172.18.0.99')
        with self.assertRaisesRegex(ValueError, '^QA server identity mismatch$'):
            self.preflight(c, w)  # Same cluster/IP but not the expected address.

    def test_ipv6_host_without_mask_still_uses_exact_comparison(self):
        c = NetworkIdentityConnection('postgres', 1, 'fd00::2')
        w = NetworkIdentityConnection('stroyka_qa', 2, 'fd00::2')
        from scripts.qa_maintenance import identity
        identity(c)
        old_sql = c.calls[-1][0].replace('host(inet_server_addr())', 'inet_server_addr()::text')
        self.assertEqual(c.exec_driver_sql(old_sql).one()[3], 'fd00::2/128')
        self.assertEqual(self.preflight(c, w, 'fd00::2')['server_address'], 'fd00::2')
        with self.assertRaisesRegex(ValueError, '^QA server identity mismatch$'):
            self.preflight(c, w, 'fd00::3')
