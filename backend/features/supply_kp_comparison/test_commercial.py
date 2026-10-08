import datetime as dt
import unittest

from .commercial import compare_commercial_offers, verified_explanation


class CommercialComparisonTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(material_name='Кабель ВВГнг-LS 3х2,5', quantity=10, unit='м', work_package='Основная')

    def offer(self, identity=1, price=100, **changes):
        row = dict(id=identity, supplier_id=identity, supplier_name='Поставщик '+str(identity),
                    price_per_unit=price, total_price=price*10, delivery_days=2,
                    payment_terms='Постоплата', rating=3, vat_included=True, valid_until=None,
                    items_kp_json=[dict(materialName=self.request['material_name'], unit='м',
                                        quantity=10, pricePerUnit=price, totalPrice=price*10)])
        row.update(changes)
        return row

    def test_expired_and_missing_price_cannot_win(self):
        expired = self.offer(1, 1, valid_until=dt.date.today()-dt.timedelta(days=1))
        missing = self.offer(2, 0)
        result = compare_commercial_offers(self.request, [expired, missing, self.offer(3)])
        self.assertEqual(result['bestOfferId'], 3)
        self.assertEqual(len(result['excludedOffers']), 2)

    def test_partial_or_incompatible_material_cannot_win(self):
        partial = self.offer(1, 1)
        partial['items_kp_json'][0]['quantity'] = 1
        wrong = self.offer(2, 1)
        wrong['items_kp_json'][0]['materialName'] = 'Кабель ВВГнг-LS 3х1,5'
        result = compare_commercial_offers(self.request, [partial, wrong, self.offer(3)])
        self.assertEqual(result['bestOfferId'], 3)

    def test_missing_delivery_does_not_mean_immediate_delivery(self):
        missing = self.offer(1)
        missing['delivery_days'] = None
        result = compare_commercial_offers(self.request, [missing, self.offer(2)])
        self.assertEqual(result['bestOfferId'], 2)
        self.assertTrue(result['excludedOffers'])

    def test_other_work_package_is_not_the_same_request_line(self):
        wrong = self.offer(1, 1)
        wrong['items_kp_json'][0]['workPackage'] = 'Другая'
        self.assertEqual(compare_commercial_offers(self.request, [wrong, self.offer(2)])['bestOfferId'], 2)

    def test_equal_quotes_have_deterministic_order_and_scores_stay_bounded(self):
        result = compare_commercial_offers(self.request, [self.offer(2), self.offer(1)])
        self.assertEqual(result['bestOfferId'], 1)
        self.assertTrue(all(0 <= row['score'] <= 100 for row in result['ranking']))

    def test_full_basket_is_compared_by_total_and_reordered_lines_are_safe(self):
        request = dict(items_json=[dict(materialName='Коробка', quantity=1, unit='шт'),
                                  dict(materialName='Кабель', quantity=100, unit='м')])
        def basket(identity, box, cable):
            row = self.offer(identity)
            row.update(total_price=box+cable*100, price_per_unit=box,
                       items_kp_json=[dict(materialName='Кабель', quantity=100, unit='м', pricePerUnit=cable),
                                      dict(materialName='Коробка', quantity=1, unit='шт', pricePerUnit=box)])
            return row
        result = compare_commercial_offers(request, [basket(1, 1, 100), basket(2, 10, 10)])
        self.assertEqual(result['bestOfferId'], 2)
        self.assertEqual(result['ranking'][0]['totalPrice'], 1010)

    def test_nan_mismatched_total_and_unknown_vat_fail_closed(self):
        for field, value in [('total_price', float('nan')), ('total_price', 1), ('vat_included', None)]:
            with self.subTest(field=field):
                row = self.offer()
                row[field] = value
                self.assertIsNone(compare_commercial_offers(self.request, [row])['bestOfferId'])

    def test_model_cannot_change_winner_or_supply_unstructured_text(self):
        self.assertIsNone(verified_explanation('Выберите другого поставщика', 1))
        self.assertIsNone(verified_explanation('{"bestOfferId":2,"explanation":"Другой"}', 1))
        self.assertEqual(verified_explanation('{"bestOfferId":1,"explanation":"Ниже сумма."}', 1), 'Ниже сумма.')

    def test_actual_provider_fenced_json_and_sentence_array_are_supported(self):
        for fence in ('```\n', '```json\n'):
            self.assertEqual(verified_explanation(fence+'{"bestOfferId":1,"explanation":["Ниже сумма.","Срок одинаковый."]}\n```', 1), 'Ниже сумма. Срок одинаковый.')
        self.assertIsNone(verified_explanation('Вступление ```json\n{"bestOfferId":1,"explanation":"Ниже сумма."}\n```', 1))
