from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from .pipeline import PipelineConfig
from .queue import QueueConfig, consume_file, pending_claims, resume_claim
from .state import Scope, RequestConflict, StorageError

SCOPE=Scope(37,'fixture-owner')
NOW=datetime(2026,10,28,tzinfo=timezone.utc)
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
NAME=PAYLOAD['request_id']+'.json'


def crash_after_claim(config):
    with patch('jev_agent.tender_finder.queue._finish',side_effect=lambda *args:os._exit(6)):
        consume_file(config,NAME,authenticate=lambda *args:True,invoke=Mock(),verify_runtime=Mock())


class QueueHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.inbox=root/'requests';self.inbox.mkdir(mode=0o700)
        self.private=root/'private';self.private.mkdir(mode=0o700)
        self.public=root/'results';self.public.mkdir(mode=0o750);self.public.chmod(0o750)
        self.config=QueueConfig(PipelineConfig(SCOPE,self.private,self.public,os.getegid()),self.inbox,os.geteuid())
        self.invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
            'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        self.auth=Mock(return_value=True)
        self.bindings={'invoke':self.invoke,'verify_runtime':Mock(),'clock':lambda:NOW}
        self.write()

    def write(self,payload=PAYLOAD):
        target=self.inbox/NAME
        target.write_text(json.dumps(payload));target.chmod(0o600)

    def consume(self,auth=None):
        return consume_file(self.config,NAME,authenticate=auth if auth is not None else self.auth,**self.bindings)

    def resume(self,handle):
        return resume_claim(self.config,handle,authenticate=self.auth,**self.bindings)

    def test_full_file_handoff_publishes_result_event_and_removes_only_claimed_file(self):
        raw=(self.inbox/NAME).read_bytes()
        out=self.consume()
        self.assertEqual(out['status'],'processed')
        self.assertFalse((self.inbox/NAME).exists())
        self.assertTrue((self.public/NAME).is_file())
        self.assertEqual(len(list(self.private.glob('completion-*.json'))),1)
        self.assertEqual(pending_claims(self.config),[])
        self.auth.assert_called_once_with(NAME,hashlib.sha256(raw).hexdigest(),SCOPE)
        self.invoke.assert_called_once()
        self.assertFalse(out['notification_sent'])

    def test_missing_provenance_does_not_execute_even_for_correct_writer_uid(self):
        self.auth.return_value=False
        out=self.consume()
        self.assertEqual(out['status'],'authorization_pending')
        self.invoke.assert_not_called()
        self.assertEqual(pending_claims(self.config),[out['claim_handle']])
        self.auth.return_value=True
        done=self.resume(out['claim_handle'])
        self.assertEqual(done['status'],'processed');self.invoke.assert_called_once()

    def test_v1_is_left_for_existing_handler_without_new_namespace_writes(self):
        self.write({key:value for key,value in {**PAYLOAD,'version':1}.items() if key!='commercial_sources'})
        (self.inbox/NAME).chmod(0o644)
        before=(self.inbox/NAME).read_bytes()
        self.assertEqual(self.consume(),{'status':'legacy_v1','handled':False})
        self.assertEqual((self.inbox/NAME).read_bytes(),before)
        self.assertEqual(list(self.private.iterdir()),[])
        self.assertEqual(list(self.public.iterdir()),[])
        self.invoke.assert_not_called();self.auth.assert_not_called()

    def test_recreated_inbox_name_is_not_deleted_by_previous_handoff(self):
        def invoke(call,timeout):
            self.write({**PAYLOAD,'keywords':['новое задание']})
            return self.invoke.return_value
        self.bindings['invoke']=invoke
        self.consume()
        self.assertEqual(json.loads((self.inbox/NAME).read_bytes())['keywords'],['новое задание'])

    def test_event_failure_recovery_uses_saved_result_without_another_search(self):
        with patch('jev_agent.tender_finder.publication._write_event',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.consume()
        handles=pending_claims(self.config);self.assertEqual(len(handles),1)
        done=self.resume(handles[0])
        self.assertEqual(done['job_disposition'],'cached')
        self.assertEqual(done['publication_disposition'],'already_published')
        self.assertEqual(pending_claims(self.config),[])
        self.invoke.assert_called_once()

    def test_original_open_descriptor_cannot_change_frozen_authorized_request(self):
        stream=open(self.inbox/NAME,'r+b');self.addCleanup(stream.close)
        self.auth.return_value=False
        out=self.consume()
        stream.seek(0);stream.write(json.dumps({**PAYLOAD,'price_min_rub':999999}).encode());stream.truncate();stream.flush()
        self.auth.return_value=True
        self.resume(out['claim_handle'])
        self.assertIsNone(json.loads((self.public/NAME).read_bytes())['filters']['price_min_rub'])

    def test_replayed_same_file_uses_cache_and_changed_payload_conflicts(self):
        self.consume();self.write();out=self.consume()
        self.assertEqual(out['job_disposition'],'cached');self.invoke.assert_called_once()
        self.write({**PAYLOAD,'price_min_rub':1000000})
        with self.assertRaises(RequestConflict):self.consume()
        self.invoke.assert_called_once()

    def test_symlink_wrong_mode_and_mismatching_id_do_not_execute(self):
        target=self.inbox/NAME;target.unlink()
        other=self.inbox/'other';other.write_text('{}')
        target.symlink_to(other)
        with self.assertRaises(OSError):self.consume()
        target.unlink();self.write();target.chmod(0o666)
        with self.assertRaises(StorageError):self.consume()
        self.write({**PAYLOAD,'request_id':'different-id'})
        with self.assertRaises(ValueError):self.consume()
        self.invoke.assert_not_called();self.auth.assert_not_called()

    def test_corrupt_private_frozen_request_is_not_resumed(self):
        self.auth.return_value=False;out=self.consume()
        frozen=next(self.private.glob('queue-request-*.json'))
        record=json.loads(frozen.read_bytes());record['scope']='0'*64
        frozen.write_text(json.dumps(record))
        with self.assertRaises(StorageError):self.resume(out['claim_handle'])
        self.invoke.assert_not_called()

    def test_process_crash_between_claim_and_freeze_is_recoverable(self):
        child=multiprocessing.get_context('fork').Process(target=crash_after_claim,args=(self.config,))
        child.start();child.join(10)
        self.assertEqual(child.exitcode,6)
        self.assertFalse((self.inbox/NAME).exists())
        handles=pending_claims(self.config);self.assertEqual(len(handles),1)
        result=self.resume(handles[0])
        self.assertEqual(result['status'],'processed')
        self.invoke.assert_called_once()
        self.assertEqual(pending_claims(self.config),[])

    def test_money_decimals_survive_wire_freeze_exactly(self):
        self.write({**PAYLOAD,'price_min_rub':1000000.25})
        result=self.consume()
        self.assertEqual(result['result']['filters']['price_min_rub'],'1000000.25')


if __name__=='__main__':unittest.main()
