"""Required CI regression against the pinned real Hermes registry/resolver.

No installed gateway, model, key, requests, config writes or messages. Sources
are public, pinned by revision AND SHA256. External plugin/credential discovery
is replaced by empty fixture data; actual selection/dispatch code is unchanged.
"""
import ast
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import typing
import urllib.request
from unittest.mock import Mock,patch

REVISION='bf0203a794a07aac3ff764972ab9087baa4e4f4e'
SOURCES={'tools/registry.py':'48c3875138ac9e1875349ed2900d6940f51dfff050d655d6fb17a1dafe30f5e7',
 'toolsets.py':'7674a11eeebcc06b7c83c816fca0bc6982107870f5615375d2ffc5dbe6044eaa',
 'model_tools.py':'da5b7db1b05de615658e56c4172426ed82099a093c5b586e48e65ef930b778c8',
 'hermes_cli/tools_config.py':'35012cc12fc709a5a95c3f547ebb76a1938f231f0012e7e6fa843bf4be52a2fd',
 'hermes_cli/_launchers.py':'f45dbb4bcf1582e82d90b7425bb1480756f85234defe9269785603735546c9b4',
 'docker/hermes-exec-shim.sh':'57637e73c8db76aa84a38e4a2edb1b155bfd86a2e89a8d4c38c4546ee1175985'}


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


def verify_docker_runtime_boundary(sources):
    from jev_agent.tender_finder.docker_delivery import RUNTIME_RESOLVE_PROGRAM,RUNTIME_BOOTSTRAP,RUNTIME_ENTRY
    import contextlib,io
    # The actual Docker shim forwards the print flag to the ordinary CLI; it
    # does not use the minted source launcher. Reproduce the relevant contract.
    shim=sources['docker/hermes-exec-shim.sh'].decode()
    assert 'REAL=/opt/hermes/.venv/bin/hermes' in shim and 'exec "$REAL" "$@"' in shim
    assert '--print-runtime-command' not in shim
    real_open=os.open;real_fstat=os.fstat
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);source=root/'opt/hermes/hermes_cli/_launchers.py';source.parent.mkdir(parents=True)
        source.write_bytes(sources['hermes_cli/_launchers.py'])
        store=root/'runtime';python=store/'python-fixture/bin/python3';python.parent.mkdir(parents=True);python.touch()
        (store/'facts.json').write_text(json.dumps({'packages':{'python':{'entry':'python-fixture'}}}))
        pm=types.ModuleType('pm');pm.__path__=[];environments=types.ModuleType('pm.environments')
        environments.owning_home_root=lambda *_:None;environments.store_root=lambda *_:store
        def opened(path,*args,**kwargs):return real_open(folder if path=='/' else path,*args,**kwargs)
        def info(fd):
            value=real_fstat(fd)
            return types.SimpleNamespace(st_uid=0,st_mode=value.st_mode,st_nlink=value.st_nlink,st_size=value.st_size)
        output=io.StringIO()
        with patch.dict(sys.modules,{'pm':pm,'pm.environments':environments}),patch.object(sys,'argv',[]),patch.object(
                os,'geteuid',return_value=10000),patch.object(os,'getegid',return_value=10000),patch.object(
                os,'open',side_effect=opened),patch.object(os,'fstat',side_effect=info),contextlib.redirect_stdout(output):
            with_exit=False
            try:exec(compile(RUNTIME_RESOLVE_PROGRAM,'reviewed-fixed-docker-resolver','exec'),{})
            except SystemExit as error:
                assert error.code==0;with_exit=True
            assert with_exit
        # FULL authenticated _launchers.py ran its real main + resolver, not an
        # AST-extracted imitation. Only PM's external store location is fixture.
        assert json.loads(output.getvalue())==[str(python),'-I','-c',RUNTIME_BOOTSTRAP+RUNTIME_ENTRY]


def verify(sources):
    verify_docker_runtime_boundary(sources)
    from jev_agent.tender_finder.docker_delivery import _runtime_command,REMOTE_PROGRAM
    runtime={'Path':Path,'os':os,'sys':sys,'PIN_DEFAULT_HOME_FLAG':'_hermes_pin_default_home',
        'resolve_store_python':lambda root:Path('/opt/hermes/tools/python-3.14.9+20261021-linux-x64/bin/python3')}
    functions(sources['hermes_cli/_launchers.py'],('_inline_string_literal','runtime_command'),runtime)
    command=runtime['runtime_command'](Path('/opt/hermes'),module='io')
    resolved=_runtime_command(json.dumps(command).encode(),REMOTE_PROGRAM)
    # Preserve the REAL pinned bootstrap, including dependency generation lease;
    # replace just its requested module with the fixed sender. No live sending.
    assert resolved[0]==command[0] and resolved[1:4]==('-I','-B','-c')
    assert resolved[4]==command[3].removesuffix("runpy.run_module('io', run_name='__main__', alter_sys=True)")+'exec('+repr(REMOTE_PROGRAM)+')'
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
        'docker_shim_boundary_verified':True,'published_runtime_bootstrap_preserved':True,'search_executed':False,'notifications_sent':False}


if __name__=='__main__':print(json.dumps(verify(load_sources())))
