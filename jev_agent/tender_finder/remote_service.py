"""Explicit, root-only service roles for a split Hermes gateway and JEV worker.

SSH authorization must use restrict, from= and the fixed receive/send command.
No model receives a key, SSH command, socket or deployment control.
"""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import threading

from .admission_broker import process_start_ticks
from .bootstrap_key import read_bootstrap_key
from .contract import validate_v2_request
from .discovery import verify_installed_runtime
from .docker_delivery import DockerHermesSender
from .host_worker import run_host_pass
from .invoker import _run_bounded
from .remote_transport import (RelayBroker, MAX_TRANSPORT, _keys, _protocol, decode_frame,
    exchange, receive_frame, send_remote_completion)
from .state import _json
from .systemd_bootstrap import (credential_pipe, discover_gateway_peer, inherited_listener,
                               runtime_settings, validate_state_directories)

ROLE=Path('/etc/stroyka-jev-remote/role.json')


def protected_json(path,*,uid=0):
    path=Path(path)
    if path.resolve(strict=True)!=path:raise ValueError('protected_role_path_required')
    for parent in path.parents:
        info=parent.stat()
        if info.st_uid!=uid or info.st_mode&0o022:raise ValueError('protected_role_parent_required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>4096):
            raise ValueError('protected_role_file_required')
        return decode_frame(os.read(fd,4097))
    finally:os.close(fd)


def require_role(expected,*,ssh=False):
    if os.geteuid()!=0 or not sys.flags.isolated:raise ValueError('isolated_root_transport_required')
    value=protected_json(ROLE)
    _keys(value,('role','peer_ip','enabled'))
    if value['role']!=expected or value['enabled'] is not True:
        raise ValueError('explicit_enabled_transport_role_required')
    import ipaddress
    peer=str(ipaddress.ip_address(value['peer_ip']))
    if ssh:
        connection=os.environ.get('SSH_CONNECTION','').split()
        if len(connection)!=4 or connection[0]!=peer or os.environ.get('SSH_ORIGINAL_COMMAND',''):
            raise ValueError('fixed_forced_command_peer_required')
    return value


def policy(protocol):
    _protocol(protocol)
    if protocol==2:
        settings=runtime_settings();validate_state_directories(settings)
        return settings,validate_v2_request,None
    from .commercial.systemd_bootstrap import runtime_policy,validate_state
    from .commercial.contract import validate_request
    value=runtime_policy();validate_state(value)
    return value.bridge,validate_request,value


def load(protocol):
    settings,validator,_=policy(protocol)
    key=Path('/etc/stroyka-jev/private/admission.key' if protocol==2 else
             '/etc/stroyka-jev-commercial/private/admission.key')
    secret=read_bootstrap_key(credential_pipe(_path=key))
    return settings,secret,validator


def _signals(stop):
    for number in (signal.SIGTERM,signal.SIGINT):
        signal.signal(number,lambda signum,frame:stop.set())


def relay(protocol):
    require_role('gateway')
    settings,_,_=policy(protocol)
    peer=discover_gateway_peer()
    if peer.uid!=settings.gateway_uid or peer.gid!=10000:raise ValueError('gateway_identity_mismatch')
    path='/run/stroyka-jev/admission.sock' if protocol==2 else '/run/stroyka-jev/commercial.sock'
    listener=inherited_listener(os.environ,listener_name='admission' if protocol==2 else 'commercial',listener_path=path)
    stop=threading.Event();_signals(stop)
    broker=RelayBroker(peer,protocol,lambda frame:exchange('main',frame))
    try:
        listener.settimeout(1)
        print(json.dumps({'relay_ready':True,'protocol':protocol,'local_search_enabled':False}),flush=True)
        while not stop.is_set():
            if process_start_ticks(peer.pid)!=peer.start_ticks:raise ValueError('gateway_rebind_required')
            try:connection,_=listener.accept()
            except socket.timeout:continue
            with connection:broker.serve_connection(connection)
    finally:listener.close()


@contextmanager
def exclusive_worker(settings):
    path=settings.queue.pipeline.private_directory/'.remote-worker.lock'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:
            raise ValueError('protected_worker_lock_required')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def worker(protocol):
    require_role('main')
    settings,secret,_=load(protocol)
    verify_installed_runtime()
    bridge=None
    if protocol==3:
        from .commercial.systemd_bootstrap import verify_document_runtime
        from .commercial.runtime_config import build_bridge
        from datetime import datetime,timezone
        verify_document_runtime()
        bridge=build_bridge(policy(3)[2],secret,clock=lambda:datetime.now(timezone.utc))
    stop=threading.Event();_signals(stop)
    with exclusive_worker(settings):
        print(json.dumps({'worker_ready':True,'protocol':protocol,'local_telegram_polling':False}),flush=True)
        while not stop.is_set():
            result=run_host_pass(settings,secret,gateway_gid=10000,deliver=send_remote_completion,
                                 should_stop=stop.is_set,commercial_bridge=bridge)
            if any(result[k] for k in ('processed','acknowledged','unknown','errors','authorization_pending')):
                print(json.dumps({'host_pass':result,'protocol':protocol}),flush=True)
            stop.wait(10 if result['errors'] else 2)


def cli_arguments(frame):
    _keys(frame,('op','argv','stdin_b64'))
    if frame['op']!='cli' or type(frame['argv']) is not list or not 1<=len(frame['argv'])<=8:
        raise ValueError('fixed_cli_frame_required')
    argv=frame['argv']
    if any(type(x) is not str or not x or len(x)>2048 or any(ord(c)<32 for c in x) for x in argv):
        raise ValueError('bounded_cli_arguments_required')
    parser=argparse.ArgumentParser(add_help=False,exit_on_error=False)
    parser.add_argument('operation',choices=['status','demo','avito','eis','eis-search','eis-review','commercial-search'])
    parser.add_argument('--query');parser.add_argument('--notice')
    parser.add_argument('--profile-stdin',action='store_true');parser.add_argument('--stavropol-open',action='store_true')
    try:args=parser.parse_args(argv)
    except (argparse.ArgumentError,SystemExit):raise ValueError('reviewed_cli_arguments_required') from None
    if ((args.profile_stdin and args.operation!='commercial-search')
            or (args.stavropol_open and args.operation!='eis-search')
            or (args.notice and args.operation!='eis-review')
            or (args.operation=='eis-review' and not args.notice)
            or (args.operation=='commercial-search' and args.query)):
        raise ValueError('cli_option_scope_mismatch')
    if type(frame['stdin_b64']) is not str or len(frame['stdin_b64'])>43692:raise ValueError('bounded_cli_stdin_required')
    stdin=base64.b64decode(frame['stdin_b64'],validate=True)
    if len(stdin)>32768 or bool(stdin)!=args.profile_stdin:raise ValueError('profile_stdin_scope_mismatch')
    return ['/usr/local/bin/stroyka-jev',*argv],stdin or None


def execute_cli(frame):
    argv,stdin=cli_arguments(frame)
    if stdin:
        from jev_agent.server_runtime.scripts.jev_commercial_search import normalize_company_profile
        profile=normalize_company_profile(decode_frame(stdin))
        if profile['companyId']!=policy(2)[0].owner.scope.company_id:raise ValueError('profile_company_mismatch')
    verify_installed_runtime()
    raw,code=_run_bounded(argv,stdin,360,maximum_bytes=2*1024*1024)
    if len(raw)>2*1024*1024:raise ValueError('bounded_cli_result_required')
    return {'output_b64':base64.b64encode(raw).decode('ascii'),'exit_code':code}


def execute_control(frame):
    _keys(frame,('op','request'));request=frame['request']
    if type(request) is not dict or request.get('operation') not in ('health','demo','avito'):
        raise ValueError('fixed_control_operation_required')
    _keys(request,('operation','query') if request['operation']=='avito' else ('operation',))
    if request['operation']=='avito':
        from .remote_transport import _query
        _query(request['query'])
    raw,code=_run_bounded(('/usr/bin/python3','-B','/usr/local/libexec/stroyka-jev-control/jev_control.py','--server'),_json(request),125)
    if code not in (0,1):raise ValueError('controller_unavailable')
    return decode_frame(raw)


def receive():
    require_role('main',ssh=True)
    frame=decode_frame(sys.stdin.buffer.read(MAX_TRANSPORT+1))
    if frame.get('op')=='ping':
        _keys(frame,('op',));return {'ok':True,'role':'main'}
    if frame.get('op')=='cli':return execute_cli(frame)
    if frame.get('op')=='control':return execute_control(frame)
    return receive_frame(frame,load=load)


def send():
    require_role('gateway',ssh=True)
    frame=decode_frame(sys.stdin.buffer.read(MAX_TRANSPORT+1))
    if frame.get('op')=='ping':
        _keys(frame,('op',));discover_gateway_peer();return {'ok':True,'role':'gateway'}
    _keys(frame,('op','protocol','args'))
    if frame['op']!='send':raise ValueError('completion_operation_required')
    settings,_,_=policy(_protocol(frame['protocol']))
    sender=DockerHermesSender(settings.owner,gateway_uid=settings.gateway_uid,gateway_gid=10000)
    return {'sender_result':sender(frame['args'])}


def cli_proxy(argv):
    require_role('gateway')
    data=sys.stdin.buffer.read(32769) if '--profile-stdin' in argv else b''
    frame={'op':'cli','argv':argv,'stdin_b64':base64.b64encode(data).decode('ascii')}
    cli_arguments(frame)
    result=exchange('main',frame,timeout=380)
    _keys(result,('output_b64','exit_code'))
    raw=base64.b64decode(result['output_b64'],validate=True)
    if len(raw)>2*1024*1024 or type(result['exit_code']) is not int:raise ValueError('bounded_cli_response_required')
    sys.stdout.buffer.write(raw);return result['exit_code']


def control_proxy(argv):
    require_role('gateway')
    if argv!=['--server']:raise ValueError('explicit_control_proxy_required')
    request=decode_frame(sys.stdin.buffer.read(8193))
    return exchange('main',{'op':'control','request':request},timeout=135)


def main(argv):
    try:
        if not argv:raise ValueError('explicit_remote_operation_required')
        mode=argv[0]
        if mode in ('relay','worker') and len(argv)==2:
            protocol=_protocol(int(argv[1]));(relay if mode=='relay' else worker)(protocol);return 0
        if mode=='receive' and len(argv)==1:result=receive()
        elif mode=='send' and len(argv)==1:result=send()
        elif mode=='cli':return cli_proxy(argv[1:])
        elif mode=='control':result=control_proxy(argv[1:])
        else:raise ValueError('fixed_remote_operation_required')
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:
        # Secrets, provider errors, origin identifiers and message text stay out.
        print(json.dumps({'ok':False,'code':'remote_operation_failed','error_type':type(error).__name__}));return 1
