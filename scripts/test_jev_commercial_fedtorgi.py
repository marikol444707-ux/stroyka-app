import json
import unittest
from datetime import datetime
from unittest.mock import patch
from urllib.parse import urlsplit

from scripts.jev_commercial_search import (
    FEDTORGI_API, MSK, fedtorgi_payload, fedtorgi_page,
    fedtorgi_row, fedtorgi_source, procedure_url,
)


class FedtorgiCommercialTest(unittest.TestCase):
    def procedure(self, **changes):
        row = {
            'id': 'f3c4204e-2191-4dbf-967a-92efa4b45f42',
            'number': 71, 'status': 'STATUS_ACCEPTING_APPLICATIONS',
            'platform_type': 'SECTION_COMMERCIAL_PROCEDURES',
            'status_localized': 'Идет прием заявок', 'type': 'REQUEST_OFFERS',
            'type_localized': 'Запрос предложений',
            'title': 'Капитальный ремонт школы в Ставрополе',
            'price_localized': '4 000 000,00 ₽',
            'organizer_full_title': 'ООО Заказчик',
            'close_bid_date': '2026-10-30 12:00:00',
        }
        row.update(changes)
        return row

    def response(self, rows=None, **changes):
        data = {'data': rows or [], 'page': 1, 'limit': 10, 'total_count': len(rows or [])}
        data.update(changes)
        return json.dumps(data, ensure_ascii=False)

    def test_payload_restricts_public_search_to_commercial_open_procedures(self):
        payload = fedtorgi_payload('капитальный ремонт')
        self.assertEqual(payload['name'], 'капитальный ремонт')
        self.assertEqual(payload['sections'], ['SECTION_COMMERCIAL_PROCEDURES'])
        self.assertEqual(payload['statuses'], ['STATUS_ACTIVE', 'STATUS_ACCEPTING_APPLICATIONS'])
        self.assertEqual(urlsplit(FEDTORGI_API).netloc, 'lk.fedtorgi.ru')

    def test_validates_search_response_and_normalizes_result_with_cautious_region(self):
        page = fedtorgi_page(self.response([self.procedure()]), page=1)
        self.assertEqual(page['total_count'], 1)
        row = fedtorgi_row(page['data'][0])
        self.assertEqual(procedure_url(row), 'https://etpp.ru/tenders/f3c4204e-2191-4dbf-967a-92efa4b45f42')
        self.assertEqual(row['region_scope'], 'title_text')
        self.assertEqual(row['deadline'], '30.10.2026 12:00')
        with self.assertRaises(RuntimeError):
            fedtorgi_page('{"data":{},"page":1,"limit":10,"total_count":0}', page=1)

    def test_rejects_invalid_ids_and_never_claims_unknown_regime_confirmed(self):
        with self.assertRaises(ValueError):
            fedtorgi_row(self.procedure(id='https://evil.example/'))
        with self.assertRaises(ValueError):
            procedure_url({'source': 'Торги Федерации', 'url': 'https://evil.example/tenders/id'})

    def test_verified_empty_active_search_is_successful_source(self):
        def fake_post(url, payload, page, limit):
            self.assertEqual(url, FEDTORGI_API)
            self.assertEqual(payload['statuses'], ['STATUS_ACTIVE', 'STATUS_ACCEPTING_APPLICATIONS'])
            return {'data': [], 'page': page, 'limit': limit, 'total_count': 0}

        with patch('scripts.jev_commercial_search.fedtorgi_public_post', side_effect=fake_post):
            rows, sources = fedtorgi_source(now=datetime(2026, 10, 21, 12, 0, tzinfo=MSK))
        self.assertEqual(rows, [])
        self.assertTrue(sources)
        self.assertTrue(all(source['ok'] for source in sources))
        self.assertTrue(all(source['status'] == 'no_active_results' for source in sources))


if __name__ == '__main__':
    unittest.main()
