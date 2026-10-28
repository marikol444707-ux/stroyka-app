from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from .contract import InvalidRequest, validate_v2_request
from .ingress import OwnerBinding, issue_admission, make_authenticator, owner_route
from .pipeline import PipelineConfig
from .notification import deliver_completion
from .queue import QueueConfig, consume_file, resume_claim
from .state import Scope

SCOPE=Scope(37,'fixture-owner')
BINDING=OwnerBinding(SCOPE,'123456789','123456789',None)
BINDINGS=(BINDING,)
KEY=b'synthetic-test-key-not-for-production-123456789'
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
RAW=json.dumps(PAYLOAD).encode();DIGEST=hashlib.sha256(RAW).hexdigest()
NAME=PAYLOAD['request_id']+'.json'


def source(**changes):
    return SimpleNamespace(platform=SimpleNamespace(value='telegram'),chat_type='dm',
                           user_id='123456789',chat_id='123456789',thread_id=None,profile=None,**changes)


def issue(raw=RAW,origin=None,policies=BINDINGS,authorize=None,issued=10000):
    return issue_admission(raw,origin or source(),authorize_source=authorize or Mock(return_value=True),
                           bindings=policies,signing_key=KEY,clock=lambda:issued)


def verifier(receipt,policies=BINDINGS,now=10001):
    return make_authenticator(receipt_loader=lambda filename:json.dumps(receipt).encode(),
                              bindings=policies,verification_key=KEY,clock=lambda:now)


class AdmissionTests(unittest.TestCase):
    def test_gateway_authorization_and_explicit_owner_create_valid_scope_receipt(self):
        authorize=Mock(return_value=True);origin=source()
        receipt=issue(origin=origin,authorize=authorize)
        authorize.assert_called_once_with(origin)
        self.assertTrue(verifier(receipt)(NAME,DIGEST,SCOPE))
        self.assertEqual(owner_route(BINDINGS,SCOPE).target(),'telegram:123456789')

    def test_gateway_denial_remains_denial_even_if_owner_policy_matches(self):
        with self.assertRaises(ValueError):issue(authorize=Mock(return_value=False))

    def test_source_from_model_json_is_never_trusted(self):
        with self.assertRaises(ValueError):issue(origin={'platform':'telegram','user_id':'123456789'})
        with self.assertRaises(InvalidRequest):issue(raw=json.dumps({**PAYLOAD,'companyId':37}).encode())

    def test_other_user_chat_bot_profile_and_thread_cannot_admit(self):
        variants=[('user_id','987654321'),('chat_id','987654321'),('is_bot',True),
                  ('profile','other'),('thread_id','7'),('chat_type','group')]
        for field,value in variants:
            origin=source();setattr(origin,field,value)
            with self.subTest(field=field),self.assertRaises(ValueError):issue(origin=origin)

    def test_ambiguous_company_mapping_is_rejected_instead_of_defaulting(self):
        other=OwnerBinding(Scope(38,'another-owner'),'123456789','123456789',None)
        with self.assertRaises(ValueError):issue(policies=(BINDING,other))

    def test_changed_company_recipient_or_digest_invalidates_signature(self):
        original=issue()
        for field,value in (('company_id',38),('reply_chat_id','987654321'),('request_sha256','0'*64)):
            changed=deepcopy(original);changed['body'][field]=value
            self.assertFalse(verifier(changed)(NAME,DIGEST,SCOPE))
        self.assertFalse(verifier(original)(NAME,'0'*64,SCOPE))
        self.assertFalse(verifier(original)(NAME,DIGEST,Scope(38,'fixture-owner')))

    def test_future_expired_and_revoked_owner_are_rejected(self):
        receipt=issue()
        self.assertFalse(verifier(receipt,now=9999)(NAME,DIGEST,SCOPE))
        self.assertFalse(verifier(receipt,now=13600)(NAME,DIGEST,SCOPE))
        other=OwnerBinding(Scope(38,'new-owner'),'987654321','987654321',None)
        self.assertFalse(verifier(receipt,policies=(other,))(NAME,DIGEST,SCOPE))

    def test_bad_or_missing_receipt_never_authorizes(self):
        for raw in (b'',b'{}',b'{"body":{},"signature":"fake"}',b'x'*4097):
            auth=make_authenticator(receipt_loader=lambda name:raw,bindings=BINDINGS,
                                     verification_key=KEY,clock=lambda:10001)
            self.assertFalse(auth(NAME,DIGEST,SCOPE))

    def test_weak_key_has_no_fallback(self):
        with self.assertRaises(ValueError):
            issue_admission(RAW,source(),authorize_source=Mock(return_value=True),bindings=BINDINGS,
                             signing_key=b'',clock=lambda:10000)

    def test_queue_only_executes_after_valid_detached_admission(self):
        receipt=issue();store=[{}]
        auth=make_authenticator(receipt_loader=lambda name:json.dumps(store[0]).encode(),
                                 bindings=BINDINGS,verification_key=KEY,clock=lambda:10001)
        invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
            'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            private=root/'private';private.mkdir(mode=0o700)
            public=root/'results';public.mkdir(mode=0o750);public.chmod(0o750)
            inbox=root/'requests';inbox.mkdir(mode=0o700)
            (inbox/NAME).write_bytes(RAW);(inbox/NAME).chmod(0o600)
            config=QueueConfig(PipelineConfig(SCOPE,private,public,os.getegid()),inbox,os.geteuid())
            bindings={'invoke':invoke,'verify_runtime':Mock(),'clock':lambda:datetime(2026,10,28,tzinfo=timezone.utc)}
            waiting=consume_file(config,NAME,authenticate=auth,**bindings)
            self.assertEqual(waiting['status'],'authorization_pending');invoke.assert_not_called()
            store[0]=receipt
            result=resume_claim(config,waiting['claim_handle'],authenticate=auth,**bindings)
            self.assertEqual(result['status'],'processed');invoke.assert_called_once()
            sender=Mock(return_value=json.dumps({'success':True,'platform':'telegram',
                                               'chat_id':'123456789','message_id':'7'}))
            for _ in range(2):
                delivered=deliver_completion(private,SCOPE,result['completion_event_id'],PAYLOAD['request_id'],
                    validate_v2_request(PAYLOAD).fingerprint(37),route=owner_route(BINDINGS,SCOPE),send=sender)
                self.assertEqual(delivered['delivery_status'],'acknowledged')
            sender.assert_called_once();invoke.assert_called_once()


if __name__=='__main__':unittest.main()
