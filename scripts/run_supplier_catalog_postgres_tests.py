#!/usr/bin/env python3
"""Run each opt-in fixture class in its own disposable, socket-only PostgreSQL."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


STRICT_TEST_RUNNER = """import os, sys, unittest
# The parent selects the repository cwd; fixtures may then chdir to a sandbox.
# Pin that root before loading tests, just as python -m unittest does.
sys.path.insert(0, os.getcwd())
suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
expected = suite.countTestCases()
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not expected or result.testsRun != expected or result.skipped or not result.wasSuccessful():
    print('PostgreSQL gate failed: every selected case must run without skips', file=sys.stderr)
    sys.exit(1)
"""


def clean_environment(environ):
    """Explicit test destinations must not inherit a libpq host/service override."""
    return {key: value for key, value in environ.items()
            if not key.startswith(('PG', 'DB', 'SUPPLY_CHAIN_', 'WAREHOUSE_RECEIPTS_'))
            and key != 'DATABASE_URL'}


def test_command(suite, *, require_no_skips=False):
    if require_no_skips:
        return [sys.executable, '-c', STRICT_TEST_RUNNER, suite]
    return [sys.executable, '-m', 'unittest', '-v', suite]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-no-skips', action='store_true',
                        help='Fail if a selected suite skips cases or collects no tests')
    parser.add_argument('suites', nargs='*')
    args = parser.parse_args(argv)
    programs = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'createdb')}
    if not all(programs.values()):
        raise SystemExit('Add PostgreSQL initdb, pg_ctl and createdb to PATH')
    root = Path(__file__).resolve().parents[1]
    work = Path(tempfile.mkdtemp(prefix='supplier-catalog-', dir='/tmp'))
    data = work / 'data'
    base_env = clean_environment(os.environ)
    base_env['PGPASSFILE'] = str(work / 'no-password-file')
    def run(*args):
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, env=base_env, timeout=40)
    try:
        run(programs['initdb'], '-D', str(data), '-A', 'trust', '-U', 'chain_test', '--no-locale', '-E', 'UTF8')
        run(programs['pg_ctl'], '-D', str(data), '-l', str(work / 'postgres.log'),
            '-o', f"-F -h '' -k {work} -p 6546", '-w', 'start')
        suites = args.suites or ['backend.features.supplier_access.test_company_directory_postgres']
        for index, suite in enumerate(suites):
            capability = {
                'test_material_capability_runtime_postgres': 'A8_4C2',
                'test_material_capability_writer_postgres': 'A8_4C',
                'test_material_capability_proof_postgres': 'A8_4B',
                'test_material_capability_schema_postgres': 'A8_4B',
            }.get(suite.rsplit('.', 1)[-1])
            name = (capability.lower() + '_catalog_' if capability else 'supply_chain_test_catalog_') + str(index)
            run(programs['createdb'], '-h', str(work), '-p', '6546', '-U', 'chain_test', name)
            env = dict(base_env, SUPPLY_CHAIN_RUN_POSTGRES='1', SUPPLY_CHAIN_TEST_DB_HOST=str(work),
                       SUPPLY_CHAIN_TEST_DB_PORT='6546', SUPPLY_CHAIN_TEST_DB_NAME=name)
            if capability:
                env[capability + '_RUN_POSTGRES_INTEGRATION'] = '1'
                env[capability + '_TEST_DATABASE_URL'] = f'host={work} port=6546 user=chain_test dbname={name}'
            result = subprocess.run(test_command(suite, require_no_skips=args.require_no_skips),
                                    cwd=root, env=env, timeout=240)
            if result.returncode:
                return result.returncode
        return 0
    finally:
        if (data / 'postmaster.pid').exists():
            run(programs['pg_ctl'], '-D', str(data), '-m', 'immediate', '-w', 'stop')
        shutil.rmtree(work)


if __name__ == '__main__':
    raise SystemExit(main())
