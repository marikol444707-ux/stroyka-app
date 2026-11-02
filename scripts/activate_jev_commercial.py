"""Explicit operator activation of the already reviewed f214b9a8 payload.

Not a general deployer. No automatic execution on import, container recreation,
SIGKILL, old-key reads/rotation, database access, data restore or receipt cleanup.
The operator invokes apply only during maintenance. Rollback preserves new
private state/key/dependencies and retains the source backup until acceptance.
"""
import argparse
import fcntl
import grp
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile

PAYLOAD='f214b9a839403c6e45beb96858016635db5c142c'
BASELINE='ba6cf4fe3357fd5549c11799452cdff4820b15ea'
PLUGIN='jev_agent/tender_finder/integration/hermes_jev_tool.py'
OLD=('stroyka-jev.socket','stroyka-jev.service')
NEW=('stroyka-jev-commercial.socket','stroyka-jev-commercial.service')
STEPS=frozenset(('wheel_download','python_venv','venv_install','document_sandbox_probe','source_backup',
    'legacy_services_stop','hermes_stop','source_install','commercial_config','systemd_reload',
    'hermes_start','legacy_services_start','commercial_services_start','broker_checks','awaiting_real_acceptance'))
WHEEL='pypdf-6.18.1-py3-none-any.whl'
WHEEL_SHA='ee93a2665670ecf57ee81d197a4ca548f3dc15f9cefc56e59b8140866aaa3de5'
WHEEL_URL='https://files.pythonhosted.org/packages/58/13/645df3995075112cb3cce15e8797c205f0f88fb50acc11012b84b071bc22/'+WHEEL


def sha(raw):return hashlib.sha256(raw).hexdigest()


def read_file(path,*,uid=0,maximum=8*1024*1024,private=False):
    path=Path(path)
    if path.resolve(strict=True)!=path:raise ValueError('protected_regular_file_required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_nlink!=1
                or info.st_mode&0o022 or info.st_size>maximum
                or private and stat.S_IMODE(info.st_mode)!=0o600):
            raise ValueError('protected_regular_file_required')
        raw=os.read(fd,maximum+1)
        if len(raw)!=info.st_size:raise ValueError('file_changed_during_read')
        return raw
    finally:os.close(fd)


def command(*args,timeout=240):
    environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    if 'DOCKER_CONFIG' in os.environ:environment['DOCKER_CONFIG']=os.environ['DOCKER_CONFIG']
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=timeout,
        env=environment)
    if result.returncode or len(result.stdout)>1024*1024:raise ValueError('operator_command_failed')
    return result.stdout


def source_name(name):
    return name in ('jev_agent/__init__.py','jev_agent/server_runtime/scripts/jev_commercial_search.py') or bool(
        re.fullmatch(r'jev_agent/tender_finder/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py',name))


def pinned_sources(repository,commit):
    files={};total=0
    for row in command('/usr/bin/git','-C',str(repository),'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        metadata,name=row.split(b'\t',1);name=name.decode()
        if not source_name(name):continue
        mode,kind,blob=metadata.decode().split()
        if mode!='100644' or kind!='blob':raise ValueError('regular_pinned_sources_required')
        raw=command('/usr/bin/git','-C',str(repository),'cat-file','blob',blob);total+=len(raw)
        if len(files)>=128 or total>8*1024*1024:raise ValueError('bounded_pinned_sources_required')
        files[name]=sha(raw)
    if PLUGIN not in files:raise ValueError('complete_pinned_sources_required')
    return files


def verify_staged_sources(stage,expected,*,uid=0):
    found={}
    for index,path in enumerate((stage/'source').rglob('*')):
        if index>=2048:raise ValueError('bounded_staged_sources_required')
        info=path.lstat()
        if info.st_uid!=uid or info.st_mode&0o022:raise ValueError('protected_staged_sources_required')
        if stat.S_ISDIR(info.st_mode):continue
        name=path.relative_to(stage/'source').as_posix()
        if name not in expected:raise ValueError('unknown_staged_file_preserved')
        found[name]=sha(read_file(path,uid=uid,maximum=1024*1024))
    if found!=expected:raise ValueError('staged_payload_changed')


def bootstrap(stage):
    """Authenticate every staged Python file before importing that package."""
    stage=Path(stage).absolute()
    if (stage.resolve(strict=True)!=stage or stage.parent!=Path('/tmp')
            or not re.fullmatch(r'jev-upgrade\.[A-Za-z0-9]+',stage.name)):
        raise ValueError('existing_private_upgrade_stage_required')
    tmp=Path('/tmp').stat()
    if tmp.st_uid!=0 or tmp.st_mode&0o022 and not tmp.st_mode&stat.S_ISVTX:
        raise ValueError('protected_operator_stage_parent_required')
    shared=Path('/run/stroyka-jev');info=shared.lstat()
    if (shared.resolve(strict=True)!=shared or not stat.S_ISDIR(info.st_mode)
            or info.st_uid!=0 or info.st_gid!=10000 or stat.S_IMODE(info.st_mode)!=0o710):
        raise ValueError('existing_shared_socket_metadata_changed')
    try:group=grp.getgrgid(10000)
    except KeyError:raise ValueError('existing_gateway_group_required') from None
    if group.gr_gid!=10000:raise ValueError('existing_gateway_group_required')
    for directory in (stage,stage/'source',stage/'repository'):
        info=directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077
                or directory.resolve(strict=True)!=directory):raise ValueError('private_operator_stage_required')
    expected=pinned_sources(stage/'repository',PAYLOAD)
    verify_staged_sources(stage,expected)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(stage/'source'))
    from jev_agent.tender_finder.commercial import upgrade_review as review
    from jev_agent.tender_finder.commercial.prepare_install import review_files
    from jev_agent.tender_finder.prepare_install import SERVICE,SOCKET
    from jev_agent.tender_finder.settings import load_settings
    from jev_agent.tender_finder.standalone_release import verify_ci,_save,root_broker_probe
    from jev_agent.tender_finder.systemd_bootstrap import discover_gateway_peer
    from jev_agent.tender_finder.docker_delivery import check_hermes_container
    legacy=load_settings('/etc/stroyka-jev/bridge.json')
    public=load_settings('/opt/stroyka-jev/config/bridge.json',trusted_root=Path('/opt/stroyka-jev'))
    if legacy!=public:raise ValueError('matching_existing_owner_policies_required')
    approved=stage/'commercial-upgrade-review'
    plan=json.loads(read_file(approved/'UPGRADE_REVIEW.json',private=True))
    previous=pinned_sources(stage/'repository',BASELINE)
    if (plan.get('kind')!='COMMERCIAL_UPGRADE_REVIEW_ONLY' or plan.get('baseline_commit')!=BASELINE
            or plan.get('candidate_commit')!=PAYLOAD or plan.get('previous_files')!=previous
            or plan.get('candidate_files')!=expected or plan.get('changes')!=review.change_plan(previous,expected)):
        raise ValueError('exact_existing_upgrade_review_required')
    prepared={name:text.encode() for name,text in review_files(legacy).items()}
    for name,raw in prepared.items():
        if read_file(approved/name,private=True)!=raw:raise ValueError('reviewed_configuration_changed')
    verify_ci(PAYLOAD)
    return {'stage':stage,'previous':previous,'candidate':expected,'prepared':prepared,
        'old_units':{OLD[1]:SERVICE.encode(),OLD[0]:SOCKET.encode()},
        'legacy_hash':sha(read_file(Path('/etc/stroyka-jev/bridge.json'),private=True)),
        'public_hash':sha(read_file(Path('/opt/stroyka-jev/config/bridge.json'))),
        'installed':review.installed_manifest,'save':_save,'probe':root_broker_probe,
        'peer':discover_gateway_peer,'container':lambda:check_hermes_container(require_jev_mounts=True)}


def atomic_file(path,raw,mode,gid,*,uid=0):
    temporary=path.parent/('.jev-activation-'+secrets.token_hex(16));fd=None
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            fd=None;stream.write(raw);stream.flush();os.fchmod(stream.fileno(),mode)
            if uid==0:os.fchown(stream.fileno(),0,gid)
            os.fsync(stream.fileno())
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if fd is not None:os.close(fd)
        temporary.unlink(missing_ok=True)


def wheel_contents(raw):
    """Only the pinned pure-Python wheel; no pip, hooks, .pth or extraction API."""
    if sha(raw)!=WHEEL_SHA:raise ValueError('pinned_wheel_hash_mismatch')
    files={};total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        if not 1<=len(entries)<=512:raise ValueError('bounded_wheel_required')
        for row in entries:
            name=row.filename;parts=name.rstrip('/').split('/')
            if (not re.fullmatch(r'[A-Za-z0-9_.\-/]+',name) or len(parts)<2
                    or parts[0] not in ('pypdf','pypdf-6.18.1.dist-info')
                    or any(part in ('','..','.') for part in parts) or row.orig_filename!=name
                    or name in files or row.flag_bits&1 or row.compress_type not in (0,8)
                    or stat.S_IFMT(row.external_attr>>16) not in (0,stat.S_IFREG,stat.S_IFDIR)
                    or name.endswith(('.pth','.pyc')) or '__pycache__' in parts
                    or row.file_size>1024*1024 or row.file_size>200*max(1,row.compress_size)):
                raise ValueError('unsafe_wheel_member')
            total+=row.file_size
            if total>8*1024*1024:raise ValueError('bounded_wheel_required')
            if row.is_dir():continue
            files[name]=archive.read(row)
        if (b'Root-Is-Purelib: true' not in files.get('pypdf-6.18.1.dist-info/WHEEL',b'')
                or 'pypdf/__init__.py' not in files or 'pypdf-6.18.1.dist-info/METADATA' not in files
                or any('/'.join(name.split('/')[:index]) in files
                       for name in files for index in range(1,len(name.split('/'))))):
            raise ValueError('pure_python_pypdf_wheel_required')
    return files


def install_wheel(site,raw,*,uid=0):
    files=wheel_contents(raw);site=Path(site)
    if site.resolve(strict=True)!=site:raise ValueError('protected_venv_site_required')
    for name in files:
        path=site/name
        if path.exists() or path.is_symlink():raise ValueError('existing_dependency_preserved')
    for name,data in files.items():
        path=site/name;path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        for directory in (path.parent,*path.parent.parents):
            info=directory.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or info.st_mode&0o022
                    or directory.resolve(strict=True)!=directory):raise ValueError('protected_dependency_parent_required')
            if directory==site:break
        atomic_file(path,data,0o644,0,uid=uid)


def validate_venv_tree(venv,*,uid=0):
    venv=Path(venv)
    if venv.resolve(strict=True)!=venv:raise ValueError('protected_venv_tree_required')
    for path in (venv,*venv.rglob('*')):
        info=path.lstat()
        if info.st_uid!=uid:raise ValueError('protected_venv_tree_required')
        if stat.S_ISLNK(info.st_mode):
            if not path.resolve(strict=True).is_relative_to(venv):raise ValueError('external_venv_alias_refused')
        elif not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or info.st_mode&0o022:
            raise ValueError('protected_venv_tree_required')


class Activation:
    """Fixed paths. Underscored seams are for isolated filesystem tests only."""
    def __init__(self,bundle,*,_root=Path('/'),_uid=0,_run=command,_provision=None,_sleep=time.sleep):
        self.bundle=bundle;self.stage=bundle['stage'];self.root=Path(_root);self.uid=_uid;self.run=_run;self.sleep=_sleep
        self.journal=self.stage/'commercial-activation.json';self.backup=self.stage/'commercial-code-backup'
        self.provision=_provision or self.dependencies
        self.changed={name for name in bundle['candidate'] if bundle['previous'].get(name)!=bundle['candidate'][name]}
        if PLUGIN in self.changed or bundle['previous'].keys()-bundle['candidate'].keys():
            raise ValueError('non_replacing_additive_source_upgrade_required')
        prepared=bundle['prepared']
        self.targets={
            '/etc/stroyka-jev-commercial/runtime.json':(prepared['policy/runtime.json'],0o600,0,True),
            '/opt/stroyka-jev/config/commercial.json':(prepared['policy/commercial.json'],0o640,10000,False),
            '/etc/systemd/system/'+NEW[0]:(prepared['units/'+NEW[0]],0o644,0,False),
            '/etc/systemd/system/'+NEW[1]:(prepared['units/'+NEW[1]],0o644,0,False),
            '/etc/tmpfiles.d/stroyka-jev-commercial.conf':(prepared['units/stroyka-jev-commercial.conf'],0o644,0,False)}

    def path(self,name):return self.root/name.lstrip('/')
    def save(self,state):self.bundle['save'](self.journal,state)
    def step(self,state,name):
        if name not in STEPS:raise ValueError('fixed_activation_step_required')
        state['step']=name;self.save(state)
    def unit(self,name):
        raw=self.run('/usr/bin/systemctl','show',name,'--no-pager',
            '--property=LoadState,ActiveState,SubState,UnitFileState,DropInPaths,TimeoutStopUSec,KillSignal')
        return dict(line.split('=',1) for line in raw.decode().splitlines() if '=' in line)

    def protected_directory(self,path,mode,gid=0,*,create=False):
        if create:path.mkdir(mode=mode)
        info=path.lstat()
        if (path.resolve(strict=True)!=path or not stat.S_ISDIR(info.st_mode)
                or info.st_uid!=self.uid or info.st_mode&0o022):raise ValueError('protected_activation_directory_required')
        if create:
            path.chmod(mode)
            if self.uid==0:os.chown(path,0,gid)

    def parents(self,path):
        missing=[];parent=path.parent
        while not parent.exists():missing.append(parent);parent=parent.parent
        for current in (parent,*parent.parents):
            info=current.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=self.uid or info.st_mode&0o022:
                raise ValueError('protected_activation_parent_required')
            if current==self.root:break
        for current in reversed(missing):self.protected_directory(current,0o755,create=True)

    def validate_old(self):
        self.bundle['installed'](self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=self.uid,trusted_root=self.root)
        for name in self.bundle['previous']:
            if stat.S_IMODE(self.path('/opt/stroyka-jev/app/'+name).stat().st_mode)!=0o644:
                raise ValueError('readable_protected_legacy_sources_required')
        self.validate_existing_policies_and_units()
        for name in NEW:
            if self.unit(name).get('LoadState')!='not-found':raise ValueError('existing_commercial_service_preserved')
        shared=self.path('/run/stroyka-jev');info=shared.lstat()
        if (shared.resolve(strict=True)!=shared or not stat.S_ISDIR(info.st_mode) or info.st_uid!=self.uid
                or stat.S_IMODE(info.st_mode)!=0o710 or self.uid==0 and info.st_gid!=10000):
            raise ValueError('existing_shared_socket_metadata_changed')
        for name in ('/etc/stroyka-jev-commercial','/opt/stroyka-jev-commercial',
                     '/var/lib/stroyka-jev-commercial','/run/stroyka-jev/commercial.sock',*self.targets):
            path=self.path(name)
            if path.exists() or path.is_symlink():raise ValueError('existing_commercial_target_preserved')
        self.bundle['peer']()

    def validate_existing_policies_and_units(self):
        if sha(read_file(self.path('/etc/stroyka-jev/bridge.json'),uid=self.uid,private=True))!=self.bundle['legacy_hash']:
            raise ValueError('existing_owner_policy_changed')
        if sha(read_file(self.path('/opt/stroyka-jev/config/bridge.json'),uid=self.uid))!=self.bundle['public_hash']:
            raise ValueError('existing_gateway_policy_changed')
        for name,raw in self.bundle['old_units'].items():
            if read_file(self.path('/etc/systemd/system/'+name),uid=self.uid)!=raw:
                raise ValueError('existing_service_configuration_changed')
            row=self.unit(name)
            if row.get('ActiveState')!='active' or row.get('UnitFileState')!='enabled' or row.get('DropInPaths'):
                raise ValueError('active_unmodified_legacy_units_required')
            if name.endswith('.service') and (row.get('TimeoutStopUSec')!='infinity' or row.get('KillSignal')!='15'):
                raise ValueError('graceful_infinite_legacy_shutdown_required')

    def write(self,state,name,raw,mode=0o644,gid=0):
        if name not in state['intents']:state['intents'].append(name);self.save(state)
        path=self.path(name);self.parents(path)
        expected=self.bundle['previous'].get(name.removeprefix('/opt/stroyka-jev/app/'))
        if expected is not None:
            if sha(read_file(path,uid=self.uid))!=expected:raise ValueError('source_changed_before_write')
        elif path.exists() or path.is_symlink():raise ValueError('new_target_changed_before_write')
        atomic_file(path,raw,mode,gid,uid=self.uid)

    def dependencies(self,state):
        # A pure Python wheel, independently pinned by hash; no sdist/setup hook,
        # pip/ensurepip dependency, global install, or system package change.
        self.step(state,'wheel_download');wheel=self.stage/WHEEL
        if not wheel.exists():
            with urllib.request.urlopen(WHEEL_URL,timeout=30) as response:
                if response.url!=WHEEL_URL:raise ValueError('pinned_wheel_origin_changed')
                raw=response.read(1024*1024)
            if sha(raw)!=WHEEL_SHA:raise ValueError('pinned_wheel_hash_mismatch')
            with wheel.open('xb') as stream:stream.write(raw)
            wheel.chmod(0o600)
        if sha(read_file(wheel,uid=self.uid,private=True))!=WHEEL_SHA:raise ValueError('pinned_wheel_hash_mismatch')
        venv=self.path('/opt/stroyka-jev-commercial/venv')
        self.step(state,'python_venv')
        self.run('/usr/bin/python3','-I','-B','-m','venv','--without-pip','--copies',str(venv))
        self.step(state,'venv_install')
        raw=self.run(str(venv/'bin/python3'),'-I','-B','-c','import sysconfig;print(sysconfig.get_path("purelib"))')
        site=Path(raw.decode().strip())
        if not site.is_relative_to(venv) or site.resolve(strict=True)!=site:raise ValueError('private_venv_site_required')
        install_wheel(site,read_file(wheel,uid=self.uid,private=True),uid=self.uid)
        validate_venv_tree(venv,uid=self.uid)
        self.step(state,'document_sandbox_probe')
        code='import sys;sys.path.insert(0,'+repr(str(self.stage/'source'))+');from jev_agent.tender_finder.commercial.systemd_bootstrap import verify_document_runtime;verify_document_runtime()'
        self.run(str(venv/'bin/python3'),'-I','-B','-c',code)

    def stopped(self,units):
        if any(self.unit(name).get('ActiveState') not in ('inactive','failed') for name in units):
            raise ValueError('service_shutdown_still_inflight')

    def container_running(self,identifier):
        if not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('fixed_container_identity_required')
        raw=self.run('/usr/bin/docker','--host=unix:///var/run/docker.sock','inspect','--format','{{json .State.Running}}',identifier)
        value=json.loads(raw)
        if type(value) is not bool:raise ValueError('container_state_required')
        return value

    def stop_container(self,state):
        state['container_stop_intent']=True;self.save(state)
        if self.container_running(state['container']):
            raw=self.run('/usr/bin/docker','--host=unix:///var/run/docker.sock','inspect','--format','{{json .Config.StopSignal}}',state['container'])
            if json.loads(raw) not in (None,'','SIGTERM','15'):raise ValueError('reviewed_term_stop_signal_required')
            # An explicit stop suppresses unless-stopped restarts. -1 instructs
            # the daemon to wait forever: a CLI timeout must NOT become SIGKILL.
            self.run('/usr/bin/docker','--host=unix:///var/run/docker.sock','stop','--timeout=-1',state['container'])
        for attempt in range(90):
            if not self.container_running(state['container']):return
            self.sleep(1)
        raise ValueError('container_shutdown_still_inflight')

    def start_container(self,state):
        if not self.container_running(state['container']):
            self.run('/usr/bin/docker','--host=unix:///var/run/docker.sock','start',state['container'])
        for attempt in range(60):
            try:
                if self.bundle['container']()!=state['container']:raise ValueError('container_identity_changed')
                self.bundle['peer']();return
            except (ValueError,OSError):self.sleep(1)
        raise ValueError('gateway_start_not_confirmed')

    def healthy(self,units):
        for attempt in range(90):
            try:
                for name in units:
                    if self.unit(name).get('ActiveState')!='active':raise ValueError('broker_not_active')
                for name in units:
                    if name.endswith('.socket'):
                        leaf='commercial.sock' if name in NEW else 'admission.sock'
                        self.bundle['probe'](self.path('/run/stroyka-jev/'+leaf))
                self.bundle['peer']();return
            except (ValueError,OSError):self.sleep(1)
        raise ValueError('initialized_brokers_not_confirmed')

    def apply(self):
        if self.journal.exists():raise ValueError('existing_activation_requires_rollback_review')
        self.validate_old();identifier=self.bundle['container']()
        state={'format':1,'payload':PAYLOAD,'phase':'provisioning','container':identifier,
            'intents':[],'maintenance':False,'container_stop_intent':False,'new_units_intent':False,
            'backups':{},'legacy_hash':self.bundle['legacy_hash'],'step':'wheel_download','failed_step':None}
        self.save(state)
        try:
            self.protected_directory(self.path('/opt/stroyka-jev-commercial'),0o700,create=True)
            self.provision(state)  # All external dependency work precedes downtime.
            # Recheck mutable inputs after dependency download/provisioning.
            self.bundle['installed'](self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=self.uid,trusted_root=self.root)
            if self.bundle['container']()!=identifier:raise ValueError('container_changed_before_maintenance')
            self.validate_existing_policies_and_units();self.bundle['peer']()
            self.step(state,'source_backup')
            self.backup.mkdir(mode=0o700)
            for name in sorted(self.changed&self.bundle['previous'].keys()):
                path=self.path('/opt/stroyka-jev/app/'+name);info=path.stat();raw=read_file(path,uid=self.uid)
                if sha(raw)!=self.bundle['previous'][name] or stat.S_IMODE(info.st_mode)!=0o644:
                    raise ValueError('legacy_source_metadata_changed')
                destination=self.backup/name;destination.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
                atomic_file(destination,raw,0o600,0,uid=self.uid)
                state['backups'][name]={'sha256':sha(raw),'mode':stat.S_IMODE(info.st_mode),'gid':info.st_gid}
            self.save(state)
            state['maintenance']=True;state['phase']='stopping';self.save(state)
            self.step(state,'legacy_services_stop')
            self.run('/usr/bin/systemctl','stop',*OLD);self.stopped(OLD)
            self.step(state,'hermes_stop')
            self.stop_container(state)
            state['phase']='installing';self.save(state)
            self.step(state,'source_install')
            for name in sorted(self.changed):
                raw=read_file(self.stage/'source'/name,uid=self.uid)
                if sha(raw)!=self.bundle['candidate'][name]:raise ValueError('candidate_source_changed')
                self.write(state,'/opt/stroyka-jev/app/'+name,raw)
            self.step(state,'commercial_config')
            for name,mode,gid in (('/etc/stroyka-jev-commercial',0o700,0),
                    ('/etc/stroyka-jev-commercial/private',0o700,0),('/var/lib/stroyka-jev-commercial',0o700,0),
                    ('/var/lib/stroyka-jev-commercial/requests',0o700,0),('/var/lib/stroyka-jev-commercial/admissions',0o700,0),
                    ('/var/lib/stroyka-jev-commercial/private',0o700,0),('/var/lib/stroyka-jev-commercial/results',0o750,10000),
                    ('/var/lib/stroyka-jev-commercial/registry',0o700,0)):
                self.protected_directory(self.path(name),mode,gid,create=True)
            key=self.path('/etc/stroyka-jev-commercial/private/admission.key')
            fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(secrets.token_bytes(32));stream.flush();os.fsync(stream.fileno())
            for name,(raw,mode,gid,retain) in self.targets.items():self.write(state,name,raw,mode,gid)
            self.bundle['installed'](self.path('/opt/stroyka-jev/app'),self.bundle['candidate'],uid=self.uid,trusted_root=self.root)
            self.step(state,'systemd_reload')
            self.run('/usr/bin/systemctl','daemon-reload')
            self.step(state,'hermes_start')
            self.start_container(state)
            self.step(state,'legacy_services_start')
            self.run('/usr/bin/systemctl','start',*OLD)
            state['new_units_intent']=True;self.save(state)
            self.step(state,'commercial_services_start')
            self.run('/usr/bin/systemctl','enable','--now',*NEW)
            self.step(state,'broker_checks')
            self.healthy(OLD+NEW)
            state['phase']='activated_unverified';self.step(state,'awaiting_real_acceptance')
            return {'activated':True,'real_search_acceptance':False,'real_telegram_acceptance':False,
                'backups_retained':True,'container_recreated':False,'installation_ready':False}
        except Exception:
            state['failed_step']=state['step'];state['phase']='failed';self.save(state)
            raise

    def state(self):
        state=json.loads(read_file(self.journal,uid=self.uid,private=True))
        allowed={'/opt/stroyka-jev/app/'+name for name in self.changed}|self.targets.keys()
        if (state.get('format')!=1 or state.get('payload')!=PAYLOAD
                or not re.fullmatch('[a-f0-9]{64}',str(state.get('container','')))
                or type(state.get('intents')) is not list or not set(state['intents'])<=allowed
                or state.get('legacy_hash')!=self.bundle['legacy_hash']
                or any(type(state.get(name)) is not bool for name in ('maintenance','container_stop_intent','new_units_intent'))
                or state.get('phase') not in ('provisioning','stopping','installing','failed','activated_unverified','rolled_back')
                or state.get('step') not in STEPS or state.get('failed_step') not in STEPS|{None}
                or len(state['intents'])!=len(set(state['intents']))
                or not set(state.get('backups',{}))<=self.changed&self.bundle['previous'].keys()):
            raise ValueError('owned_activation_journal_required')
        for name,row in state['backups'].items():
            if row.get('sha256')!=self.bundle['previous'][name] or row.get('mode')!=0o644 or type(row.get('gid')) is not int:
                raise ValueError('owned_backup_metadata_required')
        return state

    def rollback(self):
        state=self.state()
        if state['phase']=='rolled_back':
            self.bundle['installed'](self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=self.uid,trusted_root=self.root)
            self.validate_existing_policies_and_units()
            if self.bundle['container']()!=state['container']:raise ValueError('original_container_not_restored')
            self.healthy(OLD)
            return {'restored':True,'data_restored':False,'backups_retained':True}
        # Refuse foreign changes BEFORE stopping a working process or overwriting
        # anything. An intent can contain either the old bytes or our new bytes.
        for name in state['intents']:
            path=self.path(name)
            if not path.exists() and not path.is_symlink():continue
            relative=name.removeprefix('/opt/stroyka-jev/app/')
            expected={self.bundle['candidate'].get(relative),self.bundle['previous'].get(relative)} if relative!=name else {sha(self.targets[name][0])}
            if sha(read_file(path,uid=self.uid)) not in expected:raise ValueError('foreign_change_blocks_rollback')
        for name,row in state['backups'].items():
            if sha(read_file(self.backup/name,uid=self.uid,private=True))!=row['sha256']:
                raise ValueError('source_backup_changed')
        if state['maintenance']:
            if state['new_units_intent']:
                self.run('/usr/bin/systemctl','stop',*NEW);self.stopped(NEW)
                self.run('/usr/bin/systemctl','disable',*NEW)
            self.run('/usr/bin/systemctl','stop',*OLD);self.stopped(OLD)
            self.stop_container(state)
            for name in reversed(state['intents']):
                path=self.path(name);relative=name.removeprefix('/opt/stroyka-jev/app/')
                if relative!=name and relative in self.bundle['previous']:
                    row=state['backups'].get(relative)
                    if row is None:raise ValueError('original_source_backup_required')
                    atomic_file(path,read_file(self.backup/relative,uid=self.uid,private=True),row['mode'],row['gid'],uid=self.uid)
                elif relative==name and self.targets[name][3]:continue
                else:path.unlink(missing_ok=True)
            self.bundle['installed'](self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=self.uid,trusted_root=self.root)
            self.run('/usr/bin/systemctl','daemon-reload');self.start_container(state)
            self.run('/usr/bin/systemctl','start',*OLD);self.healthy(OLD)
        state['phase']='rolled_back';self.save(state)
        return {'restored':True,'data_restored':False,'new_private_state_retained':True,'backups_retained':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True);parser.add_argument('--operation',choices=('apply','rollback'),required=True)
    args=parser.parse_args(argv);lock=None;activation=None;fresh=False
    try:
        if os.geteuid()!=0 or not sys.flags.isolated:raise ValueError('explicit_isolated_root_operator_required')
        bundle=bootstrap(args.stage)
        lock=os.open('/run/stroyka-jev/operator-upgrade.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600):
            raise ValueError('protected_global_operator_lock_required')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        activation=Activation(bundle)
        fresh=not activation.journal.exists()
        result=activation.apply() if args.operation=='apply' else activation.rollback()
        print(json.dumps(result));return 0
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch('[a-z_]{1,100}',str(error)) else type(error).__name__
        result={'activated':False,'code':code,'installation_ready':False,'backups_retained':True}
        if activation is not None and activation.journal.exists():
            try:result['failed_step']=activation.state().get('failed_step')
            except Exception:result['failed_step']='journal_unavailable'
        if args.operation=='apply' and fresh and activation is not None and activation.journal.exists():
            try:result['rollback']=activation.rollback()
            except Exception as rollback_error:result['rollback']={'restored':False,'code':type(rollback_error).__name__}
        print(json.dumps(result));return 1
    finally:
        if lock is not None:os.close(lock)


if __name__=='__main__':raise SystemExit(main())
