import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import subprocess
import select
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from .admission_broker import AdmissionBroker, BrokerClient, BrokerGatewayRuntime, GatewayPeer, process_start_ticks
from .bootstrap_key import AdmissionSecret
from .contract import validate_v2_request
from .ingress import OwnerBinding
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .runtime import WorkerRuntime
from .settings import BridgeSettings
from .state import Scope
from .hermes_binding import submit_handler

SCOPE=Scope(37,'fixture-owner')
OWNER=OwnerBinding(SCOPE,'123456789','123456789',None)
PAYLOAD={'version':2,'request_id':'search-broker-fixture','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
RAW=json.dumps(PAYLOAD).encode()
KEY=b'synthetic-only-host-broker-key-123456'


class AdmissionBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jvb-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name in ('inbox','private','results','admissions'):(self.root/name).mkdir(mode=0o700)
        (self.root/'results').chmod(0o750)
        self.uid=os.geteuid();self.gid=os.getegid()
        self.settings=BridgeSettings(OWNER,QueueConfig(PipelineConfig(SCOPE,self.root/'private',self.root/'results',self.gid),
            self.root/'inbox',self.uid),self.root/'admissions',Path('/unused-container-inbox'),
            Path('/unused-container-admissions'),self.uid)
        self.peer=GatewayPeer(os.getpid(),self.uid,self.gid,process_start_ticks(os.getpid()))
        self.broker=AdmissionBroker(self.settings,AdmissionSecret(KEY),self.peer,clock=lambda:10000)
        self.path=self.root/'broker.sock'
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(self.listener.close)
        self.listener.bind(str(self.path));self.path.chmod(0o600);self.listener.listen(2);self.listener.settimeout(3)
        self.client=BrokerClient(self.path,expected_server_uid=self.uid,_trusted_directory=self.root)
        self.source=SimpleNamespace(platform='telegram',chat_type='dm',chat_id=OWNER.reply_chat_id,
                                    user_id=OWNER.telegram_user_id,profile=None,thread_id=None,is_bot=False)
        self.authorize=Mock(return_value=True)
        self.gateway=BrokerGatewayRuntime(OWNER,self.client,current_source=lambda:self.source,
                                          authorize_source=self.authorize)

    def test_lost_socket_ack_still_signals_a_durable_admission_to_host_worker(self):
        wire=json.dumps({'version':1,'request_b64':base64.b64encode(RAW).decode(),
                         'origin':{name:getattr(self.source,name) for name in (
                             'platform','chat_type','chat_id','user_id','profile')}}).encode()
        connection=Mock();connection.sendall.side_effect=BrokenPipeError()
        with patch.object(GatewayPeer,'permits',return_value=True),patch(
                'jev_agent.tender_finder.admission_broker._read_frame',return_value=wire):
            self.assertTrue(self.broker.serve_connection(connection))
        self.assertTrue((self.settings.queue.inbox/(PAYLOAD['request_id']+'.json')).is_file())
        self.assertEqual(len(list(self.settings.worker_admissions.glob('*.auth.json'))),1)

    def serve(self,action):
        failures=[]
        def once():
            try:
                connection,_=self.listener.accept()
                with connection:self.broker.serve_connection(connection)
            except Exception as error:failures.append(error)
        thread=threading.Thread(target=once);thread.start()
        try:return action()
        finally:
            thread.join(5)
            self.assertFalse(thread.is_alive());self.assertEqual(failures,[])

    def test_kernel_authenticated_gateway_admits_to_host_queue_without_key_in_gateway(self):
        result=self.serve(lambda:submit_handler(self.gateway)({'request_json':RAW.decode()}))
        self.assertTrue(result['queued']);self.assertFalse(result['search_executed'])
        self.assertNotIn('signature',json.dumps(result));self.assertNotIn(KEY.decode(),json.dumps(result))
        self.assertFalse(any('secret' in name or 'key' in name for name in vars(self.gateway)))
        self.assertFalse(any('secret' in name or 'key' in name for name in vars(self.client)))
        self.assertEqual((self.root/'inbox'/(PAYLOAD['request_id']+'.json')).read_bytes(),RAW)
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
            'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        worker=WorkerRuntime(self.settings,AdmissionSecret(KEY),invoke=invoke,verify_runtime=Mock(),clock=lambda:10000)
        worker.consume(PAYLOAD['request_id']+'.json')
        self.serve(lambda:self.gateway.submit(RAW))
        self.assertEqual(worker.consume(PAYLOAD['request_id']+'.json')['job_disposition'],'cached')
        invoke.assert_called_once()

    def test_separate_broker_process_receives_key_only_by_private_pipe(self):
        # Real exec + Unix IPC. The client program/runtime has no key argument,
        # environment key, inherited key FD or signing object. This fixture does
        # not claim production root-vs-container UID/mount acceptance.
        self.listener.close();self.path.unlink()
        script='''import json,os,socket,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from jev_agent.tender_finder.admission_broker import AdmissionBroker,GatewayPeer
from jev_agent.tender_finder.bootstrap_key import read_bootstrap_key
from jev_agent.tender_finder.ingress import OwnerBinding
from jev_agent.tender_finder.pipeline import PipelineConfig
from jev_agent.tender_finder.queue import QueueConfig
from jev_agent.tender_finder.settings import BridgeSettings
from jev_agent.tender_finder.state import Scope
secret=read_bootstrap_key(int(sys.argv[2]),expected_uid=os.geteuid())
data=json.load(sys.stdin);root=Path(data['root']);scope=Scope(37,'fixture-owner')
settings=BridgeSettings(OwnerBinding(scope,'123456789','123456789',None),
 QueueConfig(PipelineConfig(scope,root/'private',root/'results',os.getegid()),root/'inbox',os.geteuid()),
 root/'admissions',Path('/unused-inbox'),Path('/unused-admissions'),os.geteuid())
broker=AdmissionBroker(settings,secret,GatewayPeer(**data['peer']),clock=lambda:10000)
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
 listener.bind(str(root/'broker.sock'));os.chmod(root/'broker.sock',0o600);listener.listen(1);listener.settimeout(4)
 print('READY',flush=True)
 connection,_=listener.accept()
 with connection:broker.serve_connection(connection)
'''
        reader,writer=os.pipe()
        process=None
        try:
            process=subprocess.Popen([sys.executable,'-I','-B','-c',script,str(Path(__file__).resolve().parents[2]),str(reader)],
                pass_fds=(reader,),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            os.close(reader);reader=None
            os.write(writer,KEY);os.close(writer);writer=None
            process.stdin.write(json.dumps({'root':str(self.root),'peer':vars(self.peer)}).encode())
            process.stdin.close();process.stdin=None
            self.assertTrue(select.select([process.stdout],[],[],4)[0])
            self.assertEqual(process.stdout.readline(),b'READY\n')
            result=self.gateway.submit(RAW)
            self.assertTrue(result['queued']);self.assertNotIn(KEY.decode(),json.dumps(result))
            stdout,stderr=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0);self.assertEqual(stderr,b'');self.assertEqual(stdout,b'')
            self.assertEqual((self.root/'inbox'/(PAYLOAD['request_id']+'.json')).read_bytes(),RAW)
            invoke=Mock()
            worker=WorkerRuntime(self.settings,AdmissionSecret(KEY),invoke=invoke,
                verify_runtime=Mock(side_effect=ValueError('fixture stopped before search')),clock=lambda:10000)
            self.assertEqual(worker.consume(PAYLOAD['request_id']+'.json')['status'],'processed')
            invoke.assert_not_called()
        finally:
            for fd in (reader,writer):
                if fd is not None:os.close(fd)
            if process is not None:
                if process.poll() is None:process.kill()
                process.communicate(timeout=5)

    def test_different_process_same_uid_cannot_forge_owner_or_enqueue(self):
        program='''import json,socket,sys
wire=sys.stdin.buffer.read()
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
 client.settimeout(3);client.connect(sys.argv[1])
 try:client.sendall(wire);client.shutdown(socket.SHUT_WR)
 except OSError:pass
 chunks=[]
 try:
  while True:
   chunk=client.recv(4096)
   if not chunk:break
   chunks.append(chunk)
 except OSError:pass
 print(b''.join(chunks).decode())
'''
        frame={'version':1,'request_b64':base64.b64encode(RAW).decode(),
               'origin':{name:getattr(self.source,name) for name in ('platform','chat_type','chat_id','user_id','profile')}}
        result=self.serve(lambda:subprocess.run([sys.executable,'-I','-B','-c',program,str(self.path)],
            input=json.dumps(frame).encode(),capture_output=True,timeout=5))
        self.assertEqual(result.returncode,0)
        self.assertFalse(json.loads(result.stdout)['queued'])
        self.assertEqual(list((self.root/'inbox').iterdir()),[])
        self.assertEqual(list((self.root/'admissions').iterdir()),[])

    def test_reused_or_stale_pid_binding_is_denied(self):
        self.broker._peer=replace(self.peer,start_ticks=self.peer.start_ticks+1)
        with self.assertRaises(ValueError):self.serve(lambda:self.gateway.submit(RAW))
        self.assertEqual(list((self.root/'inbox').iterdir()),[])

    def test_other_owner_or_revoked_access_never_contacts_broker(self):
        self.authorize.return_value=False
        with self.assertRaises(ValueError):self.gateway.submit(RAW)
        self.authorize.return_value=True;self.source.user_id='987654321'
        with self.assertRaises(ValueError):self.gateway.submit(RAW)
        self.assertEqual(list((self.root/'inbox').iterdir()),[])

    def test_direct_peer_cannot_override_company_or_origin_policy(self):
        for field,value in (('user_id','987654321'),('profile','other'),('chat_type','group')):
            source=SimpleNamespace(**vars(self.source));setattr(source,field,value)
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.serve(lambda:self.client.submit(RAW,source))
        with self.assertRaises(ValueError):
            self.serve(lambda:self.client.submit(json.dumps({**PAYLOAD,'company_id':38}).encode(),self.source))
        self.assertEqual(list((self.root/'inbox').iterdir()),[])

    def test_changed_request_cannot_overwrite_original_admission(self):
        self.serve(lambda:self.gateway.submit(RAW))
        original=(self.root/'admissions'/(PAYLOAD['request_id']+'.auth.json')).read_bytes()
        with self.assertRaises(ValueError):
            self.serve(lambda:self.gateway.submit(json.dumps({**PAYLOAD,'limit':1}).encode()))
        self.assertEqual((self.root/'admissions'/(PAYLOAD['request_id']+'.auth.json')).read_bytes(),original)
        self.assertEqual((self.root/'inbox'/(PAYLOAD['request_id']+'.json')).read_bytes(),RAW)

    def test_socket_symlink_or_world_writable_socket_is_not_used(self):
        link=self.root/'other.sock';link.symlink_to(self.path)
        with self.assertRaises(ValueError):BrokerClient(link,expected_server_uid=self.uid,_trusted_directory=self.root).submit(RAW,self.source)
        self.path.chmod(0o666)
        with self.assertRaises(ValueError):self.client.submit(RAW,self.source)

    def test_wrong_kernel_server_uid_is_not_used(self):
        # Path ownership already blocks the wrong server; no request sent.
        with self.assertRaises(ValueError):BrokerClient(self.path,expected_server_uid=self.uid+1,_trusted_directory=self.root).submit(RAW,self.source)

    def test_peer_identity_fields_require_explicit_types(self):
        for peer in (replace(self.peer,pid=True),replace(self.peer,uid=0),replace(self.peer,start_ticks=0)):
            with self.assertRaises(ValueError):peer.validate()


if __name__=='__main__':unittest.main()
