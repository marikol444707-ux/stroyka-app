import unittest
from .legacy_reconciliation import reconciliation_preview


class LegacyReconciliationTests(unittest.TestCase):
    def invoice(self, **changes):
        return dict(id=1, companyId=2, supplierId=3, projectName='Объект',
                    workPackage='Пакет', amount='200.00', paidAmount='50.00',
                    warehouseId=None, registered=False, **changes)

    def preview(self, invoice=None, warehouses=()):
        return reconciliation_preview(invoice or self.invoice(), list(warehouses))

    def warehouse(self):
        return dict(id=4, companyId=2, supplierId=3, projectName='Объект',
                    workPackage='Пакет', amount='200.00', paidAmount='50.00',
                    invoiceId=1, registered=False)

    def test_standalone_preserves_opening_without_new_cash(self):
        result=self.preview()
        self.assertEqual(result['openingPaid'], '50.00')
        self.assertEqual(result['remainingAmount'], '150.00')
        self.assertEqual(result['newCashAmount'], '0.00')
        self.assertFalse(result['admissionGranted'])

    def test_mirrored_payment_counted_once(self):
        invoice=self.invoice(); invoice['warehouseId']=4
        result=self.preview(invoice,[self.warehouse()])
        self.assertEqual(result['openingPaid'], '50.00')
        self.assertEqual(result['amount'], '200.00')
        self.assertEqual(result['scenario'], 'matchedLegacyPair')

    def test_bad_links_and_identity_never_produce_balance(self):
        invoice=self.invoice(); invoice['warehouseId']=4
        for field,value in [('companyId',9),('supplierId',9),('projectName','Другой'),
                            ('workPackage','Другой'),('invoiceId',9),('amount','201.00'),
                            ('paidAmount','0.00')]:
            with self.subTest(field=field):
                warehouse=self.warehouse(); warehouse[field]=value
                result=self.preview(invoice,[warehouse])
                self.assertEqual(result['scenario'], 'blocked')
                self.assertNotIn('openingPaid',result)
        for rows in ([], [self.warehouse(),self.warehouse()]):
            self.assertEqual(self.preview(invoice,rows)['scenario'],'blocked')
        self.assertEqual(self.preview(warehouses=[self.warehouse()])['scenario'],'blocked')

    def test_invalid_amounts_never_become_zero_or_round(self):
        for field in ('amount','paidAmount'):
            for value in (None,True,1.1,'NaN','Infinity','-1','0.001'):
                with self.subTest(field=field,value=value):
                    invoice=self.invoice(); invoice[field]=value
                    self.assertEqual(self.preview(invoice)['scenario'],'blocked')
        invoice=self.invoice(); invoice['paidAmount']='201.00'
        self.assertEqual(self.preview(invoice)['scenario'],'blocked')

    def test_existing_ledger_requires_ledger_review(self):
        invoice=self.invoice(); invoice['registered']=True
        self.assertEqual(self.preview(invoice)['scenario'],'alreadyRegistered')
        invoice=self.invoice(); invoice['warehouseId']=4
        warehouse=self.warehouse(); warehouse['registered']=True
        self.assertEqual(self.preview(invoice,[warehouse])['scenario'],'blocked')
