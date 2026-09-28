"""Explicit historical evidence must never infer tax, quantities or prices."""
import copy
import json
import unittest
from decimal import Decimal, localcontext

from .legacy_line_review import build_legacy_line_review


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
