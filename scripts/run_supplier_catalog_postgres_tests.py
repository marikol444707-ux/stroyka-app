#!/usr/bin/env python3
"""Run each opt-in fixture class in its own disposable, socket-only PostgreSQL."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    programs = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'createdb')}
    if not all(programs.values()):
        raise SystemExit('Add PostgreSQL initdb, pg_ctl and createdb to PATH')
    root = Path(__file__).resolve().parents[1]
    work = Path(tempfile.mkdtemp(prefix='supplier-catalog-', dir='/tmp'))
    data = work / 'data'
    def run(*args):
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, timeout=40)
    try:
        run(programs['initdb'], '-D', str(data), '-A', 'trust', '-U', 'chain_test', '--no-locale', '-E', 'UTF8')
        run(programs['pg_ctl'], '-D', str(data), '-l', str(work / 'postgres.log'),
            '-o', f"-F -h '' -k {work} -p 6546", '-w', 'start')
        suites = sys.argv[1:] or ['backend.features.supplier_access.test_company_directory_postgres']
        for index, suite in enumerate(suites):
            capability = {
                'test_material_capability_runtime_postgres': 'A8_4C2',
                'test_material_capability_writer_postgres': 'A8_4C',
                'test_material_capability_proof_postgres': 'A8_4B',
                'test_material_capability_schema_postgres': 'A8_4B',
            }.get(suite.rsplit('.', 1)[-1])
            name = (capability.lower() + '_catalog_' if capability else 'supply_chain_test_catalog_') + str(index)
            run(programs['createdb'], '-h', str(work), '-p', '6546', '-U', 'chain_test', name)
            env = dict(os.environ, SUPPLY_CHAIN_RUN_POSTGRES='1', SUPPLY_CHAIN_TEST_DB_HOST=str(work),
                       SUPPLY_CHAIN_TEST_DB_PORT='6546', SUPPLY_CHAIN_TEST_DB_NAME=name)
            if capability:
                env[capability + '_RUN_POSTGRES_INTEGRATION'] = '1'
                env[capability + '_TEST_DATABASE_URL'] = f'host={work} port=6546 user=chain_test dbname={name}'
            result = subprocess.run([sys.executable, '-m', 'unittest', '-v', suite], cwd=root, env=env, timeout=240)
            if result.returncode:
                return result.returncode
        return 0
    finally:
        if (data / 'postmaster.pid').exists():
            run(programs['pg_ctl'], '-D', str(data), '-m', 'immediate', '-w', 'stop')
        shutil.rmtree(work)


if __name__ == '__main__':
    raise SystemExit(main())
