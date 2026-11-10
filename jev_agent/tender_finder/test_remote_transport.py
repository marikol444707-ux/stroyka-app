"""Offline migration boundaries: no real SSH, credentials, providers or messages."""
import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .admission_broker import GatewayPeer
from .bootstrap_key import AdmissionSecret
from .contract import validate_v2_request
from .ingress import OwnerBinding, owner_route
from .host_worker import run_host_pass
from .notification import deliver_completion
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .settings import BridgeSettings
from .state import Scope
from .remote_transport import (RelayBroker, admit_remote, decode_frame, exchange,
                               legacy_call, receive_frame, send_remote_completion)

PAYLOAD={'version':2,'request_id':'remote-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}

class RemoteFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name).resolve()
        for n in ('inbox','private','results','admissions'):(root/n).mkdir(mode=0o700)
        (root/'results').chmod(0o750)
        self.owner=OwnerBinding(Scope(37,'fixture-owner'),'123456789','123456789',None)
        self.settings=BridgeSettings(self.owner,QueueConfig(PipelineConfig(self.owner.scope,root/'private',root/'results',os.getegid()),root/'inbox',os.geteuid()),root/'admissions',root/'inbox',root/'admissions',10000)
        self.secret=AdmissionSecret(b'synthetic-only-remote-key-123456789')
        self.peer=GatewayPeer(123,10000,10000,456)
        self.raw=json.dumps(PAYLOAD).encode()
        self.wire=self.frame(self.raw)

    def frame(self,raw,**origin):
        return json.dumps({'version':1,'request_b64':base64.b64encode(raw).decode(),
            'origin':{'platform':'telegram','chat_type':'dm','chat_id':'123456789',
                      'user_id':'123456789','profile':None,**origin}}).encode()

    def admit(self,wire=None):
        return admit_remote(self.settings,self.secret,self.wire if wire is None else wire,
                            request_validator=validate_v2_request,clock=lambda:int(time.time()))

class RemoteTests(RemoteFixture):
    def test_remote_admission_preserves_owner_and_duplicate_identity(self):
        first=self.admit();second=self.admit()
        self.assertTrue(first['queued']);self.assertTrue(first['request_file_created'])
        self.assertFalse(second['request_file_created'])
        self.assertEqual((self.settings.queue.inbox/'remote-fixture-001.json').read_bytes(),self.raw)
        self.assertNotIn('signature',json.dumps(first))
        with self.assertRaises(ValueError):self.admit(self.frame(json.dumps({**PAYLOAD,'limit':1}).encode()))

    def test_foreign_company_user_chat_profile_and_group_are_rejected_before_write(self):
        cases=[self.frame(self.raw,user_id='987654321'),self.frame(self.raw,chat_id='987654321'),
               self.frame(self.raw,profile='foreign'),self.frame(self.raw,chat_type='group'),
               self.frame(json.dumps({**PAYLOAD,'company_id':99}).encode())]
        for wire in cases:
            with self.subTest(wire=wire),self.assertRaises(ValueError):self.admit(wire)
        self.assertEqual(list(self.settings.queue.inbox.iterdir()),[])
        self.assertEqual(list(self.settings.worker_admissions.iterdir()),[])

    def test_relay_checks_kernel_peer_twice_and_never_owns_a_signing_key(self):
        remote=Mock(return_value={'queued':True})
        broker=RelayBroker(self.peer,2,remote)
        connection=Mock()
        with patch.object(GatewayPeer,'permits',return_value=False):
            self.assertFalse(broker.serve_connection(connection))
        remote.assert_not_called()
        with patch.object(GatewayPeer,'permits',side_effect=[True,False]),patch(
                'jev_agent.tender_finder.admission_broker._read_frame',return_value=self.wire):
            self.assertFalse(broker.serve_connection(connection))
        remote.assert_not_called()
        with patch.object(GatewayPeer,'permits',return_value=True),patch(
                'jev_agent.tender_finder.admission_broker._read_frame',return_value=self.wire):
            self.assertTrue(broker.serve_connection(connection))
        self.assertEqual(remote.call_args.args[0],{'op':'admit','protocol':2,'wire':base64.b64encode(self.wire).decode()})
        self.assertFalse(any('secret' in k or 'key' in k for k in vars(broker)))

    def test_transport_loss_reports_no_confirmation_and_does_not_retry(self):
        runner=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):exchange('main',{'op':'ping'},_run=runner)
        runner.assert_called_once()
        remote=Mock(side_effect=TimeoutError('not printable secret'))
        broker=RelayBroker(self.peer,2,remote);connection=Mock()
        with patch.object(GatewayPeer,'permits',return_value=True),patch(
                'jev_agent.tender_finder.admission_broker._read_frame',return_value=self.wire):
            self.assertFalse(broker.serve_connection(connection))
        self.assertNotIn(b'not printable',connection.sendall.call_args.args[0])

    def test_ssh_has_fixed_destination_command_and_input_is_never_shell_text(self):
        runner=Mock(return_value=(b'{"ok":true}',0))
        value={'op':'ping','untrusted':'$(touch /tmp/no); `id`'}
        self.assertEqual(exchange('main',value,_run=runner),{'ok':True})
        argv,stdin,timeout=runner.call_args.args
        self.assertEqual(argv[-1],'jev-main')
        self.assertNotIn(value['untrusted'],' '.join(argv));self.assertEqual(json.loads(stdin),value)
        self.assertIn('StrictHostKeyChecking=yes',argv)
        with self.assertRaises(ValueError):exchange('anything',value,_run=runner)
        runner.return_value=(b'{"ok":true}',255)
        with self.assertRaises(ValueError):exchange('main',value,_run=runner)

    def test_frames_reject_duplicates_large_messages_nan_and_wrong_protocol(self):
        for raw in (b'{"op":"ping","op":"admit"}',b'{"x":NaN}',b'[]',b'x'*70000):
            with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):decode_frame(raw)
        for frame in ({'op':'admit','protocol':True,'wire':''},{'op':'admit','protocol':1,'wire':''},
                      {'op':'admit','protocol':2,'wire':'?','command':'id'}, {'op':'shell','command':'id'}):
            load=Mock()
            with self.subTest(frame=frame),self.assertRaises(ValueError):receive_frame(frame,load=load)
            load.assert_not_called()

    def test_lost_admission_ack_replay_does_not_repeat_search_or_send(self):
        self.admit() # main committed, SSH response lost
        self.admit() # original request retried
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
          'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        sender=Mock(return_value=json.dumps({'success':True,'platform':'telegram','chat_id':'123456789','message_id':7}))
        def deliver(settings,event,identifier,fingerprint,*,gateway_gid):
            return deliver_completion(settings.queue.pipeline.private_directory,settings.owner.scope,event,identifier,fingerprint,
                                      route=owner_route((settings.owner,),settings.owner.scope),send=sender)
        kwargs=dict(gateway_gid=10000,invoke=invoke,verify_runtime=Mock(),deliver=deliver,epoch=lambda:int(time.time()))
        first=run_host_pass(self.settings,self.secret,**kwargs)
        self.assertEqual(first['processed'],1);self.assertEqual(first['acknowledged'],1)
        self.admit();run_host_pass(self.settings,self.secret,**kwargs)
        invoke.assert_called_once();sender.assert_called_once()

    def test_uncertain_remote_send_is_never_retried_after_restart(self):
        self.admit();sender=Mock(side_effect=TimeoutError())
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
          'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        def deliver(settings,event,identifier,fingerprint,*,gateway_gid):
            return deliver_completion(settings.queue.pipeline.private_directory,settings.owner.scope,event,identifier,fingerprint,
                                      route=owner_route((settings.owner,),settings.owner.scope),send=sender)
        kwargs=dict(gateway_gid=10000,invoke=invoke,verify_runtime=Mock(),deliver=deliver,epoch=lambda:int(time.time()))
        self.assertEqual(run_host_pass(self.settings,self.secret,**kwargs)['unknown'],1)
        run_host_pass(self.settings,self.secret,**kwargs)
        sender.assert_called_once();invoke.assert_called_once()

    def test_legacy_adapter_only_allows_fixed_cli_operations(self):
        executable='/usr/local/bin/stroyka-jev'
        self.assertEqual(legacy_call([executable,'commercial-search']),{'op':'legacy','kind':'commercial'})
        self.assertEqual(legacy_call([executable,'eis-search','--query','кровля','--stavropol-open']),
                         {'op':'legacy','kind':'eis','query':'кровля'})
        for argv in (['sh','-c','id'],[executable,'commercial-search','--url','https://evil'],
                     [executable,'eis-search','--query','bad\nquery','--stavropol-open']):
            with self.assertRaises(ValueError):legacy_call(argv)

if __name__=='__main__':unittest.main()
