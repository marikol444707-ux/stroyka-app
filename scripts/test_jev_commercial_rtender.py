import asyncio
import json
import unittest
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts.jev_commercial_search import (
    MSK, assess, procedure_url, rtender_page_data, rtender_payload,
    rtender_row, rtender_search_url, rtender_source,
)


class RTenderCommercialTest(unittest.TestCase):
    now = datetime(2026, 10, 21, 12, 0, tzinfo=MSK)

    def item(self, **changes):
        value = {
            'identifier': '6796326008DP', 'uuid': 'corebofs002080000q2ni8slsi42kfcc',
            'type': 'BUYING_COMMERCIAL',
            'title': 'Капитальный ремонт школы в Ставрополе',
            'state': {'code': 'PurchaseLot_St_Dmnds_Started', 'title': 'Идет прием заявок'},
            'placementType': 'Аукцион в электронном виде',
            'gdEndDate': '28.10.2026 08:00&nbsp;МСК',
            'price': "<div class='aright'>1&nbsp;657&nbsp;897.44&nbsp;руб.</div>",
            'organizer': {'title': 'ООО Заказчик'},
            'lotLink': 'https://etp.r-tender.ru/app/LotCard/page?LotCard.lotEntity=LT%3Acorebofs002080000q2ni8slsi42kfcc',
        }
        value.update(changes)
        return value

    def test_payload_is_limited_to_public_active_commercial_type(self):
        payload = rtender_payload('Ставрополь')
        self.assertEqual(payload['query'], {'title': 'Ставрополь', 'types': ['BUYING_COMMERCIAL']})
        self.assertEqual(payload['filter'], {'state': ['GD']})
        self.assertEqual(payload['limit'], {'min': 0, 'max': 20, 'updateTotalCount': True})
        parsed = urlsplit(rtender_search_url('Ставрополь'))
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ('https', 'etp.r-tender.ru', '/searchServlet'))
        self.assertEqual(parse_qs(parsed.query)['query'][0],
                         '{"title":"Ставрополь","types":["BUYING_COMMERCIAL"]}')
        with self.assertRaises(ValueError):
            rtender_payload('')

    def test_row_preserves_explicit_commercial_status_and_official_identity(self):
        row = rtender_row(self.item())
        self.assertEqual(row['regime'], 'Коммерческая закупка')
        self.assertEqual(row['deadline'], '28.10.2026 08:00')
        self.assertEqual(row['price'], '1 657 897.44 руб.')
        self.assertEqual(procedure_url(row), self.item()['lotLink'].replace('%3A', '%3A'))
        reviewed = assess(row, self.now)
        self.assertEqual(reviewed['decision'], 'review')
        self.assertIn('work_location_needs_verification', reviewed['reasons'])

    def test_rejects_223_expired_states_bad_identity_and_foreign_links(self):
        with self.assertRaises(ValueError):
            rtender_row(self.item(type='BUYING_223'))
        with self.assertRaises(ValueError):
            rtender_row(self.item(state={'code': 'PurchaseLot_St_Closed', 'title': 'Завершена'}))
        with self.assertRaises(ValueError):
            rtender_row(self.item(lotLink='https://evil.example/app/LotCard/page?LotCard.lotEntity=LT:abc'))
        row = rtender_row(self.item())
        mismatch = assess(dict(row, url='https://etp.r-tender.ru/app/LotCard/page?LotCard.lotEntity=LT%3Aother'), self.now)
        self.assertEqual(mismatch['decision'], 'excluded')
        self.assertIn('invalid_source', mismatch['reasons'])

    def test_page_validation_rejects_changed_type_or_status_filter(self):
        term = 'Ставрополь'
        url = rtender_search_url(term)
        payload = {'count': 0, 'totalCount': 0, 'list': []}
        self.assertEqual(rtender_page_data(url, payload, term)['totalCount'], 0)
        self.assertEqual(rtender_page_data(url, {'count': 0, 'totalCount': 0, 'list': []}, term)['list'], [])
        wrong = url.replace('BUYING_COMMERCIAL', 'BUYING_223')
        with self.assertRaises(RuntimeError):
            rtender_page_data(wrong, payload, term)
        with self.assertRaises(RuntimeError):
            rtender_page_data(url, {'count': 0, 'totalCount': '0', 'list': []}, term)

    def test_source_verifies_each_public_search_and_accepts_empty_results(self):
        state = {'url': ''}

        async def fake_call(method, params):
            if method == 'Page.navigate':
                state['url'] = params['url']
                return {}
            self.assertEqual(method, 'Runtime.evaluate')
            return {'result': {'value': {'url': state['url'], 'state': 'complete',
                                         'body': json.dumps({'count': 0, 'totalCount': 0, 'list': []})}}}

        with patch('scripts.jev_commercial_search.asyncio.sleep'):
            rows, sources = asyncio.run(rtender_source(fake_call, self.now))
        self.assertEqual(rows, [])
        self.assertEqual(len(sources), 12)
        self.assertTrue(all(source['ok'] and source['status'] == 'no_active_results' for source in sources))

    def test_source_keeps_local_commercial_work_for_review_but_discards_other_region(self):
        state = {'url': ''}
        local = self.item()
        remote = self.item(identifier='8537326003DP', uuid='corebofs002080000q2l0e9v4hlpu3ok',
                           title='Строительство объекта в Тюмени',
                           lotLink='https://etp.r-tender.ru/app/LotCard/page?LotCard.lotEntity=LT%3Acorebofs002080000q2l0e9v4hlpu3ok')

        async def fake_call(method, params):
            if method == 'Page.navigate':
                state['url'] = params['url']
                return {}
            term = json.loads(parse_qs(urlsplit(state['url']).query)['query'][0])['title']
            rows = [local, remote] if term == 'Ставрополь' else []
            return {'result': {'value': {'url': state['url'], 'state': 'complete', 'body': json.dumps({
                'count': len(rows), 'totalCount': len(rows), 'list': rows})}}}

        with patch('scripts.jev_commercial_search.asyncio.sleep'):
            rows, sources = asyncio.run(rtender_source(fake_call, self.now))
        self.assertEqual([row['id'] for row in rows], ['6796326008DP'])
        self.assertEqual(sources[0]['status'], 'observed_first_page')
        self.assertEqual(assess(rows[0], self.now)['decision'], 'review')


if __name__ == '__main__':
    unittest.main()
