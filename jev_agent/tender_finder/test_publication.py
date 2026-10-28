import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from .contract import validate_v2_request
from .jobs import process_request
from .publication import publish_committed_result
from .state import RequestConflict, RequestLedger, Scope, StorageError

SCOPE=Scope(37,'fixture-owner')
ID='search-fixture-001'
PAYLOAD={'version':2,'request_id':ID,'region':'Ставропольский край',
         'sources':['commercial'],'topics':['кровля'],'commercial_sources':['B2B-Center']}
FINGERPRINT=validate_v2_request(PAYLOAD).fingerprint(SCOPE.company_id)


def crash_before_event(private, public, group):
    with patch('jev_agent.tender_finder.publication._write_event',side_effect=lambda *args:os._exit(7)):
        publish_committed_result(private,SCOPE,public,ID,FINGERPRINT,result_gid=group)


class PublicationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.private=self.root/'private';self.private.mkdir(mode=0o700)
        self.public=self.root/'public';self.public.mkdir(mode=0o750);self.public.chmod(0o750)
        self.invoker=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True}],
                                                  'confirmed':[],'review':[]}).encode(),0))

    def execute(self):
        return process_request(PAYLOAD,SCOPE,self.private,invoke=self.invoker,verify_runtime=Mock())

    def publish(self, **changes):
        return publish_committed_result(self.private,changes.get('scope',SCOPE),self.public,ID,
                                        changes.get('fingerprint',FINGERPRINT),result_gid=os.getegid())

    def test_request_to_receipt_result_and_single_event_without_notification(self):
        outcome=self.execute();first=self.publish();second=self.publish();self.execute()
        self.assertEqual(first.disposition,'published')
        self.assertEqual(second.disposition,'already_published')
        self.assertEqual(first.completion_event_id,second.completion_event_id)
        self.invoker.assert_called_once()
        self.assertEqual(json.loads((self.public/(ID+'.json')).read_bytes()),outcome.result)
        self.assertEqual(stat.S_IMODE((self.public/(ID+'.json')).stat().st_mode),0o640)
        events=list(self.private.glob('completion-*.json'));self.assertEqual(len(events),1)
        event=json.loads(events[0].read_bytes())
        self.assertEqual(event['delivery_status'],'pending')
        self.assertFalse(first.notification_sent);self.assertFalse(first.actual_hermes_read_verified)
        self.assertEqual(stat.S_IMODE(events[0].stat().st_mode),0o600)

    def test_killed_publisher_recovers_event_without_second_search(self):
        self.execute()
        child=multiprocessing.get_context('fork').Process(target=crash_before_event,
                    args=(str(self.private),str(self.public),os.getegid()))
        child.start();child.join(10)
        self.assertEqual(child.exitcode,7)
        self.assertTrue((self.public/(ID+'.json')).is_file())
        self.assertEqual(list(self.private.glob('completion-*.json')),[])
        result=self.publish();self.assertEqual(result.disposition,'already_published')
        self.assertEqual(len(list(self.private.glob('completion-*.json'))),1)
        self.invoker.assert_called_once()

    def test_missing_receipt_cannot_create_result_or_execution_receipt(self):
        with self.assertRaisesRegex(StorageError,'receipt_missing'):self.publish()
        self.assertEqual(list(self.public.iterdir()),[])
        self.assertEqual(list(self.private.glob('*.json')),[])

    def test_wrong_scope_cannot_read_or_publish_another_company_receipt(self):
        self.execute()
        with self.assertRaisesRegex(StorageError,'receipt_missing'):self.publish(scope=Scope(38,'fixture-owner'))
        self.assertEqual(list(self.public.iterdir()),[])

    def test_bound_channel_cannot_be_reused_for_another_principal(self):
        self.execute();self.publish()
        other=Scope(37,'another-owner');fingerprint='f'*64
        with RequestLedger(self.private,other) as ledger:
            with ledger.claim(ID,fingerprint) as claim:
                claim.complete({'request_id':ID,'company_id':37,'private':'OTHER'})
        before=(self.public/(ID+'.json')).read_bytes()
        with self.assertRaisesRegex(RequestConflict,'result_channel_scope_conflict'):
            self.publish(scope=other,fingerprint=fingerprint)
        self.assertEqual((self.public/(ID+'.json')).read_bytes(),before)
        self.assertEqual(len(list(self.private.glob('completion-*.json'))),1)

    def test_legacy_unbound_results_require_review_and_are_untouched(self):
        self.execute()
        (self.public/'latest.json').write_text('{"legacy":true}')
        before={p.name:p.read_bytes() for p in self.public.iterdir()}
        with self.assertRaisesRegex(StorageError,'legacy_result_channel_requires_review'):self.publish()
        self.assertEqual({p.name:p.read_bytes() for p in self.public.iterdir()},before)
        self.assertEqual(list(self.private.glob('completion-*.json')),[])

    def test_existing_conflicting_result_is_not_overwritten_or_notified(self):
        self.execute();self.publish()
        target=self.public/(ID+'.json');target.write_text('{"other":true}')
        events=list(self.private.glob('completion-*.json'));events[0].unlink()
        with self.assertRaises(RequestConflict):self.publish()
        self.assertEqual(target.read_text(),'{"other":true}')
        self.assertEqual(list(self.private.glob('completion-*.json')),[])

    def test_wrong_request_fingerprint_does_not_publish(self):
        self.execute()
        with self.assertRaises(RequestConflict):self.publish(fingerprint='f'*64)
        self.assertEqual(list(self.public.iterdir()),[])

    def test_restrictive_umask_keeps_channel_locks_and_event_private(self):
        self.execute()
        previous=os.umask(0o777)
        try:self.publish()
        finally:os.umask(previous)
        self.assertEqual(stat.S_IMODE((self.public/'.jev-channel.lock').stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE((self.public/'.jev-channel').stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE((self.public/(ID+'.json')).stat().st_mode),0o640)

    def test_unsafe_or_modified_completion_event_is_not_accepted(self):
        self.execute();self.publish()
        event=next(self.private.glob('completion-*.json'))
        original=event.read_bytes();event.chmod(0o666)
        with self.assertRaises(StorageError):self.publish()
        event.chmod(0o600);event.write_text('{"notification_sent":true}')
        with self.assertRaises(RequestConflict):self.publish()
        self.assertNotEqual(event.read_bytes(),original)


if __name__=='__main__':unittest.main()
