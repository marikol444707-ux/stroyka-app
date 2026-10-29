import json
import os
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from .admission_broker import BrokerClient,GatewayPeer,process_start_ticks
from .admission_files import publish_admission
from .host_service import ConnectedHost,initialize_root_service
from .ingress import issue_admission
from . import test_host_worker as fixtures


class ConnectedHostTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.HostPassTests('test_real_admission_queue_search_receipt_event_and_delivery_connected')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.peer=GatewayPeer(os.getpid(),os.geteuid(),os.getegid(),process_start_ticks(os.getpid()))
        self.source=SimpleNamespace(platform='telegram',chat_type='dm',
            chat_id=self.fixture.owner.reply_chat_id,user_id=self.fixture.owner.telegram_user_id,
            profile=None,thread_id=None)

    def start(self,run_pass=None):
        root=self.fixture.settings.queue.inbox.parent
        path=root/'service.sock'
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(str(path));path.chmod(0o600);listener.listen(4)
        self.idle=threading.Event();self.summaries=[];self.failures=[]
        def emit(summary):
            self.summaries.append(summary)
            if not summary.get('processed') and not summary.get('acknowledged'):
                self.idle.set()
        host=ConnectedHost(self.fixture.settings,self.fixture.secret,self.peer,
                           _run_pass=run_pass or self.fixture.run_pass,_emit_summary=emit)
        self.stop=threading.Event()
        def serve():
            try:host.serve(listener,self.stop)
            except Exception as error:self.failures.append(type(error).__name__)
        self.thread=threading.Thread(target=serve);self.thread.start()
        def finish():
            self.stop.set();self.thread.join(6)
            self.assertFalse(self.thread.is_alive(),'service did not stop')
            self.assertEqual(self.failures,[])
        self.addCleanup(finish)
        self.client=BrokerClient(path,expected_server_uid=os.geteuid(),_trusted_directory=root)
        return host

    def test_real_socket_wakes_pipeline_without_blocking_gateway_on_search(self):
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def run_pass():
            if self.idle.is_set():
                entered.set()
                if not release.wait(5):raise RuntimeError('fixture timeout')
            return self.fixture.run_pass()
        self.start(run_pass);self.assertTrue(self.idle.wait(5))
        initial=self.fixture.invoke.call_count
        raw=json.dumps({**fixtures.PAYLOAD,'request_id':'search-connected-new'}).encode()
        result=self.client.submit(raw,self.source)
        self.assertTrue(result['queued']);self.assertTrue(entered.wait(3))
        self.assertEqual(self.fixture.invoke.call_count,initial)
        # The response has arrived while the host search is still blocked.
        release.set();self.stop.set();self.thread.join(6)
        self.assertEqual(self.fixture.invoke.call_count,initial+1)
        self.assertEqual(self.fixture.sender.call_count,initial+1)

    def test_startup_drains_more_than_one_bounded_batch_and_then_sleeps(self):
        fixture=self.fixture
        for number in range(33):
            raw=json.dumps({**fixtures.PAYLOAD,'request_id':f'search-backlog-{number}'}).encode()
            receipt=issue_admission(raw,self.source,authorize_source=lambda source:True,
                bindings=(fixture.owner,),signing_key=fixture.secret.material,clock=lambda:int(time.time()))
            publish_admission(raw,receipt,fixture.settings,fixture.secret,clock=lambda:int(time.time()))
        self.start();self.assertTrue(self.idle.wait(8))
        self.assertEqual(fixture.invoke.call_count,34);self.assertEqual(fixture.sender.call_count,34)
        self.assertEqual(sum(row['processed'] for row in self.summaries),34)
        self.assertGreaterEqual(len(self.summaries),3)

    def test_restart_recovers_committed_completion_without_second_search(self):
        self.fixture.run_pass(deliver=Mock(side_effect=RuntimeError('before external send')))
        self.fixture.invoke.assert_called_once();self.fixture.sender.assert_not_called()
        self.start();self.assertTrue(self.idle.wait(5))
        self.fixture.invoke.assert_called_once();self.fixture.sender.assert_called_once()
        self.assertEqual(sum(row['acknowledged'] for row in self.summaries),1)

    def test_invalid_rpc_does_not_wake_an_idle_worker(self):
        calls=Mock(side_effect=self.fixture.run_pass)
        self.start(calls);self.assertTrue(self.idle.wait(5));before=calls.call_count
        with self.assertRaisesRegex(ValueError,'broker_admission_not_confirmed'):
            self.client.submit(b'{"version":2}',self.source)
        self.stop.set();self.thread.join(6)
        self.assertEqual(calls.call_count,before)
        self.fixture.invoke.assert_called_once()

    def test_unknown_delivery_remains_unknown_after_repeated_admission(self):
        self.fixture.sender.side_effect=TimeoutError('PRIVATE_TOKEN')
        self.start();self.assertTrue(self.idle.wait(5));self.idle.clear()
        self.assertTrue(self.client.submit(fixtures.RAW,self.source)['queued'])
        self.assertTrue(self.idle.wait(5))
        self.fixture.invoke.assert_called_once();self.fixture.sender.assert_called_once()
        self.assertEqual(sum(row.get('unknown',0) for row in self.summaries),1)
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(self.summaries))

    def test_fault_is_reported_without_automatic_retry_or_exception_text(self):
        failed=Mock(side_effect=RuntimeError('PRIVATE_TOKEN'))
        self.start(failed);self.assertTrue(self.idle.wait(5))
        self.stop.set();self.thread.join(6)
        failed.assert_called_once()
        self.assertEqual(self.summaries,[{'failed':True,'code':'host_pass_failed'}])

    def test_nonroot_bootstrap_closes_key_before_reading_configuration_or_key(self):
        reader,writer=os.pipe();os.close(writer)
        with patch('jev_agent.tender_finder.host_service.os',SimpleNamespace(geteuid=lambda:10000,close=os.close)),patch(
                'jev_agent.tender_finder.host_service.read_bootstrap_key') as read,patch(
                'jev_agent.tender_finder.host_service.load_settings') as load:
            with self.assertRaises(ValueError):initialize_root_service('/fixture',reader,self.peer)
        read.assert_not_called();load.assert_not_called()
        with self.assertRaises(OSError):os.fstat(reader)

    def test_shutdown_finishes_current_pass_without_starting_another(self):
        entered=threading.Event();release=threading.Event();stop=threading.Event()
        def run_pass():
            entered.set()
            if not release.wait(5):raise RuntimeError('fixture timeout')
            return {'processed':1,'acknowledged':0,'unknown':0,'errors':0}
        calls=Mock(side_effect=run_pass)
        host=ConnectedHost(self.fixture.settings,self.fixture.secret,self.peer,
                           _run_pass=calls,_emit_summary=lambda summary:None)
        def accept():
            if not entered.wait(5):raise RuntimeError('worker did not start')
            stop.set();raise socket.timeout()
        listener=SimpleNamespace(settimeout=lambda timeout:None,accept=accept)
        thread=threading.Thread(target=host.serve,args=(listener,stop));thread.start()
        try:
            self.assertTrue(host._stop.wait(5))
            self.assertTrue(thread.is_alive(),'in-flight work was abandoned')
        finally:
            release.set();thread.join(6)
        self.assertFalse(thread.is_alive());calls.assert_called_once()

    def test_gateway_restart_requires_rebinding_instead_of_trusting_reused_pid(self):
        host=ConnectedHost(self.fixture.settings,self.fixture.secret,self.peer,
            _run_pass=Mock(return_value={'processed':0,'acknowledged':0,'unknown':0,'errors':0}),
            _emit_summary=lambda summary:None)
        listener=Mock()
        with patch('jev_agent.tender_finder.host_service.process_start_ticks',return_value=self.peer.start_ticks+1):
            with self.assertRaisesRegex(ValueError,'host_service_rebind_required'):
                host.serve(listener,threading.Event())
        listener.accept.assert_not_called()
        self.assertFalse(host._thread.is_alive())


if __name__=='__main__':unittest.main()
