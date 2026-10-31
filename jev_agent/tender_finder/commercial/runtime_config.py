"""Explicit protected commercial host assembly; never installs or registers.

Existing v2 settings/tool/service remain unchanged by default. V3 has separate
queues, admissions, receipts, registry and gateway paths, with the same verified
owner as the existing deployment. No config-supplied Python, commands, key or
recipient override. Browser readers require an actual protected opener.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import os

from .bridge import CommercialBridge
from .model import Profile
from .portal_reader import source_bundle
from .sources import source_registry
from ..settings import BridgeSettings, parse_settings, load_settings, _load_settings_json, _path


@dataclass(frozen=True,repr=False)
class RuntimePolicy:
    bridge: BridgeSettings
    registry_directory: Path
    profile: Profile
    enabled_sources: tuple[str,...]

    def __repr__(self):return 'RuntimePolicy(<protected commercial bindings>)'


def _paths(settings):
    return (settings.queue.inbox,settings.queue.pipeline.private_directory,
            settings.queue.pipeline.result_directory,settings.worker_admissions,
            settings.gateway_inbox,settings.gateway_admissions)


def _overlap(left,right):return left==right or left in right.parents or right in left.parents


def separate_bridge(value,*,legacy,extra_paths=()):
    if (type(legacy) is not BridgeSettings or legacy.queue.pipeline.protocol!=2
            or type(value) is not dict or value.get('schema_version')!=2):
        raise ValueError('explicit_separate_commercial_bridge_required')
    bridge=parse_settings(value)
    if (bridge.owner!=legacy.owner or bridge.gateway_uid!=legacy.gateway_uid
            or bridge.owner.profile is not None):
        raise ValueError('existing_verified_commercial_owner_required')
    new=(*_paths(bridge),*extra_paths)
    if (any(_overlap(left,right) for index,left in enumerate(new) for right in new[index+1:])
            or any(_overlap(left,right) for left in new for right in _paths(legacy))
            or any(path.resolve(strict=False)!=path for path in new)):
        raise ValueError('commercial_and_legacy_namespaces_must_be_separate')
    return replace(bridge,queue=replace(bridge.queue,pipeline=replace(bridge.queue.pipeline,protocol=3)))


def parse_runtime(value,*,legacy):
    if (type(legacy) is not BridgeSettings or legacy.queue.pipeline.protocol!=2
            or type(value) is not dict or set(value)!={'format','protocol','bridge','registry_directory','profile','enabled_sources'}
            or type(value['format']) is not int or value['format']!=1
            or type(value['protocol']) is not int or value['protocol']!=3
            or type(value['bridge']) is not dict or value['bridge'].get('schema_version')!=2):
        raise ValueError('explicit_separate_commercial_runtime_required')
    registry=_path(value['registry_directory'])
    bridge=separate_bridge(value['bridge'],legacy=legacy,extra_paths=(registry,))
    profile=value['profile']
    if (type(profile) is not dict or set(profile)!={'legal_entity','qualifications'}
            or profile['legal_entity'] is not None and (type(profile['legal_entity']) is not str
                or not 2<=len(profile['legal_entity'])<=300 or not profile['legal_entity'].strip()
                or any(ord(char)<32 for char in profile['legal_entity']))
            or type(profile['qualifications']) is not list
            or any(type(item) is not str for item in profile['qualifications'])
            or len(set(profile['qualifications']))!=len(profile['qualifications'])):
        raise ValueError('protected_executor_profile_required')
    profile=Profile(legal_entity=profile['legal_entity'],qualifications=frozenset(profile['qualifications']))
    profile.validate()
    enabled=value['enabled_sources'];known=source_registry()
    if (type(enabled) is not list or not 1<=len(enabled)<=len(known)
            or any(type(item) is not str or item not in known for item in enabled)
            or len(set(enabled))!=len(enabled)):
        raise ValueError('explicit_enabled_commercial_sources_required')
    return RuntimePolicy(bridge,registry,profile,tuple(enabled))


def load_runtime(path,*,trusted_root=Path('/etc/stroyka-jev-commercial'),
                 legacy_policy=Path('/etc/stroyka-jev/bridge.json'),legacy_root=Path('/etc/stroyka-jev'),expected_uid=0):
    legacy=load_settings(legacy_policy,trusted_root=legacy_root,expected_uid=expected_uid)
    value=_load_settings_json(path,trusted_root=trusted_root,expected_uid=expected_uid)
    return parse_runtime(value,legacy=legacy)


def build_bridge(policy,secret,*,clock,open_browser=None):
    if type(policy) is not RuntimePolicy:raise ValueError('protected_commercial_runtime_policy_required')
    native={'step','rtender','federation'}
    if open_browser is None and set(policy.enabled_sources)-native:
        raise ValueError('reviewed_commercial_browser_factory_required')
    def unavailable_browser(_):raise ValueError('commercial_browser_not_configured')
    sources,adapters=source_bundle(open_browser=unavailable_browser if open_browser is None else open_browser,
                                  clock=clock,scope=policy.bridge.owner.scope)
    if set(policy.enabled_sources)-set(adapters):raise ValueError('configured_commercial_reader_not_bound')
    return CommercialBridge(policy.bridge,secret,policy.registry_directory,profile=policy.profile,
                            sources=sources,adapters={key:adapters[key] for key in policy.enabled_sources})


def validate_gateway_pair(policy,gateway_settings):
    if (type(policy) is not RuntimePolicy or type(gateway_settings) is not BridgeSettings
            or policy.bridge!=gateway_settings):
        raise ValueError('matching_commercial_host_and_gateway_policies_required')


def initialize_commercial_host(settings_path,key_fd,peer,*,open_browser=None):
    """Root-only initializer for an explicitly installed, separately pinned service.

    It returns a host object only. service.main validates the listener. Unit/socket
    installation, key provisioning and gateway builtin mounting are deployment work.
    """
    from datetime import datetime,timezone
    from ..bootstrap_key import read_bootstrap_key
    from ..broker_service import validate_gateway_peer
    from ..host_service import ConnectedHost
    from .startup_tool import load_gateway_policy
    owned=True
    try:
        if os.geteuid()!=0 or type(key_fd) is not int or key_fd<3:raise ValueError('root_commercial_host_required')
        policy=load_runtime(settings_path)
        validate_gateway_pair(policy,load_gateway_policy())
        validate_gateway_peer(peer)
        if policy.bridge.gateway_uid!=peer.uid:raise ValueError('commercial_gateway_identity_mismatch')
        owned=False;secret=read_bootstrap_key(key_fd)
        bridge=build_bridge(policy,secret,clock=lambda:datetime.now(timezone.utc),open_browser=open_browser)
        return ConnectedHost(policy.bridge,secret,peer,commercial_bridge=bridge)
    finally:
        if owned and type(key_fd) is int and key_fd>=3:
            try:os.close(key_fd)
            except OSError:pass
