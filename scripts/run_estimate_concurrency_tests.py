#!/usr/bin/env python3
"""Provision only a disposable repo-local, socket-only PostgreSQL for race tests.

No DSN or existing database is accepted. Never imports backend.main/config/db.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATABASE = 'estimate_concurrency_test'
USER = 'estimate_test'
PORT = '6549'


def main():
    if len(sys.argv) != 1:
        raise SystemExit('This launcher accepts no database or connection arguments.')
    programs = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'createdb')}
    if not all(programs.values()):
        raise SystemExit('Add PostgreSQL initdb, pg_ctl and createdb to PATH.')
    # libpq must not inherit an external service, password file, host or database.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PG', 'DB_', 'DATABASE_', 'ESTIMATE_CONCURRENCY_'))}
    env['PGCONNECT_TIMEOUT'] = '5'
    (ROOT / 'tmp').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='er-', dir=ROOT / 'tmp'))
    data = work / 'data'
    marker = {'kind': 'estimate-concurrency-fixture-v1', 'database': DATABASE,
              'user': USER, 'port': PORT, 'root': str(work)}
    (work / 'fixture.json').write_text(json.dumps(marker), encoding='utf-8')
    started = False

    def run(*args):
        return subprocess.run(args, check=True, env=env, timeout=45,
                              stdout=subprocess.DEVNULL)

    try:
        if len(os.fsencode(str(work / ('.s.PGSQL.' + PORT)))) >= 104:
            raise RuntimeError('Repository path is too long for a safe local PostgreSQL socket.')
        run(programs['initdb'], '-D', str(data), '-A', 'trust', '-U', USER,
            '--no-locale', '-E', 'UTF8')
        options = f'-F -h "" -k {shlex.quote(str(work))} -p {PORT}'
        run(programs['pg_ctl'], '-D', str(data), '-l', str(work / 'postgres.log'),
            '-o', options, '-w', 'start')
        started = True
        run(programs['createdb'], '-h', str(work), '-p', PORT, '-U', USER, DATABASE)
        test_env = dict(env, ESTIMATE_CONCURRENCY_RUN_POSTGRES='1',
                        ESTIMATE_CONCURRENCY_TEST_ROOT=str(work))
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', '-v',
             'backend.features.estimate_concurrency.test_postgres'],
            cwd=ROOT, env=test_env, timeout=180,
        )
        return result.returncode
    finally:
        # Only stop the cluster created above. If stopping fails, retain its files.
        if started or (data / 'postmaster.pid').exists():
            run(programs['pg_ctl'], '-D', str(data), '-m', 'immediate', '-w', 'stop')
        shutil.rmtree(work)


if __name__ == '__main__':
    raise SystemExit(main())
