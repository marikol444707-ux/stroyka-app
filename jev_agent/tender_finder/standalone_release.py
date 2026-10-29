"""Explicit root operator release controller, never an autonomous deployment.

prepare is read-only for the application. apply is a maintenance operation and
must only be invoked after the user approves its saved plan. No force/skip-CI,
SIGKILL, container deletion, database restore or removal of request receipts.
The original stopped container and private backup remain until real acceptance.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import tarfile
import time
import urllib.request

from .container_transfer import DockerAPI,DockerFailure,validate_source,stopped_snapshot,create_request,verify_created,stop_gracefully
from .docker_delivery import check_hermes_container
from .prepare_install import review_files
from .source_package import _source,REQUIRED

BRANCH='jev-tender-finder-audit-contract-20261028'
OLD_UNITS=('hermes-jev-search.timer','hermes-jev-search.path')
NEW_UNITS=('stroyka-jev.socket','stroyka-jev.service')


def _json(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def _run(*args):
    value=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=240,
                         env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if value.returncode or len(value.stdout)>4*1024*1024:raise ValueError('operator_command_not_confirmed')
    return value.stdout


def _unit(name):
    value=subprocess.run(['/usr/bin/systemctl','show',name,'--no-pager','-p','LoadState','-p','ActiveState','-p','UnitFileState'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=12,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if len(value.stdout)>4096:raise ValueError('service_metadata_limit')
    result=dict(line.split('=',1) for line in value.stdout.decode().splitlines() if '=' in line)
    if value.returncode and result.get('LoadState')!='not-found':raise ValueError('service_metadata_not_confirmed')
    return result


def _private(path,uid):
    path=Path(path)
    if path.resolve(strict=True)!=path:raise ValueError('private_release_path_required')
    info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError('private_release_directory_required')


def _read(path,uid):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>4*1024*1024:
            raise ValueError('private_release_file_required')
        return os.read(fd,4*1024*1024+1)
    finally:os.close(fd)


def _save(path,value):
    temporary=path.parent/('.jev-'+secrets.token_hex(16))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(_json(value));stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


class _Embedded(HTMLParser):
    def __init__(self):super().__init__();self.parts=None;self.values=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/json':self.parts=[]
    def handle_data(self,value):
        if self.parts is not None:self.parts.append(value)
    def handle_endtag(self,tag):
        if tag=='script' and self.parts is not None:
            try:self.values.append(json.loads(''.join(self.parts)))
            except ValueError:pass
            self.parts=None


def verify_ci(commit):
    url='https://github.com/marikol444707-ux/stroyka-app/actions?query=branch%3A'+BRANCH
    with urllib.request.urlopen(url,timeout=30) as response:
        if response.url!=url:raise ValueError('github_ci_origin_changed')
        raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise ValueError('github_ci_response_limit')
    parser=_Embedded();parser.feed(raw.decode('utf-8'))
    for value in parser.values:
        if type(value) is not dict:continue
        for row in value.get('payload',{}).get('allWorkflowRunsRoute',{}).get('workflowRuns',[]):
            if (row.get('description',{}).get('linkUrl')=='/marikol444707-ux/stroyka-app/commit/'+commit
                    and row.get('workflowFilePath')=='.github/workflows/ci.yml'):
                if row.get('state')!={'status':'WORKFLOW_RUN_STATUS_COMPLETED','conclusion':'WORKFLOW_RUN_CONCLUSION_SUCCESS'}:
                    raise ValueError('exact_source_ci_not_successful')
                if not re.fullmatch(r'https://github\.com/marikol444707-ux/stroyka-app/actions/runs/[0-9]+',str(row.get('runUrl',''))):
                    raise ValueError('exact_source_ci_url_required')
                return row['runUrl']
    raise ValueError('exact_source_ci_unconfirmed')


def source_files(repository,source,commit,uid):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('pinned_source_commit_required')
    entries=_run('git','-C',str(repository),'ls-tree','-r','-z',commit)
    result={}
    for entry in entries.split(b'\0'):
        if not entry:continue
        metadata,name=entry.split(b'\t',1);name=name.decode()
        if not _source(name):continue
        mode,kind,blob=metadata.decode().split()
        path=source/name;info=path.lstat()
        if mode!='100644' or kind!='blob' or not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_mode & 0o022 or info.st_nlink!=1 or path.resolve(strict=True)!=path:
            raise ValueError('protected_exact_source_required')
        raw=path.read_bytes()
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=blob:
            raise ValueError('source_git_blob_conflict')
        result[name]=_sha(raw)
    actual={str(path.relative_to(source)) for path in source.rglob('*') if not path.is_dir()}
    if actual!=set(result) or not REQUIRED<=result.keys():raise ValueError('complete_exact_source_required')
    return result


def _data_manifest(directory):
    result={}
    for path in (directory,*sorted(directory.rglob('*'))):
        info=path.lstat();name='hermes-data'+('/'+str(path.relative_to(directory)) if path!=directory else '')
        row={'mode':info.st_mode,'uid':info.st_uid,'gid':info.st_gid}
        if stat.S_ISREG(info.st_mode):
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            row.update(size=info.st_size,sha256=digest.hexdigest())
        elif stat.S_ISLNK(info.st_mode):row['link']=os.readlink(path)
        elif stat.S_ISSOCK(info.st_mode):continue  # Stopped-process endpoints are not persistent data.
        elif not stat.S_ISDIR(info.st_mode):raise ValueError('special_data_file_requires_review')
        result[name]=row
    return result


def backup_data(directory,archive):
    before=_data_manifest(directory)
    # dereference=False: never follow a data symlink into another host directory.
    with tarfile.open(archive,mode='x:gz',dereference=False) as tar:
        tar.add(directory,arcname='hermes-data',filter=lambda entry:entry if entry.name in before else None)
    archive.chmod(0o600)
    with archive.open('rb') as stream:os.fsync(stream.fileno())
    found={};seen=set()
    with tarfile.open(archive,mode='r:gz') as tar:
        for entry in tar:
            if entry.name in seen or entry.name not in before:raise ValueError('backup_member_conflict')
            seen.add(entry.name)
            row=before[entry.name]
            if row is not None and (entry.uid!=row['uid'] or entry.gid!=row['gid']
                    or entry.mode!=(row['mode'] & 0o7777)):
                raise ValueError('backup_metadata_conflict')
            if entry.isfile() or entry.islnk():
                digest=hashlib.sha256()
                with tar.extractfile(entry) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
                found[entry.name]=(before[entry.name].get('size'),digest.hexdigest())
            elif entry.issym():
                if before.get(entry.name,{}).get('link')!=entry.linkname:raise ValueError('backup_link_conflict')
    expected={name:(row['size'],row['sha256']) for name,row in before.items() if 'sha256' in row}
    if seen!=set(before) or found!=expected or before!=_data_manifest(directory):raise ValueError('quiescent_backup_not_verified')
    return {'regular_files':len(found),'archive_sha256':_file_sha(archive)}


def root_broker_probe(path):
    """Empty unauthenticated handshake: must be rejected, never a search request."""
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(3);connection.connect(str(path));connection.shutdown(socket.SHUT_WR)
        raw=connection.recv(4097)
    if len(raw)>4096 or json.loads(raw)!={'queued':False,'reason':'broker_admission_failed'}:
        raise ValueError('initialized_rejecting_broker_required')


class Release:
    """Fixed production paths; underscored dependency seams are test-only."""
    def __init__(self,stage,*,_api=None,_unit=_unit,_run=_run,_ci=verify_ci,_root=Path('/'),_uid=0,
                 _verify=check_hermes_container,_probe=root_broker_probe):
        self.stage=Path(stage).absolute();_private(self.stage,_uid)
        self.uid=_uid;self.api=_api or DockerAPI();self.unit=_unit;self.run=_run;self.ci=_ci;self.root=Path(_root);self.verify=_verify;self.probe=_probe
        self.state_path=self.stage/'release-state.json'

    def path(self,value):return self.root/value.lstrip('/')
    def checkpoint(self,state):_save(self.state_path,state)
    def state(self):
        state=json.loads(_read(self.state_path,self.uid))
        if (type(state) is not dict or not re.fullmatch('[a-f0-9]{32}',str(state.get('token','')))
                or not re.fullmatch('[a-f0-9]{40}',str(state.get('commit','')))
                or state.get('source_name') not in ('source','source-next') or type(state.get('written')) is not dict):
            raise ValueError('owned_release_state_required')
        if (type(state.get('remove_intents',[])) is not list
                or any(name not in state['written'] for name in state.get('remove_intents',[]))):
            raise ValueError('owned_remove_intents_required')
        fixed={self.path('/etc/stroyka-jev')/name for name in ('private/admission.key','bridge.json','container-image.json')}
        fixed|={self.path('/etc/systemd/system')/name for name in NEW_UNITS}
        fixed.add(self.path('/etc/tmpfiles.d/stroyka-jev.conf'))
        for name,digest in state['written'].items():
            path=Path(name)
            if (not path.is_relative_to(self.path('/opt/stroyka-jev')) and path not in fixed
                    or '..' in path.parts or not re.fullmatch('[a-f0-9]{64}',str(digest))):
                raise ValueError('owned_release_file_paths_required')
        return state

    def _exclusive_writer(self,state):
        directory=self.path('/root/hermes-data').resolve(strict=True)
        for row in self.api.request('GET','/containers/json?all=1'):
            if row.get('Id')==state['original']['Id'] or row.get('State')!='running':continue
            for mount in row.get('Mounts',[]):
                if mount.get('RW') is not True:continue
                source=mount.get('Source')
                if type(source) is not str or not source.startswith('/'):
                    raise ValueError('other_container_mount_requires_review')
                path=Path(source).resolve(strict=False)
                if directory.is_relative_to(path) or path.is_relative_to(directory):
                    raise ValueError('other_active_data_writer_blocks_maintenance')

    def _empty_targets(self):
        for target in ('/opt/stroyka-jev','/etc/stroyka-jev','/var/lib/stroyka-jev','/run/stroyka-jev',
                       '/etc/systemd/system/stroyka-jev.service','/etc/systemd/system/stroyka-jev.socket','/etc/tmpfiles.d/stroyka-jev.conf'):
            path=self.path(target)
            if path.exists() or path.is_symlink():raise ValueError('existing_target_requires_review')
    def _same_source(self,state,running=True):
        actual=self.api.request('GET','/containers/hermes-telegram/json')
        validate_source(actual,stopped=not running)
        if actual['Id']!=state['original']['Id'] or actual['Config']!=state['original']['Config'] or actual['HostConfig']!=state['original']['HostConfig']:
            raise ValueError('source_container_changed_since_review')
        return actual

    def prepare(self,commit,company_id,owner_id,source_name='source'):
        if self.state_path.exists():raise ValueError('existing_release_state_preserved')
        if source_name not in ('source','source-next'):raise ValueError('fixed_source_directory_required')
        files=source_files(self.stage/'repository',self.stage/source_name,commit,self.uid)
        policy=review_files(company_id,owner_id)
        original=self.api.request('GET','/containers/hermes-telegram/json');validate_source(original)
        data=self.path('/root/hermes-data')
        if data.resolve(strict=True)!=data or not data.is_dir():raise ValueError('real_data_directory_required')
        info=self.api.request('GET','/info')
        driver=info.get('Driver')
        if driver not in ('overlay2','overlayfs','btrfs','zfs','vfs'):
            raise ValueError('storage_driver_requires_review')
        image=self.api.request('GET','/images/'+original['Image']+'/json')
        data_bytes=sum(path.lstat().st_size for path in data.rglob('*') if path.is_file() and not path.is_symlink())
        # vfs duplicates complete root layers for snapshot and replacement.
        required=2*data_bytes+512*1024*1024+(2*image['Size'] if driver=='vfs' else 128*1024*1024)
        if shutil.disk_usage(self.stage).free<required:raise ValueError('verified_backup_space_required')
        docker_root=info.get('DockerRootDir')
        if type(docker_root) is not str or not docker_root.startswith('/'):
            raise ValueError('docker_storage_path_required')
        if shutil.disk_usage(self.path(docker_root)).free<required:
            raise ValueError('docker_snapshot_space_required')
        self._empty_targets()
        for name in NEW_UNITS:
            observed=self.unit(name)
            if observed.get('LoadState')!='not-found' or observed.get('UnitFileState')!='':raise ValueError('existing_new_unit_preserved')
        if self.unit('hermes-jev-search.service').get('ActiveState') not in ('inactive','failed'):
            raise ValueError('legacy_search_must_finish_first')
        ci_url=self.ci(commit)
        state={'phase':'prepared','host':socket.gethostname(),'token':secrets.token_hex(16),'commit':commit,'ci_url':ci_url,'source_name':source_name,
            'source_files':files,'original':original,'policy':policy,'old_units':{name:self.unit(name) for name in OLD_UNITS},
            'written':{},'remove_intents':[],'owned_units_started':False,'data_backup_verified':False,'container_snapshot':None,
            'new_id':None,'old_renamed':False,'activated':False,'accepted':False,'stop_intent':False,'stop_confirmed':False,
            'data_bytes':data_bytes,'storage_driver':driver,'required_free_bytes':required}
        self._exclusive_writer(state)
        self.checkpoint(state)
        return {'prepared':True,'ci_url':ci_url,'maintenance_required':True,'installation_started':False,
                'estimated_downtime_minutes':[5,10]}

    def _write(self,state,path,raw,mode=0o644,gid=0):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        path.chmod(mode)
        if self.uid==0:os.chown(path,0,gid)
        state['written'][str(path)]=_sha(raw);self.checkpoint(state)

    def _install_files(self,state):
        app=self.path('/opt/stroyka-jev/app')
        app.parent.mkdir(mode=0o755)  # Exclusive reservation; never join a foreign install directory.
        for name,digest in state['source_files'].items():
            raw=(self.stage/state['source_name']/name).read_bytes()
            if _sha(raw)!=digest:raise ValueError('source_changed_after_approval')
            self._write(state,app/name,raw)
        for directory in (app,*[path for path in app.rglob('*') if path.is_dir()]):directory.chmod(0o755)
        self.path('/opt/stroyka-jev').chmod(0o755)
        etc=self.path('/etc/stroyka-jev');etc.mkdir(mode=0o700);etc.chmod(0o700)
        private=etc/'private';private.mkdir(mode=0o700)
        self._write(state,private/'admission.key',secrets.token_bytes(32),0o600)
        self._write(state,etc/'bridge.json',state['policy']['policy/host-bridge.json'].encode(),0o600)
        gateway=self.path('/opt/stroyka-jev/config');gateway.mkdir(mode=0o750);gateway.chmod(0o750)
        if self.uid==0:os.chown(gateway,0,10000)
        self._write(state,gateway/'bridge.json',state['policy']['policy/gateway-bridge.json'].encode(),0o640,10000)
        self._write(state,etc/'container-image.json',_json(state['container_snapshot']),0o600)
        for name in NEW_UNITS:self._write(state,self.path('/etc/systemd/system/'+name),state['policy']['units/'+name].encode())
        self._write(state,self.path('/etc/tmpfiles.d/stroyka-jev.conf'),state['policy']['units/stroyka-jev.conf'].encode())
        self.run('/usr/bin/systemd-tmpfiles','--create',str(self.path('/etc/tmpfiles.d/stroyka-jev.conf')))
        self.run('/usr/bin/systemctl','daemon-reload')

    def _restore_old_units(self,state):
        for name,old in state['old_units'].items():
            if old.get('LoadState')=='not-found':continue
            current=self.unit(name)
            desired=old.get('ActiveState')=='active'
            if (current.get('ActiveState')=='active')!=desired:
                self.run('/usr/bin/systemctl','start' if desired else 'stop',name)
            restored=self.unit(name)
            if restored.get('ActiveState')!=old.get('ActiveState') or restored.get('UnitFileState')!=old.get('UnitFileState'):
                raise ValueError('previous_service_state_not_restored')

    def apply(self):
        state=self.state()
        if state['phase']!='prepared':raise ValueError('reviewed_prepared_plan_required')
        if state['host']!=socket.gethostname():raise ValueError('prepared_host_changed')
        self.ci(state['commit']);self._same_source(state);self._empty_targets()
        for name,old in state['old_units'].items():
            if self.unit(name)!=old:raise ValueError('service_states_changed_since_review')
        self._exclusive_writer(state)
        if source_files(self.stage/'repository',self.stage/state['source_name'],state['commit'],self.uid)!=state['source_files']:
            raise ValueError('source_changed_after_review')
        state['phase']='maintenance';self.checkpoint(state)
        try:
            for name in OLD_UNITS:
                if self.unit(name).get('ActiveState')=='active':self.run('/usr/bin/systemctl','stop',name)
            if self.unit('hermes-jev-search.service').get('ActiveState') not in ('inactive','failed'):
                raise ValueError('legacy_search_started_during_quiescence')
            state['stop_intent']=True;self.checkpoint(state)
            stop_gracefully(self.api,state['original']['Id'])
            state['stop_confirmed']=True
            state['phase']='old_stopped';self.checkpoint(state)
            self._same_source(state,running=False)
            self._exclusive_writer(state)
            state['data_backup']=backup_data(self.path('/root/hermes-data'),self.stage/'hermes-data.tar.gz')
            state['data_backup_verified']=True;self.checkpoint(state)
            stopped,pin=stopped_snapshot(self.api,state['original']['Id'])
            state['container_snapshot']=pin;state['phase']='snapshotted';self.checkpoint(state)
            self._install_files(state)
            candidate='hermes-jev-new-'+state['token']
            body=create_request(stopped,pin,release_token=state['token']).body
            response=self.api.request('POST','/containers/create?name='+candidate,body)
            state['new_id']=response['Id'];self.checkpoint(state)
            actual=self.api.request('GET','/containers/'+state['new_id']+'/json')
            verify_created(actual,stopped,pin,release_token=state['token'])
            backup_name='hermes-jev-old-'+state['token']
            self.api.request('POST','/containers/'+state['original']['Id']+'/rename?name='+backup_name)
            state['old_renamed']=True;self.checkpoint(state)
            self.api.request('POST','/containers/'+state['new_id']+'/rename?name=hermes-telegram')
            self.api.request('POST','/containers/'+state['new_id']+'/start')
            self.verify(require_jev_mounts=True)
            state['owned_units_started']=True;self.checkpoint(state)
            self.run('/usr/bin/systemctl','enable','--now',*NEW_UNITS)
            deadline=time.monotonic()+90
            while True:
                try:
                    if any(self.unit(name).get('ActiveState')!='active' for name in NEW_UNITS):
                        raise ValueError('new_jev_services_not_active')
                    self.probe(self.path('/run/stroyka-jev/admission.sock'))
                    break
                except (OSError,ValueError):
                    if time.monotonic()>=deadline:raise ValueError('initialized_jev_broker_not_confirmed')
                    time.sleep(1)
            self._restore_old_units(state)
            state['phase']='activated_unverified';state['activated']=True;self.checkpoint(state)
            return {'activated':True,'real_telegram_acceptance':False,'backups_retained':True,'data_restored':False}
        except Exception:
            state['phase']='failed';self.checkpoint(state)
            # Leave receipts/backup and all identities intact for explicit
            # rollback. Never claim an untested automatic recovery succeeded.
            raise

    def rollback(self):
        state=self.state()
        if state['phase']=='prepared':return {'restored':True,'data_restored':False}
        old=self.api.request('GET','/containers/'+state['original']['Id']+'/json')
        if (old.get('Config')!=state['original']['Config'] or old.get('HostConfig')!=state['original']['HostConfig']
                or old.get('Image')!=state['original']['Image']
                or old.get('Name') not in ('/hermes-telegram','/hermes-jev-old-'+state['token'])):
            raise ValueError('foreign_original_container_change_blocks_rollback')
        if state['stop_intent'] and not state['stop_confirmed'] and old['State']['Running']:
            raise ValueError('shutdown_inflight_requires_explicit_recovery')
        if old.get('Name')=='/hermes-jev-old-'+state['token']:state['old_renamed']=True
        if state['phase']=='rolled_back':
            if old['State']['Running'] is not True or old['Name']!='/hermes-telegram':raise ValueError('rollback_state_changed')
            return {'restored':True,'data_restored':False,'backups_retained':True}
        if state['new_id'] is None and state['container_snapshot'] is not None:
            candidate='hermes-jev-new-'+state['token']
            try:untracked=self.api.request('GET','/containers/'+candidate+'/json')
            except DockerFailure as error:
                if error.status!=404:raise
            else:
                source=deepcopy(state['original']);source['State']['Running']=False
                verify_created(untracked,source,state['container_snapshot'],release_token=state['token'])
                state['new_id']=untracked['Id'];self.checkpoint(state)
        for name,digest in state['written'].items():
            path=Path(name)
            if name in state.get('remove_intents',[]) and not path.exists() and not path.is_symlink():continue
            if not path.is_file() or path.is_symlink() or _sha(path.read_bytes())!=digest:
                raise ValueError('foreign_file_change_blocks_rollback')
        if state['new_id'] is not None:
            actual=self.api.request('GET','/containers/'+state['new_id']+'/json')
            if actual.get('Config',{}).get('Labels',{}).get('stroyka.jev.release')!=state['token']:
                raise ValueError('foreign_container_change_blocks_rollback')
            source=deepcopy(state['original']);source['State']['Running']=False
            expected=deepcopy(actual);expected['State']['Running']=False
            verify_created(expected,source,state['container_snapshot'],release_token=state['token'])
        if state['owned_units_started']:self.run('/usr/bin/systemctl','stop',*reversed(NEW_UNITS))
        if state['new_id'] is not None:
            stop_gracefully(self.api,state['new_id'])
            if self.api.request('GET','/containers/'+state['new_id']+'/json').get('Name')=='/hermes-telegram':
                self.api.request('POST','/containers/'+state['new_id']+'/rename?name=hermes-jev-failed-'+state['token'])
        if state['owned_units_started']:self.run('/usr/bin/systemctl','disable',*NEW_UNITS)
        # Keep the key/policy and new operational namespace for later receipt
        # recovery. Remove only our pin/code/unit bytes; never restore data tar.
        keep={str(self.path('/etc/stroyka-jev/private/admission.key')),str(self.path('/etc/stroyka-jev/bridge.json'))}
        for name in state['written']:
            if name not in keep:
                if name not in state.setdefault('remove_intents',[]):
                    state['remove_intents'].append(name);self.checkpoint(state)
                Path(name).unlink(missing_ok=True)
        self.run('/usr/bin/systemctl','daemon-reload')
        if state['old_renamed']:
            self.api.request('POST','/containers/'+state['original']['Id']+'/rename?name=hermes-telegram')
        old=self.api.request('GET','/containers/'+state['original']['Id']+'/json')
        if not old['State']['Running']:self.api.request('POST','/containers/'+state['original']['Id']+'/start')
        self._restore_old_units(state)
        state['phase']='rolled_back';state['activated']=False;self.checkpoint(state)
        return {'restored':True,'data_restored':False,'backups_retained':True}


class Parser(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'invalid operator release arguments\n')


def main(argv=None):
    parser=Parser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','apply','rollback'))
    parser.add_argument('--stage',required=True);parser.add_argument('--commit')
    parser.add_argument('--company-id',type=int);parser.add_argument('--owner-id');parser.add_argument('--source-name',default='source')
    args=parser.parse_args(argv)
    lock=None;release=None
    try:
        if os.geteuid()!=0:raise ValueError('explicit_root_operator_required')
        _private(Path(args.stage).absolute(),0)
        lock=os.open(Path(args.stage)/'release.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        info=os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:
            raise ValueError('private_release_lock_required')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        release=Release(args.stage)
        if args.operation=='prepare':
            result=release.prepare(args.commit,args.company_id,args.owner_id,args.source_name)
        else:
            if args.commit or args.company_id is not None or args.owner_id or args.source_name!='source':
                raise ValueError('existing_reviewed_plan_only')
            result=release.apply() if args.operation=='apply' else release.rollback()
        print(json.dumps(result));return 0
    except Exception as error:
        result={'ok':False,'code':type(error).__name__,'installation_ready':False,'data_restored':False}
        if re.fullmatch('[a-z][a-z0-9_]{0,100}',str(error)):result['reason']=str(error)
        if args.operation=='apply' and release is not None:
            try:result['rollback']=release.rollback()
            except Exception as rollback_error:result['rollback']={'restored':False,'code':type(rollback_error).__name__}
        print(json.dumps(result));return 1
    finally:
        if lock is not None:os.close(lock)


if __name__=='__main__':raise SystemExit(main())
