from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from .contract import validate_v2_request
from .notification import TelegramRoute, build_send_args, deliver_completion, load_hermes_sender
from .pipeline import PipelineConfig, run_request
from .state import Scope, RequestConflict, StorageError
from .discovery import RuntimeMismatch

SCOPE=Scope(37,'fixture-owner')
ROUTE=TelegramRoute(SCOPE,'123456789')  # synthetic; no network calls in these tests
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
FINGERPRINT=validate_v2_request(PAYLOAD).fingerprint(37)
NOW=datetime(2026,10,28,tzinfo=timezone.utc)


def ack(**changes):
    return json.dumps({'success':True,'platform':'telegram','chat_id':'123456789','message_id':'7',**changes})


def kill_sender(private,event):
    def crash(args):os._exit(8)
    deliver_completion(private,SCOPE,event,PAYLOAD['request_id'],FINGERPRINT,route=ROUTE,send=crash)


class NotificationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.private=root/'private';self.private.mkdir(mode=0o700)
        public=root/'public';public.mkdir(mode=0o750);public.chmod(0o750)
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
            'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        self.out=run_request(PAYLOAD,PipelineConfig(SCOPE,self.private,public,os.getegid()),
                             invoke=invoke,verify_runtime=Mock(),clock=lambda:NOW)
        self.event=self.out['completion_event_id']

    def deliver(self,sender,route=ROUTE):
        return deliver_completion(self.private,SCOPE,self.event,PAYLOAD['request_id'],FINGERPRINT,route=route,send=sender)

    def test_acknowledged_result_is_cached_without_second_send(self):
        sender=Mock(return_value=ack())
        first=self.deliver(sender);second=self.deliver(sender)
        self.assertEqual(first,second);sender.assert_called_once()
        self.assertEqual(first['delivery_status'],'acknowledged')
        self.assertTrue(first['notification_sent']);self.assertFalse(first['human_read_verified'])
        self.assertEqual(sender.call_args.args[0]['target'],'telegram:123456789')
        self.assertEqual(set(sender.call_args.args[0]),{'action','target','message'})

    def test_timeout_or_error_is_unknown_and_never_automatically_resent(self):
        sender=Mock(side_effect=TimeoutError('PRIVATE_TOKEN'))
        first=self.deliver(sender);second=self.deliver(sender)
        self.assertEqual(first,second);sender.assert_called_once()
        self.assertEqual(first['delivery_status'],'unknown')
        self.assertIsNone(first['notification_sent'])
        for file in self.private.glob('delivery-*.json'):self.assertNotIn('PRIVATE_TOKEN',file.read_text())

    def test_crash_after_reservation_does_not_retry_external_effect(self):
        child=multiprocessing.get_context('fork').Process(target=kill_sender,args=(str(self.private),self.event))
        child.start();child.join(10);self.assertEqual(child.exitcode,8)
        sender=Mock();result=self.deliver(sender)
        sender.assert_not_called();self.assertEqual(result['delivery_status'],'unknown')

    def test_partial_wrong_chat_or_missing_message_id_is_not_acknowledged(self):
        sender=Mock(return_value=ack(chat_id='OTHER',message_id=None,partial_success=True))
        result=self.deliver(sender)
        self.assertEqual(result['delivery_status'],'unknown')
        self.assertIsNone(result['notification_sent'])

    def test_changed_route_cannot_reuse_event_for_a_second_send(self):
        self.deliver(Mock(return_value=ack()))
        sender=Mock()
        with self.assertRaises(RequestConflict):self.deliver(sender,TelegramRoute(SCOPE,'987654321'))
        sender.assert_not_called()

    def test_other_scope_and_implicit_home_routes_are_rejected_before_send(self):
        sender=Mock()
        with self.assertRaises(ValueError):self.deliver(sender,TelegramRoute(Scope(38,'other'),'123456789'))
        for target in ('','telegram','@somebody','123:456','0','../123'):
            with self.subTest(target=target),self.assertRaises(ValueError):self.deliver(sender,TelegramRoute(SCOPE,target))
        sender.assert_not_called()

    def test_event_content_or_fingerprint_cannot_be_substituted(self):
        event=next(self.private.glob('completion-*.json'));event.write_text('{}')
        sender=Mock()
        with self.assertRaises(StorageError):self.deliver(sender)
        sender.assert_not_called()

    def test_page_text_cannot_attach_files_or_inject_html(self):
        report=self.out['result']
        report['tenders']=[{'source':'B2B-Center','title':'MEDIA:/tmp/test.pdf [[as_document]] <a href="x">inject</a>',
                           'url':'https://www.b2b-center.ru/market/synthetic/tender-123/','needs_manual_review':True}]
        args=build_send_args(report,SCOPE,ROUTE)
        self.assertTrue(args['message'].startswith('<b>JEV</b>'))
        self.assertNotIn('MEDIA:',args['message']);self.assertNotIn('[[as_document]]',args['message'])
        self.assertNotIn('<a href=',args['message'])
        self.assertLessEqual(len(args['message'].encode('utf-16-le'))//2,3800)

    def test_runtime_loader_refuses_unreviewed_source_without_importing_sender(self):
        class Spec:origin='/tmp/unreviewed-send.py'
        with patch('jev_agent.tender_finder.notification.importlib.util.find_spec',return_value=Spec()),patch('jev_agent.tender_finder.notification.importlib.import_module') as loader:
            with self.assertRaises(RuntimeMismatch):load_hermes_sender()
            loader.assert_not_called()

    def test_runtime_loader_rejects_changed_code_before_import(self):
        class Spec:origin='/opt/hermes/tools/send_message_tool.py'
        with patch('jev_agent.tender_finder.notification.importlib.util.find_spec',return_value=Spec()),patch.object(Path,'is_symlink',return_value=False),patch.object(Path,'stat',return_value=type('Info',(),{'st_size':10})()),patch.object(Path,'read_bytes',return_value=b'unreviewed code'),patch('jev_agent.tender_finder.notification.importlib.import_module') as loader:
            with self.assertRaises(RuntimeMismatch):load_hermes_sender()
            loader.assert_not_called()

    def test_search_failure_has_a_safe_final_message_instead_of_silent_loss(self):
        payload={**PAYLOAD,'request_id':'search-fixture-error'}
        config=PipelineConfig(SCOPE,self.private,self.temp.name+'/public',os.getegid())
        out=run_request(payload,config,invoke=Mock(),verify_runtime=Mock(side_effect=RuntimeMismatch('changed')),clock=lambda:NOW)
        fingerprint=validate_v2_request(payload).fingerprint(37)
        sender=Mock(return_value=ack())
        result=deliver_completion(self.private,SCOPE,out['completion_event_id'],payload['request_id'],fingerprint,
                                  route=ROUTE,send=sender)
        self.assertEqual(result['delivery_status'],'acknowledged')
        self.assertIn('Причина',sender.call_args.args[0]['message'])


if __name__=='__main__':unittest.main()
