import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .admission_files import read_receipt
from .bootstrap_key import AdmissionSecret, read_bootstrap_key
from .ingress import OwnerBinding, owner_route
from .notification import deliver_completion
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .runtime import GatewayRuntime, WorkerRuntime, initialize_worker
from .settings import BridgeSettings
from .state import RequestConflict, Scope
from .contract import validate_v2_request

SCOPE=Scope(37,'fixture-owner')
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
RAW=json.dumps(PAYLOAD).encode();NAME=PAYLOAD['request_id']+'.json'


class RuntimeAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        inbox=root/'requests';inbox.mkdir(mode=0o700)
        admissions=root/'admissions';admissions.mkdir(mode=0o700)
        private=root/'private';private.mkdir(mode=0o700)
        public=root/'results';public.mkdir(mode=0o750);public.chmod(0o750)
        # Direct test fixture uses current UID. Production parse_settings rejects
        # gateway UID0 and requires protected settings owned by the bootstrap.
        self.settings=BridgeSettings(OwnerBinding(SCOPE,'123456789','123456789',None),
            QueueConfig(PipelineConfig(SCOPE,private,public,os.getegid()),inbox,os.geteuid()),admissions,inbox,admissions)
        self.secret=AdmissionSecret(b'synthetic-not-a-production-key-12345')
        self.epoch=10000
        self.source=SimpleNamespace(platform=SimpleNamespace(value='telegram'),chat_type='dm',
            user_id='123456789',chat_id='123456789',thread_id=None,profile=None)
        self.authorize=Mock(return_value=True)
        self.gateway=GatewayRuntime(self.settings,self.secret,authorize_source=self.authorize,
            current_source=lambda:self.source,clock=lambda:self.epoch)
        self.invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center',
            'ok':True,'url':'https://www.b2b-center.ru/app/next/market-search'}],
            'confirmed':[],'review':[]}).encode(),0))
        self.worker=WorkerRuntime(self.settings,self.secret,invoke=self.invoke,verify_runtime=Mock(),clock=lambda:self.epoch)

    def test_actual_files_connect_gateway_worker_and_completion_consumer(self):
        submitted=self.gateway.submit(RAW)
        self.assertTrue(submitted['queued']);self.assertFalse(submitted['search_executed'])
        self.assertIsNotNone(read_receipt(self.settings.worker_admissions,NAME,writer_uid=os.geteuid()))
        processed=self.worker.consume(NAME)
        self.assertEqual(processed['status'],'processed');self.invoke.assert_called_once()
        sender=Mock(return_value=json.dumps({'success':True,'platform':'telegram','chat_id':'123456789','message_id':'7'}))
        for _ in range(2):
            result=deliver_completion(self.settings.queue.pipeline.private_directory,SCOPE,processed['completion_event_id'],
                PAYLOAD['request_id'],validate_v2_request(PAYLOAD).fingerprint(37),
                route=owner_route((self.settings.owner,),SCOPE),send=sender)
            self.assertEqual(result['delivery_status'],'acknowledged')
        sender.assert_called_once()

    def test_duplicate_submission_does_not_overwrite_or_duplicate_search(self):
        self.gateway.submit(RAW)
        before=read_receipt(self.settings.worker_admissions,NAME,writer_uid=os.geteuid())
        duplicate=self.gateway.submit(RAW)
        self.assertFalse(duplicate['request_file_created'])
        self.assertEqual(read_receipt(self.settings.worker_admissions,NAME,writer_uid=os.geteuid()),before)
        self.worker.consume(NAME)
        self.gateway.submit(RAW);replayed=self.worker.consume(NAME)
        self.assertEqual(replayed['job_disposition'],'cached');self.invoke.assert_called_once()

    def test_same_id_changed_wire_cannot_invalidate_prior_admission(self):
        self.gateway.submit(RAW)
        before=read_receipt(self.settings.worker_admissions,NAME,writer_uid=os.geteuid())
        with self.assertRaises(RequestConflict):self.gateway.submit(json.dumps({**PAYLOAD,'price_min_rub':500}).encode())
        self.assertEqual(read_receipt(self.settings.worker_admissions,NAME,writer_uid=os.geteuid()),before)
        self.assertEqual((self.settings.gateway_inbox/NAME).read_bytes(),RAW)

    def test_expired_receipt_needs_fresh_gateway_authorization(self):
        self.gateway.submit(RAW);self.epoch=14000
        waiting=self.worker.consume(NAME)
        self.assertEqual(waiting['status'],'authorization_pending');self.invoke.assert_not_called()
        self.authorize.return_value=False
        with self.assertRaises(ValueError):self.gateway.submit(RAW)
        self.authorize.return_value=True
        renewed=self.gateway.submit(RAW)
        self.assertTrue(renewed['admission_renewed'])
        result=self.worker.resume(waiting['claim_handle'])
        self.assertEqual(result['status'],'processed');self.invoke.assert_called_once()

    def test_denied_sender_leaves_no_request_or_admission_files(self):
        self.authorize.return_value=False
        with self.assertRaises(ValueError):self.gateway.submit(RAW)
        self.assertEqual(list(self.settings.gateway_inbox.iterdir()),[])
        self.assertEqual(list(self.settings.gateway_admissions.iterdir()),[])

    def test_interruption_after_admission_before_request_can_be_retried(self):
        from . import admission_files
        original=admission_files._write
        def interrupt(fd,name,*args,**kwargs):
            if name==NAME:raise OSError('synthetic request write failure')
            return original(fd,name,*args,**kwargs)
        with patch('jev_agent.tender_finder.admission_files._write',side_effect=interrupt):
            with self.assertRaises(OSError):self.gateway.submit(RAW)
        self.assertFalse((self.settings.gateway_inbox/NAME).exists())
        self.gateway.submit(RAW);self.worker.consume(NAME);self.invoke.assert_called_once()

    def test_config_failure_still_closes_inherited_secret_descriptor(self):
        reader,writer=os.pipe();os.write(writer,b'x'*32);os.close(writer)
        with patch('jev_agent.tender_finder.runtime.read_bootstrap_key',side_effect=lambda fd:read_bootstrap_key(fd,expected_uid=os.geteuid())),patch('jev_agent.tender_finder.runtime.load_settings',side_effect=ValueError('bad configuration')):
            with self.assertRaises(ValueError):initialize_worker('/fixture/settings.json',reader)
        with self.assertRaises(OSError):os.fstat(reader)


if __name__=='__main__':unittest.main()
