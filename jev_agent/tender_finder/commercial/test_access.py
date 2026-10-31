from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,AsyncMock

from .access import Rules,PublicAccess,Decision
from .b2b_browser import Session
from .b2b import B2BReader
from .model import Profile
from .portal_reader import source_bundle
from .runner import run
from .test_commercial import NOW,SCOPE


class RulesTests(unittest.TestCase):
    def test_wildcards_query_and_end_anchor(self):
        rules=Rules('User-agent: *\nDisallow: /private/*\nDisallow: /*?token=*\nDisallow: /exact$\n')
        for url in ('https://public.example/private/1','https://public.example/file?token=abc','https://public.example/exact'):
            self.assertFalse(rules.allowed(url))
        self.assertTrue(rules.allowed('https://public.example/exact-more'))

    def test_longest_rule_and_allow_on_equal_length(self):
        rules=Rules('User-agent: *\nDisallow: /\nAllow: /public/\nDisallow: /same\nAllow: /same\n')
        self.assertTrue(rules.allowed('https://public.example/public/card'))
        self.assertFalse(rules.allowed('https://public.example/private'))
        self.assertTrue(rules.allowed('https://public.example/same'))

    def test_most_specific_agent_groups_are_merged_and_wildcard_not_reused(self):
        rules=Rules('User-agent: *\nDisallow: /\n\nUser-agent: StroykaJev\nDisallow: /one\n\nUser-agent: StroykaJev\nDisallow: /two\n')
        self.assertTrue(rules.allowed('https://public.example/other'))
        self.assertFalse(rules.allowed('https://public.example/one'))
        self.assertFalse(rules.allowed('https://public.example/two'))

    def test_actual_b2b_search_rule_is_a_stop_not_empty_search(self):
        rules=Rules('User-agent: *\nDisallow: /app/next/market-search?\n')
        self.assertFalse(rules.allowed('https://www.b2b-center.ru/app/next/market-search?q=roof'))

    def test_percent_unreserved_and_unicode_are_compared_consistently(self):
        rules=Rules('User-agent: *\nDisallow: /private~\nDisallow: /ремонт\n')
        self.assertFalse(rules.allowed('https://public.example/private%7E'))
        self.assertFalse(rules.allowed('https://public.example/%D1%80%D0%B5%D0%BC%D0%BE%D0%BD%D1%82'))

    def test_empty_and_sitemap_only_policies_remain_valid(self):
        for text in ('','# comment','Sitemap: https://public.example/sitemap.xml'):
            self.assertTrue(Rules(text).allowed('https://public.example/card'))

    def test_bad_html_and_giant_policy_are_not_allow(self):
        for text in ('<html>Testing...</html>','upstream connection reset','Error: connection refused','x'*(128*1024+1)):
            with self.assertRaises(ValueError):Rules(text)


class GateTests(unittest.TestCase):
    def test_robots_404_allows_but_403_and_503_do_not(self):
        for status,allowed,reason in ((404,True,'allowed'),(403,False,'robots_disallow'),(503,False,'policy_not_verified')):
            policy=PublicAccess(('public.example',),fetch=lambda _: (status,None,b''))
            result=policy.check('https://public.example/card')
            self.assertEqual((result.allowed,result.status),(allowed,reason))

    def test_positive_and_negative_cache_do_not_hammer_origin(self):
        read=Mock(return_value=(200,None,b'User-agent: *\nDisallow: /private'))
        policy=PublicAccess(('public.example',),fetch=read)
        self.assertFalse(policy.check('https://public.example/private').allowed)
        self.assertTrue(policy.check('https://public.example/card').allowed)
        read.assert_called_once()

    def test_foreign_redirect_and_forbidden_host_never_requested(self):
        read=Mock(return_value=(302,'https://attacker.example/robots.txt',b''))
        policy=PublicAccess(('public.example',),fetch=read)
        self.assertFalse(policy.check('https://public.example/card').allowed)
        self.assertEqual(read.call_count,1)
        read.reset_mock()
        self.assertFalse(policy.check('https://attacker.example/card').allowed)
        read.assert_not_called()

    def test_error_text_is_not_exposed(self):
        policy=PublicAccess(('public.example',),fetch=Mock(side_effect=RuntimeError('PRIVATE_TOKEN')))
        result=policy.check('https://public.example/card')
        self.assertEqual(result.status,'policy_not_verified')
        self.assertNotIn('PRIVATE_TOKEN',str(result))

    def test_batch_reports_denied_source_without_navigating(self):
        from contextlib import asynccontextmanager
        calls=[]
        @asynccontextmanager
        async def browser(source):
            calls.append('browser_opened')
            async def call(method,args):calls.append(method);raise AssertionError('not allowed')
            yield call
        sources,adapters=source_bundle(open_browser=browser,clock=lambda:NOW,
                                      access_check=lambda _:Decision(False,'robots_disallow'))
        with tempfile.TemporaryDirectory() as directory:
            result=run('fixture-denied',SCOPE,directory,sources={'b2b':sources['b2b']},
                       adapters={'b2b':adapters['b2b']},clock=lambda:NOW)
        self.assertEqual(result['coverage'][0]['status'],'robots_disallow')
        self.assertEqual(calls,[])
        self.assertEqual(result['sections']['priority'],[])


class BrowserGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_gate_runs_before_browser_navigation(self):
        call=AsyncMock()
        session=Session(call,lambda:NOW,access_check=lambda _:Decision(False,'robots_disallow'))
        result=await session.read('https://www.b2b-center.ru/market/fixture/tender-123/')
        self.assertEqual(result.status,'robots_disallow');call.assert_not_called()

    async def test_denied_new_navigation_clears_old_attachment_permissions(self):
        from .test_attachment_browser import DOC_URL,CARD_URL
        from .documents import MAX_BYTES
        async def call(method,args):
            return {} if method=='Page.navigate' else {'result':{'value':{
                'url':CARD_URL,'ready':'complete','oversize':False,'text':'Закупка № fixture',
                'links':[{'url':DOC_URL,'name':'Проект договора','section':'procurement_documents'}]}}}
        session=Session(call,lambda:NOW,poll_seconds=0)
        await session.read(CARD_URL)
        session.access_check=lambda _:Decision(False,'robots_disallow')
        await session.read(CARD_URL)
        with self.assertRaises(ValueError):await session.download(DOC_URL,MAX_BYTES)


if __name__=='__main__':unittest.main()
