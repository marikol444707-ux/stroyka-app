#!/usr/bin/env python3
"""Run selector regressions only on a freshly created socket-only PostgreSQL.

Accepts no DSN, existing database, environment credentials, or extra arguments.
The cluster is under this checkout's tmp directory and removed after shutdown.
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


def main():
    if len(sys.argv) != 1:
        raise SystemExit('No database or other arguments accepted')
    programs = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'createdb')}
    if not all(programs.values()):
        raise SystemExit('Add PostgreSQL initdb, pg_ctl and createdb to PATH')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PG', 'DB_', 'DATABASE_', 'BRIGADE_DRAFT_'))}
    env['PGCONNECT_TIMEOUT'] = '5'
    (ROOT / 'tmp').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='bg-', dir=ROOT / 'tmp'))
    data = work / 'data'
    marker = {'kind': 'brigade-draft-test-v1', 'root': str(work),
              'database': 'brigade_draft_test', 'user': 'brigade_test', 'port': '6547'}
    (work / 'fixture.json').write_text(json.dumps(marker))
    started = False

    def run(*args):
        subprocess.run(args, env=env, check=True, timeout=45, stdout=subprocess.DEVNULL)

    try:
        if len(os.fsencode(str(work / '.s.PGSQL.6547'))) >= 104:
            raise RuntimeError('Checkout path is too long for a local PostgreSQL socket')
        run(programs['initdb'], '-D', str(data), '-A', 'trust', '-U', 'brigade_test',
            '--no-locale', '-E', 'UTF8')
        run(programs['pg_ctl'], '-D', str(data), '-l', str(work / 'postgres.log'),
            '-o', '-F -h "" -k ' + shlex.quote(str(work)) + ' -p 6547', '-w', 'start')
        started = True
        run(programs['createdb'], '-h', str(work), '-p', '6547', '-U', 'brigade_test', 'brigade_draft_test')
        result = subprocess.run([sys.executable, '-m', 'unittest', '-v',
            'backend.features.brigade_access.test_draft_selection_postgres'],
            cwd=ROOT, env=dict(env, BRIGADE_DRAFT_RUN_POSTGRES='1', BRIGADE_DRAFT_TEST_ROOT=str(work)),
            timeout=90)
        return result.returncode
    finally:
        if started or (data / 'postmaster.pid').exists():
            run(programs['pg_ctl'], '-D', str(data), '-m', 'immediate', '-w', 'stop')
        shutil.rmtree(work)


if __name__ == '__main__':
    raise SystemExit(main())
