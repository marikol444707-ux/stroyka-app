"""Fixed SSH transport; no shell, token, arbitrary destination or remote path API.

The gateway root relay verifies the original Hermes kernel peer. The main host's
forced SSH command uses its own protected owner policy and admission key. Only
that main host executes work and reserves completion sends in the existing ledger.
"""
import base64
import time

from .admission_broker import AdmissionBroker, GatewayPeer, MAX_FRAME, admit_authenticated_wire
from .contract import validate_v2_request
from .ingress import owner_route
from .invoker import _run_bounded
from .notification import deliver_completion
from .queue import _decode
from .state import _json

MAX_TRANSPORT=70000
CONFIG='/etc/stroyka-jev-remote/ssh_config'


def decode_frame(raw):
    if type(raw) is not bytes or len(raw)>MAX_TRANSPORT:
        raise ValueError('bounded_transport_frame_required')
    return _decode(raw)


def _transport_run(argv,wire,timeout):
    return _run_bounded(argv,wire,timeout,maximum_bytes=4*1024*1024)


def exchange(destination,frame,*,timeout=2,_run=_transport_run):
    if destination not in ('main','gateway'):
        raise ValueError('fixed_transport_destination_required')
    wire=_json(frame)
    if len(wire)>MAX_TRANSPORT:raise ValueError('transport_frame_limit')
    argv=('/usr/bin/ssh','-F',CONFIG,'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
          '-o','ConnectTimeout=2','-o','ConnectionAttempts=1','-T','jev-'+destination)
    raw,code=_run(argv,wire,timeout)
    if code!=0 or type(raw) is not bytes or len(raw)>4*1024*1024:
        raise ValueError('remote_response_not_confirmed')
    return _decode(raw)


class RelayBroker(AdmissionBroker):
    """Reuse both kernel-peer checks; this relay cannot sign or execute jobs."""
    def __init__(self,peer,protocol,remote):
        if type(peer) is not GatewayPeer or type(protocol) is not int or protocol not in (2,3):
            raise ValueError('protected_relay_binding_required')
        peer.validate()
        self._peer,self._protocol=peer,protocol
        self._remote=remote

    def _admit(self,wire):
        if type(wire) is not bytes or len(wire)>MAX_FRAME:
            raise ValueError('bounded_relay_frame_required')
        return self._remote({'op':'admit','protocol':self._protocol,
                             'wire':base64.b64encode(wire).decode('ascii')})


def admit_remote(settings,secret,wire,*,request_validator=validate_v2_request,clock=lambda:int(time.time())):
    return admit_authenticated_wire(settings,secret,wire,clock=clock,request_validator=request_validator)


def _protocol(value):
    if type(value) is not int or value not in (2,3):
        raise ValueError('reviewed_protocol_required')
    return value


def _keys(frame,keys):
    if type(frame) is not dict or set(frame)!=set(keys):
        raise ValueError('fixed_transport_fields_required')


def receive_frame(frame,*,load):
    """Admission only; caller already checked forced-command SSH peer and role."""
    _keys(frame,('op','protocol','wire'))
    if frame['op']!='admit':raise ValueError('admission_operation_required')
    protocol=_protocol(frame['protocol'])
    if type(frame['wire']) is not str or len(frame['wire'])>65536:
        raise ValueError('bounded_encoded_wire_required')
    wire=base64.b64decode(frame['wire'],validate=True)
    if len(wire)>MAX_FRAME:raise ValueError('bounded_admission_wire_required')
    settings,secret,validator=load(protocol)
    if settings.queue.pipeline.protocol!=protocol:raise ValueError('transport_protocol_mismatch')
    return admit_remote(settings,secret,wire,request_validator=validator)


def send_remote_completion(settings,event_id,request_id,fingerprint,*,gateway_gid,remote=exchange):
    if gateway_gid!=10000:raise ValueError('reviewed_gateway_group_required')
    def send(args):
        response=remote('gateway',{'op':'send','protocol':settings.queue.pipeline.protocol,'args':args},timeout=85)
        if set(response)!={'sender_result'} or type(response['sender_result']) is not str:
            raise ValueError('remote_send_not_confirmed')
        return response['sender_result']
    return deliver_completion(settings.queue.pipeline.private_directory,settings.owner.scope,event_id,
        request_id,fingerprint,route=owner_route((settings.owner,),settings.owner.scope),send=send)


def _query(query):
    if (type(query) is not str or not 1<=len(query)<=80
            or any(ord(char)<32 for char in query)):
        raise ValueError('bounded_search_query_required')
    return query


def legacy_call(argv):
    executable='/usr/local/bin/stroyka-jev'
    if argv==[executable,'commercial-search']:return {'op':'legacy','kind':'commercial'}
    if (len(argv)==5 and argv[:3]==[executable,'eis-search','--query']
            and argv[4]=='--stavropol-open'):
        return {'op':'legacy','kind':'eis','query':_query(argv[3])}
    raise ValueError('fixed_legacy_command_required')


def legacy_argv(frame):
    if frame.get('kind')=='commercial':
        _keys(frame,('op','kind'));argv=['/usr/local/bin/stroyka-jev','commercial-search']
    elif frame.get('kind')=='eis':
        _keys(frame,('op','kind','query'))
        argv=['/usr/local/bin/stroyka-jev','eis-search','--query',_query(frame['query']),'--stavropol-open']
    else:raise ValueError('reviewed_legacy_source_required')
    if frame['op']!='legacy':raise ValueError('legacy_operation_required')
    return argv
