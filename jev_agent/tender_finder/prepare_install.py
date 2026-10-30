"""Prepare review files in NEW /tmp or /workspace staging, never install them.

No key, live settings, service command, Docker change or database access. Company
and owner are explicit operator input; missing identity has no fallback. The
plan deliberately remains blocked on server evidence and deployment approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from .settings import parse_settings

SERVICE='''[Unit]
Description=JEV authenticated host worker
Requires=docker.service stroyka-jev.socket
After=docker.service stroyka-jev.socket
StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
Type=simple
User=root
Group=root
UMask=0077
LoadCredential=admission.key:/etc/stroyka-jev/private/admission.key
ExecStart=/usr/bin/python3 -I -B /opt/stroyka-jev/app/jev_agent/tender_finder/integration/host_entry.py systemd-service
Restart=on-failure
RestartSec=15
TimeoutStopSec=infinity

[Install]
WantedBy=multi-user.target
'''
SOCKET='''[Unit]
Description=JEV protected admission socket

[Socket]
ListenStream=/run/stroyka-jev/admission.sock
FileDescriptorName=admission
SocketUser=root
SocketGroup=10000
SocketMode=0660
DirectoryMode=0710
Accept=no
RemoveOnStop=no
Service=stroyka-jev.service

[Install]
WantedBy=sockets.target
'''
TMPFILES='''d /run/stroyka-jev 0710 root 10000 -
d /var/lib/stroyka-jev 0700 root root -
d /var/lib/stroyka-jev/v2 0700 root root -
d /var/lib/stroyka-jev/v2/inbox 0700 root root -
d /var/lib/stroyka-jev/v2/admissions 0700 root root -
d /var/lib/stroyka-jev/v2/private 0700 root root -
d /var/lib/stroyka-jev/v2/results 0750 root 10000 -
'''
MOUNTS=[{'source':'/run/stroyka-jev','destination':'/run/stroyka-jev','read_only':True},
        {'source':'/opt/stroyka-jev','destination':'/opt/stroyka-jev','read_only':True},
        {'source':'/opt/stroyka-jev/app/jev_agent/tender_finder/integration/hermes_jev_tool.py',
         'destination':'/opt/hermes/tools/jev_tender_tool.py','read_only':True}]
PENDING=['fresh server preflight and existing service/container configuration snapshot',
         'explicit deployment/maintenance approval and assessed downtime',
         'protected admission key provisioning outside Hermes mounts',
         'merge readonly mounts into actual container configuration without replacing existing settings',
         'confirm jev toolset exposure in live default-profile gateway',
         'confirmed GitHub CI for exact source commit',
         'real source search/card evidence and Telegram acknowledgement']


def review_files(company_id,telegram_user_id):
    base='/var/lib/stroyka-jev/v2/'
    settings={'schema_version':2,'company_id':company_id,
        'principal_subject':'telegram:'+str(telegram_user_id),'telegram_user_id':telegram_user_id,
        'reply_chat_id':telegram_user_id,'hermes_profile':None,'writer_uid':0,
        'result_gid':10000,'gateway_uid':10000,
        'worker':{key:base+name for key,name in (
            ('inbox','inbox'),('admissions','admissions'),('private','private'),('results','results'))},
        # V2 publishes on the host; these legacy schema fields are not mounted
        # into Hermes and never used by BrokerGatewayRuntime.
        'gateway':{'inbox':base+'inbox','admissions':base+'admissions'}}
    parse_settings(settings)
    policy=json.dumps(settings,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    return {'policy/host-bridge.json':policy,'policy/gateway-bridge.json':policy,
        'units/stroyka-jev.service':SERVICE,'units/stroyka-jev.socket':SOCKET,
        'units/stroyka-jev.conf':TMPFILES,
        'container-mounts-to-review.json':json.dumps({'additional_mounts':MOUNTS,
            'replace_existing_container_configuration':False},indent=2)+'\n'}


def prepare(output,company_id,telegram_user_id):
    files=review_files(company_id,telegram_user_id)
    output=Path(output).absolute()
    parent=output.parent.resolve(strict=True)
    if parent!=output.parent or not any(output.is_relative_to(root) and output!=root
                                       for root in (Path('/tmp'),Path('/workspace'))):
        raise ValueError('new_local_staging_directory_required')
    # Exclusive creation: never overwrite or remove someone else's staging.
    output.mkdir(mode=0o700)
    for name,text in files.items():
        path=output/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(text)
    manifest={'kind':'INSTALLATION_REVIEW_ONLY','installation_ready':False,
        'services_changed':False,'key_created':False,'blocked_by':PENDING,
        'files':[{'path':name,'sha256':hashlib.sha256(text.encode()).hexdigest()}
                 for name,text in files.items()],
        'activation_notes':[
            'No install/apply/force command is included. Preserve live configuration before an approved change.',
            'Host policy target /etc/stroyka-jev/bridge.json root:root0600; gateway copy /opt/stroyka-jev/config/bridge.json root:10000 0640, parent0750.',
            'Code /opt/stroyka-jev/app must be root-owned source-only with no writable files or bytecode.',
            'Credential source /etc/stroyka-jev/private/admission.key is operator-provisioned root0600 in private0700 parent; not part of package.',
            'Keep the same protected key across restarts; rotation requires explicit queue/receipt review, never deleting old state.',
            'Apply reviewed tmpfiles directories before starting the socket; never use tmpfiles --remove.',
            'Service restart only recovers existing receipts; it does not schedule new paid searches.',
            'Stop drains the current job and pauses between jobs; broad queries may take a long time. No automatic forced kill.',
            'Rollback only this release code/config/units with compare-before-restore; never restore database, erase receipts or reset v1 seen state.',
            'Retain previous configuration until actual server acceptance; clean only owned staging after verification.'
        ]}
    with (output/'REVIEW_MANIFEST.json').open('x') as stream:
        json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n')
    (output/'REVIEW_MANIFEST.json').chmod(0o600)
    return {'prepared':True,'installation_ready':False,'services_changed':False,'key_created':False}


class Parser(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'invalid preparation arguments\n')


def main(argv=None):
    parser=Parser(description=__doc__)
    parser.add_argument('--company-id',type=int,required=True)
    parser.add_argument('--telegram-user-id',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:result=prepare(args.output,args.company_id,args.telegram_user_id)
    except Exception as error:
        print(json.dumps({'prepared':False,'code':type(error).__name__,'installation_ready':False}));return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
