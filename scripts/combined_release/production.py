"""Production-only read checks/backup/service adapters; never imports backend.main."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import tarfile
import time
import urllib.request

ROOT = Path('/var/www/stroyka-app')
HOST = 'msk-1-vm-zh4n'
BASE = '5e8666c8910bdbf4607a7b3e76444854875919a0'
SERVICE = 'stroyka.service'
PUBLIC = 'https://stroyka26.pro'
Y_PATH = 'backend/features/model_gateway/yandex_adapter.py'
Y_HASH = 'f0854c841bb5bed487a6c96657cb6a36e6c09690533b0c6dfbd8768c9482e61a'

class Stop(RuntimeError):
    pass

def need(value, code):
    if not value:
        raise Stop(code)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

def run(args, *, cwd=None, env=None, capture=True, timeout=300):
    e = dict(os.environ if env is None else env, GIT_OPTIONAL_LOCKS='0')
    p = subprocess.run([str(a) for a in args], cwd=cwd, env=e, capture_output=True,
                       timeout=timeout, check=False)
    need(p.returncode == 0, 'SUBPROCESS_FAILED')
    return p.stdout.decode().strip() if capture else None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Stop('UNEXPECTED_HTTP_REDIRECT')

def http_bytes(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers={'Cache-Control':'no-cache','User-Agent':'Stroyka-release-check'})
    with opener.open(request, timeout=8) as r:
        need(r.status == 200, 'HTTP_STATUS_FAILED')
        body = r.read(8*1024*1024+1)
    need(len(body) <= 8*1024*1024, 'HTTP_RESPONSE_TOO_LARGE')
    return body

def relative_path(root, name):
    need(isinstance(name, str) and all(p not in ('', '.', '..') for p in name.split('/')), 'UNSAFE_PATH')
    p = root
    need(root.is_absolute() and root.resolve() == root and root.is_dir(), 'UNSAFE_ROOT')
    for component in name.split('/'):
        p /= component
        need(not p.is_symlink(), 'SYMLINK_COMPONENT')
    need(not p.exists() or p.is_file(), 'NOT_A_FILE')
    return p

def private_directory(p):
    p = Path(p)
    need(p.is_absolute() and p.resolve() == p and p.is_dir(), 'UNSAFE_EVIDENCE_DIRECTORY')
    st = p.stat()
    need(st.st_uid == 0 and stat.S_IMODE(st.st_mode) == 0o700, 'EVIDENCE_NOT_ROOT_PRIVATE')
    return p

def atomic_json(path, data):
    import tempfile
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temporary, path)
        d = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(d)
        finally: os.close(d)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def loopback_listener_host(table, address):
    hosts={'tcp':{'0100007F':'127.0.0.1'},
           'tcp6':{'0'*24+'01000000':'[::1]'}}
    need(table in hosts and address in hosts[table], 'PUBLIC_OR_UNKNOWN_BACKEND_LISTENER')
    return hosts[table][address]

class Production:
    root = ROOT
    def __init__(self, package, manifest):
        self.package = Path(package)
        self.manifest = manifest
        self.env = None
        self.owned_temps = set()

    def require_target(self):
        need(os.geteuid() == 0 and socket.gethostname().split('.')[0] == HOST, 'WRONG_HOST_OR_USER')
        need(ROOT.resolve() == ROOT and ROOT.is_dir(), 'WRONG_ROOT')

    def git(self, *args):
        return run(['git', '-c', 'core.fsmonitor=false', *args], cwd=ROOT)

    def service(self, require_active=True):
        active = run(['systemctl','show',SERVICE,'-p','ActiveState','--value'])
        if not require_active and active != 'active':
            return None
        need(active == 'active', 'SERVICE_NOT_ACTIVE')
        pid = run(['systemctl','show',SERVICE,'-p','MainPID','--value'])
        need(pid.isdigit() and int(pid)>0, 'SERVICE_PID_MISSING')
        proc = Path('/proc')/pid
        need((proc/'cwd').resolve() == ROOT/'backend', 'WRONG_SERVICE_CWD')
        exe = (proc/'exe').resolve()
        need(exe == Path('/usr/bin/python3.12').resolve(), 'WRONG_SERVICE_EXECUTABLE')
        argv0 = (proc/'cmdline').read_bytes().split(b'\0')[0].decode()
        python = Path(argv0)
        if not python.is_absolute(): python = ROOT/'backend'/python
        need(re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?', python.name) and python.is_file()
             and python.resolve() == exe, 'SERVICE_PYTHON_UNVERIFIED')
        started = (proc/'stat').read_text().rsplit(') ',1)[1].split()[19]
        sockets = set()
        for fd in (proc/'fd').iterdir():
            try: target = os.readlink(fd)
            except FileNotFoundError: continue
            m = re.fullmatch(r'socket:\[(\d+)\]', target)
            if m: sockets.add(m.group(1))
        listeners = []
        for table in ('tcp','tcp6'):
            for line in (proc/'net'/table).read_text().splitlines()[1:]:
                fields = line.split(); address, port = fields[1].split(':')
                if fields[3]=='0A' and fields[9] in sockets:
                    listeners.append((int(port,16), loopback_listener_host(table,address)))
        need(len({p for p,h in listeners}) == 1, 'SERVICE_HTTP_LISTENER_UNVERIFIED')
        port, host = sorted(listeners, key=lambda item: item[1] != '127.0.0.1')[0]
        return dict(pid=int(pid), started=started, python=str(python), exe=str(exe),
                    endpoint=f'http://{host}:{port}')

    def load_helpers(self):
        for filename, expected in self.manifest['helpers'].items():
            need(sha(relative_path(ROOT,'scripts/'+filename))==expected, 'HELPER_CHANGED')
        for attr, filename in [('u','unified_release.py'),('db','release_database_check.py')]:
            p = relative_path(ROOT, 'scripts/'+filename)
            need(sha(p) == self.manifest['helpers'][filename], 'HELPER_CHANGED')
            spec = importlib.util.spec_from_file_location('_release_'+attr, p)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            setattr(self, attr, module)
        self.u.run = run
        self.env = self.u.runtime_environment(ROOT, SERVICE)
        need(self.db.connection_settings(self.env)['dbname']=='stroyka', 'WRONG_DATABASE_SETTINGS')

    def db_snapshot(self):
        import psycopg2
        conn = psycopg2.connect(**self.db.connection_settings(self.env))
        conn.set_session(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
        try:
            with conn.cursor() as c:
                c.execute("SET LOCAL statement_timeout='20s'; SET LOCAL lock_timeout='2s'")
                c.execute("SELECT current_database(),current_setting('transaction_read_only'),inet_server_addr()::text,inet_server_port(),pg_database_size(current_database())")
                name, readonly, address, port, size = c.fetchone()
                need(name=='stroyka' and readonly=='on', 'READONLY_DATABASE_IDENTITY_FAILED')
                c.execute('SELECT version_num FROM public.alembic_version ORDER BY version_num')
                need(c.fetchall()==[('0102_job_candidates',)], 'SCHEMA_REVISION_CHANGED')
                checks = [
                    ("SELECT count(*) FROM users WHERE email=ANY(%s)", (['admin@stroyka.ru','buh@stroyka.ru','prorab@stroyka.ru','master@stroyka.ru'],), 4),
                    ("SELECT count(*) FROM users WHERE active IS NULL", (), 0),
                    ("SELECT count(*) FROM users WHERE role=ANY(%s) AND two_factor_required IS DISTINCT FROM TRUE", (['директор','зам_директора','бухгалтер','system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin'],), 0),
                    ("SELECT count(*) FROM companies WHERE id=1", (), 1),
                    ("SELECT count(*) FROM platform_accounts WHERE id=1", (), 1),
                    ("SELECT count(*) FROM companies c LEFT JOIN platform_accounts a ON a.id=c.platform_account_id WHERE c.platform_account_id IS NULL OR a.id IS NULL", (), 0),
                    ("SELECT count(*) FROM users u WHERE u.company_id IS NOT NULL AND coalesce(u.role,'')<>'' AND u.role NOT IN ('system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin') AND NOT EXISTS(SELECT 1 FROM user_company_roles r WHERE r.user_id=u.id AND r.company_id=u.company_id AND r.role=u.role)", (), 0),
                ]
                for query, params, expected in checks:
                    c.execute(query, params)
                    need(c.fetchone()[0] == expected, 'EXISTING_STARTUP_SECURITY_PRECONDITION_FAILED')
                security = {}
                projections = {
                    'users': "jsonb_build_array(id,email,role,company_id,platform_account_id,active,password,two_factor_required,two_factor_enabled,two_factor_secret,assigned_projects,assigned_packages,supplier_team_epoch)",
                    'companies': 'jsonb_build_array(id,platform_account_id,active)',
                    'platform_accounts': 'to_jsonb(t)',
                    'user_company_roles': "to_jsonb(t)-'updated_at'",
                    'suppliers': 'jsonb_build_array(id,user_id,participant_owner_epoch)',
                    'supplier_team_members': 'to_jsonb(t)',
                    'supplier_offer_assignments': 'to_jsonb(t)',
                    'supplier_customer_assignments': 'to_jsonb(t)',
                }
                for table, projection in projections.items():
                    # Identifiers are fixed literals above, never caller input.
                    c.execute(f"SELECT md5(coalesce(string_agg(v,'|' ORDER BY v),'')) FROM (SELECT md5(({projection})::text) v FROM public.{table} t) q")
                    security[table] = c.fetchone()[0]
                c.execute("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")
                columns = c.fetchall()
                c.execute("SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname")
                constraints = c.fetchall()
                c.execute("SELECT c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname")
                schema = digest([columns,constraints,c.fetchall()])
                return dict(identity=[name,address,port], schema=schema, security=digest(security), size=size)
        finally:
            conn.rollback(); conn.close()

    def filesystem_guard(self):
        exclusions = set(self.manifest['source']) | self.owned_temps
        inventory = {}
        names = self.git('ls-files','-z').split('\0') + self.git('ls-files','--others','--exclude-standard','-z').split('\0')
        for name in sorted(set(names)-{''}-exclusions):
            p = ROOT/name
            need(p.parent.resolve()==p.parent, 'UNTOUCHED_PATH_SYMLINK_PARENT')
            st = p.lstat()
            need(stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode), 'UNEXPECTED_SOURCE_TYPE')
            inventory[name] = [os.readlink(p) if p.is_symlink() else sha(p), st.st_mode,st.st_uid,st.st_gid,st.st_mtime_ns]
        index = Path(self.git('rev-parse','--git-path','index'))
        if not index.is_absolute(): index = ROOT/index
        need(index.is_file() and not index.is_symlink(), 'UNSAFE_GIT_INDEX')
        indexes = {str(p):sha(p) for p in [index,*sorted(index.parent.glob('sharedindex.*'))]}
        return dict(indexes=indexes, untouched=digest(inventory))

    def health(self, service):
        data = json.loads(http_bytes(service['endpoint']+'/health'))
        need(data.get('ok') is True and data.get('db',{}).get('ok') is True, 'BACKEND_HEALTH_FAILED')
        return data.get('version')

    def public_check(self, hashes):
        for name in ('asset-manifest.json','index.html'):
            endpoint = '/' if name == 'index.html' else '/'+name
            body = http_bytes(PUBLIC+endpoint+'?release_check='+self.manifest['source_tree'][:12])
            need(hashlib.sha256(body).hexdigest()==hashes[name], 'PUBLIC_FRONTEND_HASH_MISMATCH')

    def preflight(self):
        self.require_target(); self.load_helpers()
        need(self.git('rev-parse','HEAD')==BASE, 'BASE_HEAD_CHANGED')
        need(not self.git('diff','--no-ext-diff','--no-textconv','--cached','--name-only'), 'STAGED_CHANGES_PRESENT')
        need(set(self.git('diff','--no-ext-diff','--no-textconv','--name-only','HEAD').splitlines())=={'backend/main.py',Y_PATH}, 'UNEXPECTED_TRACKED_CHANGES')
        for name, entry in self.manifest['source'].items():
            p = relative_path(ROOT,name)
            need((sha(p) if p.exists() else None)==entry['before_sha256'], 'SOURCE_BASELINE_CHANGED')
        self.git('apply','--check',str(self.package/'combined-live-update.patch'))
        need(sha(relative_path(ROOT,Y_PATH))==Y_HASH, 'YANDEx_PATCH_CHANGED')
        source_before = ast.parse((ROOT/'backend/main.py').read_text())
        source_after = ast.parse((self.package/'payload/source/backend/main.py').read_text())
        for name in ('init_db','_invoice_scan_ai_content'):
            nodes = [next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name) for tree in (source_before,source_after)]
            need(ast.dump(nodes[0],include_attributes=False)==ast.dump(nodes[1],include_attributes=False), 'PRESERVED_STARTUP_OR_PDF_CHANGED')
        build = ROOT/'build'
        need(build.is_dir() and build.resolve()==build, 'FRONTEND_ROOT_CHANGED')
        for name, expected in self.manifest['frontend_before'].items():
            need(sha(relative_path(ROOT,'build/'+name))==expected, 'FRONTEND_BASELINE_CHANGED')
        need((ROOT/'backend/uploads').resolve()==ROOT/'uploads' and (ROOT/'uploads').resolve()==ROOT/'uploads', 'UPLOAD_ROOT_CHANGED')
        need(self.env.get('STORAGE_BACKEND','local')=='local', 'EXTERNAL_STORAGE_BACKUP_REVIEW_REQUIRED')
        service = self.service(); version = self.health(service)
        resolver = relative_path(ROOT,'scripts/resolve-frontend-build-env.sh')
        need(sha(resolver)==self.manifest['helpers']['resolve-frontend-build-env.sh'], 'RESOLVER_CHANGED')
        child_env = {k:self.env[k] for k in ('PATH','HOME','LANG','LC_ALL') if k in self.env}
        child_env['PYTHONDONTWRITEBYTECODE']='1'
        flags = run(['bash',resolver,self.u.frontend_service_environment(self.env),''],cwd=ROOT,env=child_env).splitlines()
        need(sorted(flags)==sorted(self.manifest['build_settings']['flags']), 'FEATURE_FLAGS_CHANGED')
        for name in ('REACT_APP_API_URL','PUBLIC_URL','REACT_APP_CLIENT_ERROR_LOGGING'):
            need(not self.env.get(name), 'FRONTEND_DEFAULT_OVERRIDDEN')
        self.public_check(self.manifest['frontend_before'])
        baseline = dict(service=service,version=version,files=self.filesystem_guard(),
                        runtime=digest(self.env),db=self.db_snapshot())
        self.frontend_plan()  # checks omitted assets and immutable collisions too
        return baseline

    def verify_installer_ci(self):
        import base64
        import ci_gate
        evidence=self.manifest.get('installer_ci',{})
        need(set(evidence)=={'run_id','head_sha','tree_sha','files'},'INSTALLER_CI_BINDING_REQUIRED')
        files=evidence['files']
        required={'install.py','production.py','maintenance.py','maintenance_runtime.py',
                  'ci_gate.py','durable_files.py','server-readonly-check.py','nginx_readonly.py',
                  'test_install.py','test_maintenance.py','test_maintenance_runtime.py',
                  'test_ci_gate.py','test_durable_files.py','test_readonly_probe.py','test_startup_postgres.py',
                  'bootstrap.py','test_bootstrap.py'}
        need(set(files)==required,'INCOMPLETE_INSTALLER_CI_FILE_BINDING')
        result=ci_gate.verify_ci(evidence['run_id'],expected_tree=evidence['tree_sha'])
        need(result['head_sha']==evidence['head_sha'],'INSTALLER_CI_COMMIT_CHANGED')
        for name,expected in files.items():
            need(sha(relative_path(self.package,name))==expected,'INSTALLER_SOURCE_CHANGED')
            remote=ci_gate._get(ci_gate.defaultsafeGET,ci_gate.API_ROOT+
                '/contents/scripts/combined_release/'+name+'?ref='+evidence['head_sha'])
            need(remote.get('type')=='file' and remote.get('encoding')=='base64','INSTALLER_CI_FILE_MISSING')
            content=base64.b64decode(remote.get('content',''),validate=False)
            need(hashlib.sha256(content).hexdigest()==expected,'INSTALLER_NOT_EXACT_CI_SOURCE')
        return result

    def startup_snapshot(self):
        import psycopg2
        runner=self.maintenance.operations.probe.startup_module()
        conn=psycopg2.connect(**runner.connection_settings(self.env))
        try:return runner.inspect_connection(conn,runner.load_plan())
        finally:conn.close()

    def prepare_maintenance(self, baseline):
        from maintenance_runtime import Session
        self.maintenance=Session(self,baseline,lambda phase,state:self.maintenance_save(phase,state))
        self.maintenance.preview()

    def require_startup_ready(self, baseline):
        from maintenance import require_clean_snapshot
        need(hasattr(self,'maintenance'),'VERIFIED_MAINTENANCE_BINDING_REQUIRED')
        require_clean_snapshot(self.startup_snapshot())

    def begin_maintenance(self, save):
        self.maintenance_save=save
        self.maintenance.freeze()

    def deployment_lock(self):
        from install import deployment_lock
        return deployment_lock()

    def prepare_recovery(self, baseline):
        from maintenance_runtime import Session
        self.maintenance=Session(self,baseline,lambda phase,state:None)

    def verify_live_after_open(self, baseline):
        # Legitimate writers are live again. Do not compare their current rows
        # with the frozen snapshot, or roll back in response to a real new user.
        need(self.git('rev-parse','HEAD')==BASE,'HEAD_CHANGED_AFTER_REOPEN')
        need(self.filesystem_guard()==baseline['files'],'UNTOUCHED_FILES_CHANGED_AFTER_REOPEN')
        env=self.u.runtime_environment(ROOT,SERVICE)
        need(digest(env)==baseline['runtime'],'SERVICE_ENVIRONMENT_CHANGED')
        need(self.health(self.service())==baseline['version'],'LIVE_HEALTH_FAILED')

    def start_in_maintenance(self, baseline):
        self.maintenance.start(self.startup_snapshot())
        return self.service()

    def finish_maintenance(self):self.maintenance.restore()

    def frontend_plan(self):
        changed = set(self.manifest['frontend_delta'])
        plan = {}
        for name, expected in self.manifest['frontend_files'].items():
            p = relative_path(ROOT,'build/'+name)
            actual = sha(p) if p.exists() else None
            if name not in changed:
                need(actual==expected, 'UNCHANGED_FRONTEND_ASSET_MISSING_OR_CHANGED')
            elif name.startswith('static/'):
                need(actual in (None,expected), 'IMMUTABLE_ASSET_COLLISION')
                if actual is None:
                    plan['build/'+name] = dict(before_sha256=None,after_sha256=expected)
            else:
                need(name in ('index.html','asset-manifest.json'), 'UNREVIEWED_MUTABLE_FRONTEND_PATH')
                need(actual==self.manifest['frontend_before'][name], 'MUTABLE_FRONTEND_CHANGED')
                plan['build/'+name] = dict(before_sha256=actual,after_sha256=expected)
        return plan

    def assert_preserved(self, baseline, *, same_process=False):
        need(self.git('rev-parse','HEAD')==BASE, 'HEAD_CHANGED_DURING_RELEASE')
        need(self.filesystem_guard()==baseline['files'], 'INDEX_OR_UNTOUCHED_FILES_CHANGED')
        self.env = self.u.runtime_environment(ROOT,SERVICE)
        need(digest(self.env)==baseline['runtime'], 'SERVICE_ENVIRONMENT_CHANGED')
        db = self.db_snapshot()
        for key in ('identity','schema','security'):
            need(db[key]==baseline['db'][key], 'DATABASE_OR_SECURITY_CHANGED_REQUIRES_MANUAL_REVIEW')
        if same_process:
            current = self.service()
            need((current['pid'],current['started'])==(baseline['service']['pid'],baseline['service']['started']), 'SERVICE_CHANGED_DURING_BACKUP')

    def backup(self, evidence, baseline):
        # Source bytes/attributes are already durably captured by Transaction.prepare.
        b = Path(evidence)
        disk = shutil.disk_usage(b).free
        uploads = ROOT/'uploads'
        before = tree_inventory(uploads)
        current_assets = self.u.manifest_files(ROOT/'build')
        size = baseline['db']['size']+sum((ROOT/'build'/p).stat().st_size for p in current_assets)+sum(v.get('size',0) for v in before.values())
        need(disk > 3*size+512*1024**2, 'INSUFFICIENT_BACKUP_SPACE')
        self.u.backup_frontend(ROOT/'build',b/'frontend-before')
        for index_name in baseline['files']['indexes']:
            shutil.copy2(index_name,b/Path(index_name).name)
        (b/'HEAD').write_text(BASE+'\n')
        shutil.copy2(ROOT/Y_PATH,b/'yandex-adapter-before.py')
        with tarfile.open(b/'uploads-before.tar.gz','w:gz',dereference=False) as t:
            t.add(uploads,arcname='uploads')
        need(tree_inventory(uploads)==before, 'UPLOADS_CHANGED_DURING_BACKUP')
        # Independently stream archive member contents; archive listing alone is insufficient.
        with tarfile.open(b/'uploads-before.tar.gz','r:gz') as t:
            archived = {}
            for member in t.getmembers():
                if member.name=='uploads': continue
                need(member.name.startswith('uploads/'), 'UPLOAD_ARCHIVE_PATH_FAILED')
                name = member.name[len('uploads/'):]
                if member.isfile():
                    f=t.extractfile(member); h=hashlib.sha256()
                    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
                    archived[name]={'kind':'file','hash':h.hexdigest(),'size':member.size}
                elif member.issym(): archived[name]={'kind':'link','target':member.linkname,'size':0}
                elif member.isdir(): continue
                else: raise Stop('UPLOAD_ARCHIVE_SPECIAL_FILE')
        need(archived=={k:{a:v[a] for a in ('kind','hash','size') if a in v} if v['kind']=='file' else {a:v[a] for a in ('kind','target','size')} for k,v in before.items()}, 'UPLOAD_ARCHIVE_CONTENT_MISMATCH')
        backup_env = {k:self.env[k] for k in ('DB_NAME','DB_HOST','DB_PORT','DB_USER','DB_PASSWORD','PATH','HOME','LANG','LC_ALL') if k in self.env}
        self.u.database_backup(self.db,backup_env,b/'database-before.dump')
        # Traverse/decompress every archive payload, beyond the TOC-only check.
        run(['pg_restore','--exit-on-error','--file=/dev/null',b/'database-before.dump'],env=backup_env)
        need(tree_inventory(uploads)==before, 'UPLOADS_CHANGED_DURING_DATABASE_BACKUP')
        atomic_json(b/'uploads-inventory.json',before)
        self.assert_preserved(baseline)
        hashes = {str(p.relative_to(b)):sha(p) for p in sorted(b.rglob('*')) if p.is_file() and str(p.relative_to(b)) not in ('release.json','backup-hashes.json','source-transaction/files/journal.json','frontend-transaction/files/journal.json')}
        fsync_backup_tree(b)
        atomic_json(b/'backup-hashes.json',hashes)
        verify_backups(b)

    def stop_for_code_recovery(self):
        # Explicit stop suppresses Restart=always. Never replay init_db on rollback.
        if hasattr(self,'maintenance'):
            self.maintenance.operations.hold_for_recovery()
        run(['systemctl','stop',SERVICE],timeout=120)
        state=dict(line.split('=',1) for line in run(['systemctl','show',SERVICE,
            '-p','ActiveState','-p','ControlGroup']).splitlines() if '=' in line)
        need(state.get('ActiveState')=='inactive','RECOVERY_SERVICE_NOT_STOPPED')
        group=state.get('ControlGroup','')
        if group:
            need(group.startswith('/') and '..' not in Path(group).parts,'UNSAFE_SERVICE_CGROUP')
            directory=Path('/sys/fs/cgroup')/group.lstrip('/')
            need(not any(p.read_text().split() for p in directory.rglob('cgroup.procs')),
                 'RECOVERY_SERVICE_CHILDREN_REMAIN')

    def restart(self, baseline):
        run(['systemctl','restart',SERVICE],timeout=90)
        last = None
        for _ in range(30):
            try:
                service = self.service()
                need((service['pid'],service['started'])!=(baseline['service']['pid'],baseline['service']['started']), 'SERVICE_DID_NOT_RESTART')
                need(service['python']==baseline['service']['python'], 'SERVICE_INTERPRETER_CHANGED')
                need(self.health(service)==baseline['version'], 'RUNTIME_VERSION_CHANGED')
                return service
            except Exception as error:
                last = error; time.sleep(2)
        raise Stop('RESTART_HEALTH_FAILED') from last

    def verify_frontend(self, local_only=False):
        for name, expected in self.manifest['frontend_files'].items():
            need(sha(relative_path(ROOT,'build/'+name))==expected, 'INSTALLED_FRONTEND_HASH_FAILED')
        if local_only:return
        last = None
        for _ in range(15):
            try:
                self.public_check({n:self.manifest['frontend_files'][n] for n in ('index.html','asset-manifest.json')})
                return
            except Exception as error:
                last=error; time.sleep(2)
        raise Stop('PUBLIC_FRONTEND_VERIFICATION_FAILED') from last

    def verify_rollback(self, baseline):
        self.assert_preserved(baseline)
        for name,expected in self.manifest['frontend_before'].items():
            need(sha(relative_path(ROOT,'build/'+name))==expected,'ROLLED_BACK_FRONTEND_HASH_FAILED')
        for name, entry in self.manifest['source'].items():
            p=relative_path(ROOT,name)
            need((sha(p) if p.exists() else None)==entry['before_sha256'], 'ROLLED_BACK_SOURCE_HASH_FAILED')

def tree_inventory(root):
    result={}
    for directory, dirs, files in os.walk(root,followlinks=False):
        for name in [*dirs,*files]:
            p=Path(directory)/name; st=p.lstat(); relative=str(p.relative_to(root))
            if p.is_symlink(): result[relative]=dict(kind='link',target=os.readlink(p),size=0)
            elif p.is_file(): result[relative]=dict(kind='file',hash=sha(p),size=st.st_size)
            else: need(p.is_dir(),'UPLOAD_SPECIAL_FILE')
    return result

def verify_backups(evidence):
    b=Path(evidence)
    hashes=json.loads((b/'backup-hashes.json').read_text())
    for name, expected in hashes.items():
        need(sha(relative_path(b,name))==expected,'BACKUP_INTEGRITY_FAILED')


def fsync_backup_tree(evidence):
    """Persist our private backup files, then directories, before application writes."""
    b=private_directory(evidence)
    entries=sorted(b.rglob('*'))
    need(all(not p.is_symlink() for p in entries), 'BACKUP_SYMLINK_REFUSED')
    for p in entries:
        if p.is_dir(): continue
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode), 'BACKUP_SPECIAL_FILE_REFUSED')
            os.fsync(fd)
        finally: os.close(fd)
    directories=sorted([p for p in entries if p.is_dir()],key=lambda p:len(p.parts),reverse=True)
    for p in [*directories,b,b.parent]:
        fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
