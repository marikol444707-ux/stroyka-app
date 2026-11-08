#!/usr/bin/env python3
"""Run receipt regressions in fresh socket-only databases; skips are failures.

No ambient application database or PostgreSQL service is used. All roles and
schema/data exist only in the temporary cluster removed at exit. The real-writer
suite uses the guarded supply-chain fixture in its own empty database; the
resolver and adapter suites retain their stricter receipt DSN safety checks.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    ('receipt', 'backend.features.warehouse_receipts.test_confirmation_postgres.ConfirmationPostgresTests'),
    ('receipt', 'backend.features.warehouse_receipts.test_confirmation_postgres.ResolverPostgresTests'),
    ('chain', 'backend.features.warehouse_receipts.test_production_writer_postgres.ProductionWriterPostgresTests'),
)
PORT = '6547'


def clean_environment(environ):
    """Do not let libpq or an inherited opt-in select a different server."""
    return {key: value for key, value in environ.items()
            if not key.startswith(('PG', 'DB', 'WAREHOUSE_RECEIPTS_', 'SUPPLY_CHAIN_'))
            and key != 'DATABASE_URL'}


def run_suite(name):
    """A misconfigured opt-in must fail CI, even when unittest reports OK(skipped)."""
    sys.path.insert(0, str(ROOT))
    suite = unittest.TestLoader().loadTestsFromName(name)
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if (not expected or result.testsRun != expected or result.skipped
            or not result.wasSuccessful()):
        print('Receipt PostgreSQL gate failed: every selected case must run without skips', file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-suite', choices=[name for _, name in SUITES], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.run_suite:
        return run_suite(args.run_suite)
    programs = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'createdb', 'createuser')}
    if not all(programs.values()):
        raise SystemExit('Add PostgreSQL initdb, pg_ctl, createdb and createuser to PATH')
    env = clean_environment(os.environ)
    with tempfile.TemporaryDirectory(prefix='warehouse-receipt-', dir='/tmp') as directory:
        work = Path(directory)
        data = work / 'data'
        env['PGPASSFILE'] = str(work / 'no-password-file')

        def run(*command):
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, env=env, timeout=40)

        try:
            run(programs['initdb'], '-D', str(data), '-A', 'trust', '-U', 'receipt_test',
                '--no-locale', '-E', 'UTF8')
            run(programs['pg_ctl'], '-D', str(data), '-l', str(work / 'postgres.log'),
                '-o', f"-F -h '' -k {work} -p {PORT}", '-w', 'start')
            # Legacy schema bootstrap needs this disposable cluster-local role.
            run(programs['createuser'], '-h', str(work), '-p', PORT, '-U', 'receipt_test',
                '--superuser', 'chain_test')
            for index, (kind, suite) in enumerate(SUITES):
                role = 'receipt_test' if kind == 'receipt' else 'chain_test'
                prefix = 'warehouse_receipts_test_' if kind == 'receipt' else 'supply_chain_test_'
                database = prefix + 'ci_' + str(index)
                run(programs['createdb'], '-h', str(work), '-p', PORT, '-U', role, database)
                child_env = dict(env)
                if kind == 'receipt':
                    child_env.update(WAREHOUSE_RECEIPTS_RUN_POSTGRES='1',
                        WAREHOUSE_RECEIPTS_TEST_DSN=f'host={work} port={PORT} dbname={database} user={role}')
                else:
                    child_env.update(SUPPLY_CHAIN_RUN_POSTGRES='1', SUPPLY_CHAIN_TEST_DB_HOST=str(work),
                        SUPPLY_CHAIN_TEST_DB_PORT=PORT, SUPPLY_CHAIN_TEST_DB_NAME=database)
                result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--run-suite', suite],
                                        cwd=ROOT, env=child_env, timeout=300)
                if result.returncode:
                    return result.returncode
            return 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            log = work / 'postgres.log'
            if log.exists():
                print(log.read_text(encoding='utf-8', errors='replace'), file=sys.stderr)
            raise
        finally:
            if (data / 'postmaster.pid').exists():
                run(programs['pg_ctl'], '-D', str(data), '-m', 'immediate', '-w', 'stop')


if __name__ == '__main__':
    raise SystemExit(main())
