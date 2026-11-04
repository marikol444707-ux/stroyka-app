"""Required CI regression against the pinned real Hermes registry/resolver.

No installed gateway, model, key, requests, config writes or messages. Sources
are public, pinned by revision AND SHA256. External plugin/credential discovery
is replaced by empty fixture data; actual selection/dispatch code is unchanged.
"""
import ast
import hashlib
import json
import logging
from pathlib import Path
import sys
import types
import typing
import urllib.request
from unittest.mock import Mock,patch

REVISION='bf0203a794a07aac3ff764972ab9087baa4e4f4e'
SOURCES={'tools/registry.py':'48c3875138ac9e1875349ed2900d6940f51dfff050d655d6fb17a1dafe30f5e7',
 'toolsets.py':'7674a11eeebcc06b7c83c816fca0bc6982107870f5615375d2ffc5dbe6044eaa',
 'model_tools.py':'da5b7db1b05de615658e56c4172426ed82099a093c5b586e48e65ef930b778c8',
 'hermes_cli/tools_config.py':'35012cc12fc709a5a95c3f547ebb76a1938f231f0012e7e6fa843bf4be52a2fd',
 'pm/environments.py':'40b5fb014b07ad7c7187352bacb9b79581da4c1304d2e86768eb5dfd95a2ea2b',
 'agent/secret_scope.py':'dce64ce99a6966836108e202e1db41c4be97bd3dad41a79e357f39b8d7e90dec'}


def load_sources():
    result={}
    for name,digest in SOURCES.items():
        url='https://raw.githubusercontent.com/NousResearch/hermes-agent/'+REVISION+'/'+name
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(200000)
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('reviewed_hermes_source_required')
        result[name]=raw
    return result


def functions(raw,names,namespace):
    tree=ast.parse(raw);nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes}!=set(names):raise ValueError('reviewed_resolver_contract_changed')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'reviewed-resolver','exec'),namespace)


def verify_sealed_docker_contract(sources):
    # Reproduce the live NoCommittedEnvironment from actual pinned PM code.
    # A dependency-carrying venv returns normally; a bare store Python refuses.
    namespace={'Path':Path,'store_root':lambda _:Path('/fixture/store'),
        '__name__':'reviewed_pm_fixture'}
    tree=ast.parse(sources['pm/environments.py'])
    error_class=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NoCommittedEnvironment')
    exec(compile(ast.Module(body=[error_class],type_ignores=[]),'reviewed-pm-error','exec'),namespace)
    functions(sources['pm/environments.py'],('_require_own_dependencies',),namespace)
    require=namespace['_require_own_dependencies']
    with patch.object(sys,'prefix','/fixture/venv'),patch.object(sys,'base_prefix','/fixture/store'):
        require(Path('/opt/hermes'))
    with patch.object(sys,'prefix','/fixture/store'),patch.object(sys,'base_prefix','/fixture/store'):
        try:require(Path('/opt/hermes'))
        except namespace['NoCommittedEnvironment']:pass
        else:raise AssertionError('bare_store_must_refuse_missing_dependencies')
    from jev_agent.tender_finder import docker_delivery
    # Removing ONLY the scoped-credential wrapper must reconstruct exact f214:
    # UID/mount/image/source/recipient gates and delivery ledger stay identical.
    raw=Path(docker_delivery.__file__).read_bytes()
    start=raw.index(b'\ndef _profile_sender(sender):')
    end=raw.index(b'\ndef main():',start)
    original=(raw[:start]+raw[end:]).replace(
        b'return _profile_sender(module.send_message_tool)',b'return module.send_message_tool')
    assert hashlib.sha256(original).hexdigest()=='9d5ab6593fc20bc68e3c5a13e098b180ae13abbbbdd68bdb4cc472b809f785c8'
    # Real pinned Hermes scope implementation: a standalone environment misses
    # profile credentials until scoped resolution, with no .env or network use.
    scope=types.ModuleType('agent.secret_scope')
    exec(compile(sources['agent/secret_scope.py'],'reviewed-secret-scope','exec'),scope.__dict__)
    constants=types.ModuleType('hermes_constants')
    constants.get_hermes_home=lambda:Path('/opt/data')
    namespace={'__name__':'credential_fixture'}
    exec(compile(docker_delivery.REMOTE_PROGRAM,'fixed-transport','exec'),namespace)
    with patch.dict(sys.modules,{'agent.secret_scope':scope,'hermes_constants':constants}),patch.dict(
            'os.environ',{'HERMES_HOME':'/opt/data','HERMES_PROFILE':''}):
        assert scope.current_secret_scope() is None
        assert scope.get_secret('JEV_SYNTHETIC_TEST_TOKEN') is None
        with patch.object(scope,'build_profile_secret_scope',return_value={'JEV_SYNTHETIC_TEST_TOKEN':'fixture'}):
            assert namespace['_profile_sender'](lambda _:scope.get_secret('JEV_SYNTHETIC_TEST_TOKEN'))({})=='fixture'
        assert scope.current_secret_scope() is None


def verify(sources):
    verify_sealed_docker_contract(sources)
    from jev_agent.tender_finder import startup_tool as v2
    from jev_agent.tender_finder.commercial import startup_tool as v3
    from jev_agent.tender_finder.commercial.test_runtime_config import policies
    from jev_agent.tender_finder.commercial.runtime_config import parse_runtime
    from jev_agent.tender_finder.settings import parse_settings
    constants=types.ModuleType('hermes_constants')
    constants.hermes_home_key=lambda scope=None:str(scope or '/opt/data')
    constants.normalize_scope=lambda scope:str(scope) if scope else None
    tools=types.ModuleType('tools');tools.__path__=[]
    registry=types.ModuleType('tools.registry')
    toolsets=types.ModuleType('toolsets');model=types.ModuleType('model_tools')
    agent=types.ModuleType('agent');agent.__path__=[]
    skill=types.ModuleType('agent.skill_utils');skill.parse_config_string_list=lambda value:value
    modules={'hermes_constants':constants,'tools':tools,'tools.registry':registry,'toolsets':toolsets,
        'model_tools':model,'agent':agent,'agent.skill_utils':skill}
    with patch.dict(sys.modules,modules):
        exec(compile(sources['tools/registry.py'],'reviewed-registry','exec'),registry.__dict__)
        exec(compile(sources['toolsets.py'],'reviewed-toolsets','exec'),toolsets.__dict__)
        model.__dict__.update(vars(typing));model.__dict__.update({'os':types.SimpleNamespace(environ={}),
            'resolve_toolset':toolsets.resolve_toolset,'validate_toolset':toolsets.validate_toolset,
            '_LEGACY_TOOLSET_MAP':{},'_WARNED_DISABLED_BUNDLES':set(),'logger':logging.getLogger(__name__)})
        functions(sources['model_tools.py'],('_apply_toolset_selection','_select_tool_names'),model.__dict__)
        namespace={**vars(typing),'PLATFORMS':{'telegram':{'default_toolset':'hermes-telegram'}},
            '_TOOLSET_PLATFORM_RESTRICTIONS':{},'_toolset_allowed_for_platform':lambda *_:True,
            '_get_plugin_toolset_keys':lambda:set(),'_coerce_platform_toolsets_value':lambda value,platform:value,
            '_xai_credentials_present':lambda:False,'enabled_mcp_server_names':lambda config:set(),
            '_warn_all_invalid_platform_toolsets':lambda *_:None}
        tree=ast.parse(sources['hermes_cli/tools_config.py'])
        for node in tree.body:
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                if any(isinstance(target,ast.Name) and target.id in ('CONFIGURABLE_TOOLSETS','_DEFAULT_OFF_TOOLSETS','_RECENTLY_SHIPPED_TOOLSETS') for target in targets):
                    exec(compile(ast.Module(body=[node],type_ignores=[]),'reviewed-config-data','exec'),namespace)
        functions(sources['hermes_cli/tools_config.py'],('_platform_default_toolset','_configurable_keys',
            '_platform_default_keys','_configurable_subset_of','_default_off_toolsets',
            '_enable_recently_shipped_toolsets','_explicit_toolsets','_composite_toolsets',
            '_enabled_plugin_toolsets','_context_engine_active','_recover_platform_native_toolsets',
            '_merge_mcp_servers','_prune_toolsets_stripped_by_disabled','_get_platform_tools'),namespace)
        resolve=namespace['_get_platform_tools'];select=model._select_tool_names
        configured=['browser','cronjob','session_search','terminal','todo']
        config={'platform_toolsets':{'telegram':configured}}
        actual=registry.registry
        actual.register(name=v3.NAME,toolset='hermes-telegram',schema=v3.SCHEMA,
            handler=lambda args:{'queued':True},scope='/opt/data')
        assert v3.NAME not in select(sorted(resolve(config,'telegram')),None,True)
        rejected=json.loads(actual.dispatch(v3.NAME,{},scope='/opt/data'))
        assert rejected.get('error_type')=='tool_result_contract',rejected
        actual.deregister(v3.NAME,scope='/opt/data')
        old,raw=policies();policy=parse_runtime(raw,legacy=parse_settings(old))
        with patch.object(v3,'POLICY',Mock()),patch.object(v3,'load_gateway_policy',return_value=policy.bridge):
            v2.StartupRegistration(actual).register()
        before=select(sorted(resolve(config,'telegram')),None,True)
        new={'platform_toolsets':{'telegram':[*configured,'jev']}}
        after=select(sorted(resolve(new,'telegram')),None,True)
        assert after-before=={v2.NAME,v3.NAME},after-before
        assert not before-after
        bundle_only={'platform_toolsets':{'telegram':['hermes-telegram']}}
        bundle_jev={'platform_toolsets':{'telegram':['hermes-telegram','jev']}}
        before_bundle=select(sorted(resolve(bundle_only,'telegram')),None,True)
        after_bundle=select(sorted(resolve(bundle_jev,'telegram')),None,True)
        assert after_bundle-before_bundle=={v2.NAME,v3.NAME}
        assert not before_bundle-after_bundle
        with patch.object(v3,'handle',return_value={'queued':True,'search_executed':False}):
            result=actual.dispatch(v3.NAME,{'request_json':'{}'},scope='/opt/data')
        assert json.loads(result)=={'queued':True,'search_executed':False},result
        disabled={'platform_toolsets':{'telegram':[*configured,'jev']},'agent':{'disabled_toolsets':['jev']}}
        assert v3.NAME not in select(sorted(resolve(disabled,'telegram')),['jev'],True)
        assert v3.NAME not in select(sorted(resolve(config,'telegram')),None,True)
    return {'pinned_registry_and_resolver':'PASS','old_bundle_hidden_reproduced':True,
        'old_dictionary_result_rejected_reproduced':True,'dedicated_opt_in_exposes_only_jev':True,
        'json_acknowledgement_preserved':True,'disabled_group_respected':True,
        'docker_transport_gates_preserved':True,'native_profile_scope_verified':True,
        'bare_store_no_committed_reproduced':True,'search_executed':False,'notifications_sent':False}


if __name__=='__main__':print(json.dumps(verify(load_sources())))
