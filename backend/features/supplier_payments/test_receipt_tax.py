"""Tax arithmetic uses declared invoice values, never inferred tax rates."""
import unittest
from decimal import Decimal, localcontext, ROUND_DOWN

from .receipt_tax import invoice_tax_lines, receipt_tax_slice


class ReceiptTaxTests(unittest.TestCase):
    def test_mixed_declared_tax_is_not_spread_across_exempt_lines(self):
        result=invoice_tax_lines([
            {'lineNo':1,'amount':'120.00','vatAmount':'20.00'},
            {'lineNo':2,'amount':'50.00','vatAmount':'0.00'},
            {'lineNo':3,'amount':'110.00','vatAmount':'10.00'},
        ],invoice_amount='280.00',invoice_vat_amount='30.00')
        self.assertEqual([r['baseAmount'] for r in result],['100.00','50.00','100.00'])
        self.assertEqual([r['vatAmount'] for r in result],['20.00','0.00','10.00'])

    def test_three_receipts_conserve_last_tax_penny(self):
        rows=[receipt_tax_slice(line_amount='1.00',line_vat_amount='0.17',
              previous_amount=before,received_amount=amount)
              for before,amount in [('0.00','0.33'),('0.33','0.33'),('0.66','0.34')]]
        self.assertEqual([r['vatAmount'] for r in rows],['0.06','0.05','0.06'])
        self.assertEqual(sum(Decimal(r['vatAmount']) for r in rows),Decimal('0.17'))
        self.assertEqual(sum(Decimal(r['baseAmount']) for r in rows),Decimal('0.83'))

    def test_every_cent_receipt_is_nonnegative_and_full_total_is_conserved(self):
        for tax_cents in range(101):
            total_tax=Decimal(0)
            for before in range(100):
                row=receipt_tax_slice(line_amount='1.00',line_vat_amount=Decimal(tax_cents)/100,
                    previous_amount=Decimal(before)/100,received_amount='0.01')
                self.assertGreaterEqual(Decimal(row['baseAmount']),0)
                self.assertEqual(Decimal(row['baseAmount'])+Decimal(row['vatAmount']),Decimal('0.01'))
                total_tax+=Decimal(row['vatAmount'])
            self.assertEqual(total_tax,Decimal(tax_cents)/100)

    def test_ambient_decimal_context_cannot_change_rounding(self):
        with localcontext() as ctx:
            ctx.prec=3;ctx.rounding=ROUND_DOWN
            result=receipt_tax_slice(line_amount='123456.00',line_vat_amount='20576.00',
                previous_amount='0.00',received_amount='100.00')
        self.assertEqual(result,{'amount':'100.00','vatAmount':'16.67','baseAmount':'83.33'})

    def test_missing_duplicate_or_mismatched_line_tax_is_rejected(self):
        valid={'lineNo':1,'amount':'120.00','vatAmount':'20.00'}
        for lines in ([{'lineNo':1,'amount':'120.00'}],[valid,valid],
                      [{**valid,'vatAmount':'19.99'}],[{**valid,'lineNo':True}]):
            with self.subTest(lines=lines),self.assertRaises(ValueError):
                invoice_tax_lines(lines,invoice_amount='120.00',invoice_vat_amount='20.00')

    def test_invalid_or_excess_receipt_values_are_rejected(self):
        baseline=dict(line_amount='100.00',line_vat_amount='20.00',previous_amount='0.00',received_amount='10.00')
        for patch in ({'line_vat_amount':'100.01'},{'previous_amount':'95.00'},
                      {'received_amount':'0'},{'received_amount':'0.001'},
                      {'line_vat_amount':True},{'received_amount':1.1},
                      {'previous_amount':'NaN'},{'line_amount':'Infinity'},
                      {'previous_amount':'-1.00'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                receipt_tax_slice(**{**baseline,**patch})
