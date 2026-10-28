"""Key-free Hermes ingress; signing/publication stay in a separate host process.

No automatic listener, daemon, service installation or process registration.
The privileged startup must pin the actual verified gateway PID + start time.
SO_PEERCRED is checked before reading input: another process with the SAME UID
does not gain admission. This trusts the gateway's Python code and authorization
callback, not arbitrary in-process plugins. Real startup policy remains a gate.
"""
import base64
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import socket
import stat
import struct
import time
from types import SimpleNamespace

from .admission_files import publish_admission
from .bootstrap_key import AdmissionSecret, read_bootstrap_key
from .contract import MAX_REQUEST_BYTES
from .ingress import OwnerBinding, authorized_owner, issue_admission
from .queue import _decode
from .settings import BridgeSettings, load_settings
from .state import _json

MAX_FRAME=49152
ORIGIN_FIELDS={'platform','chat_type','chat_id','user_id','profile'}


def process_start_ticks(pid):
    """Read only public stat metadata; never cmdline, environ or memory."""
    if type(pid) is not int or pid<=0:raise ValueError('pinned_gateway_pid_required')
    with open(f'/proc/{pid}/stat','rb') as stream:raw=stream.read(8193)
    if len(raw)>8192:raise ValueError('process_stat_limit')
    fields=raw.rsplit(b')',1)[1].split()
    ticks=int(fields[19])  # field 22; comm (field 2) can contain spaces/parentheses.
    if ticks<=0:raise ValueError('process_start_required')
    return ticks


@dataclass(frozen=True)
class GatewayPeer:
    pid: int
    uid: int
    gid: int
    start_ticks: int

    def validate(self):
        if (any(type(value) is not int for value in (self.pid,self.uid,self.gid,self.start_ticks))
                or self.pid<=0 or self.uid<=0 or self.gid<=0 or self.start_ticks<=0):
            raise ValueError('explicit_unprivileged_gateway_process_required')

    def permits(self,connection):
        self.validate()
        if connection.family!=socket.AF_UNIX:return False
        pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if (pid,uid,gid)!=(self.pid,self.uid,self.gid):return False
        try:return process_start_ticks(pid)==self.start_ticks
        except (OSError,ValueError,IndexError):return False


def _read_frame(connection,maximum):
    deadline=time.monotonic()+3
    chunks=[];size=0
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('broker_deadline')
        connection.settimeout(remaining)
        chunk=connection.recv(min(8192,maximum+1-size))
        if not chunk:return b''.join(chunks)
        chunks.append(chunk);size+=len(chunk)
        if size>maximum:raise ValueError('broker_frame_limit')


class AdmissionBroker:
    """Protected host core. Only initialize_root_broker is a production bootstrap.

    Test fixtures can run the core as their own UID; production settings v2
    require root-owned queues and a DIFFERENT, unprivileged gateway UID. The key
    and signatures never enter the client process or its response.
    """
    def __init__(self,settings,secret,peer,*,clock=lambda:int(time.time())):
        if (type(settings) is not BridgeSettings or type(secret) is not AdmissionSecret
                or type(peer) is not GatewayPeer or not callable(clock)):
            raise ValueError('protected_broker_bootstrap_required')
        peer.validate()
        if settings.queue.writer_uid!=os.geteuid() or settings.gateway_uid!=peer.uid:
            raise ValueError('broker_queue_and_gateway_identity_mismatch')
        settings.owner.validate()
        # Use the host view, never /opt/data mappings from the gateway.
        self._settings=replace(settings,gateway_inbox=settings.queue.inbox,
                               gateway_admissions=settings.worker_admissions)
        self._secret=secret;self._peer=peer;self._clock=clock

    def _admit(self,wire):
        value=_decode(wire)
        if (set(value)!={'version','request_b64','origin'} or type(value['version']) is not int
                or value['version']!=1 or type(value['request_b64']) is not str
                or len(value['request_b64'])>43692 or type(value['origin']) is not dict
                or set(value['origin'])!=ORIGIN_FIELDS):
            raise ValueError('fixed_broker_frame_required')
        raw=base64.b64decode(value['request_b64'],validate=True)
        if len(raw)>MAX_REQUEST_BYTES:raise ValueError('request_limit')
        origin=value['origin']
        if (origin['platform']!='telegram' or origin['chat_type']!='dm'
                or any(type(origin[name]) is not str for name in ('chat_id','user_id'))
                or origin['profile'] is not None and type(origin['profile']) is not str):
            raise ValueError('private_gateway_origin_required')
        source=SimpleNamespace(**origin,is_bot=False,thread_id=None,profile_route_rejected=False)
        # Peer process is the trust boundary, NOT the JSON source alone. The
        # client binding first uses real SessionSource + live Hermes policy.
        receipt=issue_admission(raw,source,authorize_source=lambda source:True,
            bindings=(self._settings.owner,),signing_key=self._secret.material,clock=self._clock)
        return publish_admission(raw,receipt,self._settings,self._secret,clock=self._clock)

    def serve_connection(self,connection):
        """One accepted Unix connection; caller owns listener lifecycle."""
        outcome={'queued':False,'reason':'broker_admission_failed'}
        try:
            if not self._peer.permits(connection):raise ValueError('gateway_peer_required')
            wire=_read_frame(connection,MAX_FRAME)
            if not self._peer.permits(connection):raise ValueError('gateway_peer_changed')
            outcome=self._admit(wire)
        except Exception:
            pass  # No key/config/exception/request text in response or logs.
        try:
            connection.settimeout(3);connection.sendall(_json(outcome))
            connection.shutdown(socket.SHUT_WR)
        except OSError:pass  # Publication may already be durable; retry same ID only.


def initialize_root_broker(settings_path,key_fd,peer):
    """Explicit privileged bootstrap; no key in Hermes, env, argv or shared mount."""
    if os.geteuid()!=0:
        if type(key_fd) is int and key_fd>=3:
            try:os.close(key_fd)
            except OSError:pass
        raise ValueError('root_broker_bootstrap_required')
    secret=read_bootstrap_key(key_fd)
    settings=load_settings(settings_path)
    if (os.geteuid()!=0 or settings.queue.writer_uid!=0 or settings.gateway_uid is None
            or settings.gateway_uid<=0):raise ValueError('root_broker_settings_v2_required')
    return AdmissionBroker(settings,secret,peer)


class BrokerClient:
    """Trusted gateway transport, never a model-visible generic socket API.

    A protected root-owned socket directory and kernel server UID are mandatory.
    expected_server_uid is a bootstrap parameter solely for isolated fixtures.
    """
    def __init__(self,path,*,expected_server_uid=0,_trusted_directory=Path('/')):
        if type(expected_server_uid) is not int or expected_server_uid<0:
            raise ValueError('explicit_server_identity_required')
        self._path=Path(path).absolute();self._server_uid=expected_server_uid
        self._trusted_directory=Path(_trusted_directory).absolute()
        if len(os.fsencode(self._path))>100:raise ValueError('bounded_unix_path_required')

    def submit(self,raw,source):
        path=self._path
        root=self._trusted_directory
        if (path.resolve(strict=True)!=path or root.resolve(strict=True)!=root
                or path==root or not path.is_relative_to(root)):
            raise ValueError('broker_socket_symlink')
        for directory in (path.parent,*path.parent.parents):
            info=directory.stat()
            if info.st_uid not in (0,self._server_uid) or info.st_mode & 0o022:
                raise ValueError('protected_broker_directory_required')
            if directory==root:break
        info=path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=self._server_uid or info.st_mode & 0o007:
            raise ValueError('protected_broker_socket_required')
        if type(raw) is not bytes or len(raw)>MAX_REQUEST_BYTES:raise ValueError('bounded_request_required')
        frame={'version':1,'request_b64':base64.b64encode(raw).decode('ascii'),
               'origin':{name:getattr(source,name) for name in ORIGIN_FIELDS}}
        frame['origin']['platform']=getattr(source.platform,'value',source.platform)
        wire=_json(frame)
        if len(wire)>MAX_FRAME:raise ValueError('broker_frame_limit')
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                connection.set_inheritable(False);connection.settimeout(3)
                connection.connect(str(path))
                _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if uid!=self._server_uid:raise ValueError('root_broker_peer_required')
                connection.sendall(wire);connection.shutdown(socket.SHUT_WR)
                outcome=_decode(_read_frame(connection,4096))
        except (OSError,ValueError):
            raise ValueError('broker_admission_not_confirmed') from None
        expected={'request_id','queued','request_file_created','admission_renewed','search_executed','notification_sent'}
        request=_decode(raw)
        if (set(outcome)!=expected or outcome.get('request_id')!=request.get('request_id')
                or outcome.get('queued') is not True or outcome.get('search_executed') is not False
                or outcome.get('notification_sent') is not False
                or any(type(outcome[name]) is not bool for name in ('request_file_created','admission_renewed'))):
            raise ValueError('broker_admission_not_confirmed')
        return outcome


class BrokerGatewayRuntime:
    """No secret/key/signing method exists in the gateway-side object."""
    def __init__(self,owner,client,*,current_source,authorize_source):
        if type(owner) is not OwnerBinding:raise ValueError('protected_owner_binding_required')
        owner.validate()
        if type(client) is not BrokerClient or not callable(current_source) or not callable(authorize_source):
            raise ValueError('protected_broker_gateway_binding_required')
        self._owner=owner;self._client=client;self._source=current_source;self._authorize=authorize_source

    def submit(self,raw):
        source=self._source()
        authorized_owner(raw,source,authorize_source=self._authorize,bindings=(self._owner,))
        return self._client.submit(raw,source)
