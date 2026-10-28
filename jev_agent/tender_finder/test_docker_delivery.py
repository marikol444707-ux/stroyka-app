import contextlib
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from .contract import validate_v2_request
from .docker_delivery import DockerHermesSender, IMAGE, REMOTE_PROGRAM, deliver_via_hermes
from .ingress import OwnerBinding
from .notification import build_send_args, deliver_completion, TelegramRoute
from .pipeline import PipelineConfig, run_request
from .queue import QueueConfig
from .settings import BridgeSettings
from .state import Scope, StorageError

SCOPE=Scope(37,'fixture-owner')
OWNER=OwnerBinding(SCOPE,'123456789','123456789',None)
ROUTE=TelegramRoute(SCOPE,OWNER.reply_chat_id)
PAYLOAD={'version':2,'request_id':'search-delivery-fixture','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
FINGERPRINT=validate_v2_request(PAYLOAD).fingerprint(37)
FRAME={'action':'send','target':'telegram:123456789','message':'<b>JEV</b>\nТест без отправки'}


def metadata(**changes):
    return json.dumps({'id':'a'*64,'image':IMAGE,'running':True,'privileged':False,
        'mounts':[{'Type':'bind','Source':'/root/hermes-data','Destination':'/opt/data','RW':True}],
        **changes}).encode()


def acknowledgement(**changes):
    return json.dumps({'success':True,'platform':'telegram','chat_id':OWNER.reply_chat_id,
                       'message_id':'7',**changes})


class RemoteProgramTests(unittest.TestCase):
    def setUp(self):
        self.program={'__name__':'test_fixture_not_main'}
        exec(compile(REMOTE_PROGRAM,'fixed-hermes-send-program','exec'),self.program)

    def invoke(self,wire,sender):
        self.program['_load_sender']=lambda:sender
        output=io.StringIO()
        with patch.object(sys,'stdin',SimpleInput(wire)),contextlib.redirect_stdout(output):
            code=self.program['main']()
        return code,output.getvalue()

    def test_fixed_program_accepts_existing_escaped_report_format(self):
        report={'company_id':37,'protected_scope':SCOPE.key(),'status':'failed','reason':'runtime_changed',
                'schema_version':2,'request_id':PAYLOAD['request_id']}
        args=build_send_args(report,SCOPE,ROUTE)
        sender=Mock(return_value=acknowledgement())
        code,raw=self.invoke(json.dumps(args).encode(),sender)
        self.assertEqual(code,0);self.assertTrue(json.loads(raw)['success'])
        sender.assert_called_once_with(args)

    def test_invalid_frames_do_not_reach_sender(self):
        bad=[b'{"action":"send","action":"send"}',b'x'*32769,
             json.dumps({**FRAME,'attachment':'/root/private'}).encode(),
             json.dumps({**FRAME,'target':'telegram'}).encode(),
             json.dumps({**FRAME,'target':'telegram:-100123'}).encode(),
             json.dumps({**FRAME,'message':'<b>JEV</b>\nMEDIA:/root/private'}).encode(),
             json.dumps({**FRAME,'message':'<b>JEV</b>\n[[as_document]]'}).encode(),
             json.dumps({**FRAME,'message':'<b>JEV</b>\n<a href="x">inject</a>'}).encode(),
             json.dumps({**FRAME,'message':'<b>JEV</b>\n'+'я'*3900}).encode()]
        sender=Mock()
        for wire in bad:
            with self.subTest(wire=wire[:40]):
                code,raw=self.invoke(wire,sender)
                self.assertEqual(code,1);self.assertFalse(json.loads(raw)['success'])
        sender.assert_not_called()

    def test_sender_logs_errors_and_extra_fields_are_not_forwarded(self):
        def noisy(args):
            print('PRIVATE_TOKEN')
            return acknowledgement(private='PRIVATE_TOKEN',note='PRIVATE_TOKEN')
        code,raw=self.invoke(json.dumps(FRAME).encode(),noisy)
        self.assertEqual(code,0);self.assertNotIn('PRIVATE',raw)
        self.assertEqual(set(json.loads(raw)),{'success','platform','chat_id','message_id'})
        for sender in (Mock(side_effect=ValueError('PRIVATE_TOKEN')),
                       Mock(return_value=acknowledgement(error='PRIVATE_TOKEN'))):
            code,raw=self.invoke(json.dumps(FRAME).encode(),sender)
            self.assertEqual(code,1);self.assertNotIn('PRIVATE',raw)

    def test_partial_wrong_chat_duplicate_or_missing_ack_is_not_success(self):
        for ack in (acknowledgement(chat_id='987654321'),acknowledgement(partial_success=True),
                    acknowledgement(message_id=None),acknowledgement(warnings=['partial']),
                    '{"success":true,"success":true}', 'NaN'):
            code,raw=self.invoke(json.dumps(FRAME).encode(),Mock(return_value=ack))
            self.assertEqual(code,1);self.assertFalse(json.loads(raw)['success'])

    def test_remote_wrong_uid_never_imports_sender(self):
        with patch.object(os,'geteuid',return_value=0),patch('importlib.import_module') as load:
            with self.assertRaises(ValueError):self.program['_load_sender']()
        load.assert_not_called()

    def test_real_isolated_program_refuses_non_gateway_identity_without_send(self):
        if os.geteuid()==10000:
            # Invalid wire fails before importing sender on every UID.
            wire=b'{}'
        else:wire=json.dumps(FRAME).encode()
        result=subprocess.run([sys.executable,'-I','-B','-c',REMOTE_PROGRAM],input=wire,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,check=False)
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout),{'success':False,'code':'hermes_delivery_failed'})
        self.assertEqual(result.stderr,b'')

    def test_changed_sender_source_is_rejected_before_import(self):
        real_open=os.open;real_fstat=os.fstat
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'opt/hermes/tools').mkdir(parents=True)
            (root/'opt/hermes/tools/send_message_tool.py').write_bytes(b'raise RuntimeError("MUST_NOT_IMPORT")')
            def opened(path,*args,**kwargs):
                return real_open(folder if path=='/' else path,*args,**kwargs)
            def info(fd):
                value=real_fstat(fd)
                return SimpleNamespace(st_uid=0,st_mode=value.st_mode,st_size=value.st_size)
            with patch.object(os,'geteuid',return_value=10000),patch.object(os,'getegid',return_value=10000),patch.object(
                    os,'open',side_effect=opened),patch.object(os,'fstat',side_effect=info),patch('importlib.import_module') as load:
                with self.assertRaisesRegex(ValueError,'reviewed_sender_required'):
                    self.program['_load_sender']()
            load.assert_not_called()


class SimpleInput:
    def __init__(self,raw):self.buffer=io.BytesIO(raw)


class HostDockerTransportTests(unittest.TestCase):
    def sender(self,run):
        return DockerHermesSender(OWNER,gateway_uid=10000,gateway_gid=10000,_run=run)

    def test_exec_is_fixed_unprivileged_container_id_and_message_stays_in_stdin(self):
        run=Mock(side_effect=[(metadata(),0),(acknowledgement().encode(),0)])
        with patch.object(os,'geteuid',return_value=0):self.sender(run)(FRAME)
        argv,wire,timeout=run.call_args.args
        self.assertEqual(argv[:3],('/usr/bin/docker','exec','--interactive'))
        self.assertIn('10000:10000',argv);self.assertIn('a'*64,argv)
        self.assertNotIn('hermes-telegram',argv)
        self.assertEqual(argv[-5:],('/opt/hermes/.venv/bin/python','-I','-B','-c',REMOTE_PROGRAM))
        self.assertNotIn(OWNER.reply_chat_id,' '.join(argv))
        self.assertNotIn(FRAME['message'],' '.join(argv))
        self.assertEqual(json.loads(wire),FRAME);self.assertEqual(timeout,75)
        self.assertEqual(run.call_args_list[0].args[1:],(None,10))

    def test_other_recipient_extra_fields_and_nonroot_never_launch_docker(self):
        run=Mock();sender=self.sender(run)
        for args in ({**FRAME,'target':'telegram:987654321'},{**FRAME,'key':'PRIVATE_TOKEN'},
                     {**FRAME,'action':'list'}):
            with patch.object(os,'geteuid',return_value=0),self.assertRaises(ValueError):sender(args)
        with patch.object(os,'geteuid',return_value=10000),self.assertRaises(ValueError):sender(FRAME)
        run.assert_not_called()

    def test_unreviewed_identity_and_named_profile_have_no_fallback(self):
        for owner,uid,gid in ((replace(OWNER,profile='other'),10000,10000),
                              (OWNER,0,10000),(OWNER,10000,0),(OWNER,True,10000)):
            with self.assertRaises(ValueError):DockerHermesSender(owner,gateway_uid=uid,gateway_gid=gid)

    def test_wrong_image_stopped_privileged_or_other_mount_prevents_exec(self):
        bad=[metadata(image='sha256:'+'b'*64),metadata(running=False),metadata(privileged=True),
             metadata(mounts=[]),metadata(mounts=[{'Type':'bind','Source':'/','Destination':'/opt/hermes','RW':True}]),
             metadata(id='hermes-telegram'),b'{"id":0,"id":1}']
        for raw in bad:
            run=Mock(return_value=(raw,0))
            with self.subTest(raw=raw[:80]),patch.object(os,'geteuid',return_value=0),self.assertRaises(ValueError):
                self.sender(run)(FRAME)
            self.assertEqual(run.call_count,1)

    def test_failed_inspection_nonzero_send_and_oversized_ack_are_not_accepted(self):
        for outcomes in ([(b'PRIVATE_TOKEN',1)],[(metadata(),0),(b'PRIVATE_TOKEN',1)],
                         [(metadata(),0),(b'x'*32769,0)]):
            with patch.object(os,'geteuid',return_value=0),self.assertRaises(ValueError):
                self.sender(Mock(side_effect=outcomes))(FRAME)

    def test_failed_or_timed_out_send_is_not_retried_from_committed_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);private=root/'private';private.mkdir(mode=0o700)
            public=root/'public';public.mkdir(mode=0o750);public.chmod(0o750)
            output=run_request(PAYLOAD,PipelineConfig(SCOPE,private,public,os.getegid()),invoke=Mock(),
                verify_runtime=Mock(side_effect=ValueError('runtime fixture')),clock=lambda:datetime(2026,10,28,tzinfo=timezone.utc))
            run=Mock(side_effect=[(metadata(),0),subprocess.TimeoutExpired('fixed transport',75)])
            sender=self.sender(run)
            for _ in range(2):
                with patch('jev_agent.tender_finder.docker_delivery.os',SimpleNamespace(geteuid=lambda:0)):
                    result=deliver_completion(private,SCOPE,output['completion_event_id'],PAYLOAD['request_id'],
                                              FINGERPRINT,route=ROUTE,send=sender)
                self.assertEqual(result['delivery_status'],'unknown')
                self.assertIsNone(result['notification_sent'])
            self.assertEqual(run.call_count,2)  # One inspect and one exec, no resend.

    def test_other_company_event_never_launches_transport(self):
        run=Mock()
        with tempfile.TemporaryDirectory() as folder:
            private=Path(folder)/'private';private.mkdir(mode=0o700)
            with self.assertRaises(StorageError):
                deliver_completion(private,SCOPE,'a'*64,PAYLOAD['request_id'],FINGERPRINT,
                                   route=ROUTE,send=self.sender(run))
        run.assert_not_called()

    def test_host_entrypoint_uses_protected_owner_and_caches_acknowledged_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('private','public','inbox','admissions'):(root/name).mkdir(mode=0o700)
            (root/'public').chmod(0o750)
            config=PipelineConfig(SCOPE,root/'private',root/'public',os.getegid())
            output=run_request(PAYLOAD,config,invoke=Mock(),verify_runtime=Mock(side_effect=ValueError('fixture')),
                               clock=lambda:datetime(2026,10,28,tzinfo=timezone.utc))
            settings=BridgeSettings(OWNER,QueueConfig(config,root/'inbox',10000),root/'admissions',
                                    Path('/opt/data/fixture-requests'),Path('/opt/data/fixture-admissions'))
            sender=Mock(return_value=acknowledgement())
            with patch('jev_agent.tender_finder.docker_delivery.DockerHermesSender',return_value=sender) as factory:
                for _ in range(2):
                    result=deliver_via_hermes(settings,output['completion_event_id'],PAYLOAD['request_id'],
                                             FINGERPRINT,gateway_gid=10000)
                    self.assertEqual(result['delivery_status'],'acknowledged')
            factory.assert_called_with(OWNER,gateway_uid=10000,gateway_gid=10000)
            sender.assert_called_once()
            self.assertEqual(sender.call_args.args[0]['target'],FRAME['target'])


if __name__=='__main__':unittest.main()
