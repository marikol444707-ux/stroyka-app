"""Explicit host-to-Hermes completion transport; no daemon or installation.

Only the root host completion consumer may call this. No signing key, private
journal, Docker socket, shell or arbitrary command is exposed to the model.
Deployment still needs acceptance of the real Python/venv and container policy.
Killing docker exec may leave its remote send running: ledger outcome must remain
unknown and must NEVER cause an automatic retry.
"""
import json
import os
import re

from .cli_result import _pairs, _nonfinite
from .ingress import OwnerBinding, owner_route
from .invoker import _run_bounded
from .notification import deliver_completion
from .settings import BridgeSettings

IMAGE = 'sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d'
DOCKER = '/usr/bin/docker'
CONTAINER = 'hermes-telegram'
INSPECT_TEMPLATE='{"id":{{json .Id}},"image":{{json .Image}},"running":{{json .State.Running}},"privileged":{{json .HostConfig.Privileged}},"mounts":{{json .Mounts}},"cap_add":{{json .HostConfig.CapAdd}},"pid_mode":{{json .HostConfig.PidMode}},"security_opt":{{json .HostConfig.SecurityOpt}},"devices":{{json .HostConfig.Devices}}}'

# Fixed program, passed as argv code rather than importing JEV from a writable
# shared volume. Request/message/recipient are stdin data, never executable code.
# -I ignores PYTHONPATH/user site; only the reviewed root-owned source is added.
REMOTE_PROGRAM = r'''
import contextlib, hashlib, importlib, io, json, os, re, stat, sys

def _pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise ValueError('duplicate_field')
        result[key] = value
    return result

def _decode(raw):
    def constant(value): raise ValueError('nonfinite')
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=constant)

def _frame(raw):
    if type(raw) is not bytes or len(raw)>32768: raise ValueError('frame_limit')
    args = _decode(raw.decode('utf-8'))
    if (type(args) is not dict or set(args)!={'action','target','message'}
            or args['action']!='send' or type(args['target']) is not str
            or not re.fullmatch(r'telegram:[1-9][0-9]{0,18}',args['target'])
            or type(args['message']) is not str): raise ValueError('fixed_send_frame_required')
    message = args['message']
    prefix = '<b>JEV</b>\n'
    if (not message.startswith(prefix) or len(message.encode('utf-16-le'))//2>3800
            or any(char in message[len(prefix):] for char in '<>:[]')
            or 'MEDIA:' in message or '[[as_document]]' in message):
        raise ValueError('escaped_jev_text_required')
    return args

def _load_sender():
    if os.geteuid()!=10000 or os.getegid()!=10000:
        raise ValueError('observed_unprivileged_identity_required')
    descriptors = []
    try:
        parent = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
        descriptors.append(parent)
        for part in ('opt','hermes','tools'):
            parent = os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            descriptors.append(parent)
            info = os.fstat(parent)
            if info.st_uid!=0 or info.st_mode & 0o022: raise ValueError('protected_source_required')
        fd = os.open('send_message_tool.py',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        descriptors.append(fd)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022
                or info.st_size>262144): raise ValueError('protected_sender_required')
        with os.fdopen(fd,'rb',closefd=False) as stream: raw=stream.read(262145)
        if hashlib.sha256(raw).hexdigest()!='65058bf22cf614c4e954131d81e5655b8016dfc8c87e74b9ed6582c733f02227':
            raise ValueError('reviewed_sender_required')
    finally:
        for fd in reversed(descriptors): os.close(fd)
    sys.path.insert(0,'/opt/hermes')
    module = importlib.import_module('tools.send_message_tool')
    if module.__file__!='/opt/hermes/tools/send_message_tool.py':
        raise ValueError('reviewed_sender_origin_required')
    return module.send_message_tool

def main():
    result = {'success':False,'code':'hermes_delivery_failed'}
    try:
        args = _frame(sys.stdin.buffer.read(32769))
        # Never return plugin/config/provider logs or raw sender errors to host.
        with open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink):
            response = _load_sender()(args)
        if type(response) is not str or len(response.encode('utf-8'))>32768:
            raise ValueError('bounded_sender_ack_required')
        ack = _decode(response)
        if (type(ack) is not dict or ack.get('success') is not True
                or ack.get('partial_success') or ack.get('error') or ack.get('warnings')
                or ack.get('platform')!='telegram'
                or str(ack.get('chat_id'))!=args['target'].split(':')[1]
                or type(ack.get('message_id')) not in (str,int)
                or not re.fullmatch('[1-9][0-9]{0,29}',str(ack['message_id']))):
            raise ValueError('explicit_target_ack_required')
        result = {'success':True,'platform':'telegram','chat_id':str(ack['chat_id']),
                  'message_id':str(ack['message_id'])}
    except Exception:
        pass
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__=='__main__': sys.exit(main())
'''


def _container_id(raw,*,require_jev_mounts=False):
    if type(raw) is not bytes or len(raw)>32768:
        raise ValueError('bounded_container_metadata_required')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_nonfinite)
    if (type(value) is not dict or set(value)!={'id','image','running','privileged','mounts','cap_add','pid_mode','security_opt','devices'}
            or type(value['id']) is not str or not re.fullmatch('[a-f0-9]{64}',value['id'])
            or value['image']!=IMAGE or value['running'] is not True or value['privileged'] is not False):
        raise ValueError('reviewed_running_container_required')
    if (value['cap_add'] not in (None,[]) or value['pid_mode']!=''
            or value['devices'] not in (None,[]) or value['security_opt'] not in (
                None,[],['no-new-privileges'],['no-new-privileges:true'])):
        raise ValueError('private_unprivileged_container_policy_required')
    mounts=value['mounts']
    allowed={('/root/hermes-data','/opt/data',True),
             ('/run/stroyka-jev','/run/stroyka-jev',False),
             ('/opt/stroyka-jev','/opt/stroyka-jev',False),
             ('/opt/stroyka-jev/app/jev_agent/tender_finder/integration/hermes_jev_tool.py',
              '/opt/hermes/tools/jev_tender_tool.py',False)}
    seen=set()
    if type(mounts) is not list or not 1<=len(mounts)<=4:
        raise ValueError('reviewed_data_mount_only_required')
    for mount in mounts:
        if type(mount) is not dict or mount.get('Type')!='bind' or type(mount.get('RW')) is not bool:
            raise ValueError('reviewed_data_mount_only_required')
        identity=(mount.get('Source'),mount.get('Destination'),mount['RW'])
        if identity not in allowed or identity in seen:raise ValueError('reviewed_data_mount_only_required')
        seen.add(identity)
    if ('/root/hermes-data','/opt/data',True) not in seen:
        raise ValueError('reviewed_data_mount_only_required')
    if require_jev_mounts and seen!=allowed:
        raise ValueError('complete_readonly_jev_mounts_required')
    return value['id']


def check_hermes_container(*,_run=_run_bounded,require_jev_mounts=False):
    """Fresh policy gate usable BEFORE any privileged signing key is loaded."""
    raw,code=_run((DOCKER,'inspect','--format',INSPECT_TEMPLATE,CONTAINER),None,10)
    if code!=0:raise ValueError('container_inspection_failed')
    return _container_id(raw,require_jev_mounts=require_jev_mounts)


class DockerHermesSender:
    """Construct only in trusted host bootstrap from explicit protected policy.

    First integration supports the observed UID/GID10000/default profile only;
    named profiles and other images/identities fail closed, without a fallback.
    _run is private test injection, never a model or operator command argument.
    """
    def __init__(self, owner, *, gateway_uid, gateway_gid, _run=_run_bounded):
        if type(owner) is not OwnerBinding:
            raise ValueError('protected_owner_required')
        owner.validate()
        if (owner.profile is not None or type(gateway_uid) is not int or gateway_uid!=10000
                or type(gateway_gid) is not int or gateway_gid!=10000 or not callable(_run)):
            raise ValueError('observed_hermes_identity_required')
        self._target='telegram:'+owner.reply_chat_id
        self._run=_run

    def __call__(self, args):
        if os.geteuid()!=0:raise ValueError('host_root_completion_consumer_required')
        if (type(args) is not dict or set(args)!={'action','target','message'}
                or args['action']!='send' or args['target']!=self._target
                or type(args['message']) is not str or len(args['message'])>16384):
            raise ValueError('protected_completion_target_required')
        wire=json.dumps(args,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(wire)>32768:raise ValueError('bounded_completion_required')
        identifier=check_hermes_container(_run=self._run)
        # Execute by immutable container ID: name replacement cannot redirect it.
        argv=(DOCKER,'exec','--interactive','--user','10000:10000','--workdir','/opt/hermes',
              '--env','HOME=/opt/data','--env','HERMES_HOME=/opt/data','--env','HERMES_PROFILE=',
              identifier,'/opt/hermes/.venv/bin/python','-I','-B','-c',REMOTE_PROGRAM)
        raw,code=self._run(argv,wire,75)
        if code!=0 or type(raw) is not bytes or len(raw)>32768:
            raise ValueError('hermes_delivery_not_acknowledged')
        return raw.decode('utf-8')


def deliver_via_hermes(settings,event_id,request_id,fingerprint,*,gateway_gid):
    """Explicit root host completion entrypoint; no search or automatic retry."""
    if type(settings) is not BridgeSettings:raise ValueError('protected_bridge_settings_required')
    uid=settings.gateway_uid if settings.gateway_uid is not None else settings.queue.writer_uid
    sender=DockerHermesSender(settings.owner,gateway_uid=uid,gateway_gid=gateway_gid)
    return deliver_completion(settings.queue.pipeline.private_directory,settings.owner.scope,event_id,
        request_id,fingerprint,route=owner_route((settings.owner,),settings.owner.scope),send=sender)
