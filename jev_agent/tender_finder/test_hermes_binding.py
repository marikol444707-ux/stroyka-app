import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .bootstrap_key import AdmissionSecret
from .discovery import RuntimeMismatch
from .hermes_binding import HermesSessionBinding, bind_gateway, submit_handler, verified_loaded_modules
from .ingress import OwnerBinding, issue_admission
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .runtime import GatewayRuntime, WorkerRuntime
from .settings import BridgeSettings
from .state import Scope

PAYLOAD={'version':2,'request_id':'search-hermes-fixture','region':'Ставропольский край',
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}
RAW=json.dumps(PAYLOAD).encode()
KEY=b'synthetic-bootstrap-fixture-key-12345'
SCOPE=Scope(37,'fixture-owner')
OWNER=OwnerBinding(SCOPE,'123456789','123456789',None)


@dataclass
class Source:
    platform: str = 'telegram'
    chat_id: str = '123456789'
    user_id: str = '123456789'
    chat_type: str = 'dm'
    thread_id: str | None = None
    profile: str | None = None
    is_bot: bool = False
    profile_route_rejected: bool = False


def context():
    values={name:ContextVar(name,default=object()) for name in (
        '_SESSION_PLATFORM','_SESSION_CHAT_ID','_SESSION_USER_ID','_SESSION_CHAT_TYPE',
        '_SESSION_THREAD_ID','_SESSION_PROFILE','_CRON_SESSION','key')}
    result=SimpleNamespace(**values)
    result.bound_session_key=lambda:result.key.get()
    return result


def bind_context(ctx, source, key='fixture-session'):
    ctx.key.set(key);ctx._CRON_SESSION.set('')
    for field in ('platform','chat_id','user_id','chat_type','thread_id','profile'):
        getattr(ctx,'_SESSION_'+field.upper()).set(getattr(source,field) or '')


class HermesBindingTests(unittest.TestCase):
    def setUp(self):
        self.ctx=context();self.source=Source();bind_context(self.ctx,self.source)
        self.runner=SimpleNamespace(_get_cached_session_source=Mock(return_value=self.source),
            _is_user_authorized_for_source=Mock(return_value=True))
        self.binding=HermesSessionBinding(self.runner,self.ctx,Source)

    def admit(self):
        return issue_admission(RAW,self.binding.current_source(),authorize_source=self.binding.authorize_source,
            bindings=(OWNER,),signing_key=KEY,clock=lambda:10000)

    def test_real_source_copy_and_live_profile_aware_authorization(self):
        result=self.admit()
        self.assertEqual(result['body']['company_id'],37)
        self.runner._is_user_authorized_for_source.assert_called_once_with(self.source,allow_adapter_delegation=False)
        self.assertIsNot(self.binding.current_source(),self.source)

    def test_revoked_gateway_access_is_not_replaced_by_matching_owner(self):
        self.runner._is_user_authorized_for_source.return_value=False
        with self.assertRaises(ValueError):self.admit()

    def test_missing_context_and_fake_environment_cannot_borrow_cached_owner(self):
        self.ctx=context();self.binding=HermesSessionBinding(self.runner,self.ctx,Source)
        with patch.dict(os.environ,{'HERMES_SESSION_KEY':'fixture-session','HERMES_SESSION_USER_ID':'123456789'}):
            with self.assertRaises(ValueError):self.admit()
        self.runner._get_cached_session_source.assert_not_called()

    def test_stale_cache_other_profile_and_transport_are_rejected(self):
        for field,value in (('user_id','987654321'),('chat_id','987654321'),('profile','other'),
                            ('chat_type','group'),('thread_id','9'),('platform','webhook')):
            with self.subTest(field=field):
                self.runner._get_cached_session_source.return_value=replace(self.source,**{field:value})
                with self.assertRaises(ValueError):self.admit()
        self.runner._is_user_authorized_for_source.assert_not_called()

    def test_cron_cleared_context_bot_and_profile_rejection_cannot_admit(self):
        for field,value in (('is_bot',True),('profile_route_rejected',True)):
            self.runner._get_cached_session_source.return_value=replace(self.source,**{field:value})
            with self.assertRaises(ValueError):self.admit()
        self.runner._get_cached_session_source.return_value=self.source
        self.ctx._CRON_SESSION.set('1')
        with self.assertRaises(ValueError):self.admit()
        self.ctx._CRON_SESSION.set('');self.ctx.key.set('')
        with self.assertRaises(ValueError):self.admit()

    def test_dict_source_is_not_a_gateway_object(self):
        self.runner._get_cached_session_source.return_value=vars(self.source)
        with self.assertRaises(ValueError):self.admit()

    def test_concurrent_tasks_cannot_use_other_sessions_cached_identity(self):
        other=Source(chat_id='987654321',user_id='987654321')
        sources={'owner':self.source,'other':other}
        self.runner._get_cached_session_source.side_effect=lambda key:sources[key]
        async def turn(source,key):
            bind_context(self.ctx,source,key)
            await asyncio.sleep(0)
            return self.binding.current_source().user_id
        async def both():return await asyncio.gather(turn(self.source,'owner'),turn(other,'other'))
        self.assertEqual(asyncio.run(both()),['123456789','987654321'])

    def test_model_handler_queues_to_real_files_then_worker_consumes_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('inbox','admissions','private','results'):(root/name).mkdir(mode=0o700)
            (root/'results').chmod(0o750)
            settings=BridgeSettings(OWNER,QueueConfig(PipelineConfig(SCOPE,root/'private',root/'results',os.getegid()),
                root/'inbox',os.geteuid()),root/'admissions',root/'inbox',root/'admissions')
            runtime=GatewayRuntime(settings,AdmissionSecret(KEY),current_source=self.binding.current_source,
                authorize_source=self.binding.authorize_source,clock=lambda:10000)
            handler=submit_handler(runtime)
            for args in ({'request_json':RAW.decode(),'company_id':37},{'request_json':RAW.decode(),'source':vars(self.source)},
                         {'request_json':'я'*32768},{'request_json':'\ud800'}):
                self.assertFalse(handler(args)['queued'])
            self.assertEqual(list((root/'inbox').iterdir()),[])
            submitted=handler({'request_json':RAW.decode()},session_id='ignored-model-identity')
            self.assertTrue(submitted['queued']);self.assertFalse(submitted['search_executed'])
            invoke=Mock(return_value=(json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True,
                'url':'https://www.b2b-center.ru/app/next/market-search'}],'confirmed':[],'review':[]}).encode(),0))
            worker=WorkerRuntime(settings,AdmissionSecret(KEY),invoke=invoke,verify_runtime=Mock(),clock=lambda:10000)
            self.assertEqual(worker.consume(PAYLOAD['request_id']+'.json')['status'],'processed')
            handler({'request_json':RAW.decode()})
            self.assertEqual(worker.consume(PAYLOAD['request_id']+'.json')['job_disposition'],'cached')
            invoke.assert_called_once()
            self.runner._is_user_authorized_for_source.side_effect=ValueError('PRIVATE_TOKEN')
            self.assertNotIn('PRIVATE_TOKEN',json.dumps(handler({'request_json':RAW.decode()})))

    def test_unknown_sources_are_not_imported_when_hash_or_origin_differs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'gateway').mkdir()
            path=root/'gateway/run.py';path.write_bytes(b'raise RuntimeError("MUST_NOT_EXECUTE")\n')
            expected={'gateway.run':hashlib.sha256(path.read_bytes()).hexdigest()}
            module=SimpleNamespace(__file__=str(path))
            with patch('jev_agent.tender_finder.hermes_binding.REVIEWED_MODULES',expected),patch.dict('sys.modules',{'gateway.run':module}):
                self.assertIs(verified_loaded_modules(root,expected_uid=os.geteuid())['gateway.run'],module)
                module.__file__='/some/other/source.py'
                with self.assertRaises(RuntimeMismatch):verified_loaded_modules(root,expected_uid=os.geteuid())
                module.__file__=str(path);path.write_bytes(b'changed')
                with self.assertRaises(RuntimeMismatch):verified_loaded_modules(root,expected_uid=os.geteuid())

    def test_writable_or_symlinked_source_does_not_pass_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'gateway').mkdir()
            path=root/'gateway/run.py';path.write_bytes(b'public')
            expected={'gateway.run':hashlib.sha256(b'public').hexdigest()}
            with patch('jev_agent.tender_finder.hermes_binding.REVIEWED_MODULES',expected),patch.dict('sys.modules',{'gateway.run':SimpleNamespace(__file__=str(path))}):
                path.chmod(0o666)
                with self.assertRaises(RuntimeMismatch):verified_loaded_modules(root,expected_uid=os.geteuid())
                path.unlink();(root/'other.py').write_bytes(b'public');path.symlink_to(root/'other.py')
                with self.assertRaises(RuntimeMismatch):verified_loaded_modules(root,expected_uid=os.geteuid())

    def test_bootstrap_requires_actual_reviewed_runner(self):
        with patch('jev_agent.tender_finder.hermes_binding.verified_loaded_modules',return_value={
                'gateway.run':SimpleNamespace(GatewayRunner=type('ActualRunner',(),{}))}):
            with self.assertRaises(RuntimeMismatch):bind_gateway(self.runner,None,None)

    def test_bootstrap_wires_verified_session_and_authorization_callbacks(self):
        modules={'gateway.run':SimpleNamespace(GatewayRunner=type(self.runner)),
                 'gateway.session_context':self.ctx,
                 'gateway.session':SimpleNamespace(SessionSource=Source)}
        with patch('jev_agent.tender_finder.hermes_binding.verified_loaded_modules',return_value=modules),patch(
                'jev_agent.tender_finder.hermes_binding.GatewayRuntime') as runtime:
            bind_gateway(self.runner,'protected-settings','protected-key')
        args,callbacks=runtime.call_args
        self.assertEqual(args,('protected-settings','protected-key'))
        source=callbacks['current_source']()
        self.assertEqual(source,self.source)
        self.assertTrue(callbacks['authorize_source'](source))
        self.runner._is_user_authorized_for_source.assert_called_once_with(source,allow_adapter_delegation=False)


if __name__=='__main__':unittest.main()
