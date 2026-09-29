"""Explicit historical evidence must never infer tax, quantities or prices."""
import copy
import json
import unittest
from decimal import Decimal, localcontext

from .legacy_line_review import build_legacy_line_candidates, build_legacy_line_review


class LegacyLineReviewTests(unittest.TestCase):
    def setUp(self):
        self.request = json.dumps([dict(materialName='Кабель', unit='м', workPackage='Электрика', quantity='2')])
        self.offer = json.dumps([dict(materialName='Кабель', unit='м', workPackage='Электрика', quantity='2', pricePerUnit='100', totalPrice='200')])
        self.rows = [dict(sourceRequestPosition=0, sourceOfferPosition=0, materialName='Кабель', unit='м', workPackage='Электрика', quantity='2', unitPrice='100', amount='200', vatAmount='20')]
        self.args = dict(invoice_amount=Decimal('200'), invoice_vat=Decimal('20'), offer_amount=Decimal('200'), work_package='Электрика', request_json=self.request, offer_json=self.offer, reviewed_lines=self.rows, reviewed_vat='20.00')

    def build(self, **changes):
        return build_legacy_line_review(**dict(self.args, **changes))

    def test_explicit_review_preserves_source_positions_and_exact_tax(self):
        result = self.build()
        self.assertEqual(result['provenance'], 'legacy_original_review')
        self.assertEqual(result['lines'][0]['quantity'], '2.000000')
        self.assertEqual(result['lines'][0]['vatAmount'], '20.00')
        self.assertEqual(result['amount'], '200.00')
        self.assertEqual(result['vatAmount'], '20.00')
        self.assertEqual(self.rows, self.args['reviewed_lines'])

    def test_missing_fields_and_unknown_fields_rejected(self):
        for key in self.rows[0]:
            with self.subTest(key=key):
                rows=copy.deepcopy(self.rows);del rows[0][key]
                with self.assertRaises(ValueError):self.build(reviewed_lines=rows)
        with self.assertRaises(ValueError):self.build(reviewed_lines=[dict(self.rows[0], inferred=True)])

    def test_changed_source_identity_quantity_price_total_or_position_rejected(self):
        for key,value in dict(materialName='Другое', unit='шт', workPackage='Другой', quantity='1', unitPrice='200', amount='199', sourceRequestPosition=1, sourceOfferPosition=True).items():
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.build(reviewed_lines=[dict(self.rows[0], **{key:value})])

    def test_partial_invoice_uses_explicit_reviewed_quantities_at_kp_prices(self):
        request = json.dumps([
            dict(materialName='Гипсовая штукатурка', unit='мешок', workPackage='Отделка', quantity='1200'),
            dict(materialName='Цементная штукатурка', unit='мешок', workPackage='Отделка', quantity='400'),
        ])
        offer = json.dumps([
            dict(materialName='Гипсовая штукатурка', unit='мешок', workPackage='Отделка', quantity='1200', pricePerUnit='340', totalPrice='408000'),
            dict(materialName='Цементная штукатурка', unit='мешок', workPackage='Отделка', quantity='400', pricePerUnit='295', totalPrice='118000'),
        ])
        candidates = build_legacy_line_candidates(
            request, offer, invoice_amount=Decimal('263000'), offer_amount=Decimal('526000'),
            work_package='Отделка')
        self.assertEqual(
            [(row['quantity'], row['maxQuantity'], row['amount']) for row in candidates['lines']],
            [('600.000000', '1200.000000', '204000.00'), ('200.000000', '400.000000', '59000.00')],
        )
        reviewed = [
            {key: value for key, value in row.items() if key not in ('lineNo', 'maxQuantity')}
            | {'vatAmount': vat}
            for row, vat in zip(candidates['lines'], ('36754.10', '10672.13'))
        ]
        result = build_legacy_line_review(
            invoice_amount=Decimal('263000'), invoice_vat=Decimal('47426.23'),
            offer_amount=Decimal('526000'), work_package='Отделка', request_json=request,
            offer_json=offer, reviewed_lines=reviewed, reviewed_vat='47426.23')
        self.assertEqual([row['quantity'] for row in result['lines']], ['600.000000', '200.000000'])
        self.assertEqual([row['amount'] for row in result['lines']], ['204000.00', '59000.00'])

    def test_partial_review_rejects_excess_duplicate_and_unbalanced_rows(self):
        request = json.dumps([dict(materialName='Кабель', unit='м', workPackage='Электрика', quantity='2')])
        offer = json.dumps([dict(materialName='Кабель', unit='м', workPackage='Электрика', quantity='2', pricePerUnit='100', totalPrice='200')])
        base = dict(self.rows[0], quantity='1', amount='100', vatAmount='20')
        args = dict(invoice_amount=Decimal('100'), invoice_vat=Decimal('20'), offer_amount=Decimal('200'),
                    work_package='Электрика', request_json=request, offer_json=offer,
                    reviewed_vat='20.00')
        self.assertEqual(build_legacy_line_review(**args, reviewed_lines=[base])['amount'], '100.00')
        for rows in ([dict(base, quantity='3', amount='300')], [base, base], [dict(base, amount='99')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                build_legacy_line_review(**args, reviewed_lines=rows)

    def test_tax_cannot_be_missing_invented_or_distributed(self):
        for changes in (dict(invoice_vat=None),dict(reviewed_vat=None),dict(reviewed_vat='0'),dict(reviewed_vat='20.001'),dict(invoice_vat=Decimal('10')),dict(reviewed_lines=[dict(self.rows[0],vatAmount='21')])):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.build(**changes)

    def test_zero_tax_still_requires_explicit_evidence(self):
        result=self.build(invoice_vat=Decimal('0'),reviewed_vat='0',reviewed_lines=[dict(self.rows[0],vatAmount='0')])
        self.assertEqual(result['vatAmount'],'0.00')

    def test_bad_number_types_and_oversize_input_rejected(self):
        for value in (True,100.0,'NaN','Infinity','1e100000','-1','',None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.build(reviewed_lines=[dict(self.rows[0],unitPrice=value)])
        for rows in ([],self.rows*2001,{}):
            with self.assertRaises(ValueError):self.build(reviewed_lines=rows)

    def test_decimal_context_does_not_change_result(self):
        with localcontext() as ctx:
            ctx.prec=2
            self.assertEqual(self.build()['amount'],'200.00')

    def test_two_lines_tax_is_not_redistributed(self):
        request=json.loads(self.request);request.append(dict(request[0],materialName='Труба'))
        offer=json.loads(self.offer);offer.append(dict(offer[0],materialName='Труба'))
        rows=[*self.rows,dict(self.rows[0],materialName='Труба',sourceRequestPosition=1,sourceOfferPosition=1,vatAmount='0')]
        result=self.build(invoice_amount=Decimal('400'),offer_amount=Decimal('400'),request_json=json.dumps(request),offer_json=json.dumps(offer),reviewed_lines=rows)
        self.assertEqual([r['vatAmount'] for r in result['lines']],['20.00','0.00'])
