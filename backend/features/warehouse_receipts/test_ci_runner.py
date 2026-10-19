"""Fail-closed runner contracts; no PostgreSQL server or main runtime imported."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]


def load_runner(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner('run_warehouse_receipt_postgres_tests.py', 'receipt_ci_runner')
supplier_runner = load_runner('run_supplier_catalog_postgres_tests.py', 'supplier_ci_runner')
AMBIENT = dict(PGHOSTADDR='192.0.2.1', PGSERVICE='production', PGOPTIONS='unexpected',
    PGPASSFILE='/ambient/password-file', PGPASSWORD='synthetic', DB_HOST='remote',
    DBNAME='production', DB_URL='remote', DATABASE_URL='remote',
    SUPPLY_CHAIN_TEST_DB_HOST='remote', SUPPLY_CHAIN_TEST_DB_NAME='production',
    WAREHOUSE_RECEIPTS_TEST_DSN='remote', OWNED_DISTRIBUTION_QUALITY_ENABLED='1')


class ReceiptCiRunnerTests(unittest.TestCase):
    def test_exact_suite_inventory_includes_all_receipt_postgres_cases(self):
        prefix = 'backend.features.warehouse_receipts.'
        self.assertEqual(runner.SUITES, (
            ('receipt', prefix + 'test_confirmation_postgres.ConfirmationPostgresTests'),
            ('receipt', prefix + 'test_confirmation_postgres.ResolverPostgresTests'),
            ('chain', prefix + 'test_production_writer_postgres.ProductionWriterPostgresTests'),
        ))
        def identities(suite):
            result = set()
            for test in suite:
                result.update(identities(test) if isinstance(test, unittest.TestSuite) else {test.id()})
            return result
        loader = unittest.TestLoader()
        # Also detect newly added PostgreSQL classes omitted from the runner.
        for module in ('test_confirmation_postgres', 'test_production_writer_postgres'):
            collected = identities(loader.loadTestsFromName(prefix + module))
            selected = set()
            for _, suite in runner.SUITES:
                if suite.startswith(prefix + module + '.'):
                    selected.update(identities(loader.loadTestsFromName(suite)))
            self.assertEqual(selected, collected)
            self.assertTrue(collected)

    def test_ambient_database_and_libpq_configuration_is_removed(self):
        for module in (runner, supplier_runner):
            with self.subTest(runner=module.__name__):
                self.assertEqual(module.clean_environment(AMBIENT),
                                 {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '1'})

    def run_selected(self, suite):
        with patch.object(runner.unittest.TestLoader, 'loadTestsFromName', return_value=suite), redirect_stderr(io.StringIO()):
            return runner.run_suite('selected')

    def test_success_requires_every_selected_test_to_run(self):
        self.assertEqual(self.run_selected(unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])), 0)

    def test_zero_collected_tests_are_a_failure(self):
        self.assertEqual(self.run_selected(unittest.TestSuite()), 1)

    def test_skipped_opt_in_cases_are_a_failure(self):
        def skipped():
            raise unittest.SkipTest('missing opt-in or dedicated DSN')
        self.assertEqual(self.run_selected(unittest.TestSuite([unittest.FunctionTestCase(skipped)])), 1)

    def test_setup_class_skip_cannot_look_like_success(self):
        class SkippedClass(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest('missing PostgreSQL')
            def test_database(self):
                pass
        self.assertEqual(self.run_selected(unittest.defaultTestLoader.loadTestsFromTestCase(SkippedClass)), 1)

    def test_test_error_is_a_failure(self):
        def failed():
            raise RuntimeError('database unavailable')
        self.assertEqual(self.run_selected(unittest.TestSuite([unittest.FunctionTestCase(failed)])), 1)

    def execute_runner(self, *, child_status=0, child_timeout=False):
        calls, workdirs = [], []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            if '-w' in command and command[-1] == 'start':
                data = Path(command[command.index('-D') + 1])
                data.mkdir()
                (data / 'postmaster.pid').write_text('synthetic-pid')
                workdirs.append(data.parent)
            if '--run-suite' in command:
                if child_timeout:
                    raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                return subprocess.CompletedProcess(command, child_status)
            return subprocess.CompletedProcess(command, 0)
        with patch.dict(runner.os.environ, AMBIENT), \
                patch.object(runner.shutil, 'which', side_effect=lambda name: '/synthetic/bin/' + name), \
                patch.object(runner.subprocess, 'run', side_effect=execute):
            try:
                status = runner.main([])
            except subprocess.TimeoutExpired:
                status = 'timeout'
        self.assertEqual(len(workdirs), 1)
        self.assertFalse(workdirs[0].exists(), 'Disposable cluster directory was not removed')
        self.assertEqual(calls[-1][0][-3:], ('immediate', '-w', 'stop'))
        for command, kwargs in calls:
            environment = kwargs['env']
            self.assertFalse(set(environment) & {'PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS', 'PGPASSWORD',
                'DB_HOST', 'DBNAME', 'DB_URL', 'DATABASE_URL'})
            self.assertEqual(environment['PGPASSFILE'], str(workdirs[0] / 'no-password-file'))
            self.assertNotEqual(environment.get('SUPPLY_CHAIN_TEST_DB_HOST'), 'remote')
            self.assertNotEqual(environment.get('WAREHOUSE_RECEIPTS_TEST_DSN'), 'remote')
            if '--run-suite' not in command:
                self.assertNotIn('SUPPLY_CHAIN_TEST_DB_HOST', environment)
                self.assertNotIn('WAREHOUSE_RECEIPTS_TEST_DSN', environment)
        return status, calls

    def test_runner_provisions_isolated_roles_and_explicit_databases(self):
        status, calls = self.execute_runner()
        self.assertEqual(status, 0)
        start = next(command for command, _ in calls if command[-1] == 'start')
        self.assertIn("-h ''", start[start.index('-o') + 1])
        children = [(command, kwargs) for command, kwargs in calls if '--run-suite' in command]
        self.assertEqual(len(children), len(runner.SUITES))
        receipt_env, resolver_env, chain_env = (kwargs['env'] for _, kwargs in children)
        self.assertEqual(receipt_env['WAREHOUSE_RECEIPTS_RUN_POSTGRES'], '1')
        self.assertIn('dbname=warehouse_receipts_test_ci_0 user=receipt_test', receipt_env['WAREHOUSE_RECEIPTS_TEST_DSN'])
        self.assertNotIn('SUPPLY_CHAIN_RUN_POSTGRES', receipt_env)
        self.assertIn('dbname=warehouse_receipts_test_ci_1 user=receipt_test', resolver_env['WAREHOUSE_RECEIPTS_TEST_DSN'])
        self.assertNotEqual(receipt_env['WAREHOUSE_RECEIPTS_TEST_DSN'], resolver_env['WAREHOUSE_RECEIPTS_TEST_DSN'])
        self.assertEqual(chain_env['SUPPLY_CHAIN_RUN_POSTGRES'], '1')
        self.assertEqual(chain_env['SUPPLY_CHAIN_TEST_DB_NAME'], 'supply_chain_test_ci_2')
        self.assertTrue(chain_env['SUPPLY_CHAIN_TEST_DB_HOST'].startswith('/tmp/warehouse-receipt-'))
        self.assertNotIn('WAREHOUSE_RECEIPTS_RUN_POSTGRES', chain_env)

    def test_runner_stops_cluster_after_suite_failure(self):
        status, calls = self.execute_runner(child_status=7)
        self.assertEqual(status, 7)
        self.assertEqual(sum('--run-suite' in command for command, _ in calls), 1)

    def test_runner_stops_cluster_after_suite_timeout(self):
        status, _ = self.execute_runner(child_timeout=True)
        self.assertEqual(status, 'timeout')


class SupplierCatalogStrictModeTests(unittest.TestCase):
    def test_existing_command_is_unchanged_without_opt_in(self):
        self.assertEqual(supplier_runner.test_command('selected'),
                         [supplier_runner.sys.executable, '-m', 'unittest', '-v', 'selected'])

    def test_strict_command_fails_for_skipped_cases_and_empty_suite(self):
        for name in ('backend.features.warehouse_receipts.test_confirmation_postgres.ConfirmationPostgresTests',
                     'backend.features.warehouse_receipts'):
            with self.subTest(suite=name):
                result = subprocess.run(supplier_runner.test_command(name, require_no_skips=True),
                    cwd=ROOT, env=runner.clean_environment(runner.os.environ),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('every selected case must run without skips', result.stderr)

    def test_strict_command_passes_fully_executed_suite(self):
        result = subprocess.run(supplier_runner.test_command(
            'backend.features.warehouse_receipts.test_fixture_postgres.IsolatedDatabaseSettingsTests',
            require_no_skips=True), cwd=ROOT, env=runner.clean_environment(runner.os.environ),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ran 5 tests', result.stderr)

    def test_supplier_utilities_and_children_never_inherit_database_targets(self):
        calls, workdirs = [], []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            if '-w' in command and command[-1] == 'start':
                data = Path(command[command.index('-D') + 1])
                data.mkdir()
                (data / 'postmaster.pid').write_text('synthetic-pid')
                workdirs.append(data.parent)
            return subprocess.CompletedProcess(command, 0)
        with patch.dict(supplier_runner.os.environ, AMBIENT), \
                patch.object(supplier_runner.shutil, 'which', side_effect=lambda name: '/synthetic/bin/' + name), \
                patch.object(supplier_runner.subprocess, 'run', side_effect=execute):
            self.assertEqual(supplier_runner.main(['--require-no-skips', 'example.SelectedTests',
                'example.test_material_capability_runtime_postgres']), 0)
        self.assertEqual(len(workdirs), 1)
        self.assertFalse(workdirs[0].exists())
        for command, kwargs in calls:
            environment = kwargs['env']
            self.assertFalse(set(environment) & {'PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS', 'PGPASSWORD',
                'DB_HOST', 'DBNAME', 'DB_URL', 'DATABASE_URL', 'WAREHOUSE_RECEIPTS_TEST_DSN'})
            self.assertEqual(environment['PGPASSFILE'], str(workdirs[0] / 'no-password-file'))
            self.assertEqual(environment['OWNED_DISTRIBUTION_QUALITY_ENABLED'], '1')
            if '-c' in command:
                self.assertEqual(environment['SUPPLY_CHAIN_RUN_POSTGRES'], '1')
                self.assertEqual(environment['SUPPLY_CHAIN_TEST_DB_HOST'], str(workdirs[0]))
                self.assertNotEqual(environment['SUPPLY_CHAIN_TEST_DB_NAME'], 'production')
            else:
                self.assertNotIn('SUPPLY_CHAIN_TEST_DB_HOST', environment)
        capability = [kwargs['env'] for command, kwargs in calls if '-c' in command][-1]
        self.assertEqual(capability['A8_4C2_RUN_POSTGRES_INTEGRATION'], '1')
        self.assertEqual(capability['A8_4C2_TEST_DATABASE_URL'],
            f'host={workdirs[0]} port=6546 user=chain_test dbname=a8_4c2_catalog_1')
