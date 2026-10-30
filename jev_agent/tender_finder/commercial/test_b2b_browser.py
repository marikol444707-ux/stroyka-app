from contextlib import asynccontextmanager
import unittest
from unittest.mock import AsyncMock

from .b2b_browser import Session, browser_adapter, approved_url
from .model import Profile
from .test_b2b import URL,TEXT
from .test_commercial import NOW
from jev_agent.server_runtime.scripts.jev_commercial_search import search_url,OBSERVE


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_primary_text_is_stable_and_navigation_is_read_only(self):
        async def call(method,args):
            if method=='Page.navigate':return {}
            return {'result':{'value':{'url':URL,'ready':'complete','oversize':False,'text':TEXT}}}
        bound=AsyncMock(side_effect=call)
        page=await Session(bound,lambda:NOW,poll_seconds=0).read(URL)
        self.assertEqual(page.text,TEXT);self.assertEqual(page.status,'ok')
        self.assertTrue(all(item.args[0] in ('Page.navigate','Runtime.evaluate') for item in bound.call_args_list))

    async def test_foreign_login_post_and_mutation_urls_rejected_before_cdp(self):
        for url in ('https://attacker.example/a','https://www.b2b-center.ru/login/',
                    'https://www.b2b-center.ru/app/next/market-search?q=x&command=delete'):
            call=AsyncMock()
            with self.assertRaises(ValueError):await Session(call,lambda:NOW,poll_seconds=0).read(url)
            call.assert_not_called()

    async def test_captcha_stops_immediately(self):
        async def call(method,args):
            return {} if method=='Page.navigate' else {'result':{'value':{
                'url':URL,'ready':'complete','oversize':False,'text':'Подтвердите, что вы не робот'}}}
        page=await Session(call,lambda:NOW,poll_seconds=0).read(URL)
        self.assertEqual(page.status,'captcha')

    async def test_redirect_and_oversize_fail_closed(self):
        for change in ({'url':'https://www.b2b-center.ru/login/'},{'oversize':True}):
            async def call(method,args):
                return {} if method=='Page.navigate' else {'result':{'value':{
                    'url':URL,'ready':'complete','oversize':False,'text':TEXT,**change}}}
            with self.assertRaises(ValueError):await Session(call,lambda:NOW,poll_seconds=0).read(URL)

    async def test_worker_does_not_nest_hermes_event_loop(self):
        adapter=browser_adapter(open_browser=lambda:None,clock=lambda:NOW)
        with self.assertRaises(ValueError):adapter(Profile(),NOW)


class SyncBrowserTests(unittest.TestCase):
    def test_browser_lifecycle_and_live_transport_shape_to_primary_reader(self):
        state={'url':None};closed=[]
        @asynccontextmanager
        async def open_browser():
            async def call(method,args):
                if method=='Page.navigate':state['url']=args['url'];return {}
                url=state['url']
                if args['expression']==OBSERVE:
                    from urllib.parse import parse_qs,urlsplit
                    return {'result':{'value':{'url':url,'query':parse_qs(urlsplit(url).query)['q'][0],
                        'selected':['Объявления о закупках','Актуально • 1'],'rows':[{'url':URL}]}}}
                return {'result':{'value':{'url':url,'ready':'complete','oversize':False,
                                           'text':TEXT if url==URL else 'Синтетическая выдача'}}}
            try:yield call
            finally:closed.append(True)
        result=browser_adapter(open_browser=open_browser,clock=lambda:NOW)(Profile(queries=('кровля',)),NOW)
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(closed,[True])
        self.assertEqual(result.status,'partial')


if __name__=='__main__':unittest.main()
