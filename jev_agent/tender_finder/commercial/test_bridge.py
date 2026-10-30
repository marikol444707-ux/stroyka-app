"""Synthetic end-to-end: signed admission, real file queue, report, fake sender."""
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .bridge import CommercialBridge
from .contract import validate_request
from .model import Profile
from .runner import SourceResult
from .sources import Source
from .tool import handler, register, NAME
from .test_commercial import NOW, SCOPE, HOSTS, candidate, checked
from ..bootstrap_key import AdmissionSecret
from ..admission_broker import BrokerClient, GatewayPeer
from ..contract import validate_v2_request
from ..ingress import OwnerBinding, issue_admission
from ..notification import TelegramRoute, build_send_args, deliver_completion
from ..pipeline import PipelineConfig, prepare_pipeline
from ..queue import QueueConfig, pending_claims
from ..settings import BridgeSettings
from ..state import RequestConflict

PAYLOAD={'version':3,'mode':'direct_commercial','request_id':'commercial-fixture-001','source_ids':['b2b']}
EPOCH=lambda:int(NOW.timestamp())
SOURCE=SimpleNamespace(platform='telegram',chat_type='dm',user_id='123456789',chat_id='123456789',
                       profile=None,is_bot=False,thread_id=None)


class ContractTests(unittest.TestCase):
    def test_defaults_and_two_regions(self):
        request=validate_request(PAYLOAD)
        self.assertEqual(len(request.regions),2)
        self.assertEqual(str(request.minimum_rub),'3000000')
        self.assertEqual(validate_request(request.canonical_payload()),request)

    def test_no_ownership_credentials_endpoints_or_qualification_fields(self):
        for key in ('company_id','owner_id','telegram_user_id','reply_chat_id','url','token','command',
                    'legal_entity','qualifications','documents','adapters'):
            with self.subTest(key=key),self.assertRaises(ValueError):validate_request({**PAYLOAD,key:'fake'})

    def test_unknown_sources_regions_nan_and_float_rejected(self):
        for change in ({'regions':['Москва']},{'source_ids':['unknown']},{'minimum_rub':'NaN'},
                       {'minimum_rub':True},{'minimum_rub':3.0},{'version':True},
                       {'minimum_rub':'1e-99999999'},{'minimum_rub':'3000000.001'},
                       {'queries':['arbitrary shell']},{'exclude_keywords':['x']*21}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_request({**PAYLOAD,**change})

    def test_request_cannot_supply_entity_and_profile_is_immutable(self):
        base=Profile(legal_entity='Синтетическое ООО',qualifications=frozenset({'construction_sro'}))
        request=validate_request({**PAYLOAD,'regions':['Краснодарский край']})
        result=request.profile(base)
        self.assertEqual(len(base.regions),2)
        self.assertEqual(result.qualifications,base.qualifications)
        self.assertEqual(result.legal_entity,base.legal_entity)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.paths={name:root/name for name in ('private','results','inbox','admissions','registry')}
        for name,path in self.paths.items():path.mkdir(mode=0o750 if name=='results' else 0o700)
        self.paths['results'].chmod(0o750)
        self.owner=OwnerBinding(SCOPE,'123456789','123456789',None)
        config=PipelineConfig(SCOPE,self.paths['private'],self.paths['results'],os.getegid(),protocol=3)
        self.settings=BridgeSettings(self.owner,QueueConfig(config,self.paths['inbox'],os.geteuid()),
                         self.paths['admissions'],self.paths['inbox'],self.paths['admissions'],10000)
        self.secret=AdmissionSecret(b'fixture-private-key-32-characters-long')
        self.reader=Mock(side_effect=lambda *_:checked(candidate()))
        self.bridge=CommercialBridge(self.settings,self.secret,self.paths['registry'],
            sources={'b2b':Source('b2b','B2B','platform',HOSTS['b2b'])},adapters={'b2b':self.reader})
        self.raw=json.dumps(PAYLOAD).encode()

    def submit(self,raw=None,source=SOURCE):
        return self.bridge.submit(self.raw if raw is None else raw,source,authorize_source=lambda _:True,clock=EPOCH)

    def consume(self):return self.bridge.consume(PAYLOAD['request_id']+'.json',epoch=EPOCH,clock=lambda:NOW)

    def test_signed_owner_queue_report_and_telegram_ack_once(self):
        admission=self.submit()
        self.assertTrue(admission['queued']);self.assertFalse(admission['search_executed'])
        out=self.consume()
        self.assertEqual(out['status'],'processed');self.reader.assert_called_once()
        report=out['result']
        self.assertEqual(report['schema_version'],3)
        self.assertEqual(report['company_id'],SCOPE.company_id)
        self.assertEqual(len(report['sections']['priority']),1)
        self.assertTrue((self.paths['results']/(PAYLOAD['request_id']+'.json')).exists())
        sender=Mock(return_value=json.dumps({'success':True,'platform':'telegram','chat_id':'123456789','message_id':'7'}))
        route=TelegramRoute(SCOPE,'123456789')
        args=(self.paths['private'],SCOPE,out['completion_event_id'],PAYLOAD['request_id'],
              self.bridge.validate(PAYLOAD).fingerprint(SCOPE.company_id))
        first=deliver_completion(*args,route=route,send=sender)
        second=deliver_completion(*args,route=route,send=sender)
        self.assertEqual(first,second);self.assertEqual(first['delivery_status'],'acknowledged')
        sender.assert_called_once()

    def test_duplicate_queued_request_never_reads_again(self):
        self.submit();first=self.consume()
        self.submit();second=self.consume()
        self.assertEqual(first['result'],second['result']);self.reader.assert_called_once()

    def test_changed_wire_owner_or_unauthorized_source_cannot_admit(self):
        for source in (SimpleNamespace(**{**vars(SOURCE),'user_id':'987654321'}),
                       SimpleNamespace(**{**vars(SOURCE),'chat_type':'group'})):
            with self.assertRaises(ValueError):self.submit(source=source)
        with self.assertRaises(ValueError):
            self.bridge.submit(self.raw,SOURCE,authorize_source=lambda _:False,clock=EPOCH)
        self.assertEqual(list(self.paths['inbox'].iterdir()),[])
        self.reader.assert_not_called()

    def test_tampered_payload_has_no_valid_signature_or_search(self):
        self.submit()
        path=self.paths['inbox']/(PAYLOAD['request_id']+'.json')
        path.write_text(json.dumps({**PAYLOAD,'minimum_rub':'4000000'}))
        out=self.consume()
        self.assertEqual(out['status'],'authorization_pending');self.reader.assert_not_called()

    def test_expired_receipt_does_not_search(self):
        self.submit()
        out=self.bridge.consume(PAYLOAD['request_id']+'.json',epoch=lambda:EPOCH()+3601,clock=lambda:NOW)
        self.assertEqual(out['status'],'authorization_pending');self.reader.assert_not_called()

    def test_v2_defaults_reject_v3_and_namespace_cannot_be_adopted(self):
        with self.assertRaises(ValueError):validate_v2_request(PAYLOAD)
        with self.assertRaises(ValueError):
            issue_admission(self.raw,SOURCE,authorize_source=lambda _:True,bindings=(self.owner,),
                            signing_key=self.secret.material,clock=EPOCH)
        old=replace(self.settings.queue.pipeline,protocol=2)
        prepare_pipeline(old)
        self.submit()
        with self.assertRaises(RequestConflict):self.consume()
        self.reader.assert_not_called()

    def test_event_failure_recovery_reuses_committed_report(self):
        self.submit()
        with patch('jev_agent.tender_finder.publication._write_event',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.consume()
        handle=pending_claims(self.settings.queue)[0]
        out=self.bridge.resume(handle,epoch=EPOCH,clock=lambda:NOW)
        self.assertEqual(out['job_disposition'],'cached');self.reader.assert_called_once()

    def test_preview_cannot_attach_files_inject_html_or_leak_other_scope(self):
        self.reader.side_effect=lambda *_:checked(candidate({'title':'MEDIA:/etc/secret [[as_document]] <b>test</b>'}))
        self.submit();out=self.consume()
        args=build_send_args(out['result'],SCOPE,TelegramRoute(SCOPE,'123456789'))
        self.assertNotIn('MEDIA:',args['message']);self.assertNotIn('[[as_document]]',args['message'])
        self.assertNotIn('<b>test',args['message'])
        self.assertLessEqual(len(args['message'].encode('utf-16-le'))//2,3800)
        with self.assertRaises(ValueError):
            build_send_args({**out['result'],'company_id':999},SCOPE,TelegramRoute(SCOPE,'123456789'))

    def test_gateway_has_no_key_and_checks_owner_before_broker_call(self):
        gateway=self.bridge.gateway('/tmp/synthetic-no-listener.sock',current_source=lambda:SOURCE,
                                    authorize_source=lambda _:True)
        self.assertNotIn(self.secret.material,list(vars(gateway).values()))
        self.assertFalse(any(name in vars(gateway) for name in ('secret','_secret','signing_key')))
        with patch.object(BrokerClient,'submit',return_value={'queued':True}) as submit:
            self.assertEqual(gateway.submit(self.raw),{'queued':True});submit.assert_called_once()
        rejected=self.bridge.gateway('/tmp/synthetic-no-listener.sock',
            current_source=lambda:SimpleNamespace(**{**vars(SOURCE),'user_id':'987654321'}),authorize_source=lambda _:True)
        with patch.object(BrokerClient,'submit') as submit,self.assertRaises(ValueError):rejected.submit(self.raw)
        submit.assert_not_called()

    def test_host_broker_receipt_uses_same_v3_validator_and_protocol(self):
        import base64
        peer=GatewayPeer(os.getpid(),10000,10000,1)
        broker=self.bridge.broker(peer,epoch=EPOCH)
        origin={key:getattr(SOURCE,key) for key in ('platform','chat_type','chat_id','user_id','profile')}
        frame=json.dumps({'version':1,'request_b64':base64.b64encode(self.raw).decode(),'origin':origin}).encode()
        self.assertTrue(broker._admit(frame)['queued'])
        self.consume();self.reader.assert_called_once()

    def test_tool_rejects_extra_commands_and_utf8_byte_overflow_before_broker(self):
        gateway=self.bridge.gateway('/tmp/synthetic-no-listener.sock',current_source=lambda:SOURCE,
                                    authorize_source=lambda _:True)
        execute=handler(gateway)
        with patch.object(BrokerClient,'submit') as submit:
            for args in ({'request_json':self.raw.decode(),'command':'fake'},
                         {'request_json':'😀'*10000},{'request_json':'not-json'},{}):
                self.assertFalse(execute(args)['queued'])
        submit.assert_not_called()

    def test_startup_preserves_existing_handler_instead_of_overriding(self):
        gateway=self.bridge.gateway('/tmp/synthetic-no-listener.sock',current_source=lambda:SOURCE,
                                    authorize_source=lambda _:True)
        original=object()
        class Registry:
            _lock=threading.RLock()
            def get_entry(self,*args,**kwargs):return original
            def register(self,**kwargs):raise AssertionError('must preserve existing registration')
        with self.assertRaises(ValueError):register(Registry(),gateway,scope='/opt/data')

    def test_new_tool_uses_real_session_authorization_and_preserves_v2_name(self):
        gateway=self.bridge.gateway('/tmp/synthetic-no-listener.sock',current_source=lambda:SOURCE,
                                    authorize_source=lambda _:True)
        entries={}
        class Registry:
            _lock=threading.RLock()
            def get_entry(self,name,**kwargs):return entries.get(name)
            def register(self,**kwargs):entries[kwargs['name']]=kwargs
        register(Registry(),gateway,scope='/opt/data')
        self.assertNotIn('jev_tender_search',entries)
        with patch.object(BrokerClient,'submit',return_value={'queued':True}) as submit:
            self.assertTrue(entries[NAME]['handler']({'request_json':self.raw.decode()})['queued'])
        submit.assert_called_once()


if __name__=='__main__':unittest.main()
