"""Synthetic CDP responses. No site access or live transport acceptance."""
import asyncio
import base64
from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from .b2b_browser import Session,browser_adapter,DOWNLOAD_JS
from .documents import MAX_BYTES
from .document_worker import extract
from .model import Profile
from .runner import run
from .sources import source_registry
from .test_b2b import URL as CARD_URL,TEXT as CARD_TEXT
from .test_commercial import NOW,SCOPE
from .test_documents import URL as DOC_URL,TEXT as TERMS_TEXT,docx
from jev_agent.server_runtime.scripts.jev_commercial_search import OBSERVE


def downloaded(raw):return {'status':'ok','url':DOC_URL,'bytes':len(raw),'base64':base64.b64encode(raw).decode()}


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def session(self,result=None):
        state={'url':None};calls=[]
        async def call(method,args):
            calls.append((method,args))
            if method=='Page.navigate':state['url']=args['url'];return {}
            if method=='Page.getFrameTree':return {'frameTree':{'frame':{'id':'fixture-frame','url':state['url']}}}
            if method=='Page.createIsolatedWorld':return {'executionContextId':77}
            if method=='Runtime.evaluate' and args.get('contextId')==77:
                return {'result':{'value':downloaded(b'fixture') if result is None else result}}
            return {'result':{'value':{'url':state['url'],'ready':'complete','oversize':False,
                'text':CARD_TEXT,'links':[{'url':DOC_URL,'name':'Проект договора','section':'procurement_documents'}]}}}
        session=Session(call,lambda:NOW,poll_seconds=0)
        await session.read(CARD_URL)
        return session,calls,state

    async def test_only_observed_link_uses_isolated_world_no_credentials_or_redirects(self):
        session,calls,_=await self.session()
        result=await session.download(DOC_URL,MAX_BYTES)
        self.assertEqual(result.content,b'fixture')
        evaluate=next(args for method,args in calls if args.get('contextId')==77)
        self.assertIn("credentials:'omit'",evaluate['expression'])
        self.assertIn("redirect:'error'",evaluate['expression'])
        self.assertIn("method:'GET'",evaluate['expression'])
        self.assertTrue(evaluate['awaitPromise'])
        world=next(args for method,args in calls if method=='Page.createIsolatedWorld')
        self.assertFalse(world['grantUniveralAccess'])

    async def test_unknown_link_or_excessive_limit_never_reaches_cdp(self):
        session,calls,_=await self.session();before=len(calls)
        for url,limit in ((DOC_URL.replace('synthetic','other'),MAX_BYTES),
                          ('https://attacker.example/file.pdf',MAX_BYTES),(DOC_URL,MAX_BYTES+1)):
            with self.assertRaises(ValueError):await session.download(url,limit)
        self.assertEqual(len(calls),before)

    async def test_footer_or_unknown_section_never_authorizes_download(self):
        for section in (None,'footer'):
            calls=[]
            async def call(method,args):
                calls.append((method,args))
                if method=='Page.navigate':return {}
                row={'url':DOC_URL,'name':'Политика конфиденциальности'}
                if section:row['section']=section
                return {'result':{'value':{'url':CARD_URL,'ready':'complete','oversize':False,'text':CARD_TEXT,'links':[row]}}}
            session=Session(call,lambda:NOW,poll_seconds=0)
            await session.read(CARD_URL);before=len(calls)
            with self.assertRaises(ValueError):await session.download(DOC_URL,MAX_BYTES)
            self.assertEqual(len(calls),before)

    async def test_download_without_primary_card_is_rejected(self):
        call=AsyncMock()
        with self.assertRaises(ValueError):await Session(call,lambda:NOW).download(DOC_URL,MAX_BYTES)
        call.assert_not_called()

    async def test_changed_frame_blocks_fetch(self):
        session,calls,state=await self.session();state['url']='https://www.b2b-center.ru/login/'
        result=await session.download(DOC_URL,MAX_BYTES)
        self.assertEqual(result.status,'unavailable')
        self.assertFalse(any(args.get('contextId')==77 for method,args in calls))

    async def test_login_or_failure_is_cached_without_automatic_retry(self):
        for status in ('login_required','unavailable'):
            session,calls,_=await self.session({'status':status})
            first=await session.download(DOC_URL,MAX_BYTES);count=len(calls)
            self.assertEqual(first.status,status)
            self.assertEqual(first,await session.download(DOC_URL,MAX_BYTES))
            self.assertEqual(len(calls),count)

    async def test_oversize_corrupt_base64_wrong_url_and_size_fail_closed(self):
        for result in ({**downloaded(b'fixture'),'bytes':MAX_BYTES+1},
                       {**downloaded(b'fixture'),'base64':'invalid%%%'} ,
                       {**downloaded(b'fixture'),'url':'https://attacker.example/file.pdf'},
                       {**downloaded(b'fixture'),'bytes':1}):
            session,_,_=await self.session(result)
            self.assertEqual((await session.download(DOC_URL,MAX_BYTES)).status,'unavailable')

    async def test_navigation_invalidates_previous_card_links(self):
        session,calls,_=await self.session()
        # A failed navigation must not preserve attachment authority from before.
        original=session.call
        async def fail(method,args):
            if method=='Page.navigate':raise RuntimeError('fixture')
            return await original(method,args)
        session.call=fail
        with self.assertRaises(RuntimeError):await session.read(CARD_URL)
        before=len(calls)
        with self.assertRaises(ValueError):await session.download(DOC_URL,MAX_BYTES)
        self.assertEqual(len(calls),before)

    async def test_expired_download_budget_makes_no_remote_call(self):
        session,calls,_=await self.session();session._download_deadline=0
        before=len(calls)
        self.assertEqual((await session.download(DOC_URL,MAX_BYTES)).status,'unavailable')
        self.assertEqual(len(calls),before)

    async def test_navigation_during_world_creation_invalidates_old_permission(self):
        session,calls,_=await self.session();original=session.call;once=[True]
        async def navigate(method,args):
            if method=='Page.createIsolatedWorld' and once[0]:
                once[0]=False
                await session.read(CARD_URL)
            return await original(method,args)
        session.call=navigate
        self.assertEqual((await session.download(DOC_URL,MAX_BYTES)).status,'unavailable')
        self.assertFalse(any(args.get('contextId')==77 for method,args in calls))
        self.assertNotIn(DOC_URL,session._downloads)
        self.assertEqual((await session.download(DOC_URL,MAX_BYTES)).status,'ok')


class EndToEndTests(unittest.TestCase):
    def browser(self,*,content=None,status='ok'):
        state={'url':None};closed=[]
        raw=docx(TERMS_TEXT) if content is None else content
        @asynccontextmanager
        async def open_browser():
            async def call(method,args):
                if method=='Page.navigate':state['url']=args['url'];return {}
                url=state['url']
                if method=='Page.getFrameTree':return {'frameTree':{'frame':{'id':'fixture-frame','url':url}}}
                if method=='Page.createIsolatedWorld':return {'executionContextId':77}
                if args.get('contextId')==77:
                    return {'result':{'value':downloaded(raw) if status=='ok' else {'status':status}}}
                if args['expression']==OBSERVE:
                    from urllib.parse import parse_qs,urlsplit
                    return {'result':{'value':{'url':url,'query':parse_qs(urlsplit(url).query)['q'][0],
                        'selected':['Объявления о закупках','Актуально • 1'],'rows':[{'url':CARD_URL}]}}}
                return {'result':{'value':{'url':url,'ready':'complete','oversize':False,
                    'text':CARD_TEXT if url==CARD_URL else 'Синтетическая выдача',
                    'links':[{'url':DOC_URL,'name':'Проект договора','section':'procurement_documents'}] if url==CARD_URL else []}}}
            try:yield call
            finally:closed.append(True)
        return open_browser,closed

    def test_card_browser_binary_document_conditions_to_saved_report(self):
        browser,closed=self.browser()
        adapter=browser_adapter(open_browser=browser,clock=lambda:NOW,document_scope=SCOPE,
                                extract_document=extract) # synthetic originals only
        with tempfile.TemporaryDirectory() as directory:
            report=run('fixture-browser-binary',SCOPE,directory,sources={'b2b':source_registry()['b2b']},
                       adapters={'b2b':adapter},clock=lambda:NOW)
            replay=run('fixture-browser-binary',SCOPE,directory,sources={'b2b':source_registry()['b2b']},
                       adapters={'b2b':lambda *_:self.fail('duplicate search')},clock=lambda:NOW)
        self.assertEqual(report,replay)
        self.assertEqual(closed,[True])
        self.assertEqual(report['coverage'][0]['documents'],1)
        self.assertEqual(report['coverage'][0]['attachments'][0]['status'],'text')
        self.assertIn('payment',report['sections']['unconfirmed'][0]['conflicts'])

    def test_login_required_is_reported_and_never_upgraded_to_no_document(self):
        browser,closed=self.browser(status='login_required')
        adapter=browser_adapter(open_browser=browser,clock=lambda:NOW,document_scope=SCOPE,extract_document=extract)
        result=adapter(Profile(queries=('кровля',)),NOW)
        self.assertEqual(result.attachment_statuses[0]['status'],'login_required')
        self.assertEqual(result.candidates[0].facts['documents'][0].missing,'Не удалось проверить')
        self.assertEqual(closed,[True])

    def test_default_extractor_requires_real_sandbox_and_has_no_implicit_fallback(self):
        from unittest.mock import patch
        browser,_=self.browser()
        adapter=browser_adapter(open_browser=browser,clock=lambda:NOW,document_scope=SCOPE)
        with patch('shutil.which',return_value=None):result=adapter(Profile(queries=('кровля',)),NOW)
        self.assertEqual(result.attachment_statuses[0]['status'],'not_verified')

    def test_no_implicit_company_or_ambiguous_document_binding(self):
        browser,_=self.browser()
        with self.assertRaises(ValueError):browser_adapter(open_browser=browser,clock=lambda:NOW,document_scope=1)
        with self.assertRaises(ValueError):browser_adapter(open_browser=browser,clock=lambda:NOW,
            document_scope=SCOPE,document_enricher=lambda *_:None)


if __name__=='__main__':unittest.main()
