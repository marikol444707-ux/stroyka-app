"""Local policy mocks/AST only: no install, subprocess, network or real database."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

release = module('unified_release')
checker = module('release_database_check')

class Cursor:
    def __init__(self, revision): self.revision = revision; self.last = ''; self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=None): self.last = sql; self.calls.append(sql)
    def fetchone(self):
        if self.last.startswith('SHOW'): return ('on',)
        if 'server_version_num' in self.last: return (150000, False)
        if 'count(*)' in self.last: return (0,)
        raise AssertionError(self.last)
    def fetchall(self):
        if 'information_schema.columns' in self.last: return [('alembic_version', 'version_num')]
        if 'SELECT version_num' in self.last: return [(self.revision,)]
        if 'pg_catalog.pg_trigger' in self.last: return []
        raise AssertionError(self.last)

class ReleasePolicyTests(unittest.TestCase):
    def graph(self):
        from scripts.test_server_audit_integration_static import migration_graph
        return migration_graph()
    def test_real_source_graph_and_checker_agree(self):
        release.validate_revision_graph(self.graph())
        self.assertEqual(release.BASE_REVISION, checker.SOURCE_REVISION)
        self.assertEqual(release.TARGET_REVISION, checker.TARGET_REVISION)
        self.assertEqual(list(release.PENDING_REVISIONS), checker.PENDING_REVISIONS)
    def test_old_head_and_dangling_and_audit_lineage_rejected(self):
        for mode in ('missing', 'old_audit', 'extra_head'):
            g = self.graph()
            if mode == 'missing': g['0103_room_owner_identity'] = 'missing'
            if mode == 'old_audit': g['0102_platform_company_features'] = None
            if mode == 'extra_head': g['unexpected'] = release.BASE_REVISION
            with self.subTest(mode=mode), self.assertRaises(ValueError): release.validate_revision_graph(g)
    def test_cycle_rejected(self):
        g = self.graph();g['cycle_a']='cycle_b';g['cycle_b']='cycle_a'
        with self.assertRaises(ValueError): release.validate_revision_graph(g)
    def test_apply_rejected_before_config_or_other_effects(self):
        # AST extraction of the leading guard only: do not execute install().
        tree = ast.parse((ROOT/'scripts/unified_release.py').read_text())
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install')
        first = ast.Module(body=[fn.body[0]], type_ignores=[])
        with self.assertRaisesRegex(ValueError, 'INTEGRATION_RELEASE_NOT_ACCEPTED'):
            exec(compile(first,'guard-only','exec'), {'require':release.require,'args':SimpleNamespace(action='apply')})
    def report(self, revision, target=False):
        cur=Cursor(revision);conn=Mock();conn.cursor.return_value=cur
        result=checker.inspect_connection(conn, require_target=target)
        conn.set_session.assert_called_once_with(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
        conn.rollback.assert_called_once()
        self.assertTrue(all(q.lstrip().startswith(('SELECT','SET LOCAL','SHOW')) for q in cur.calls))
        self.assertEqual(result['status'],'blocked')
        self.assertIn('INTEGRATION_RELEASE_ACCEPTANCE_REQUIRED',result['blockers'])
        return result
    def test_source_has_exact_pending_but_missing_schema_never_ready(self):
        r=self.report(checker.SOURCE_REVISION)
        self.assertEqual(r['pendingMigrations'],checker.PENDING_REVISIONS)
        self.assertIn('REQUIRED_SCHEMA_MISSING',r['blockers'])
    def test_target_is_not_accepted_by_revision_alone(self):
        r=self.report(checker.TARGET_REVISION,True)
        self.assertIn('TARGET_SCHEMA_AND_DATA_ACCEPTANCE_REQUIRED',r['blockers'])
    def test_old_audit_revision_rejected(self):
        r=self.report('0102_platform_company_features')
        self.assertIn('UNEXPECTED_DATABASE_REVISION',r['blockers']);self.assertEqual(r['pendingMigrations'],[])
    def test_query_failure_rolls_back(self):
        c=Mock();c.cursor.side_effect=RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):checker.inspect_connection(c)
        c.rollback.assert_called_once()
    def test_historical_delivery_stops_before_network_or_staging(self):
        t=(ROOT/'scripts/install-unified-from-git.sh').read_text()
        self.assertLess(t.index('exit 1'),t.index('git fetch'))
        self.assertLess(t.index('exit 1'),t.index('mktemp'))
    def test_backup_and_rollback_guards_retained(self):
        t=(ROOT/'scripts/unified_release.py').read_text()
        self.assertIn("['pg_restore', '--list', destination]",t)
        self.assertIn("'automaticDowngrade': False",t)
        self.assertIn("'browser': False",t)
        self.assertIn("require(current == args.expect_current",t)
        self.assertIn("report['status'] == 'ready'",t)
        self.assertIn("'Installed checkout must be on main'",t)
