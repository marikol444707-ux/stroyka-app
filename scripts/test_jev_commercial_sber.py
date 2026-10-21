import json
import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from scripts.jev_commercial_search import (
    MSK, assess, procedure_url, sber_row, sber_search_checks, sber_search_url,
)


class SberCommercialTest(unittest.TestCase):
    now = datetime(2026, 10, 21, 12, 0, tzinfo=MSK)

    def test_url_has_public_commercial_source_and_active_deadline_range(self):
        url = sber_search_url('Ставрополь', self.now)
        parsed = urlsplit(url)
        query = json.loads(parse_qs(parsed.query)['query'][0])
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ('https', 'www.sberbank-ast.ru', '/UnitedPurchaseList.html'))
        self.assertEqual(query['sourceTerm'], ['Торги коммерческих заказчиков'])
        self.assertEqual(query['mainInput'], 'Ставрополь')
        self.assertEqual(query['requestEndDate'], {
            'startRequestDate': '21.10.2026', 'endRequestDate': '21.10.2027'})

    def test_query_is_verified_against_url_and_rendered_page(self):
        observed = {'url': sber_search_url('Ставрополь', self.now), 'query': 'Ставрополь',
                    'page_state': 'Источник: Торги коммерческих заказчиков\nСтрока поиска: Ставрополь\n'
                                  'Окончание подачи заявок: 21.10.2026 - 21.10.2027'}
        bare_url = 'https://www.sberbank-ast.ru/UnitedPurchaseList.html'
        self.assertTrue(all(sber_search_checks(observed, 'Ставрополь', self.now,
                                               sber_search_url('Ставрополь', self.now)).values()))
        # The SPA consumes and removes its JSON query from the final address bar.
        self.assertTrue(all(sber_search_checks(dict(observed, url=bare_url), 'Ставрополь',
                                               self.now, sber_search_url('Ставрополь', self.now)).values()))
        observed['page_state'] = observed['page_state'].replace('21.10.2027', '21.10.2025')
        self.assertFalse(sber_search_checks(observed, 'Ставрополь', self.now)['active_deadline_filter'])

    def test_only_first_party_purchaseview_links_are_accepted(self):
        value = 'https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/43/0/0/4257576'
        self.assertEqual(procedure_url({'source': 'Сбер А', 'url': value}), value)
        for url in (value + '?x=1', value.replace('utp.sberbank-ast.ru', 'evil.test'),
                    'https://www.sberbank-ast.ru/UnitedPurchaseList.html'):
            with self.assertRaises(ValueError):
                procedure_url({'source': 'Сбер А', 'url': url})

    def test_sales_are_excluded_and_active_work_is_reviewed_safely(self):
        card = {'url': 'https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/43/0/0/4257576',
                'title': 'Строительство объекта в Ставропольском крае',
                'procedure_type': 'Аукцион (продажа, с ЭП)', 'deadline': '31.10.2026 12:00'}
        sale = assess(sber_row(card), self.now)
        self.assertEqual((sale['decision'], sale['reasons']), ('excluded', ['sale_not_procurement']))
        work = assess(sber_row(dict(card, procedure_type='Запрос предложений')), self.now)
        self.assertEqual(work['decision'], 'confirmed')

    def test_other_region_and_unknown_type_are_not_confirmed(self):
        card = {'url': 'https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/43/0/0/4257576',
                'title': 'Капитальный ремонт здания, г. Краснодар',
                'procedure_type': 'Запрос предложений', 'deadline': '31.10.2026 12:00'}
        self.assertEqual(assess(sber_row(card), self.now)['reasons'], ['other_region'])
        card['title'] = 'Капитальный ремонт здания, г. Ставрополь'
        card['procedure_type'] = 'Иной тип'
        self.assertEqual(assess(sber_row(card), self.now)['decision'], 'review')


if __name__ == '__main__':
    unittest.main()
