"""Lifecycle ordering and refusal gates; no live service, credentials or sends."""
from contextlib import ExitStack,redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import systemd_bootstrap as boot
from .runtime_config import parse_runtime
from .test_runtime_config import policies
from ..settings import parse_settings
from ..bootstrap_key import AdmissionSecret


def policy():
    old,value=policies();base=str(boot.STATE)
    value['bridge']['worker']={'inbox':base+'/requests','private':base+'/private',
                              'results':base+'/results','admissions':base+'/admissions'}
    value['registry_directory']=base+'/registry'
    return parse_runtime(value,legacy=parse_settings(old))


class PolicyTests(unittest.TestCase):
    def test_fixed_namespace_and_key_free_gateway_policy_must_match(self):
        current=policy()
        with patch.object(boot,'load_runtime',return_value=current),patch.object(boot,'load_gateway_policy',return_value=current.bridge):
            self.assertIs(boot.runtime_policy(),current)
        wrong=replace(current,registry_directory=Path('/var/lib/stroyka-jev/v2/private'))
        with patch.object(boot,'load_runtime',return_value=wrong),patch.object(boot,'load_gateway_policy',return_value=current.bridge):
            with self.assertRaises(ValueError):boot.runtime_policy()

    def test_browser_mode_is_not_silently_enabled_without_reviewed_opener(self):
        current=replace(policy(),enabled_sources=('b2b',))
        with patch.object(boot,'load_runtime',return_value=current),patch.object(boot,'load_gateway_policy',return_value=current.bridge):
            with self.assertRaises(ValueError):boot.runtime_policy()

    def test_arbitrary_python_runtime_is_not_accepted(self):
        with patch('sys.prefix','/tmp/untrusted-python'),self.assertRaises(ValueError):boot.verify_document_runtime()


class LifecycleTests(unittest.TestCase):
    def run_boot(self,*,failure=None,pid=321):
        current=policy();events=[];listener=Mock();peer=SimpleNamespace(pid=pid,uid=10000,gid=10000)
        secret=AdmissionSecret(b'fixture-commercial-root-key-123456')
        host=Mock();bridge=Mock();calls={}
        def call(name,result=None):
            def execute(*args,**kwargs):
                events.append(name)
                if failure==name:raise ValueError('PRIVATE_TOKEN')
                return result
            return Mock(side_effect=execute)
        functions={'runtime_policy':call('policy',current),'validate_state':call('state'),
            'verify_document_runtime':call('runtime'),'inherited_listener':call('listener',listener),
            'discover_gateway_peer':call('peer',peer),'credential_pipe':call('credential',9),
            'read_bootstrap_key':call('key',secret),'build_bridge':call('bridge',bridge),
            'ConnectedHost':call('host',host)}
        output=io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch('os.geteuid',return_value=0))
            stack.enter_context(patch.object(boot.signal,'signal',return_value=None))
            for name,function in functions.items():stack.enter_context(patch.object(boot,name,function))
            with redirect_stdout(output):code=boot.main([])
        self.assertNotIn('PRIVATE_TOKEN',output.getvalue())
        return code,events,functions,listener,host,output.getvalue()

    def test_failed_attestation_never_reads_credential(self):
        for stage in ('policy','state','runtime','listener','peer'):
            with self.subTest(stage=stage):
                code,events,functions,listener,host,_=self.run_boot(failure=stage)
                self.assertEqual(code,1);functions['credential_pipe'].assert_not_called()
                functions['read_bootstrap_key'].assert_not_called();host.serve.assert_not_called()
                if stage=='peer':listener.close.assert_called_once()

    def test_verified_startup_uses_own_credential_and_named_listener(self):
        code,events,functions,listener,host,_=self.run_boot()
        self.assertEqual(code,0)
        self.assertLess(events.index('peer'),events.index('credential'))
        functions['credential_pipe'].assert_called_once_with(_path=boot.CREDENTIAL)
        self.assertEqual(functions['inherited_listener'].call_args.kwargs['listener_name'],'commercial')
        self.assertEqual(functions['inherited_listener'].call_args.kwargs['listener_path'],boot.SOCKET)
        self.assertIn('commercial_bridge',functions['ConnectedHost'].call_args.kwargs)
        host.serve.assert_called_once();listener.close.assert_called_once()

    def test_each_new_start_rediscovers_peer_instead_of_reusing_old_pid(self):
        first=self.run_boot(pid=321);second=self.run_boot(pid=654)
        self.assertEqual(first[0],0);self.assertEqual(second[0],0)
        first[2]['discover_gateway_peer'].assert_called_once()
        second[2]['discover_gateway_peer'].assert_called_once()
        self.assertEqual(first[2]['ConnectedHost'].call_args.args[2].pid,321)
        self.assertEqual(second[2]['ConnectedHost'].call_args.args[2].pid,654)

    def test_nonroot_and_extra_arguments_do_not_read_policy(self):
        for uid,args in ((12345,[]),(0,['--key','fake'])):
            with patch('os.geteuid',return_value=uid),patch.object(boot,'runtime_policy') as load,redirect_stdout(io.StringIO()):
                self.assertEqual(boot.main(args),1)
            load.assert_not_called()
