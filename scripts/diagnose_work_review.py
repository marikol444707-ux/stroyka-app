#!/usr/bin/env python3
"""Read-only local PostgreSQL diagnostic; never imports or initializes the app."""
import argparse
import ast
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
workers AS (SELECT u.id,u.name,u.role AS legacy_role,COALESCE(u.active,TRUE) AS active,
                   (u.company_id=p.company_id) AS legacy_company_matches,
                   EXISTS(SELECT 1 FROM user_company_roles m WHERE m.user_id=u.id) AS has_explicit_memberships,
                   ARRAY(SELECT m.role FROM user_company_roles m WHERE m.user_id=u.id
                         AND m.company_id=p.company_id AND COALESCE(m.active,TRUE)) AS active_company_roles
            FROM users u JOIN one_project p ON u.company_id=p.company_id OR EXISTS(
                         SELECT 1 FROM user_company_roles m WHERE m.user_id=u.id AND m.company_id=p.company_id),requested r
            WHERE EXISTS(SELECT 1 FROM unnest(string_to_array(r.worker,'|')) term
                         WHERE length(trim(term))>=2 AND strpos(lower(u.name),lower(trim(term)))>0)),
matched_works AS (SELECT w.id,w.date,w.status,w.description,w.quantity,w.unit,w.master_id,w.master_name,
                        w.material_accounting_version
                 FROM work_journal w JOIN one_project p ON w.company_id=p.company_id AND w.project=p.name,requested r
                 WHERE w.master_id IN (SELECT id FROM workers) OR EXISTS(
                      SELECT 1 FROM unnest(string_to_array(r.worker,'|')) term WHERE length(trim(term))>=2
                      AND strpos(lower(COALESCE(w.master_name,'')),lower(trim(term)))>0)),
works AS (SELECT * FROM matched_works ORDER BY id DESC LIMIT 50)
SELECT jsonb_build_object('project_matches',(SELECT COUNT(*) FROM projects_found),
 'worker_matches',(SELECT COUNT(*) FROM workers),'company_id',(SELECT company_id FROM one_project),
 'matched_profiles',COALESCE((SELECT jsonb_agg(to_jsonb(workers)) FROM workers),'[]'::jsonb),
 'matching_work_count',(SELECT COUNT(*) FROM matched_works),
 'unassigned_company_rows_inspected',FALSE,
 'acceptance_tables',jsonb_build_object(
     'reviews',to_regclass('public.work_acceptance_reviews') IS NOT NULL,
     'rework_links',to_regclass('public.work_rework_links') IS NOT NULL,
     'material_entries',to_regclass('public.work_material_entries') IS NOT NULL),
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
    allowed=('WORK_ACCEPTANCE_ENABLED','WORK_MATERIAL_ACCOUNTING_ENABLED')
    state={'server_head':'unknown','backend_flags':{},'work_function_sha256':{},
           'backend_flags_source':'initial_process_environment','env_file_flags':{key:'UNSET' for key in allowed},
           'env_file_flags_source':'backend/.env_current_file'}
    env_file=app/'backend/.env'
    if env_file.is_file():
        seen=set()
        for line in env_file.read_text().splitlines():
            key,separator,value=line.partition('=');key=key.strip()
            if separator and key in allowed and key not in seen:
                seen.add(key);value=value.strip().strip('\"').strip("'")
                state['env_file_flags'][key]=value if value in ('0','1') else 'OTHER'
    for key,relative in [('backend_main_sha256','backend/main.py'),('yandex_adapter_sha256','backend/features/model_gateway/yandex_adapter.py')]:
        file=app/relative
        if file.is_file():
            state[key]=hashlib.sha256(file.read_bytes()).hexdigest()
    try:
        main_file=app/'backend/main.py'
        if main_file.is_file():
            source=main_file.read_text();lines=source.splitlines(keepends=True)
            for node in ast.parse(source).body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ('update_estimate','get_work_journal','create_work_journal','add_work_journal','update_work_journal','scan_invoice','_apply_supplier_invoice_template_metadata','_extract_invoice_scan_pdf_text','_invoice_scan_ai_content','_create_warehouse_invoice_record'):
                    fragment=''.join(lines[node.lineno-1:node.end_lineno])
                    state['work_function_sha256'][node.name]=hashlib.sha256(fragment.encode()).hexdigest()
        result=subprocess.run(['/usr/bin/git','-C',str(app),'rev-parse','HEAD'],text=True,capture_output=True,timeout=5,env=environment)
        head=result.stdout.strip()
        if result.returncode==0 and re.fullmatch('[0-9a-f]{40}',head):
            state['server_head']=head
        result=subprocess.run(['/usr/bin/systemctl','show','stroyka.service','-p','MainPID','--value'],text=True,capture_output=True,timeout=5,env=environment)
        pid=result.stdout.strip()
        if result.returncode==0 and pid.isdecimal() and int(pid)>0:
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
    if not args.project.strip() or not args.worker.strip() or any(len(term.strip())<2 for term in args.worker.split('|')) or max(len(args.project),len(args.worker))>200:
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
    print(json.dumps({'read_only':True,'report_complete':True,'diagnostic_version':2,**state,**json.loads(result.stdout)},ensure_ascii=False,default=str))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) else type(error).__name__
        print(json.dumps({'read_only':True,'report_complete':False,'code':code}))
        raise SystemExit(1)
