from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from .invoker import _run_bounded
from .pipeline import PipelineConfig, run_request
from .state import Scope, StorageError, RequestConflict

SCOPE=Scope(37,'fixture-owner')
NOW=datetime(2026,10,28,tzinfo=timezone.utc)
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
SCRIPT='''import json,sys
profile=json.load(sys.stdin)
assert profile['companyId']==37
print(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,'url':'https://www.b2b-center.ru/app/next/market-search'}],
                 'confirmed':[],'review':[],'model_calls':0}))
'''


class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.public=self.root/'public';self.public.mkdir(mode=0o750);self.public.chmod(0o750)
        self.config=PipelineConfig(SCOPE,self.private,self.public,os.getegid())
        # Real, local synthetic process. Never stroyka-jev, Docker or network.
        self.invoke=Mock(side_effect=lambda call,timeout:_run_bounded((sys.executable,'-c',SCRIPT),call.stdin,5))

    def run_job(self,payload=PAYLOAD):
        return run_request(payload,self.config,invoke=self.invoke,verify_runtime=Mock(),clock=lambda:NOW)

    def test_complete_local_pipeline_replay_does_not_launch_second_process(self):
        first=self.run_job();second=self.run_job()
        self.assertEqual(first['job_disposition'],'execute')
        self.assertEqual(second['job_disposition'],'cached')
        self.assertEqual(second['publication_disposition'],'already_published')
        self.assertEqual(first['result'],second['result'])
        self.invoke.assert_called_once()
        self.assertEqual(json.loads((self.public/(PAYLOAD['request_id']+'.json')).read_bytes()),first['result'])
        self.assertEqual(len(list(self.private.glob('completion-*.json'))),1)
        self.assertIn('completion_preview',first['result'])
        self.assertFalse(first['notification_sent'])

    def test_event_write_failure_replays_receipt_without_new_search(self):
        with patch('jev_agent.tender_finder.publication._write_event',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):self.run_job()
        result=self.run_job()
        self.assertEqual(result['job_disposition'],'cached')
        self.assertEqual(result['publication_disposition'],'already_published')
        self.invoke.assert_called_once()

    def test_legacy_public_or_private_data_block_before_any_search(self):
        (self.public/'latest.json').write_text('{"legacy":true}')
        with self.assertRaisesRegex(StorageError,'legacy_result_channel_requires_review'):self.run_job()
        self.invoke.assert_not_called()
        self.assertEqual(list(self.private.iterdir()),[])
        (self.public/'latest.json').unlink()
        (self.private/'search-legacy.seen').write_text('')
        with self.assertRaisesRegex(StorageError,'legacy_private_namespace_requires_review'):self.run_job()
        self.invoke.assert_not_called()
        self.assertTrue((self.private/'search-legacy.seen').exists())

    def test_conflicting_reused_id_does_not_search_again(self):
        self.run_job()
        with self.assertRaises(RequestConflict):self.run_job({**PAYLOAD,'price_min_rub':1000000})
        self.invoke.assert_called_once()

    def test_published_result_without_receipt_does_not_trigger_replacement_search(self):
        self.run_job()
        for path in self.private.glob('ledger-*.json'):path.unlink()
        self.invoke.reset_mock()
        with self.assertRaisesRegex(StorageError,'receipt_missing'):self.run_job()
        self.invoke.assert_not_called()


if __name__=='__main__':unittest.main()
