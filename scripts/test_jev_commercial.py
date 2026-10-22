import unittest
from datetime import datetime, timezone

from scripts.jev_commercial_search import (
    B2B_TERMS, CONSTRUCTION_QUERY_TERMS, search_url, verify_search,
    assess, build_report, tender_url,
)


class CommercialTest(unittest.TestCase):
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)

    def row(self, **kwargs):
        return dict({'id': '123', 'url': 'https://www.b2b-center.ru/market/test/tender-123/',
            'title': 'Выполнение ремонта помещений магазина', 'organizer': 'ООО Заказчик',
            'region': 'Ставропольский край', 'deadline': 'до 25.10.2026 12:00',
            'price': 'Без указания цены'}, **kwargs)

    def test_search_requires_rendered_query_and_active_buy_tab(self):
        observed = {'url': search_url('Ставрополь'), 'query': 'Ставрополь',
                    'selected': ['Объявления о закупках', 'Актуально • 1'], 'rows': [self.row()]}
        self.assertTrue(verify_search(observed, 'Ставрополь'))
        self.assertFalse(verify_search(dict(observed, query=''), 'Ставрополь'))
        self.assertFalse(verify_search(dict(observed, selected=['В архиве • 1']), 'Ставрополь'))
        self.assertFalse(verify_search(dict(observed, rows=[]), 'Ставрополь'))
        self.assertTrue(verify_search(dict(observed, rows=[], selected=['Объявления о закупках','Актуально • 0']), 'Ставрополь'))

    def test_construction_not_supplies_vehicle_repair_or_cleaning(self):
        for title in ('Закупка кабеля Ставрополь', 'Ремонт ТС в Ставрополе', 'Уборка снега с кровли'):
            self.assertEqual(assess(self.row(title=title), self.now)['decision'], 'excluded')
        self.assertEqual(assess(self.row(), self.now)['decision'], 'review')

    def test_construction_synonyms_cover_capremont_roof_smr_and_networks(self):
        for title in (
            'Капремонт кровли школы',
            'Устройство кровли здания',
            'Выполнение СМР по реконструкции фасада',
            'Ремонт инженерных сетей здания',
            'Общестроительные работы в помещениях',
        ):
            with self.subTest(title=title):
                self.assertEqual(assess(self.row(title=title), self.now)['decision'], 'review')

    def test_search_terms_include_region_and_construction_synonyms_without_duplicates(self):
        self.assertEqual(len(B2B_TERMS), len(set(B2B_TERMS)))
        self.assertGreater(len(B2B_TERMS), 12)
        self.assertIn('Ставрополь капремонт', B2B_TERMS)
        self.assertIn('Ставропольский край инженерные сети', B2B_TERMS)
        self.assertIn('Ставрополь фасадные работы', B2B_TERMS)
        self.assertIn('капремонт', CONSTRUCTION_QUERY_TERMS)
        self.assertIn('строительно-монтажные работы', CONSTRUCTION_QUERY_TERMS)
        self.assertIn('устройство кровли', CONSTRUCTION_QUERY_TERMS)

    def test_address_not_organizer_and_deadline_moscow(self):
        self.assertEqual(assess(self.row(region='Москва', organizer='ООО Ставрополь'), self.now)['decision'], 'excluded')
        self.assertEqual(assess(self.row(deadline='до 21.10.2026 02:00'), self.now)['decision'], 'excluded')
        self.assertEqual(assess(self.row(deadline='не указано'), self.now)['decision'], 'review')

    def test_region_recognizes_all_searched_cities(self):
        for city in ('Георгиевск', 'Железноводск', 'Лермонтов'):
            with self.subTest(city=city):
                self.assertNotEqual(assess(self.row(region=city), self.now)['decision'], 'excluded')

    def test_unknown_regime_not_presented_as_commercial_and_duplicates(self):
        report = build_report([self.row(), self.row()], [], self.now)
        self.assertEqual(len(report['review']), 1)
        self.assertEqual(report['confirmed'], [])
        self.assertIn('procurement_regime_unknown', report['review'][0]['reasons'])
        self.assertEqual(assess(self.row(regime='223-ФЗ'), self.now)['decision'], 'excluded')

    def test_url_scope(self):
        self.assertEqual(tender_url(self.row()['url']+'#tracking'), self.row()['url'])
        for value in ('https://evil.test/market/test/tender-123/', 'https://www.b2b-center.ru/account/', 'http://www.b2b-center.ru/market/tender-123/'):
            with self.assertRaises(ValueError): tender_url(value)


if __name__ == '__main__': unittest.main()
