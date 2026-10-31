"""Opt-in key-free v3 builtin; default legacy registration is preserved.

No configuration/key writes, startup search, send or live Runner resolution.
An absent/invalid optional policy never replaces the existing v2 tool. Installer
preflight must validate both protected host and gateway policies explicitly.
"""
import os
from pathlib import Path

from .tool import NAME,SCHEMA,handler,bind_live_gateway
from .runtime_config import separate_bridge
from .sources import source_registry
from .service import SOCKET
from ..settings import _load_settings_json,load_settings

POLICY=Path('/opt/stroyka-jev/config/commercial.json')
LEGACY_POLICY=Path('/opt/stroyka-jev/config/bridge.json')
ROOT=Path('/opt/stroyka-jev')
SCOPE='/opt/data'


def load_gateway_policy(path=POLICY,*,legacy_policy=LEGACY_POLICY,trusted_root=ROOT,expected_uid=0):
    legacy=load_settings(legacy_policy,trusted_root=trusted_root,expected_uid=expected_uid)
    value=_load_settings_json(path,trusted_root=trusted_root,expected_uid=expected_uid)
    if (type(value) is not dict or set(value)!={'format','protocol','bridge'}
            or type(value['format']) is not int or value['format']!=1
            or type(value['protocol']) is not int or value['protocol']!=3):
        raise ValueError('explicit_key_free_commercial_gateway_policy_required')
    return separate_bridge(value['bridge'],legacy=legacy)


def handle(args,**_ignored):
    try:
        settings=load_gateway_policy()
        if settings.gateway_uid!=os.geteuid():raise ValueError('actual_commercial_gateway_uid_required')
        from ..hermes_binding import verified_loaded_modules
        runner=verified_loaded_modules()['gateway.run']._gateway_runner_ref()
        gateway=bind_live_gateway(runner,settings.owner,SOCKET,sources=source_registry())
        return handler(gateway)(args)
    except Exception:
        return {'queued':False,'reason':'commercial_gateway_not_ready'}


def register_if_configured(registry):
    try:
        POLICY.lstat()
        load_gateway_policy()
    except Exception:
        return False
    with registry._lock:
        if registry.get_entry(NAME,scope=SCOPE) is not None:return False
        registry.register(name=NAME,toolset='hermes-telegram',schema=SCHEMA,handler=handle,
                          scope=SCOPE,override=False,execution_timeout=5)
    return True
