import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from .admission_files import publish_admission
from .bootstrap_key import AdmissionSecret
from .host_worker import pending_completions,run_host_pass
from .ingress import OwnerBinding,issue_admission,owner_route
from .notification import deliver_completion
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .settings import BridgeSettings
from .state import Scope
import time

PAYLOAD={'version':2,'request_id':'search-host-pass-fixture','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
RAW=json.dumps(PAYLOAD).encode()
SCOPE=Scope(37,'fixture-owner')


class HostPassTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        for name in ('inbox','admissions','private','results'):(root/name).mkdir(mode=0o700)
        (root/'results').chmod(0o750)
        self.owner=OwnerBinding(SCOPE,'123456789','123456789',None)
        self.settings=BridgeSettings(self.owner,QueueConfig(PipelineConfig(SCOPE,root/'private',root/'results',os.getegid()),
            root/'inbox',os.geteuid()),root/'admissions',root/'inbox',root/'admissions',os.geteuid())
        self.secret=AdmissionSecret(b'synthetic-host-only-key-1234567890')
        source=SimpleNamespace(platform='telegram',chat_type='dm',chat_id=self.owner.reply_chat_id,
                               user_id=self.owner.telegram_user_id,profile=None,thread_id=None)
        receipt=issue_admission(RAW,source,authorize_source=lambda source:True,bindings=(self.owner,),
            signing_key=self.secret.material,clock=lambda:int(time.time()))
        publish_admission(RAW,receipt,self.settings,self.secret,clock=lambda:int(time.time()))
        self.invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
            'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        self.sender=Mock(return_value=json.dumps({'success':True,'platform':'telegram','chat_id':'123456789','message_id':'7'}))

    def deliver(self,settings,event,identifier,fingerprint,*,gateway_gid):
        return deliver_completion(settings.queue.pipeline.private_directory,SCOPE,event,identifier,fingerprint,
            route=owner_route((self.owner,),SCOPE),send=self.sender)

    def run_pass(self,deliver=None):
        return run_host_pass(self.settings,self.secret,gateway_gid=10000,invoke=self.invoke,
                             verify_runtime=Mock(),deliver=deliver or self.deliver)

    def test_real_admission_queue_search_receipt_event_and_delivery_connected(self):
        first=self.run_pass();second=self.run_pass()
        self.assertEqual(first['processed'],1);self.assertEqual(first['acknowledged'],1)
        self.assertEqual(first['errors'],0);self.assertFalse(first['human_read_verified'])
        self.assertEqual(second['processed'],0);self.assertEqual(second['acknowledged'],0)
        self.invoke.assert_called_once();self.sender.assert_called_once()
        self.assertEqual(pending_completions(self.settings),[])

    def test_restart_after_result_before_delivery_recovers_without_search(self):
        first=self.run_pass(deliver=Mock(side_effect=RuntimeError('interrupted before send')))
        self.assertEqual(first['errors'],1);self.sender.assert_not_called()
        second=self.run_pass()
        self.assertEqual(second['processed'],0);self.assertEqual(second['acknowledged'],1)
        self.invoke.assert_called_once();self.sender.assert_called_once()

    def test_timeout_is_cached_unknown_and_not_sent_again(self):
        self.sender.side_effect=TimeoutError('PRIVATE_TOKEN')
        first=self.run_pass();second=self.run_pass()
        self.assertEqual(first['unknown'],1);self.assertEqual(second['unknown'],0)
        self.assertNotIn('PRIVATE',json.dumps(first));self.assertNotIn('PRIVATE',json.dumps(second))
        self.invoke.assert_called_once();self.sender.assert_called_once()

    def test_invalid_mac_keeps_pending_without_search_or_send(self):
        receipt=next(self.settings.worker_admissions.glob('*.auth.json'))
        data=json.loads(receipt.read_bytes());data['signature']='0'*64;receipt.write_text(json.dumps(data));receipt.chmod(0o600)
        first=self.run_pass();self.assertEqual(first['authorization_pending'],1)
        self.assertEqual(first['processed'],0);self.invoke.assert_not_called();self.sender.assert_not_called()

    def test_stop_between_search_and_delivery_recovers_without_repeating_search(self):
        stop=[]
        response=self.invoke.return_value
        self.invoke.side_effect=lambda *args:(stop.append(True) or response)
        first=run_host_pass(self.settings,self.secret,gateway_gid=10000,invoke=self.invoke,
            verify_runtime=Mock(),deliver=self.deliver,should_stop=lambda:bool(stop))
        self.assertEqual(first['processed'],1);self.assertEqual(first['acknowledged'],0)
        self.sender.assert_not_called()
        self.assertEqual(self.run_pass()['acknowledged'],1)
        self.invoke.assert_called_once();self.sender.assert_called_once()

    def test_model_json_cannot_supply_delivery_handles_or_other_scope(self):
        self.run_pass(deliver=Mock(side_effect=RuntimeError('not delivered')))
        event=next(self.settings.queue.pipeline.private_directory.glob('completion-*.json'))
        value=json.loads(event.read_bytes());value['scope']='other-scope';event.write_text(json.dumps(value));event.chmod(0o600)
        with self.assertRaises(ValueError):pending_completions(self.settings)
        self.sender.assert_not_called();self.invoke.assert_called_once()
