import asyncio
from datetime import datetime, timezone
import hashlib
import unittest
from unittest.mock import AsyncMock, Mock

from .card_page import MAX_TEXT_BYTES, notice_identity, read_notice_page

NUMBER='0000000000000000001'
URL='https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber='+NUMBER
NOW=datetime(2026,10,28,tzinfo=timezone.utc)


def page(**changes):
    return {'url':URL,'ready':'complete','text':'Синтетическая закупка № '+NUMBER,
            'html':'<html>synthetic</html>', **changes}


class CardPageTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_wait_budget_cancels_stuck_page_method(self):
        cancelled=[]
        async def stuck(*args):
            try:await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        browser=Mock();browser.page=AsyncMock(side_effect=stuck)
        result=await read_notice_page(URL,browser=browser,clock=lambda:NOW,timeout_seconds=1)
        self.assertEqual(result['status'],'page_timeout')
        self.assertEqual(cancelled,[True])

    async def test_existing_page_method_only_no_document_or_model_operations(self):
        browser=Mock();browser.page=AsyncMock(return_value=page())
        result=await read_notice_page(URL,browser=browser,clock=lambda:NOW)
        browser.page.assert_awaited_once_with(URL,NUMBER)
        self.assertEqual([call[0] for call in browser.mock_calls],['page'])
        self.assertEqual(result['text_sha256'],hashlib.sha256(page()['text'].encode()).hexdigest())
        self.assertTrue(result['untrusted_source_text'])
        self.assertFalse(result['card_fields_verified'])
        self.assertFalse(result['attachments_requested'])
        self.assertEqual(result['model_calls'],0)

    async def test_arbitrary_url_and_duplicate_id_rejected_before_browser_call(self):
        browser=Mock();browser.page=AsyncMock()
        for url in ('http://zakupki.gov.ru/1',URL.replace('zakupki.gov.ru','zakupki.gov.ru.evil.example'),
                    URL+'&regNumber='+NUMBER,URL+'&download=true',URL+'#fragment',
                    URL.replace('/common-info.html','/documents.html'),
                    URL.replace('https://','https://user:PRIVATE@')):
            with self.subTest(url=url),self.assertRaises(ValueError):
                await read_notice_page(url,browser=browser,clock=lambda:NOW)
        browser.page.assert_not_awaited()

    async def test_redirect_to_other_notice_or_page_is_not_accepted(self):
        for changes in ({'url':URL.replace(NUMBER,'0000000000000000002')},
                        {'url':URL.replace('/ea20/','/ok20/')},
                        {'url':'https://example.org/'},{'text':'Не найдено'},
                        {'text':'9'+NUMBER+'9'},{'ready':'loading'}):
            browser=Mock();browser.page=AsyncMock(return_value=page(**changes))
            result=await read_notice_page(URL,browser=browser,clock=lambda:NOW)
            self.assertFalse(result['ok']);self.assertNotIn('text',result)

    async def test_large_page_is_not_silently_truncated(self):
        browser=Mock();browser.page=AsyncMock(return_value=page(text=NUMBER+'я'*MAX_TEXT_BYTES))
        result=await read_notice_page(URL,browser=browser,clock=lambda:NOW)
        self.assertEqual(result['status'],'page_size_limit');self.assertNotIn('text',result)

    async def test_error_and_timeout_do_not_expose_private_exception_text(self):
        for exception,expected in ((TimeoutError('PRIVATE'),'page_timeout'),
                                   (RuntimeError('PRIVATE'),'page_not_verified')):
            browser=Mock();browser.page=AsyncMock(side_effect=exception)
            result=await read_notice_page(URL,browser=browser,clock=lambda:NOW)
            self.assertEqual(result['status'],expected);self.assertNotIn('PRIVATE',str(result))

    async def test_cancellation_is_not_swallowed_as_page_failure(self):
        browser=Mock();browser.page=AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await read_notice_page(URL,browser=browser,clock=lambda:NOW)

    async def test_naive_clock_and_unbounded_timeout_cannot_verify_page(self):
        browser=Mock();browser.page=AsyncMock(return_value=page())
        result=await read_notice_page(URL,browser=browser,clock=lambda:NOW.replace(tzinfo=None))
        self.assertFalse(result['ok'])
        with self.assertRaises(ValueError):
            await read_notice_page(URL,browser=browser,clock=lambda:NOW,timeout_seconds=99999)


if __name__=='__main__':unittest.main()
