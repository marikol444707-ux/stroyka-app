"""Explicit v3 systemd lifecycle; no install, key creation or provider polling."""
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import stat
import sys
import threading
from datetime import datetime,timezone

from .runtime_config import load_runtime,validate_gateway_pair,build_bridge
from .startup_tool import load_gateway_policy
from .service import SOCKET
from .documents import extract_isolated
from ..bootstrap_key import read_bootstrap_key
from ..host_service import ConnectedHost
from ..systemd_bootstrap import discover_gateway_peer,inherited_listener,credential_pipe,validate_state_directories

HOST_POLICY=Path('/etc/stroyka-jev-commercial/runtime.json')
CREDENTIAL=Path('/run/credentials/stroyka-jev-commercial.service/admission.key')
STATE=Path('/var/lib/stroyka-jev-commercial')
VENV=Path('/opt/stroyka-jev-commercial/venv')
NATIVE=frozenset({'step','rtender','federation'})


def runtime_policy():
    policy=load_runtime(HOST_POLICY)
    validate_gateway_pair(policy,load_gateway_policy())
    settings=policy.bridge
    if (settings.queue.writer_uid!=0 or settings.gateway_uid!=10000
            or settings.queue.pipeline.result_gid!=10000 or settings.owner.profile is not None
            or settings.queue.inbox!=STATE/'requests' or settings.worker_admissions!=STATE/'admissions'
            or settings.queue.pipeline.private_directory!=STATE/'private'
            or settings.queue.pipeline.result_directory!=STATE/'results'
            or policy.registry_directory!=STATE/'registry'):
        raise ValueError('dedicated_commercial_host_namespace_required')
    if set(policy.enabled_sources)-NATIVE:raise ValueError('reviewed_commercial_browser_not_bound')
    return policy


def validate_state(policy):
    validate_state_directories(policy.bridge)
    path=policy.registry_directory
    if path.resolve(strict=True)!=path:raise ValueError('protected_commercial_registry_required')
    for directory in (path,*path.parents):
        info=directory.stat()
        if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('protected_commercial_registry_parent_required')
    info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError('private_commercial_registry_required')


def verify_document_runtime():
    prefix=Path(sys.prefix)
    if prefix!=VENV or prefix.resolve(strict=True)!=prefix:
        raise ValueError('dedicated_protected_commercial_venv_required')
    for directory in (prefix,*prefix.parents):
        info=directory.stat()
        if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('protected_commercial_venv_parent_required')
    if importlib.metadata.version('pypdf')!='6.18.1':raise ValueError('pinned_commercial_document_dependency_required')
    # No website, model, user document or request is used by this health check.
    text='JEV isolated runtime probe'
    result=extract_isolated(text.encode(),'.txt')
    if result!={'status':'text','complete':True,'blocks':[{'locator':'текст','text':text}]}:
        raise ValueError('commercial_document_sandbox_not_confirmed')


def main(argv=None):
    listener=None;handlers={};stage='arguments'
    try:
        if argv is None:argv=sys.argv[1:]
        if argv or os.geteuid()!=0:raise ValueError('explicit_root_commercial_systemd_bootstrap_required')
        stage='policy';policy=runtime_policy()
        stage='state_permissions';validate_state(policy)
        stage='document_runtime';verify_document_runtime()
        stage='inherited_listener'
        listener=inherited_listener(os.environ,listener_name='commercial',listener_path=SOCKET)
        stage='gateway_peer';peer=discover_gateway_peer()
        if peer.uid!=policy.bridge.gateway_uid or peer.gid!=10000:
            raise ValueError('commercial_gateway_identity_mismatch')
        stage='credential';secret=read_bootstrap_key(credential_pipe(_path=CREDENTIAL))
        stage='broker_initialization'
        bridge=build_bridge(policy,secret,clock=lambda:datetime.now(timezone.utc))
        host=ConnectedHost(policy.bridge,secret,peer,commercial_bridge=bridge)
        stop=threading.Event()
        for number in (signal.SIGTERM,signal.SIGINT):
            handlers[number]=signal.signal(number,lambda signum,frame:stop.set())
        print(json.dumps({'commercial_host_started':True,'installation_ready':False}),flush=True)
        stage='serving';host.serve(listener,stop)
        return 0
    except Exception as error:
        print(json.dumps({'commercial_host_started':False,'code':type(error).__name__,'stage':stage,
                          'installation_ready':False}),flush=True)
        return 1
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)
        if listener is not None:listener.close()


if __name__=='__main__':raise SystemExit(main())
