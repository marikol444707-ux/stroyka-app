"""Private host Docker primitives for preserving a stopped standalone container.

No import-time operations or install CLI. Controller must obtain maintenance
approval, quiesce writers, verify its data backup and reserve new file targets
before using these primitives. No secrets are put in argv or public repr/logs.
"""
from copy import deepcopy
from dataclasses import dataclass,field
import http.client
import json
import re
import socket
import time
from urllib.parse import quote

from .cli_result import _pairs,_nonfinite
from .image_pin import BASE_IMAGE,snapshot_pin
from .prepare_install import MOUNTS


class DockerFailure(RuntimeError):
    def __init__(self,code,*,status=None):super().__init__(code);self.status=status


class _UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


class DockerAPI:
    """Trusted host transport only; not registered as a model tool."""
    def __init__(self):
        version=self._request('GET','/version')
        if type(version) is not dict or not re.fullmatch(r'1\.[0-9]{1,3}',str(version.get('ApiVersion',''))):
            raise DockerFailure('reviewed_docker_api_required')
        self.prefix='/v'+version['ApiVersion']

    def _request(self,method,path,body=None):
        client=_UnixHTTP('localhost',timeout=180)
        try:
            client.request(method,path,body=None if body is None else json.dumps(body,allow_nan=False).encode(),
                           headers={'Content-Type':'application/json'})
            response=client.getresponse();raw=response.read(4*1024*1024+1)
            if response.status>=300 or len(raw)>4*1024*1024:
                raise DockerFailure('docker_operation_unconfirmed',status=response.status)
            return json.loads(raw,object_pairs_hook=_pairs,parse_constant=_nonfinite) if raw else None
        finally:client.close()

    def request(self,method,path,body=None):return self._request(method,self.prefix+path,body)


def _identifier(identifier):
    if type(identifier) is not str or not re.fullmatch('[a-f0-9]{64}',identifier):
        raise ValueError('immutable_container_id_required')
    return identifier


def validate_source(value,*,stopped=False,_base=BASE_IMAGE):
    """Supported observed topology only; no guessed handling of extra volumes."""
    if (type(value) is not dict or value.get('Name')!='/hermes-telegram' or value.get('Image')!=_base
            or type(value.get('State')) is not dict or value['State'].get('Running') is not (not stopped)
            or type(value.get('Config')) is not dict or type(value.get('HostConfig')) is not dict):
        raise ValueError('exact_observed_hermes_source_required')
    _identifier(value.get('Id'))
    host=value['HostConfig'];mounts=value.get('Mounts')
    if (host.get('Privileged') is not False or host.get('CapAdd') not in (None,[])
            or host.get('PidMode')!='' or host.get('Devices') not in (None,[])
            or host.get('SecurityOpt') not in (None,[],['no-new-privileges'],['no-new-privileges:true'])
            or host.get('NetworkMode')!='bridge' or host.get('PortBindings') not in (None,{})
            or host.get('AutoRemove',False) is not False or host.get('VolumesFrom') not in (None,[])
            or host.get('Links') not in (None,[]) or host.get('ReadonlyRootfs') is not False
            or host.get('RestartPolicy',{}).get('Name')!='unless-stopped'):
        raise ValueError('unsupported_container_topology_requires_review')
    if (type(mounts) is not list or len(mounts)!=1 or mounts[0].get('Type')!='bind'
            or mounts[0].get('Source')!='/root/hermes-data' or mounts[0].get('Destination')!='/opt/data'
            or mounts[0].get('RW') is not True):raise ValueError('exact_data_mount_required')
    network=value.get('NetworkSettings',{}).get('Networks',{})
    if (set(network)!={'bridge'} or network['bridge'].get('IPAMConfig') is not None
            or network['bridge'].get('Links') not in (None,[]) or network['bridge'].get('Aliases') not in (None,[])):
        raise ValueError('custom_network_configuration_requires_review')
    config=value['Config']
    if set(config.get('Volumes') or {})-{'/opt/data'}:
        raise ValueError('unbacked_image_volumes_require_review')
    if type(config.get('Env')) is not list or any(type(item) is not str or '=' not in item for item in config['Env']):
        raise ValueError('opaque_environment_list_required')


@dataclass(frozen=True,repr=False)
class PrivateCreateRequest:
    body: dict=field(repr=False)
    def __repr__(self):return 'PrivateCreateRequest(<private Docker configuration>)'


def create_request(stopped,pin,*,_base=BASE_IMAGE,release_token=None):
    validate_source(stopped,stopped=True,_base=_base)
    expected=snapshot_pin(stopped,{'Id':pin.get('snapshot_image'),'Parent':pin.get('base_image')},_base=_base)
    if pin!=expected:raise ValueError('snapshot_identity_conflict')
    extra=[{'Type':'bind','Source':row['source'],'Target':row['destination'],'ReadOnly':True} for row in MOUNTS]
    return _private_clone(stopped,pin['snapshot_image'],extra,release_token=release_token)


def _private_clone(stopped,snapshot_image,extra,*,release_token=None):
    """Internal copier; production caller must validate topology and provenance."""
    body=deepcopy(stopped['Config']);body['Image']=snapshot_image
    body['HostConfig']=deepcopy(stopped['HostConfig'])
    body['HostConfig']['Mounts']=deepcopy(body['HostConfig'].get('Mounts') or [])+extra
    if release_token is not None:
        if type(release_token) is not str or not re.fullmatch('[a-f0-9]{32}',release_token):
            raise ValueError('owned_release_token_required')
        labels=deepcopy(body.get('Labels') or {})
        if 'stroyka.jev.release' in labels:raise ValueError('foreign_release_label_preserved')
        labels['stroyka.jev.release']=release_token;body['Labels']=labels
    # No secret argv/env-file reconstruction: preserve strings, including line
    # breaks and '=' bytes, inside the private Unix-socket JSON request only.
    return PrivateCreateRequest(body)


def stop_gracefully(api,identifier,*,timeout=120,_clock=time.monotonic,_wait=time.sleep):
    identifier=_identifier(identifier)
    if type(timeout) is not int or not 1<=timeout<=120:raise ValueError('bounded_graceful_stop_required')
    if not api.request('GET','/containers/'+identifier+'/json')['State']['Running']:return
    # Never Docker stop's automatic SIGKILL after a timeout. A timed-out TERM
    # remains unconfirmed for explicit recovery; do not pretend rollback passed.
    api.request('POST','/containers/'+identifier+'/kill?signal=SIGTERM')
    deadline=_clock()+timeout
    while True:
        value=api.request('GET','/containers/'+identifier+'/json')
        if value['Id']!=identifier:raise DockerFailure('container_identity_changed')
        if value['State']['Running'] is False:return
        if _clock()>=deadline:raise DockerFailure('graceful_stop_not_confirmed')
        _wait(.25)


def stopped_snapshot(api,identifier):
    identifier=_identifier(identifier)
    stopped=api.request('GET','/containers/'+identifier+'/json')
    validate_source(stopped,stopped=True)
    result=api.request('POST','/commit?container='+identifier+'&pause=false',deepcopy(stopped['Config']))
    image=result.get('Id') if type(result) is dict else None
    if type(image) is not str or not re.fullmatch('sha256:[a-f0-9]{64}',image):
        raise DockerFailure('snapshot_not_confirmed')
    metadata=api.request('GET','/images/'+quote(image,safe='')+'/json')
    pin=snapshot_pin(stopped,metadata)
    return stopped,pin


def _same_host_config(actual,desired):
    expected=deepcopy(desired)
    # Engine inspect uses null for a newly created OOM default, then false after
    # a round-trip. Both mean the OOM killer is enabled. Never accept true.
    if expected.get('OomKillDisable') is None and actual.get('OomKillDisable') is False:
        expected['OomKillDisable']=False
    return actual==expected


def verify_created(actual,source,pin,*,release_token=None):
    """Compare private settings before the replacement is ever started."""
    if (actual.get('Image')!=pin['snapshot_image'] or actual.get('State',{}).get('Running') is not False):
        raise DockerFailure('stopped_replacement_required')
    desired=create_request(source,pin,release_token=release_token).body
    # Runtime identity/settings are kept byte-for-byte. A daemon rewrite must
    # be reviewed instead of silently accepted (even if usually equivalent).
    for key in ('Env','Cmd','Entrypoint','User','WorkingDir','Hostname','Domainname','Labels',
                'Healthcheck','StopSignal','StopTimeout','Tty','OpenStdin','StdinOnce'):
        if actual.get('Config',{}).get(key)!=desired.get(key):
            raise DockerFailure('replacement_configuration_conflict')
    if not _same_host_config(actual.get('HostConfig',{}),desired['HostConfig']):
        raise DockerFailure('replacement_host_configuration_conflict')
