import base64
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from contextlib import redirect_stdout,redirect_stderr

from . import remote_service as service
from .test_remote_transport import RemoteFixture
from .remote_transport import send_remote_completion
from .host_worker import run_host_pass

class ServiceBoundaryTests(unittest.TestCase):
    def test_role_requires_isolated_root_enabled_configuration_and_exact_ssh_peer(self):
        config={'role':'main','peer_ip':'192.0.2.10','enabled':True}
        with patch.object(service.os,'geteuid',return_value=0),patch.object(service.sys,'flags',SimpleNamespace(isolated=True)),patch.object(service,'protected_json',return_value=config),patch.dict(service.os.environ,{'SSH_CONNECTION':'192.0.2.10 12345 192.0.2.20 22','SSH_ORIGINAL_COMMAND':''},clear=True):
            self.assertEqual(service.require_role('main',ssh=True),config)
            for change in ({'SSH_CONNECTION':'192.0.2.11 12345 192.0.2.20 22'},{'SSH_ORIGINAL_COMMAND':'id'},{'SSH_CONNECTION':''}):
                with patch.dict(service.os.environ,change),self.assertRaises(ValueError):service.require_role('main',ssh=True)
            with self.assertRaises(ValueError):service.require_role('gateway')
            config['enabled']=False
            with self.assertRaises(ValueError):service.require_role('main',ssh=True)
        with patch.object(service.os,'geteuid',return_value=10000),patch.object(service,'protected_json') as reader,self.assertRaises(ValueError):service.require_role('main')
        reader.assert_not_called()

    def test_disabled_or_wrong_ssh_receiver_cannot_read_frame_or_key(self):
        for mode in ('receive','send'):
            with patch.object(service,'require_role',side_effect=ValueError('SECRET')),patch.object(service,'load') as key,patch.object(service.sys,'stdin') as stdin,redirect_stdout(io.StringIO()) as output:
                self.assertEqual(service.main([mode]),1)
            key.assert_not_called();stdin.buffer.read.assert_not_called()
            self.assertNotIn('SECRET',output.getvalue())

    def test_cli_cannot_select_executable_extra_flags_credentials_or_oversized_input(self):
        good={'op':'cli','argv':['eis-search','--query','кровля','--stavropol-open'],'stdin_b64':''}
        argv,data=service.cli_arguments(good)
        self.assertEqual(argv[0],'/usr/local/bin/stroyka-jev');self.assertIsNone(data)
        for words in (['sh','-c','id'],['commercial-search','--url','https://evil'],['status','--profile-stdin'],['eis-search','--query','x\ny'],['status','--notice','https://evil']):
            with redirect_stderr(io.StringIO()),self.subTest(words=words),self.assertRaises(ValueError):service.cli_arguments({**good,'argv':words})
        with self.assertRaises(ValueError):service.cli_arguments({**good,'stdin_b64':base64.b64encode(b'secret').decode()})
        with self.assertRaises(ValueError):service.cli_arguments({**good,'argv':['commercial-search','--profile-stdin'],'stdin_b64':base64.b64encode(b'x'*32769).decode()})

    def test_forbidden_controller_operation_never_launches_a_process(self):
        for request in ({'operation':'watchdog'},{'operation':'shell','command':'id'}, {'operation':'health','url':'https://evil'}, {'operation':'avito','query':'bad\nquery'}):
            with patch.object(service,'_run_bounded') as run,self.subTest(request=request),self.assertRaises(ValueError):service.execute_control({'op':'control','request':request})
            run.assert_not_called()

    def test_receiver_uses_its_own_policy_instead_of_supplied_tenant(self):
        frame={'op':'admit','protocol':2,'wire':'','company_id':99}
        with patch.object(service,'require_role'),patch.object(service.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(json.dumps(frame).encode()))),patch.object(service,'load') as load,self.assertRaises(ValueError):service.receive()
        load.assert_not_called()

    def test_source_send_target_is_checked_by_existing_docker_sender_before_execution(self):
        from .docker_delivery import DockerHermesSender
        from .ingress import OwnerBinding
        from .state import Scope
        owner=OwnerBinding(Scope(37,'fixture-owner'),'123456789','123456789',None)
        run=Mock()
        sender=DockerHermesSender(owner,gateway_uid=10000,gateway_gid=10000,_run=run)
        with patch('os.geteuid',return_value=0),self.assertRaises(ValueError):
            sender({'action':'send','target':'telegram:987654321','message':'<b>JEV</b>\nfixture'})
        run.assert_not_called()

    def test_worker_lock_excludes_second_executor_and_releases_after_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            settings=SimpleNamespace(queue=SimpleNamespace(pipeline=SimpleNamespace(private_directory=Path(folder))))
            with service.exclusive_worker(settings):
                with self.assertRaises(BlockingIOError):
                    with service.exclusive_worker(settings):pass
            with service.exclusive_worker(settings):pass

class RemoteCompletionTests(RemoteFixture):
    def test_actual_transport_send_is_reserved_once_when_ack_is_lost(self):
        self.admit()
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
          'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        remote=Mock(side_effect=TimeoutError())
        def deliver(*args,**kwargs):return send_remote_completion(*args,**kwargs,remote=remote)
        for _ in range(2):run_host_pass(self.settings,self.secret,gateway_gid=10000,invoke=invoke,verify_runtime=Mock(),deliver=deliver)
        remote.assert_called_once()
        destination,frame=remote.call_args.args
        self.assertEqual(destination,'gateway');self.assertEqual(frame['op'],'send')
        self.assertEqual(frame['args']['target'],'telegram:123456789')
        self.assertNotIn('secret',json.dumps(frame));invoke.assert_called_once()

class CommercialWorkerAssemblyTests(unittest.TestCase):
    def test_worker_executes_with_the_same_validated_commercial_policy_instance(self):
        from dataclasses import replace
        from .commercial import test_bridge as fixture_module
        from .commercial.bridge import CommercialBridge
        from .commercial.contract import validate_request
        from contextlib import ExitStack
        import threading
        fixture=fixture_module.BridgeTests()
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.submit()
        def read_policy(protocol):
            self.assertEqual(protocol,3)
            settings=replace(fixture.settings)
            return settings,validate_request,SimpleNamespace(bridge=settings)
        def build(configuration,secret,**kwargs):
            return CommercialBridge(configuration.bridge,secret,fixture.paths['registry'],
                sources=fixture.bridge.sources,adapters=fixture.bridge.adapters)
        stop=threading.Event()
        with ExitStack() as stack:
            stack.enter_context(patch.object(service,'require_role'))
            reader=stack.enter_context(patch.object(service,'policy',side_effect=read_policy))
            stack.enter_context(patch.object(service,'credential_pipe',return_value=12))
            stack.enter_context(patch.object(service,'read_bootstrap_key',return_value=fixture.secret))
            stack.enter_context(patch.object(service,'verify_installed_runtime'))
            stack.enter_context(patch.object(service,'_signals'))
            stack.enter_context(patch.object(service.threading,'Event',return_value=stop))
            stack.enter_context(patch.object(stop,'wait',side_effect=lambda _:stop.set()))
            stack.enter_context(patch('jev_agent.tender_finder.commercial.systemd_bootstrap.verify_document_runtime'))
            stack.enter_context(patch('jev_agent.tender_finder.commercial.runtime_config.build_bridge',side_effect=build))
            stack.enter_context(patch('jev_agent.tender_finder.host_worker.time.time',fixture_module.EPOCH))
            sender=stack.enter_context(patch.object(service,'send_remote_completion',return_value={'delivery_status':'acknowledged'}))
            stack.enter_context(redirect_stdout(io.StringIO()))
            service.worker(3)
        fixture.reader.assert_called_once()
        sender.assert_called_once()
        self.assertEqual(reader.call_count,1)

if __name__=='__main__':unittest.main()
