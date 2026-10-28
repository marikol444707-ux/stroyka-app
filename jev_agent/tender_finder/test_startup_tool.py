import ast
import json
from pathlib import Path
import threading
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from . import startup_tool
from .settings import parse_settings
from .test_settings import settings
from .admission_broker import BrokerClient,BrokerGatewayRuntime
from .ingress import OwnerBinding
from .state import Scope


class StartupToolTests(unittest.TestCase):
    def test_host_launcher_requires_privileged_isolated_bootstrap(self):
        entry=Path(__file__).parent/'integration/host_entry.py'
        result=subprocess.run([sys.executable,'-I','-B',str(entry),'worker'],capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'_',result.stderr)
        tree=ast.parse(entry.read_bytes())
        writes=[node for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Attribute) and target.attr=='dont_write_bytecode' for target in node.targets)]
        self.assertEqual(len(writes),1);self.assertIs(writes[0].value.value,True)

    def test_regular_package_does_not_merge_foreign_namespace_on_python_path(self):
        with tempfile.TemporaryDirectory() as folder:
            foreign=Path(folder)/'jev_agent';foreign.mkdir()
            (foreign/'__init__.py').write_text('raise RuntimeError("FOREIGN_PACKAGE_EXECUTED")')
            (foreign/'injected.py').write_text('raise RuntimeError("FOREIGN_MODULE_EXECUTED")')
            program='''import importlib,sys
sys.path[:0]=[sys.argv[1],sys.argv[2]]
import jev_agent
assert jev_agent.__file__==sys.argv[1]+'/jev_agent/__init__.py'
try: importlib.import_module('jev_agent.injected')
except ModuleNotFoundError: pass
else: raise AssertionError('foreign namespace merged')
print('PACKAGE_ISOLATED')
'''
            result=subprocess.run([sys.executable,'-I','-B','-c',program,
                str(Path(__file__).resolve().parents[2]),folder],capture_output=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual(result.stdout,b'PACKAGE_ISOLATED\n')

    def test_scanner_from_pinned_hermes_recognizes_builtin_registration(self):
        # This is the exact public scanner contract: module-level Expr(Call) of
        # registry.register (not a nested with/function which discovery ignores).
        path=Path(__file__).parent/'integration/hermes_jev_tool.py'
        tree=ast.parse(path.read_bytes())
        calls=[node.value for node in tree.body if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)]
        self.assertTrue(any(isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
            and call.func.value.id=='registry' and call.func.attr=='register' for call in calls))
        self.assertNotIn('read_bootstrap_key',path.read_text())
        self.assertNotIn('/opt/data',ast.unparse(tree).replace("'/opt/data directory'",''))

    def test_registration_is_explicit_scoped_and_preserves_other_tools(self):
        registry=SimpleNamespace(_lock=threading.RLock(),get_entry=Mock(return_value=None),register=Mock())
        startup_tool.StartupRegistration(registry).register()
        kwargs=registry.register.call_args.kwargs
        self.assertEqual(kwargs['name'],'jev_tender_search');self.assertEqual(kwargs['scope'],'/opt/data')
        self.assertFalse(kwargs['override']);self.assertIs(kwargs['handler'],startup_tool.handle)
        registry.get_entry.return_value=object();registry.register.reset_mock()
        with self.assertRaises(ValueError):startup_tool.StartupRegistration(registry).register()
        registry.register.assert_not_called()

    def test_missing_host_policy_fails_without_binding_search_or_signing_key(self):
        with patch.object(startup_tool,'load_settings',side_effect=PermissionError('PRIVATE')),patch.object(
                startup_tool,'bind_broker_gateway') as binding:
            value=startup_tool.handle({'request_json':'{}'})
        self.assertFalse(value['queued']);self.assertNotIn('PRIVATE',json.dumps(value));binding.assert_not_called()

    def test_real_registry_handler_uses_live_runner_and_key_free_broker_runtime(self):
        config=parse_settings({**settings(),'schema_version':2,'writer_uid':0,'gateway_uid':10000})
        owner=config.owner
        source=SimpleNamespace(platform='telegram',chat_type='dm',chat_id=owner.reply_chat_id,
                               user_id=owner.telegram_user_id,profile=None,thread_id=None,is_bot=False)
        client=BrokerClient('/run/stroyka-jev/admission.sock')
        client.submit=Mock(return_value={'queued':True,'search_executed':False})
        runtime=BrokerGatewayRuntime(owner,client,current_source=lambda:source,authorize_source=Mock(return_value=True))
        runner=object();payload={'version':2,'request_id':'search-startup-fixture',
            'region':'Ставропольский край','sources':['commercial'],'topics':['кровля']}
        with patch.object(startup_tool,'load_settings',return_value=config),patch.object(startup_tool.os,'geteuid',return_value=10000),patch.object(
                startup_tool,'verified_loaded_modules',return_value={'gateway.run':SimpleNamespace(_gateway_runner_ref=lambda:runner)}),patch.object(
                startup_tool,'bind_broker_gateway',return_value=runtime) as binding:
            result=startup_tool.handle({'request_json':json.dumps(payload)},session_id='ignored')
        self.assertTrue(result['queued']);self.assertFalse(result['search_executed'])
        binding.assert_called_once_with(runner,owner,'/run/stroyka-jev/admission.sock')
        client.submit.assert_called_once()

    def test_legacy_writer_policy_is_not_accepted_by_new_builtin(self):
        config=parse_settings(settings())
        with patch.object(startup_tool,'load_settings',return_value=config),patch.object(
                startup_tool,'bind_broker_gateway') as binding:
            self.assertFalse(startup_tool.handle({'request_json':'{}'})['queued'])
        binding.assert_not_called()
