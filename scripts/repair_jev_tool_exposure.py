"""Explicit, scoped repair of the installed f214 JEV Telegram adapters.

Only pinned JEV adapters/delivery and Telegram's JEV opt-in are changed. The existing
container, keys, queues, model settings and other platform permissions remain.
Uses the previously verified operator's shutdown/probe primitives. No YAML
package installation, old worker rewrite, registration override, or auto-search.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import urllib.request

BASE_REV='11bda5ff0200848d5948ea73f41a28c299cb9c9b'
BASE_SHA='621c7c2bcea211f3d5e425591be8b65fc2585d0ad1c03cfac3b5e82503826917'
PATCH_REV='2d8ba5f3b66f4d0e70f0ad39438e3733528c9ec5'
PATCHES={
 'jev_agent/tender_finder/startup_tool.py':'006418ed67e94d48d6828fc0c4ae6205f962187ae68e3a954894f656d26b2eb7',
 'jev_agent/tender_finder/hermes_binding.py':'e31db6b5690a99c45bca50683cd029eb873d25a5b15f9aca2b5c7a537706eec4',
 'jev_agent/tender_finder/commercial/startup_tool.py':'372df99ee86b900863cc9ca21664a36336ce8bd897b62fd74cee68e5abe4637d',
 'jev_agent/tender_finder/commercial/tool.py':'a42acc7236803a5162727f802fa939197caf73b0119d94cdb71a4a93abfdba9f',
 'jev_agent/tender_finder/docker_delivery.py':'07c6406aa0eb5b81a5e374b386abad638a75acea9aade455d89cabb0064e637d'}
CONFIG='/root/hermes-data/config.yaml'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def download(path,revision,digest):
    url='https://raw.githubusercontent.com/marikol444707-ux/stroyka-app/'+revision+'/'+path
    with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(200000)
    if sha(raw)!=digest:raise ValueError('pinned_repair_source_required')
    return raw


def config_patch(raw):
    """Narrow editor for the reviewed single-bundle selection; no YAML eval.

    All bytes outside the Telegram node stay identical. Ambiguous/aliased/flow
    parent mappings are refused. The actual Hermes reader verifies semantics
    before code replacement; fixture tests also parse the resulting YAML.
    """
    text=raw.decode('utf-8');lines=text.splitlines(keepends=True)
    if len(raw)>262144 or '\t' in text:raise ValueError('simple_reviewed_yaml_required')
    eol='\r\n' if '\r\n' in text else '\n'
    if any(re.match(r'^(?:\ufeff)?[\'"]?<<',line) for line in lines):raise ValueError('yaml_root_merge_requires_review')
    parents=[i for i,line in enumerate(lines) if re.match(r'^(?:\ufeff)?platform_toolsets\s*:',line)]
    if len(parents)>1:raise ValueError('duplicate_platform_selection_requires_review')
    if not parents:
        if re.search(r'^[\'"]platform_toolsets[\'"]\s*:',text,re.M):raise ValueError('quoted_platform_mapping_requires_review')
        suffix=('' if not text or text.endswith(('\n','\r')) else eol)+'platform_toolsets:'+eol+'  telegram: ["hermes-telegram", "jev"]'+eol
        return (text+suffix).encode()
    start=parents[0]
    if not re.fullmatch(r'(?:\ufeff)?platform_toolsets\s*:\s*(?:#[^\r\n]*)?',lines[start].rstrip('\r\n')):
        raise ValueError('aliased_or_flow_platform_mapping_requires_review')
    end=len(lines)
    for i in range(start+1,len(lines)):
        if lines[i].strip() and not lines[i].lstrip().startswith('#') and not lines[i].startswith(' '):end=i;break
    matches=[]
    for i in range(start+1,end):
        match=re.match(r'^( +)telegram\s*:(.*?)(\r?\n)?$',lines[i])
        if match:matches.append((i,match))
    if len(matches)>1:raise ValueError('duplicate_telegram_selection_requires_review')
    if not matches:
        if end and not lines[end-1].endswith(('\n','\r')):lines[end-1]+=eol
        lines.insert(end,'  telegram: ["hermes-telegram", "jev"]'+eol)
        return ''.join(lines).encode()
    index,match=matches[0];indent=match.group(1);value=match.group(2).strip()
    inline=re.fullmatch(r'\[\s*([\'"]?)hermes-telegram\1\s*\]\s*(#[^\r\n]*)?',value)
    if inline:
        comment=(' '+inline.group(2)) if inline.group(2) else ''
        lines[index]=indent+'telegram: ["hermes-telegram", "jev"]'+comment+(eol if match.group(3) else '')
        return ''.join(lines).encode()
    if value and not value.startswith('#'):raise ValueError('unsupported_telegram_yaml_requires_review')
    items=[]
    for i in range(index+1,end):
        line=lines[i]
        if not line.strip() or line.lstrip().startswith('#'):continue
        leading=len(line)-len(line.lstrip(' '))
        if leading<len(indent) or leading==len(indent) and not line.lstrip().startswith('-'):break
        item=re.fullmatch(r'( *)-\s+([\'"]?)hermes-telegram\2\s*(?:#[^\r\n]*)?(?:\r?\n)?',line)
        if item is None:raise ValueError('unsupported_telegram_list_requires_review')
        items.append((i,item.group(1)))
    if len(items)!=1:raise ValueError('reviewed_single_bundle_selection_required')
    item_index,item_indent=items[0]
    if not lines[item_index].endswith(('\n','\r')):lines[item_index]+=eol
    lines.insert(item_index+1,item_indent+'- jev'+eol)
    return ''.join(lines).encode()


def config_write(path,raw,metadata):
    temporary=path.parent/('.jev-config-'+secrets.token_hex(16))
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),metadata['mode'])
            if os.geteuid()==0:os.fchown(stream.fileno(),metadata['uid'],metadata['gid'])
            os.fsync(stream.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)


class Repair:
    def __init__(self,operator,bundle,patches,*,_root=Path('/'),_uid=0,_run=None,_sleep=None,_probe=None):
        self.op=operator;self.bundle=dict(bundle);self.stage=bundle['stage'];self.uid=_uid
        self.bundle['previous']=dict(bundle['candidate']);self.bundle['candidate']={**bundle['candidate'],**{name:sha(raw) for name,raw in patches.items()}}
        if set(patches)!=set(PATCHES):raise ValueError('exact_pinned_repair_files_required')
        self.patches=patches
        self.probe=_probe or self.delivery_probe
        kwargs={'_root':_root,'_uid':_uid}
        if _run is not None:kwargs['_run']=_run
        if _sleep is not None:kwargs['_sleep']=_sleep
        self.base=operator.Activation(self.bundle,**kwargs)
        self.base.journal=self.stage/'tool-exposure-repair.json'
        self.journal=self.base.journal;self.backup=self.stage/'tool-exposure-backup'

    def path(self,name):return self.base.path(name)
    def read(self,path,**kwargs):return self.op.read_file(path,uid=self.uid,**kwargs)
    def save(self,state):self.base.save(state)
    def config_read(self):
        path=self.path(CONFIG);info=path.lstat()
        if (path.resolve(strict=True)!=path or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode) not in (0o600,0o640,0o644)
                or self.uid==0 and info.st_uid not in (0,10000)):
            raise ValueError('protected_owned_hermes_config_required')
        raw=self.op.read_file(path,uid=info.st_uid,maximum=262144)
        return raw,{'uid':info.st_uid,'gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode)}

    def cli(self,*args):
        raw=self.base.run('/usr/bin/docker','--host=unix:///var/run/docker.sock','exec',
            '--user','10000:10000','hermes-telegram','/opt/hermes/bin/hermes','config',*args)
        return raw.decode().strip()

    def settings(self):
        if self.cli('path')!='/opt/data/config.yaml':raise ValueError('default_hermes_profile_config_required')
        groups=json.loads(self.cli('get','platform_toolsets','--json'))
        disabled=json.loads(self.cli('get','agent.disabled_toolsets','--json'))
        if not isinstance(groups,dict) or not isinstance(disabled,list):raise ValueError('typed_toolset_configuration_required')
        if 'jev' in disabled:raise ValueError('jev_explicitly_disabled_by_policy')
        return groups,disabled

    def snapshot(self,expected):
        return self.bundle['installed'](self.path('/opt/stroyka-jev/app'),expected,uid=self.uid,trusted_root=self.base.root)

    def units_ready(self):
        self.base.validate_existing_policies_and_units()
        for name in self.op.NEW:
            row=self.base.unit(name)
            if row.get('ActiveState')!='active' or row.get('UnitFileState')!='enabled' or row.get('DropInPaths'):
                raise ValueError('active_unmodified_commercial_units_required')
            if self.read(self.path('/etc/systemd/system/'+name))!=self.bundle['prepared']['units/'+name]:
                raise ValueError('commercial_unit_changed')

    def delivery_probe(self):
        namespace={'__name__':'jev_agent.tender_finder.verified_delivery_repair',
            '__package__':'jev_agent.tender_finder'}
        exec(compile(self.patches['jev_agent/tender_finder/docker_delivery.py'],'pinned-delivery-repair','exec'),namespace)
        # Imports/validates sender in published Hermes runtime; no request,
        # message, credentials output, or automatic retry of old deliveries.
        return namespace['probe_delivery_runtime']()

    def apply(self):
        if self.journal.exists():raise ValueError('existing_repair_requires_review')
        self.snapshot(self.bundle['previous']);self.units_ready()
        identifier=self.bundle['container']();self.base.validate_stop_signal(identifier);self.bundle['peer']()
        groups,disabled=self.settings()
        if groups.get('telegram')!=['hermes-telegram']:raise ValueError('telegram_selection_changed_since_review')
        old,metadata=self.config_read();new=config_patch(old)
        if old==new:raise ValueError('explicit_telegram_group_change_required')
        self.probe()
        state={'kind':'JEV_TOOL_EXPOSURE_REPAIR','patch_revision':PATCH_REV,'phase':'backing_up',
            'container':identifier,'container_stop_intent':False,'maintenance':False,'config_intent':False,
            'source_intents':[],'config_old_sha':sha(old),'config_new_sha':sha(new),'config_metadata':metadata,
            'old_groups':groups,'old_disabled':disabled}
        self.save(state);self.backup.mkdir(mode=0o700)
        try:
            self.op.atomic_file(self.backup/'config.original',old,0o600,0,uid=self.uid)
            for name in PATCHES:
                raw=self.read(self.path('/opt/stroyka-jev/app/'+name))
                if sha(raw)!=self.bundle['previous'][name]:raise ValueError('adapter_changed_before_backup')
                target=self.backup/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                self.op.atomic_file(target,raw,0o600,0,uid=self.uid)
            self.snapshot(self.bundle['previous']);self.units_ready()
            if self.bundle['container']()!=identifier or self.config_read()[0]!=old:raise ValueError('server_changed_before_repair')
            state['maintenance']=True;state['phase']='stopping';self.save(state)
            self.base.run('/usr/bin/systemctl','stop',*self.op.NEW,*self.op.OLD)
            self.base.stopped(self.op.OLD+self.op.NEW)
            state['config_intent']=True;self.save(state)
            config_write(self.path(CONFIG),new,metadata)
            current,current_disabled=self.settings();wanted={**groups,'telegram':['hermes-telegram','jev']}
            if current!=wanted or current_disabled!=disabled or self.config_read()[0]!=new:
                raise ValueError('telegram_only_configuration_change_not_confirmed')
            self.base.stop_container(state)
            state['phase']='patching';self.save(state)
            for name,raw in self.patches.items():
                path=self.path('/opt/stroyka-jev/app/'+name)
                if sha(self.read(path))!=self.bundle['previous'][name]:raise ValueError('adapter_changed_before_patch')
                state['source_intents'].append(name);self.save(state)
                self.op.atomic_file(path,raw,0o644,0,uid=self.uid)
            self.snapshot(self.bundle['candidate']);self.base.start_container(state)
            self.base.run('/usr/bin/systemctl','start',*self.op.OLD,*self.op.NEW)
            self.base.healthy(self.op.OLD+self.op.NEW)
            self.probe()
            state['phase']='repaired_unverified';self.save(state)
            return {'repaired':True,'telegram_group_added':'jev','source_files_updated':len(PATCHES),
                'runtime_sender_ready':True,'notifications_sent':False,
                'container_recreated':False,'real_search_acceptance':False,'real_telegram_acceptance':False,
                'installation_ready':False,'backups_retained':True}
        except Exception:
            state['failed_phase']=state['phase'];state['phase']='failed';self.save(state);raise

    def state(self):
        state=json.loads(self.read(self.journal,private=True))
        if (state.get('kind')!='JEV_TOOL_EXPOSURE_REPAIR' or state.get('patch_revision')!=PATCH_REV
                or not re.fullmatch('[a-f0-9]{64}',str(state.get('container','')))
                or type(state.get('source_intents')) is not list or not set(state['source_intents'])<=PATCHES.keys()
                or any(type(state.get(k)) is not bool for k in ('maintenance','config_intent','container_stop_intent'))
                or state.get('phase') not in ('backing_up','stopping','patching','failed','repaired_unverified','rolled_back')):
            raise ValueError('owned_visibility_repair_journal_required')
        metadata=state.get('config_metadata',{})
        if (not all(type(metadata.get(k)) is int for k in ('uid','gid','mode'))
                or metadata['mode'] not in (0o600,0o640,0o644)
                or self.uid==0 and metadata['uid'] not in (0,10000)):raise ValueError('owned_config_metadata_required')
        return state

    def rollback(self):
        state=self.state()
        if state['phase']=='rolled_back':
            self.snapshot(self.bundle['previous']);self.units_ready()
            if self.bundle['container']()!=state['container'] or sha(self.config_read()[0])!=state['config_old_sha']:
                raise ValueError('rolled_back_configuration_or_container_changed')
            return {'restored':True,'data_restored':False,'backups_retained':True}
        for name in state['source_intents']:
            if sha(self.read(self.path('/opt/stroyka-jev/app/'+name))) not in (self.bundle['previous'][name],self.bundle['candidate'][name]):
                raise ValueError('foreign_adapter_change_blocks_rollback')
            if sha(self.read(self.backup/name,private=True))!=self.bundle['previous'][name]:raise ValueError('source_backup_changed')
        if state['config_intent']:
            if sha(self.config_read()[0]) not in (state['config_old_sha'],state['config_new_sha']):raise ValueError('foreign_config_change_blocks_rollback')
            original=self.read(self.backup/'config.original',private=True)
            if sha(original)!=state['config_old_sha']:raise ValueError('config_backup_changed')
        if state['maintenance']:
            self.base.run('/usr/bin/systemctl','stop',*self.op.NEW,*self.op.OLD);self.base.stopped(self.op.OLD+self.op.NEW)
            self.base.stop_container(state)
            for name in reversed(state['source_intents']):
                self.op.atomic_file(self.path('/opt/stroyka-jev/app/'+name),self.read(self.backup/name,private=True),0o644,0,uid=self.uid)
            if state['config_intent']:config_write(self.path(CONFIG),original,state['config_metadata'])
            self.snapshot(self.bundle['previous']);self.base.start_container(state)
            self.base.run('/usr/bin/systemctl','start',*self.op.OLD,*self.op.NEW);self.base.healthy(self.op.OLD+self.op.NEW)
        state['phase']='rolled_back';self.save(state)
        return {'restored':True,'data_restored':False,'keys_and_receipts_retained':True,'backups_retained':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',required=True)
    parser.add_argument('--operation',choices=('apply','rollback'),required=True);args=parser.parse_args(argv)
    repair=None;lock=None;fresh=False
    try:
        if os.geteuid()!=0 or not sys.flags.isolated:raise ValueError('isolated_root_operator_required')
        namespace={'__name__':'jev_verified_activation_primitives'}
        exec(compile(download('scripts/activate_jev_commercial.py',BASE_REV,BASE_SHA),'verified-operator','exec'),namespace)
        operator=type('VerifiedOperator',(),namespace)
        bundle=operator.bootstrap(args.stage)
        from jev_agent.tender_finder.standalone_release import verify_ci
        verify_ci(PATCH_REV)
        lock=os.open('/run/stroyka-jev/operator-upgrade.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        info=os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600):raise ValueError('protected_operator_lock_required')
        operator.fcntl.flock(lock,operator.fcntl.LOCK_EX|operator.fcntl.LOCK_NB)
        patches={name:download(name,PATCH_REV,digest) for name,digest in PATCHES.items()}
        for name,raw in patches.items():compile(raw,name,'exec')
        repair=Repair(operator,bundle,patches);fresh=not repair.journal.exists()
        print(json.dumps(repair.apply() if args.operation=='apply' else repair.rollback()));return 0
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch('[a-z_]{1,100}',str(error)) else type(error).__name__
        result={'repaired':False,'code':code,'installation_ready':False,'backups_retained':True}
        if args.operation=='apply' and fresh and repair is not None and repair.journal.exists():
            try:result['rollback']=repair.rollback()
            except Exception as rollback_error:result['rollback']={'restored':False,'code':type(rollback_error).__name__}
        print(json.dumps(result));return 1
    finally:
        if lock is not None:os.close(lock)


if __name__=='__main__':raise SystemExit(main())
