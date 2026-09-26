"""Pure request/KP correspondence; no database, runtime imports or auth claims."""
import json
import unittest
from decimal import Decimal, localcontext

from .invoice_line_spec import build_invoice_line_spec


class InvoiceLineSpecTests(unittest.TestCase):
    def request(self):
        return dict(materialName='Кабель', unit='м', workPackage='Основная', quantity='2')

    def offer(self):
        return {**self.request(), 'pricePerUnit': '1.25', 'totalPrice': '2.50'}

    def build(self, request=None, offer=None, **headers):
        options = dict(invoice_amount='2.50', offer_amount='2.50', vat_amount=0,
                       vat_included=False, work_package='Основная')
        options.update(headers)
        return build_invoice_line_spec(
            json.dumps([self.request()] if request is None else request, ensure_ascii=False),
            json.dumps([self.offer()] if offer is None else offer, ensure_ascii=False), **options)

    def test_explicit_exact_spec_and_source_positions(self):
        second = {**self.request(), 'unit': 'шт', 'quantity': '1'}
        second_offer = {**second, 'pricePerUnit': '2', 'totalPrice': '2'}
        result = self.build([self.request(), second], [second_offer, self.offer()],
                            invoice_amount=Decimal('4.50'), offer_amount='4.50')
        self.assertEqual(result, dict(amount='4.50', workPackage='Основная', lines=[
            dict(lineNo=1, sourceRequestPosition=0, sourceOfferPosition=1, materialName='Кабель',
                 unit='м', workPackage='Основная', quantity='2.000000', unitPrice='1.250000', amount='2.50'),
            dict(lineNo=2, sourceRequestPosition=1, sourceOfferPosition=0, materialName='Кабель',
                 unit='шт', workPackage='Основная', quantity='1.000000', unitPrice='2.000000', amount='2.00'),
        ]))

    def test_raw_json_decimals_are_not_binary_floats(self):
        request = '[{"name":"A","unit":"m","work_package":"P","quantity":0.1}]'
        offer = '[{"name":"A","unit":"m","work_package":"P","quantity":0.1,"pricePerUnit":0.2}]'
        result = build_invoice_line_spec(request, offer, invoice_amount='0.02', offer_amount='0.02',
                                        vat_amount=Decimal('0'), vat_included=False, work_package='P')
        self.assertEqual(result['lines'][0]['amount'], '0.02')
        self.assertEqual(result['lines'][0]['quantity'], '0.100000')

    def test_duplicate_identity_in_either_source_is_ambiguous(self):
        for request, offer in (([self.request()] * 2, [self.offer()]),
                               ([self.request()], [self.offer()] * 2)):
            with self.subTest(request=request, offer=offer), self.assertRaises(ValueError):
                self.build(request, offer)

    def test_exact_identity_no_case_folding_unit_conversion_or_name_only_join(self):
        for changes in ({'materialName': 'кабель'}, {'unit': 'метр'}, {'workPackage': 'Другой'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(offer=[{**self.offer(), **changes}])

    def test_missing_identity_quantity_or_price_has_no_default(self):
        for side, keys in (('request', ('materialName', 'unit', 'workPackage', 'quantity')),
                           ('offer', ('materialName', 'unit', 'workPackage', 'quantity', 'pricePerUnit'))):
            for key in keys:
                row = self.request() if side == 'request' else self.offer()
                del row[key]
                with self.subTest(side=side, key=key), self.assertRaises(ValueError):
                    self.build(**{side: [row]})

    def test_quantity_mismatch_and_subkopeck_products_rejected(self):
        for row in ({**self.offer(), 'quantity': '3'},
                    {**self.offer(), 'pricePerUnit': '1.250001'}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.build(offer=[row])

    def test_conflicting_aliases_never_select_first_truthy_value(self):
        for extra in ({'name': 'Other'}, {'material_name': ''}, {'work_package': None},
                      {'unitPrice': '1.26'}, {'price_per_unit': False}, {'amount': '2.49'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.build(offer=[{**self.offer(), **extra}])

    def test_matching_aliases_and_explicit_price_without_line_total(self):
        row = {**self.offer(), 'name': 'Кабель', 'work_package': 'Основная',
               'unitPrice': '1.250000', 'amount': '2.500'}
        self.assertEqual(self.build(offer=[row])['amount'], '2.50')
        del row['totalPrice']
        del row['amount']
        self.assertEqual(self.build(offer=[row])['amount'], '2.50')

    def test_header_amounts_and_supplied_line_total_must_match_exactly(self):
        for headers in ({'invoice_amount': '2.49'}, {'offer_amount': '2.51'}, {'invoice_amount': '2.501'}):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.build(**headers)
        with self.assertRaises(ValueError):
            self.build(offer=[{**self.offer(), 'totalPrice': '2.49'}])

    def test_zero_vat_only_with_actual_false_flag(self):
        for headers in ({'vat_amount': '0.01'}, {'vat_amount': '-1'}, {'vat_included': True},
                        {'vat_included': 0}, {'vat_included': None}, {'vat_included': 'false'}):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.build(**headers)

    def test_header_bool_float_nonfinite_and_invalid_types_rejected(self):
        for field in ('invoice_amount', 'offer_amount', 'vat_amount'):
            for value in (True, False, 0.0, 2.5, None, [], 'NaN', 'Infinity', Decimal('sNaN')):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.build(**{field: value})

    def test_uniform_explicit_header_package(self):
        for value in ('Другой', '', None, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(work_package=value)

    def raw_build(self, request, offer):
        return build_invoice_line_spec(request, offer, invoice_amount='2.50', offer_amount='2.50',
                                       vat_amount=0, vat_included=False, work_package='Основная')

    def test_both_json_inputs_require_nonempty_arrays_of_objects(self):
        good_request, good_offer = json.dumps([self.request()]), json.dumps([self.offer()])
        for bad in (None, [], {}, b'[]', '', '[]', '{}', 'null', '1', '[null]', '[true]',
                    '[[]]', '[1]', '["row"]', '[{', '[{}] trailing'):
            for request, offer in ((bad, good_offer), (good_request, bad)):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    self.raw_build(request, offer)

    def test_duplicate_json_keys_and_nonstandard_numbers_rejected(self):
        request, offer = json.dumps([self.request()]), json.dumps([self.offer()])
        for raw in ('[{"quantity":2,"quantity":2}]', '[{"quantity":NaN}]',
                    '[{"quantity":Infinity}]', '[{"quantity":-Infinity}]'):
            for left, right in ((raw, offer), (request, raw)):
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    self.raw_build(left, right)

    def test_utf8_one_mib_limit_each_and_inclusive_boundary(self):
        request = json.dumps([self.request()])
        offer = json.dumps([self.offer()])
        padded_request = request + ' ' * (1024 * 1024 - len(request.encode('utf-8')))
        padded_offer = offer + ' ' * (1024 * 1024 - len(offer.encode('utf-8')))
        self.assertEqual(self.raw_build(padded_request, padded_offer)['amount'], '2.50')
        for left, right in ((padded_request + ' ', offer), (request, padded_offer + ' '),
                            (json.dumps([{**self.request(), 'notes': 'я' * (512 * 1024)}],
                                        ensure_ascii=False), offer)):
            with self.subTest(left_bytes=len(left.encode('utf-8')), right_bytes=len(right.encode('utf-8'))), \
                    self.assertRaises(ValueError):
                self.raw_build(left, right)

    def test_two_thousand_lines_allowed_but_not_two_thousand_one(self):
        request = [{**self.request(), 'materialName': f'Material {i}'} for i in range(2000)]
        offer = [{**row, 'pricePerUnit': '1.25'} for row in request]
        result = self.build(request, offer, invoice_amount=5000, offer_amount=5000)
        self.assertEqual(len(result['lines']), 2000)
        self.assertEqual(result['lines'][-1]['lineNo'], 2000)
        for left, right in ((request + [{**self.request(), 'materialName': 'Extra'}], offer),
                            (request, offer + [{**self.offer(), 'materialName': 'Extra'}])):
            with self.assertRaises(ValueError):
                self.build(left, right, invoice_amount=5000, offer_amount=5000)

    def test_extra_missing_or_differently_packaged_lines_rejected(self):
        second = {**self.request(), 'materialName': 'Second'}
        for request, offer in (([self.request(), second], [self.offer()]),
                               ([self.request()], [self.offer(), {**second, 'pricePerUnit': '1.25'}]),
                               ([self.request(), {**second, 'workPackage': 'Other'}],
                                [self.offer(), {**second, 'workPackage': 'Other', 'pricePerUnit': '1.25'}])):
            with self.subTest(request=request, offer=offer), self.assertRaises(ValueError):
                self.build(request, offer)

    def test_trim_identity_but_preserve_internal_whitespace_and_detect_trimmed_duplicates(self):
        row = {**self.offer(), 'materialName': ' Кабель ', 'unit': '\tм\n', 'workPackage': ' Основная '}
        self.assertEqual(self.build(offer=[row], work_package=' Основная ')['lines'][0]['materialName'], 'Кабель')
        with self.assertRaises(ValueError):
            self.build(offer=[self.offer(), row])
        with self.assertRaises(ValueError):
            self.build(offer=[{**self.offer(), 'materialName': 'Ка  бель'}])

    def test_identity_values_cannot_be_empty_nontext_nul_or_invalid_unicode(self):
        for field in ('materialName', 'unit', 'workPackage'):
            for value in ('', ' \t', False, 1, None, [], 'a\x00b', '\ud800'):
                with self.subTest(field=field, value=repr(value)), self.assertRaises(ValueError):
                    self.build(offer=[{**self.offer(), field: value}])

    def test_quantities_and_prices_exact_scale_positive_finite_and_below_trillion(self):
        for field in ('quantity', 'pricePerUnit'):
            for value in ('0', '-1', '1000000000000', '1e100000', '1e-100000',
                          '0.0000001', '2.0000001', True, False, None, [], 'NaN', 'Infinity', '1_0'):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.build(offer=[{**self.offer(), field: value}])
        for value in ('0', '-1', '1e12', '0.0000001', True, 'NaN'):
            with self.subTest(request_quantity=value), self.assertRaises(ValueError):
                self.build(request=[{**self.request(), 'quantity': value}])

    def test_six_decimal_quantities_and_prices_exact_product(self):
        row = {**self.request(), 'quantity': '0.000001'}
        result = self.build([row], [{**row, 'pricePerUnit': '10000.000000'}],
                            invoice_amount='0.01', offer_amount=Decimal('0.01'))
        self.assertEqual(result['lines'][0]['quantity'], '0.000001')
        self.assertEqual(result['lines'][0]['unitPrice'], '10000.000000')
        row = {**self.request(), 'quantity': '10000.000000'}
        result = self.build([row], [{**row, 'pricePerUnit': '0.000001'}],
                            invoice_amount='0.01', offer_amount='0.01')
        self.assertEqual(result['lines'][0]['amount'], '0.01')

    def test_arithmetic_independent_of_callers_decimal_precision(self):
        row = {**self.request(), 'quantity': '999999999999.99'}
        amount = '999999999999.99'
        with localcontext() as context:
            context.prec = 3
            result = self.build([row], [{**row, 'pricePerUnit': '1'}],
                                invoice_amount=amount, offer_amount=amount)
            self.assertEqual(context.prec, 3)
        self.assertEqual(result['amount'], amount)
        self.assertEqual(result['lines'][0]['quantity'], '999999999999.990000')

    def test_maximum_ledger_money_allowed_but_trillion_rejected(self):
        maximum = '999999999999.99'
        row = {**self.request(), 'quantity': '1'}
        offer = {**row, 'pricePerUnit': maximum, 'totalPrice': maximum}
        self.assertEqual(self.build([row], [offer], invoice_amount=maximum, offer_amount=maximum)['amount'], maximum)
        # Quantity and price individually valid, product exceeds ledger money.
        row = {**self.request(), 'quantity': '1000000'}
        offer = {**row, 'pricePerUnit': '1000000', 'totalPrice': '1000000000000'}
        with self.assertRaises(ValueError):
            self.build([row], [offer], invoice_amount='1000000000000', offer_amount='1000000000000')
        with self.assertRaises(ValueError):
            self.build([row], [offer], invoice_amount=maximum, offer_amount=maximum)

    def test_sum_cannot_exceed_ledger_money_even_when_each_line_fits(self):
        rows = [{**self.request(), 'materialName': name, 'quantity': '1'} for name in ('A', 'B')]
        offers = [{**row, 'pricePerUnit': '500000000000'} for row in rows]
        with self.assertRaises(ValueError):
            self.build(rows, offers, invoice_amount='1000000000000', offer_amount='1000000000000')

    def test_numeric_alias_variants_are_explicit_not_guessed_from_total(self):
        for field in ('pricePerUnit', 'price_per_unit', 'unitPrice', 'unit_price'):
            row = {**self.request(), field: '1.25'}
            self.assertEqual(self.build(offer=[row])['amount'], '2.50')
        for field in ('totalPrice', 'total_price', 'amount', 'price'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.build(offer=[{**self.request(), field: '2.50'}])

    def test_generic_errors_do_not_include_source_content(self):
        private = 'PRIVATE-SUPPLIER-DATA'
        for raw in (private, '["' + private + '"]', '[' * 2000 + '0' + ']' * 2000,
                    '[{"quantity":1e9999999999999999999}]', '\ud800'):
            with self.subTest(raw_length=len(raw)), self.assertRaises(ValueError) as error:
                self.raw_build(raw, json.dumps([self.offer()]))
            self.assertEqual(str(error.exception), 'Invalid invoice line specification')


if __name__ == '__main__':
    unittest.main()
