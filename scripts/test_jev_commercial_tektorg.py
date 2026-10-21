import json
import unittest
from datetime import datetime
from urllib.error import HTTPError
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts.jev_commercial_search import (
    MSK, assess, procedure_url, tektorg_page_data, tektorg_row,
    tektorg_public_get, tektorg_search_checks, tektorg_search_url, tektorg_source,
)


class TektorgCommercialTest(unittest.TestCase):
    now = datetime(2026, 10, 21, 12, 0, tzinfo=MSK)

    def listing(self, *, rows=None, total=0, status='loading', title='Поиск закупок 223-ФЗ'):
        return {
            'props': {'pageProps': {'meta': {'title': title}, 'initialReduxState': {
                'listingProcedures': {'data': rows or [], 'total': total,
                    'totalPages': max(1, (total + 14) // 15), 'status': status,
                    'sectionsCodes': {'sectionsCodes[0]': 'zakupki'}}}}}}

    def html(self, state):
        return '<script id="__NEXT_DATA__" type="application/json">{}</script>'.format(
            json.dumps(state, ensure_ascii=False))

    def item(self, **changes):
        row = {'id': 13910293, 'registryNumber': '12345',
               'title': 'Капитальный ремонт школы в Ставрополе',
               'statusName': 'Приём заявок', 'typeName': 'Запрос предложений',
               'organizerName': 'ООО Заказчик',
               'dates': {'dateEndRegistration': '2026-10-30T12:00:00+03:00'},
               'geoPoints': [], 'sumPrice': 500000, 'typeCustomName': 'Коммерческая закупка'}
        row.update(changes)
        return row

    def test_search_url_is_first_party_and_preserves_exact_term(self):
        url = tektorg_search_url('Ставрополь капитальный ремонт')
        parsed = urlsplit(url)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ('https', 'www.tektorg.ru', '/223-fz/procedures'))
        self.assertEqual(parse_qs(parsed.query)['name'], ['Ставрополь капитальный ремонт'])
        with self.assertRaises(ValueError):
            tektorg_search_url('')

    def test_extracts_server_rendered_rows_and_accepts_verified_empty_search(self):
        props, listing, rows = tektorg_page_data(self.html(self.listing()))
        checks = tektorg_search_checks(
            tektorg_search_url('Ставрополь'), props, listing, rows, 'Ставрополь')
        self.assertTrue(all(checks.values()))
        with self.assertRaises(RuntimeError):
            tektorg_page_data('<html>not the procedure listing</html>')

    def test_inconsistent_or_untrusted_search_state_fails_closed(self):
        item = self.item()
        props, listing, rows = tektorg_page_data(self.html(
            self.listing(rows=[item], total=15, status='success')))
        self.assertFalse(tektorg_search_checks(
            'https://evil.example/223-fz/procedures?name=Ставрополь',
            props, listing, rows, 'Ставрополь')['official_search_page'])
        self.assertFalse(tektorg_search_checks(
            tektorg_search_url('Москва'), props, listing, rows, 'Ставрополь')['term_preserved'])
        bad = dict(listing, total=-1)
        self.assertFalse(tektorg_search_checks(
            tektorg_search_url('Ставрополь'), props, bad, rows,
            'Ставрополь')['result_shape'])

    def test_normalizes_official_link_and_keeps_mixed_regime_unconfirmed(self):
        row = tektorg_row(self.item())
        self.assertEqual(procedure_url(row), 'https://www.tektorg.ru/223-fz/procedures/13910293')
        self.assertEqual(row['deadline'], '30.10.2026 12:00')
        reviewed = assess(row, self.now)
        self.assertEqual(reviewed['decision'], 'review')
        self.assertIn('procurement_regime_unknown', reviewed['reasons'])
        self.assertNotIn('confirmed', reviewed['decision'])

    def test_title_only_region_requires_review_and_expired_rows_are_excluded(self):
        row = tektorg_row(self.item(title='Капитальный ремонт школы в Ставрополе'))
        self.assertEqual(row['region_scope'], 'title_text')
        self.assertEqual(assess(row, self.now)['decision'], 'review')
        expired = tektorg_row(self.item(dates={'dateEndRegistration': '2026-10-20T12:00:00+03:00'}))
        self.assertEqual(assess(expired, self.now)['decision'], 'excluded')

    def test_source_does_not_report_active_rows_without_a_future_deadline(self):
        item = self.item(dates={})
        state = self.listing(rows=[item], total=1, status='success')
        body = self.html(state)
        with patch('scripts.jev_commercial_search.tektorg_public_get',
                   side_effect=lambda url: (url, body)):
            rows, sources = tektorg_source(self.now)
        self.assertEqual(rows, [])
        self.assertTrue(all(source['ok'] for source in sources))
        self.assertTrue(all(source['status'] == 'no_active_results' for source in sources))

    def test_untrusted_procedure_urls_are_rejected(self):
        good = tektorg_row(self.item())
        for url in ('http://www.tektorg.ru/223-fz/procedures/13910293',
                    'https://evil.example/223-fz/procedures/13910293',
                    'https://www.tektorg.ru/223-fz/procedures/13910293?next=evil'):
            with self.assertRaises(ValueError):
                procedure_url(dict(good, url=url))

    def test_retries_one_transient_gateway_failure_but_not_access_denial(self):
        with patch('scripts.jev_commercial_search.public_get',
                   side_effect=[HTTPError('https://www.tektorg.ru/', 502, 'gateway', {}, None),
                                ('https://www.tektorg.ru/', '<html>ok</html>')]), \
             patch('scripts.jev_commercial_search.time.sleep') as sleep:
            self.assertEqual(tektorg_public_get('https://www.tektorg.ru/'),
                             ('https://www.tektorg.ru/', '<html>ok</html>'))
            sleep.assert_called_once()
        with patch('scripts.jev_commercial_search.public_get',
                   side_effect=HTTPError('https://www.tektorg.ru/', 403, 'forbidden', {}, None)), \
             patch('scripts.jev_commercial_search.time.sleep') as sleep:
            with self.assertRaises(HTTPError):
                tektorg_public_get('https://www.tektorg.ru/')
            sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
