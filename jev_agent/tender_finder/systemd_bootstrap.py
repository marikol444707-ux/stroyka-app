"""Explicit systemd socket/credential bootstrap; no installation or key creation.

Only the root-owned isolated host_entry launcher calls main. Files, listener and
the actual gateway are checked before the credential is read. No user-supplied
key path, PID fallback, environment key or model-selected service is supported.
"""
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import threading

from .admission_broker import GatewayPeer,process_start_ticks
from .bootstrap_key import read_bootstrap_key
from .broker_service import validate_gateway_peer,validate_listener
from .docker_delivery import DOCKER,check_hermes_container
from .discovery import verify_installed_runtime
from .host_service import ConnectedHost
from .invoker import _run_bounded
from .settings import load_settings

HOST_POLICY=Path('/etc/stroyka-jev/bridge.json')
GATEWAY_POLICY=Path('/opt/stroyka-jev/config/bridge.json')
CREDENTIAL=Path('/run/credentials/stroyka-jev.service/admission.key')


def discover_gateway_peer(*,_run=_run_bounded):
    identifier=check_hermes_container(_run=_run,require_jev_mounts=True)
    raw,code=_run((DOCKER,'top',identifier,'-eo','pid,euid,egid,comm'),None,10)
    if code!=0 or type(raw) is not bytes or len(raw)>32768:
        raise ValueError('gateway_process_inventory_required')
    candidates=[]
    for line in raw.decode('utf-8').splitlines()[1:]:
        fields=line.split()
        if len(fields)==4 and fields[3]=='hermes':
            if not all(value.isdecimal() for value in fields[:3]):
                raise ValueError('gateway_process_inventory_required')
            candidates.append(tuple(map(int,fields[:3])))
    if len(candidates)!=1 or candidates[0][1:]!=(10000,10000):
        raise ValueError('unique_observed_gateway_required')
    pid,uid,gid=candidates[0]
    peer=GatewayPeer(pid,uid,gid,process_start_ticks(pid))
    # Reinspect membership/source permissions after obtaining start ticks. PID
    # replacement or ambiguity between the two observations fails closed.
    validate_gateway_peer(peer,_run=_run)
    return peer


def inherited_listener(environment,*,listener_name='admission',listener_path=None,_pid=None,_factory=socket.socket):
    if (environment.get('LISTEN_PID')!=str(os.getpid() if _pid is None else _pid)
            or environment.get('LISTEN_FDS')!='1'
            or listener_name not in ('admission','commercial')
            or environment.get('LISTEN_FDNAMES')!=listener_name):
        raise ValueError('single_named_systemd_listener_required')
    listener=_factory(fileno=3)
    try:
        listener.set_inheritable(False)
        if listener_path is None:validate_listener(listener,10000)
        else:validate_listener(listener,10000,_path=listener_path)
        return listener
    except BaseException:
        listener.close();raise


def credential_pipe(*,_path=CREDENTIAL,_uid=0,_trusted_root=Path('/')):
    """Transfer one bounded protected credential into a close-on-exec pipe.

    Path/UID seams exist for filesystem tests, not operator/model arguments.
    The caller must have completed source/listener/gateway/policy attestation.
    """
    path=Path(_path).absolute();root=Path(_trusted_root).absolute()
    if (path.resolve(strict=True)!=path or root.resolve(strict=True)!=root
            or path==root or not path.is_relative_to(root)):
        raise ValueError('protected_systemd_credential_required')
    for directory in (path.parent,*path.parent.parents):
        info=directory.stat()
        if info.st_uid!=_uid or info.st_mode & 0o022:
            raise ValueError('protected_credential_parent_required')
        if directory==path.parent and stat.S_IMODE(info.st_mode) not in (0o500,0o700):
            raise ValueError('private_credential_directory_required')
        if directory==root:break
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=_uid or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode) not in (0o400,0o600) or not 32<=info.st_size<=64):
            raise ValueError('bounded_private_credential_required')
        raw=os.read(fd,65)
        if len(raw)!=info.st_size:raise ValueError('credential_changed_during_read')
    finally:os.close(fd)
    reader,writer=os.pipe2(os.O_CLOEXEC)
    try:
        os.fchmod(reader,0o600)
        if os.write(writer,raw)!=len(raw):raise ValueError('credential_transfer_failed')
    except BaseException:
        os.close(reader);raise
    finally:os.close(writer)
    return reader


def runtime_settings():
    settings=load_settings(HOST_POLICY)
    gateway=load_settings(GATEWAY_POLICY,trusted_root=Path('/opt/stroyka-jev'))
    if (settings!=gateway or settings.queue.writer_uid!=0 or settings.gateway_uid!=10000
            or settings.queue.pipeline.result_gid!=10000 or settings.owner.profile is not None):
        raise ValueError('matching_reviewed_host_gateway_policies_required')
    base=Path('/var/lib/stroyka-jev/v2')
    if (settings.queue.inbox!=base/'inbox' or settings.worker_admissions!=base/'admissions'
            or settings.queue.pipeline.private_directory!=base/'private'
            or settings.queue.pipeline.result_directory!=base/'results'):
        raise ValueError('dedicated_host_only_v2_namespace_required')
    return settings


def validate_state_directories(settings):
    for path in (settings.queue.inbox,settings.worker_admissions,
                 settings.queue.pipeline.private_directory,settings.queue.pipeline.result_directory):
        if path.resolve(strict=True)!=path:raise ValueError('protected_state_directory_required')
        for directory in (path,*path.parents):
            info=directory.stat()
            if info.st_uid!=0 or info.st_mode & 0o022:
                raise ValueError('protected_state_directory_required')
        info=path.stat()
        result=path==settings.queue.pipeline.result_directory
        if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)!=(0o750 if result else 0o700)
                or result and info.st_gid!=10000):raise ValueError('protected_state_permissions_required')


def main(argv=None):
    listener=None;handlers={};stage='arguments'
    try:
        if argv is None:argv=sys.argv[1:]
        if argv or os.geteuid()!=0:raise ValueError('explicit_root_systemd_bootstrap_required')
        stage='policy';settings=runtime_settings()
        stage='state_permissions'
        validate_state_directories(settings)
        stage='installed_runtime'
        verify_installed_runtime()
        stage='inherited_listener'
        listener=inherited_listener(os.environ)
        stage='gateway_peer'
        peer=discover_gateway_peer()
        # Existing anonymous-pipe reader closes its FD on every outcome.
        stage='credential';secret=read_bootstrap_key(credential_pipe())
        stage='broker_initialization'
        host=ConnectedHost(settings,secret,peer)
        stop=threading.Event()
        for number in (signal.SIGTERM,signal.SIGINT):
            handlers[number]=signal.signal(number,lambda signum,frame:stop.set())
        print(json.dumps({'host_service_started':True,'installation_ready':False}),flush=True)
        stage='serving';host.serve(listener,stop)
        return 0
    except Exception as error:
        print(json.dumps({'host_service_started':False,'code':type(error).__name__,'stage':stage,
                          'installation_ready':False}),flush=True)
        return 1
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)
        if listener is not None:listener.close()


if __name__=='__main__':raise SystemExit(main())
