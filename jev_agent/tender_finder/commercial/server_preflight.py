"""Standalone read-only VM metadata probe. No package, key, env or model access.

Can run as a pinned/hash-checked script before the new package is installed.
Only explicit bridge-policy metadata is read; credentials are stat'ed, never read.
No configuration is written and no service/container/search/send is started.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys


def metadata(path):
    try:
        info=Path(path).lstat()
        return {'exists':True,'uid':info.st_uid,'gid':info.st_gid,
                'mode':format(stat.S_IMODE(info.st_mode),'04o'),'symlink':stat.S_ISLNK(info.st_mode)}
    except FileNotFoundError:return {'exists':False}
    except Exception as error:return {'metadata_error_type':type(error).__name__}


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('duplicate_field')
        result[key]=value
    return result


def policy_metadata(path,*,expected_uid=0,system_uid=0):
    """No raw JSON, principal string, additional fields or paths are returned."""
    path=Path(path)
    try:
        if path.resolve(strict=True)!=path:raise ValueError('policy_alias')
        for parent in (path.parent,*path.parent.parents):
            info=parent.stat()
            if info.st_uid not in (system_uid,expected_uid) or info.st_mode&0o022:
                if parent==Path('/tmp') and info.st_uid in (system_uid,expected_uid) and info.st_mode&0o1000:continue
                raise ValueError('unsafe_policy_parent')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=expected_uid or info.st_nlink!=1
                    or stat.S_IMODE(info.st_mode) not in (0o600,0o640) or info.st_size>8192):
                raise ValueError('unsafe_policy_file')
            raw=os.read(fd,8193)
        finally:os.close(fd)
        if len(raw)>8192:raise ValueError('policy_size')
        def constant(_):raise ValueError('nonfinite')
        value=json.loads(raw,object_pairs_hook=_pairs,parse_constant=constant)
        keys={'schema_version','company_id','principal_subject','telegram_user_id','reply_chat_id',
              'hermes_profile','writer_uid','result_gid','gateway_uid','worker','gateway'}
        if type(value) is not dict or set(value)!=keys:return {'recognized_v2_policy':False}
        safe=('schema_version','company_id','writer_uid','result_gid','gateway_uid')
        if any(type(value[key]) is not int for key in safe):raise ValueError('policy_metadata_types')
        for key in ('telegram_user_id','reply_chat_id'):
            if type(value[key]) is not str or not value[key].isdecimal() or not 1<=len(value[key])<=19:
                raise ValueError('policy_route_types')
        return {'recognized_v2_policy':value['schema_version']==2,
                **{key:value[key] for key in (*safe,'telegram_user_id','reply_chat_id')},
                'default_profile':value['hermes_profile'] is None}
    except Exception as error:return {'read_error_type':type(error).__name__}


def command(args):
    environment=dict(os.environ)
    for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):
        environment.pop(key,None)
    try:
        result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15,env=environment)
        if result.returncode!=0 or len(result.stdout)>65536:return None
        return result.stdout.decode('utf-8')
    except Exception:return None


def collect(*,_run=command):
    report={'read_only':True,'services_changed':False,'configuration_changed':False,'signing_key_read':False,
        'application_secrets_read':False,'search_executed':False,'model_called':False,'notifications_sent':False,
        'installation_ready':False,'diagnostic_version':1,'hostname':socket.gethostname(),'uid':os.geteuid()}
    if os.geteuid()!=0:return {**report,'code':'root_metadata_access_required'}
    report['target_host_matches']=report['hostname'].split('.')[0]=='stroyka-dev-agent'
    report['legacy_policy']=policy_metadata(Path('/etc/stroyka-jev/bridge.json'))
    units={}
    for unit in ('stroyka-jev.service','stroyka-jev.socket','stroyka-jev-commercial.service','stroyka-jev-commercial.socket'):
        raw=_run(['/usr/bin/systemctl','show',unit,'--property=LoadState,ActiveState,SubState,UnitFileState','--no-pager'])
        units[unit]={'metadata_available':False} if raw is None else dict(
            line.split('=',1) for line in raw.splitlines() if '=' in line and line.split('=',1)[0] in (
                'LoadState','ActiveState','SubState','UnitFileState'))
    report['units']=units
    template='{"running":{{json .State.Running}},"image":{{json .Image}},"privileged":{{json .HostConfig.Privileged}}}'
    raw=_run(['/usr/bin/docker','--host=unix:///var/run/docker.sock','inspect','--format',template,'hermes-telegram'])
    try:
        value=json.loads(raw) if raw is not None else None
        report['container']={key:value[key] for key in ('running','image','privileged')} if type(value) is dict else {'metadata_available':False}
    except Exception:report['container']={'metadata_available':False}
    raw=_run(['/usr/bin/docker','--host=unix:///var/run/docker.sock','top','hermes-telegram','-eo','pid,euid,egid,comm'])
    actors=[]
    for line in (raw or '').splitlines()[1:]:
        fields=line.split()
        if len(fields)==4 and fields[3]=='hermes' and all(value.isdecimal() for value in fields[:3]):
            actors.append({'pid':int(fields[0]),'uid':int(fields[1]),'gid':int(fields[2])})
    report['hermes_actors']=actors
    report['paths']={path:metadata(path) for path in (
        '/run/stroyka-jev','/run/stroyka-jev/admission.sock','/run/stroyka-jev/commercial.sock',
        '/etc/stroyka-jev/private/admission.key','/etc/stroyka-jev-commercial',
        '/etc/stroyka-jev-commercial/private/admission.key','/var/lib/stroyka-jev-commercial',
        '/opt/stroyka-jev-commercial/venv','/opt/stroyka-jev/config/commercial.json')}
    report['bwrap_present']=shutil.which('bwrap') is not None
    report['free_bytes']=shutil.disk_usage('/var/lib').free
    report['runtime_probe_executed']=False
    return report


def main():
    if sys.argv[1:]:
        print(json.dumps({'read_only':True,'code':'no_diagnostic_arguments','installation_ready':False}));return 2
    print(json.dumps(collect(),ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
