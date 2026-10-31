"""Protected policy and real durable host pass, entirely offline/no real sender."""
from dataclasses import replace
from copy import deepcopy
import json
import base64
import os
from pathlib import Path
import tempfile
import socket
import threading
import unittest
from unittest.mock import Mock,patch

from .runtime_config import parse_runtime,load_runtime,build_bridge,initialize_commercial_host,validate_gateway_pair
from . import test_bridge as fixtures
from .test_bridge import PAYLOAD,EPOCH,SOURCE
from .test_commercial import NOW
from ..bootstrap_key import AdmissionSecret
from ..host_worker import run_host_pass
from ..host_service import ConnectedHost
from ..admission_broker import GatewayPeer,process_start_ticks,BrokerClient
from ..notification import deliver_completion
from ..ingress import owner_route
from ..settings import parse_settings
from ..test_settings import settings
from ..state import StorageError


def policies():
    old={**settings(),'schema_version':2,'writer_uid':0,'gateway_uid':10000}
    new=deepcopy(old)
    new['worker']={key:'/fixture/commercial/host/'+key for key in old['worker']}
    new['gateway']={key:'/fixture/commercial/container/'+key for key in old['gateway']}
    value={'format':1,'protocol':3,'bridge':new,'registry_directory':'/fixture/commercial/registry',
        'profile':{'legal_entity':None,'qualifications':[]},'enabled_sources':['step','federation','rtender']}
    return old,value


class PolicyTests(unittest.TestCase):
    def test_v3_is_explicit_and_preserves_verified_legacy_owner_without_mutation(self):
        old,value=policies();legacy=parse_settings(old);policy=parse_runtime(value,legacy=legacy)
        self.assertEqual(legacy.queue.pipeline.protocol,2)
        self.assertEqual(policy.bridge.queue.pipeline.protocol,3)
        self.assertEqual(policy.bridge.owner,legacy.owner)
        self.assertNotIn('123456789',repr(policy))
        self.assertEqual(policy.enabled_sources,('step','federation','rtender'))

    def test_company_recipient_gateway_and_private_namespace_cannot_be_adopted(self):
        old,base=policies();legacy=parse_settings(old)
        for field,wrong in (('company_id',1),('telegram_user_id','987654321'),('gateway_uid',9999)):
            value=deepcopy(base);value['bridge'][field]=wrong
            with self.subTest(field=field),self.assertRaises(ValueError):parse_runtime(value,legacy=legacy)
        for location in (old['worker']['private'],old['worker']['private']+'/nested','/fixture'):
            value=deepcopy(base);value['registry_directory']=location
            with self.assertRaises(ValueError):parse_runtime(value,legacy=legacy)

    def test_no_keys_commands_arbitrary_profiles_or_inferred_qualifications(self):
        old,base=policies();legacy=parse_settings(old)
        for key in ('key','command','factory','company_id'):
            with self.assertRaises(ValueError):parse_runtime({**base,key:'fake'},legacy=legacy)
        for profile in ({'legal_entity':{'command':'fake'},'qualifications':[]},
                        {'legal_entity':None,'qualifications':['construction_sro']},
                        {'legal_entity':'ООО Пример','qualifications':['unknown']}):
            with self.assertRaises(ValueError):parse_runtime({**base,'profile':profile},legacy=legacy)
        value={**base,'profile':{'legal_entity':'ООО Пример','qualifications':['construction_sro']}}
        parsed=parse_runtime(value,legacy=legacy)
        self.assertEqual(parsed.profile.qualifications,frozenset({'construction_sro'}))

    def test_enabling_browser_reader_requires_explicit_protected_factory(self):
        old,value=policies();value['enabled_sources']=['b2b']
        policy=parse_runtime(value,legacy=parse_settings(old))
        with self.assertRaisesRegex(ValueError,'browser_factory_required'):
            build_bridge(policy,AdmissionSecret(b'x'*32),clock=lambda:NOW)

    def test_host_and_gateway_configuration_must_agree_on_the_exact_namespace(self):
        old,value=policies();policy=parse_runtime(value,legacy=parse_settings(old))
        validate_gateway_pair(policy,policy.bridge)
        wrong=replace(policy.bridge,gateway_inbox=Path('/fixture/other/inbox'))
        with self.assertRaises(ValueError):validate_gateway_pair(policy,wrong)

    def test_native_assembly_does_not_start_search_browser_or_notification(self):
        old,value=policies();policy=parse_runtime(value,legacy=parse_settings(old))
        with tempfile.TemporaryDirectory() as directory:
            policy=replace(policy,registry_directory=Path(directory))
            with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
                bridge=build_bridge(policy,AdmissionSecret(b'x'*32),clock=lambda:NOW)
            self.assertEqual(set(bridge.adapters),{'step','federation','rtender'})
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_private_load_checks_permissions_and_legacy_before_assembly(self):
        old,value=policies()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prior=root/'old';new=root/'new';prior.mkdir();new.mkdir()
            legacy=prior/'bridge.json';legacy.write_text(json.dumps(old));legacy.chmod(0o600)
            path=new/'runtime.json';path.write_text(json.dumps(value));path.chmod(0o600)
            args={'trusted_root':new,'legacy_policy':legacy,'legacy_root':prior,'expected_uid':os.geteuid()}
            self.assertEqual(load_runtime(path,**args).bridge.queue.pipeline.protocol,3)
            path.chmod(0o666)
            with self.assertRaises(StorageError):load_runtime(path,**args)
            path.chmod(0o600);alias=new/'alias.json';alias.symlink_to(path)
            with self.assertRaises(StorageError):load_runtime(alias,**args)

    def test_nonroot_initializer_closes_descriptor_without_reading_key_or_policy(self):
        reader,writer=os.pipe()
        try:
            with patch('os.geteuid',return_value=12345),patch('jev_agent.tender_finder.commercial.runtime_config.load_runtime') as load:
                with self.assertRaises(ValueError):initialize_commercial_host('/fake',reader,None)
            load.assert_not_called()
            with self.assertRaises(OSError):os.fstat(reader)
        finally:os.close(writer)


class HostPassTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.BridgeTests('test_signed_owner_queue_report_and_telegram_ack_once')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.submit();self.sender=Mock(return_value=json.dumps({
            'success':True,'platform':'telegram','chat_id':'123456789','message_id':'7'}))

    def deliver(self,settings,event,identifier,fingerprint,*,gateway_gid):
        return deliver_completion(settings.queue.pipeline.private_directory,settings.owner.scope,event,identifier,fingerprint,
                                  route=owner_route((settings.owner,),settings.owner.scope),send=self.sender)

    def run_pass(self,**kwargs):
        f=self.fixture
        return run_host_pass(f.settings,f.secret,gateway_gid=10000,commercial_bridge=f.bridge,
                             epoch=EPOCH,clock=lambda:NOW,deliver=self.deliver,**kwargs)

    def test_real_signed_queue_result_and_delivery_run_once_through_host_pass(self):
        first=self.run_pass();second=self.run_pass()
        self.assertEqual(first['processed'],1);self.assertEqual(first['acknowledged'],1)
        self.assertEqual(first['errors'],0);self.assertEqual(second['processed'],0)
        self.fixture.reader.assert_called_once();self.sender.assert_called_once()

    def test_uncertain_send_is_not_repeated_after_host_restart(self):
        self.sender.side_effect=TimeoutError('PRIVATE_TOKEN')
        first=self.run_pass();second=self.run_pass()
        self.assertEqual(first['unknown'],1);self.assertEqual(second['unknown'],0)
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(first));self.sender.assert_called_once()
        self.fixture.reader.assert_called_once()

    def test_v3_cannot_fall_back_to_v2_host_or_legacy_invoker(self):
        f=self.fixture
        with self.assertRaises(ValueError):run_host_pass(f.settings,f.secret,gateway_gid=10000)
        with self.assertRaises(ValueError):self.run_pass(invoke=Mock())
        self.fixture.reader.assert_not_called();self.sender.assert_not_called()

    def test_connected_service_binds_commercial_validator_explicitly(self):
        f=self.fixture
        f.settings=replace(f.settings,gateway_uid=os.geteuid())
        f.bridge.settings=f.settings
        peer=GatewayPeer(os.getpid(),os.geteuid(),os.getegid(),process_start_ticks(os.getpid()))
        with self.assertRaises(ValueError):ConnectedHost(f.settings,f.secret,peer)
        host=ConnectedHost(f.settings,f.secret,peer,commercial_bridge=f.bridge)
        self.assertTrue(host.broker._admit(json.dumps({'version':1,'request_b64':base64.b64encode(
            json.dumps({**PAYLOAD,'request_id':'commercial-new-fixture'}).encode()).decode(),
            'origin':{'platform':'telegram','chat_type':'dm','chat_id':SOURCE.chat_id,'user_id':SOURCE.user_id,'profile':None}}).encode())['queued'])

    def test_real_unix_rpc_wakes_commercial_pipeline_and_stops_cleanly(self):
        f=self.fixture;f.settings=replace(f.settings,gateway_uid=os.geteuid());f.bridge.settings=f.settings
        peer=GatewayPeer(os.getpid(),os.geteuid(),os.getegid(),process_start_ticks(os.getpid()))
        root=f.paths['inbox'].parent;path=root/'commercial.sock'
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.addCleanup(listener.close)
        listener.bind(str(path));listener.listen(4);path.chmod(0o600)
        idle=threading.Event();done=threading.Event();stop=threading.Event();errors=[]
        def emit(summary):
            if not summary.get('processed') and not summary.get('acknowledged'):idle.set()
            if f.reader.call_count>=2 and self.sender.call_count>=2:done.set()
        host=ConnectedHost(f.settings,f.secret,peer,commercial_bridge=f.bridge,epoch=EPOCH,
                           clock=lambda:NOW,_run_pass=self.run_pass,_emit_summary=emit)
        def serve():
            try:host.serve(listener,stop)
            except Exception as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=serve);thread.start()
        def finish():
            stop.set();thread.join(6)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.addCleanup(finish)
        self.assertTrue(idle.wait(5))
        client=BrokerClient(path,expected_server_uid=os.geteuid(),_trusted_directory=root)
        queued=client.submit(json.dumps({**PAYLOAD,'request_id':'commercial-socket-fixture'}).encode(),SOURCE)
        self.assertTrue(queued['queued']);self.assertTrue(done.wait(5))
        self.assertEqual(f.reader.call_count,2);self.assertEqual(self.sender.call_count,2)

