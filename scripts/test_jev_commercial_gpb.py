import unittest
from datetime import datetime, timezone

from scripts.jev_commercial_search import assess, etpgpb_row, procedure_url


class EtpgpbNormalizationTest(unittest.TestCase):
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)

    def item(self, category='Закупки.Бизнес', regions=None, path='/procedures/price_request/12345-test-procedure/'):
        return {'id': 'api-id-1', 'attributes': {
            'registry_number': '12345', 'rebranding_truncated_path': path,
            'section_category_name': category,
            'title': 'Выполнение капитального ремонта школы',
            'company_name': 'ООО Заказчик', 'lot_regions': regions or ['Ставропольский край'],
            'stage': 'Приём заявок', 'end_registration': '2026-10-25T09:00:00Z',
            'amount': 1500000,
        }}

    def test_commercial_business_record_is_normalized_and_confirmed(self):
        row = etpgpb_row(self.item())
        self.assertEqual(row['source'], 'ЭТП ГПБ')
        self.assertEqual(row['deadline'], '25.10.2026 12:00')
        self.assertEqual(row['regime'], 'Коммерческая закупка')
        self.assertEqual(assess(row, self.now)['decision'], 'confirmed')
        self.assertEqual(procedure_url(row), 'https://etpgpb.ru/procedures/price_request/12345-test-procedure/')

    def test_regulated_sections_are_excluded(self):
        for section, law in (('Закупки.Бизнес223', '223-ФЗ'), ('Закупки.Гос44', '44-ФЗ')):
            with self.subTest(section=section):
                row = etpgpb_row(self.item(category=section))
                self.assertEqual(row['regime'], law)
                result = assess(row, self.now)
                self.assertEqual(result['decision'], 'excluded')
                self.assertEqual(result['reasons'], ['regulated_procurement'])

    def test_unknown_category_requires_review(self):
        row = etpgpb_row(self.item(category='Торговый портал'))
        result = assess(row, self.now)
        self.assertEqual(result['decision'], 'review')
        self.assertIn('procurement_regime_unknown', result['reasons'])

    def test_non_stavropol_worksite_is_excluded(self):
        row = etpgpb_row(self.item(regions=['Республика Татарстан']))
        self.assertEqual(assess(row, self.now)['reasons'], ['other_region'])

    def test_malformed_or_untrusted_paths_are_rejected(self):
        for path in ('https://evil.example/procedures/price_request/123-test/',
                     '/procedures/../../account/', '/procedures/price_request/123-test/?redirect=x'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    etpgpb_row(self.item(path=path))

    def test_missing_attributes_are_rejected(self):
        with self.assertRaises(ValueError):
            etpgpb_row({'id': '1', 'attributes': None})


if __name__ == '__main__':
    unittest.main()
