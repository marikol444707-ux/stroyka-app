"""Explicit socket-activated root broker entrypoint; no automatic installation.

The privileged launcher supplies a listening Unix FD, an anonymous key pipe and
the verified gateway PID/start time. It must not select an arbitrary same-UID
process or trust a PID delivered in a client JSON message.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import stat
import threading

from .admission_broker import GatewayPeer,initialize_root_broker
from .admission_broker import process_start_ticks
from .audit_bridge import process_startup_sources
from .docker_delivery import DOCKER,check_hermes_container
from .hermes_binding import REVIEWED_MODULES
from .invoker import _run_bounded
from .settings import load_settings


class BrokerParser(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'invalid broker arguments\n')


def validate_listener(listener,gateway_gid,*,_path=Path('/run/stroyka-jev/admission.sock'),
                      _uid=0,_trusted_directory=Path('/')):
    """Kernel/listener/path gate. Private parameters support isolated fixtures."""
    if (listener.family!=socket.AF_UNIX or listener.type!=socket.SOCK_STREAM
            or listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)!=1
            or listener.getsockname()!=str(_path)):
        raise ValueError('protected_unix_listener_required')
    path=Path(_path).absolute();root=Path(_trusted_directory).absolute()
    if (path.resolve(strict=True)!=path or root.resolve(strict=True)!=root
            or path==root or not path.is_relative_to(root)):
        raise ValueError('protected_socket_path_required')
    info=path.lstat();parent=path.parent.stat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid!=_uid or info.st_gid!=gateway_gid
            or stat.S_IMODE(info.st_mode)!=0o660 or parent.st_uid!=_uid
            or parent.st_gid!=gateway_gid or stat.S_IMODE(parent.st_mode)!=0o710):
        raise ValueError('protected_socket_permissions_required')
    for directory in (path.parent,*path.parent.parents):
        info=directory.stat()
        if info.st_uid not in (0,_uid) or info.st_mode & 0o022:
            raise ValueError('protected_socket_parent_required')
        if directory==root:break


def serve(listener,broker,stop):
    """Idle accept loop only. No model/search/timer or notification is invoked."""
    listener.settimeout(1)
    while not stop.is_set():
        try:connection,_=listener.accept()
        except socket.timeout:continue
        with connection:broker.serve_connection(connection)


def validate_gateway_peer(peer,*,_run=_run_bounded):
    """Verify pinned PID is the unique observed Hermes actor, not another shell.

    Docker metadata/top and fixed public source hashes only; no exec, environment
    dump, key, configuration values, model call or search.
    """
    peer.validate()
    identifier=check_hermes_container(_run=_run)
    raw,code=_run((DOCKER,'top',identifier,'-eo','pid,euid,egid,comm'),None,10)
    if code!=0 or type(raw) is not bytes or len(raw)>32768:raise ValueError('gateway_process_inventory_required')
    candidates=[]
    for line in raw.decode('utf-8').splitlines()[1:]:
        fields=line.split()
        if (len(fields)==4 and all(value.isdecimal() for value in fields[:3])
                and fields[3]=='hermes' and int(fields[1])==peer.uid):
            candidates.append(tuple(map(int,fields[:3])))
    if candidates!=[(peer.pid,peer.uid,peer.gid)]:raise ValueError('unique_verified_gateway_process_required')
    inventory=process_startup_sources(peer.pid)
    modules={row['module']:row for row in inventory.get('gateway_modules',[])}
    for name,digest in REVIEWED_MODULES.items():
        row=modules.get(name.replace('.','/')+'.py')
        if row is None or row.get('sha256')!=digest:raise ValueError('reviewed_gateway_sources_required')
        if any(info.get('uid')!=0 or int(info.get('mode','0'),8)&0o022
               for info in (row,*row.get('directory_permissions',[]))):
            raise ValueError('protected_gateway_sources_required')
    if process_start_ticks(peer.pid)!=peer.start_ticks:raise ValueError('gateway_process_changed')


def _main(argv,initialize,run_loop):
    parser=BrokerParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--key-fd',type=int,required=True)
    parser.add_argument('--listener-fd',type=int,required=True)
    parser.add_argument('--gateway-pid',type=int,required=True)
    parser.add_argument('--gateway-start-ticks',type=int,required=True)
    parser.add_argument('--gateway-gid',type=int,required=True)
    args=parser.parse_args(argv)
    listener=None;key_owned=True;handlers={}
    try:
        if (args.key_fd<3 or args.listener_fd<3 or args.key_fd==args.listener_fd
                or os.geteuid()!=0):raise ValueError('privileged_separate_descriptors_required')
        settings=load_settings(args.config)
        if settings.queue.writer_uid!=0 or settings.gateway_uid is None:
            raise ValueError('root_broker_settings_v2_required')
        peer=GatewayPeer(args.gateway_pid,settings.gateway_uid,args.gateway_gid,args.gateway_start_ticks)
        peer.validate()
        validate_gateway_peer(peer)
        listener=socket.socket(fileno=args.listener_fd)
        listener.set_inheritable(False);validate_listener(listener,args.gateway_gid)
        # initialize_root_broker takes ownership and closes the key FD even if
        # later validation fails. The caller never receives a signing object.
        key_owned=False
        broker=initialize(args.config,args.key_fd,peer)
        stop=threading.Event()
        for number in (signal.SIGTERM,signal.SIGINT):
            handlers[number]=signal.signal(number,lambda signum,frame:stop.set())
        print(json.dumps({'broker_listening':True,'search_executed':False,'installation_ready':False}),flush=True)
        run_loop(listener,broker,stop)
        return 0
    except Exception as error:
        print(json.dumps({'broker_listening':False,'code':type(error).__name__,'installation_ready':False}))
        return 1
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)
        if listener is not None:listener.close()
        if key_owned and args.key_fd>=3:
            try:os.close(args.key_fd)
            except OSError:pass


def main(argv=None):
    return _main(argv,initialize_root_broker,serve)


if __name__=='__main__':raise SystemExit(main())
