#!/usr/bin/env python3
"""Read-only local PostgreSQL diagnostic; never imports or initializes the app."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess

QUERY = """
WITH requested AS (SELECT :'project'::text AS project, :'worker'::text AS worker),
projects_found AS (SELECT p.id,p.name,p.company_id FROM projects p,requested r
                  WHERE p.name=r.project AND p.company_id IS NOT NULL),
one_project AS (SELECT * FROM projects_found WHERE (SELECT COUNT(*) FROM projects_found)=1),
workers AS (SELECT DISTINCT u.id,u.name,ur.role FROM users u
            JOIN user_company_roles ur ON ur.user_id=u.id AND ur.active=TRUE
            JOIN one_project p ON p.company_id=ur.company_id,requested r
            WHERE strpos(lower(u.name),lower(r.worker))>0),
one_worker AS (SELECT * FROM workers WHERE (SELECT COUNT(*) FROM workers)=1),
works AS (SELECT w.id,w.date,w.status,w.description,w.quantity,w.unit,
                  w.material_accounting_version
          FROM work_journal w JOIN one_project p ON w.company_id=p.company_id AND w.project=p.name
          JOIN one_worker u ON w.master_id=u.id
          ORDER BY w.id DESC LIMIT 30)
SELECT jsonb_build_object('project_matches',(SELECT COUNT(*) FROM projects_found),
 'worker_matches',(SELECT COUNT(*) FROM workers),
 'company_id',(SELECT company_id FROM one_project),
 'worker_roles',COALESCE((SELECT jsonb_agg(role) FROM one_worker),'[]'::jsonb),
 'works',COALESCE((SELECT jsonb_agg(to_jsonb(works)) FROM works),'[]'::jsonb));
"""


def database_name(app):
    # Read only the non-secret database name, never execute shell configuration.
    path = app / 'backend/.env'
    if not path.is_file():
        raise ValueError('DATABASE_NAME_NOT_FOUND')
    for line in path.read_text().splitlines():
        match = re.fullmatch(r'\s*(?:export\s+)?DB_NAME\s*=\s*([A-Za-z_][A-Za-z0-9_-]{0,62}|"[A-Za-z_][A-Za-z0-9_-]{0,62}"|\'[A-Za-z_][A-Za-z0-9_-]{0,62}\')\s*', line)
        if match:
            return match[1].strip('"\'')
    raise ValueError('DATABASE_NAME_NOT_FOUND')



def runtime_state(app):
    environment={'PATH':'/usr/bin:/usr/sbin:/bin','LANG':'C.UTF-8'}
    state={'server_head':'unknown','backend_flags':{}}
    for key,relative in [('backend_main_sha256','backend/main.py'),('yandex_adapter_sha256','backend/features/model_gateway/yandex_adapter.py')]:
        file=app/relative
        if file.is_file():
            state[key]=hashlib.sha256(file.read_bytes()).hexdigest()
    try:
        result=subprocess.run(['/usr/bin/git','-C',str(app),'rev-parse','HEAD'],text=True,capture_output=True,timeout=5,env=environment)
        head=result.stdout.strip()
        if result.returncode==0 and re.fullmatch('[0-9a-f]{40}',head):
            state['server_head']=head
        result=subprocess.run(['/usr/bin/systemctl','show','stroyka.service','-p','MainPID','--value'],text=True,capture_output=True,timeout=5,env=environment)
        pid=result.stdout.strip()
        if result.returncode==0 and pid.isdecimal() and int(pid)>0:
            allowed=('WORK_ACCEPTANCE_ENABLED','WORK_MATERIAL_ACCOUNTING_ENABLED')
            values={}
            for entry in Path('/proc',pid,'environ').read_bytes().split(b'\0'):
                key,separator,value=entry.partition(b'=')
                name=key.decode('ascii',errors='ignore')
                if separator and name in allowed:
                    values[name]=value.decode('ascii',errors='ignore') if value in (b'0',b'1') else 'OTHER'
            state['backend_flags']={key:values.get(key,'UNSET') for key in allowed}
    except (OSError,subprocess.SubprocessError):
        pass
    return state


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True)
    parser.add_argument('--worker',required=True)
    parser.add_argument('--app',type=Path,default=Path('/var/www/stroyka-app'))
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise ValueError('SERVER_ROOT_REQUIRED')
    if not args.project.strip() or not args.worker.strip() or max(len(args.project),len(args.worker))>200:
        raise ValueError('INVALID_SEARCH')
    db=database_name(args.app)
    state=runtime_state(args.app)
    command=['/usr/sbin/runuser','-u','postgres','--','/usr/bin/psql','-X','-qAt','--no-password',
             '--host=/var/run/postgresql','--port=5432','--dbname='+db,'-v','ON_ERROR_STOP=1',
             '-v','project='+args.project,'-v','worker='+args.worker]
    sql="BEGIN READ ONLY;\nSET LOCAL statement_timeout='5s';\n"+QUERY+'\nROLLBACK;\n'
    result=subprocess.run(command,input=sql,text=True,capture_output=True,timeout=15,
                          env={'PATH':'/usr/bin:/usr/sbin:/bin','LANG':'C.UTF-8',
                               'PGOPTIONS':'-c default_transaction_read_only=on'})
    if result.returncode:
        raise ValueError('READ_ONLY_QUERY_FAILED_OR_SCHEMA_INCOMPATIBLE')
    print(json.dumps({'read_only':True,'report_complete':True,**state,**json.loads(result.stdout)},ensure_ascii=False,default=str))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) else type(error).__name__
        print(json.dumps({'read_only':True,'report_complete':False,'code':code}))
        raise SystemExit(1)
