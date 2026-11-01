"""Review-only v3 files from the existing verified owner; never installs anything."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from .runtime_config import parse_runtime,validate_gateway_pair
from ..settings import BridgeSettings,load_settings

SERVICE='''[Unit]
Description=JEV direct commercial host worker
Requires=docker.service stroyka-jev-commercial.socket
After=docker.service stroyka-jev-commercial.socket
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Group=root
UMask=0077
LoadCredential=admission.key:/etc/stroyka-jev-commercial/private/admission.key
ExecStart=/opt/stroyka-jev-commercial/venv/bin/python3 -I -B /opt/stroyka-jev/app/jev_agent/tender_finder/integration/host_entry.py commercial-systemd-service
Restart=on-failure
RestartSec=15
TimeoutStopSec=infinity

[Install]
WantedBy=multi-user.target
'''
SOCKET='''[Unit]
Description=JEV protected direct commercial admission socket

[Socket]
ListenStream=/run/stroyka-jev/commercial.sock
FileDescriptorName=commercial
SocketUser=root
SocketGroup=10000
SocketMode=0660
DirectoryMode=0710
Accept=no
RemoveOnStop=no
Service=stroyka-jev-commercial.service

[Install]
WantedBy=sockets.target
'''
TMPFILES='''d /run/stroyka-jev 0710 root 10000 -
d /var/lib/stroyka-jev-commercial 0700 root root -
d /var/lib/stroyka-jev-commercial/requests 0700 root root -
d /var/lib/stroyka-jev-commercial/admissions 0700 root root -
d /var/lib/stroyka-jev-commercial/private 0700 root root -
d /var/lib/stroyka-jev-commercial/results 0750 root 10000 -
d /var/lib/stroyka-jev-commercial/registry 0700 root root -
'''


def review_files(legacy):
    if (type(legacy) is not BridgeSettings or legacy.queue.writer_uid!=0
            or legacy.gateway_uid!=10000 or legacy.queue.pipeline.protocol!=2):
        raise ValueError('installed_root_broker_policy_required')
    owner=legacy.owner;owner.validate();base='/var/lib/stroyka-jev-commercial/'
    bridge={'schema_version':2,'company_id':owner.scope.company_id,
        'principal_subject':owner.scope.principal_subject,'telegram_user_id':owner.telegram_user_id,
        'reply_chat_id':owner.reply_chat_id,'hermes_profile':owner.profile,
        'writer_uid':0,'result_gid':10000,'gateway_uid':10000,
        'worker':{'inbox':base+'requests','private':base+'private','results':base+'results','admissions':base+'admissions'},
        'gateway':{'inbox':'/opt/data/jev-commercial/requests','admissions':'/opt/data/jev-commercial/admissions'}}
    host={'format':1,'protocol':3,'bridge':bridge,'registry_directory':base+'registry',
          'profile':{'legal_entity':None,'qualifications':[]},'enabled_sources':['step','federation','rtender']}
    gateway={key:host[key] for key in ('format','protocol','bridge')}
    parsed=parse_runtime(host,legacy=legacy)
    from .runtime_config import separate_bridge
    validate_gateway_pair(parsed,separate_bridge(gateway['bridge'],legacy=legacy))
    encode=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    return {'policy/runtime.json':encode(host),'policy/commercial.json':encode(gateway),
        'units/stroyka-jev-commercial.service':SERVICE,'units/stroyka-jev-commercial.socket':SOCKET,
        'units/stroyka-jev-commercial.conf':TMPFILES,'runtime/requirements.txt':'pypdf==6.18.1\n'}


def prepare(output,legacy):
    files=review_files(legacy);output=Path(output).absolute()
    if (output.parent.resolve(strict=True)!=output.parent or '..' in output.parts
            or not any(output!=root and output.is_relative_to(root) for root in (Path('/tmp'),Path('/workspace')))):
        raise ValueError('new_local_commercial_review_directory_required')
    output.mkdir(mode=0o700)
    for name,text in files.items():
        path=output/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(text)
    manifest={'kind':'COMMERCIAL_INSTALLATION_REVIEW_ONLY','installation_ready':False,'services_changed':False,
        'key_created':False,'legacy_configuration_changed':False,'additional_container_mounts':[],
        'files':[{'path':name,'sha256':hashlib.sha256(text.encode()).hexdigest()} for name,text in files.items()],
        'blocked_by':['Exact source CI and fresh server preflight','Protected host-only Python venv and sandbox dependencies',
            'Separate host-only key provisioning; never rotate/delete existing receipts automatically',
            'Reviewed activation/rollback preserving existing units, configuration, container writable layer and v2 state',
            'Real native source search and Telegram acceptance'],
        'notes':['Owner copied from existing protected policy; no company/user fallback.',
            'These files are not installed by preparation. No apply/force command is included.',
            'Do not hot-replace live Python modules; gateway restart and verified PID rebind are required.',
            'Compare shared /run/stroyka-jev ownership/mode before activation; never repair it blindly.',
            'Retain one protected signing key across restarts; key and private executor profile stay outside Hermes mounts.',
            'If gateway PID disappears the service fails closed; systemd retries bootstrap every 15s without polling procurement sites.',
            'Graceful stop drains current work. Unknown deliveries are not automatically resent.',
            'Do not use tmpfiles --remove, reset seen history or restore production data on rollback.',
            'Preserve backups/staging until actual server verification; follow repository retention policy.']}
    path=output/'REVIEW_MANIFEST.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');path.chmod(0o600)
    return {'prepared':True,'installation_ready':False,'services_changed':False,'key_created':False,'files':len(files)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-policy',required=True)
    parser.add_argument('--legacy-root',default='/etc/stroyka-jev')
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:
        legacy=load_settings(args.legacy_policy,trusted_root=Path(args.legacy_root))
        result=prepare(args.output,legacy)
    except Exception as error:
        print(json.dumps({'prepared':False,'code':type(error).__name__,'installation_ready':False}));return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
