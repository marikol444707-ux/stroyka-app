import json
import unittest
from .legacy_package_review import package_review, mixed_reconciliation_preview


class MixedPackageReviewTests(unittest.TestCase):
    def items(self):
        return json.dumps([{'workPackage':'Отделка'}, {'work_package':'Электрика'},
                           {'workPackage':'Отделка'}])

    def pair(self):
        invoice=dict(id=1,companyId=2,supplierId=3,projectName='Объект',workPackage='Основная',
                     amount='200',paidAmount='50',warehouseId=4,registered=False)
        warehouse=dict(id=4,companyId=2,supplierId=3,projectName='Объект',
                       amount='200',paidAmount='50',invoiceId=1,registered=False)
        return invoice,warehouse

    def test_groups_keep_original_positions_and_literal_empty_package(self):
        review=package_review(self.items())
        self.assertEqual(review['groups'],[dict(workPackage='Отделка',positions=[1,3]),
                                          dict(workPackage='Электрика',positions=[2])])
        self.assertEqual(package_review('[{"workPackage":""},{"workPackage":"Основная"}]')['packageCount'],2)

    def test_bad_or_ambiguous_input_blocks_entire_review(self):
        for raw in (None, [], '{}','[]','[1]','[{}]', '[{"workPackage":null}]',
                    '[{"workPackage":" A"}]','[{"workPackage":"A","work_package":"B"}]',
                    '[{"workPackage":"A","workPackage":"A"}]','[NaN]'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):package_review(raw)

    def test_one_cash_balance_and_complete_scope(self):
        invoice,warehouse=self.pair()
        result=mixed_reconciliation_preview(invoice,[warehouse],self.items())
        self.assertEqual(result['scenario'],'mixedPackageLegacyPair')
        self.assertEqual((result['openingPaid'],result['remainingAmount'],result['newCashAmount']),('50.00','150.00','0.00'))
        self.assertEqual(result['requiredPackages'],['Основная','Отделка','Электрика'])
        self.assertFalse(result['admissionGranted'])
        self.assertNotIn('paidAmount',result['packageReview']['groups'][0])

    def test_identity_balance_or_link_failure_never_exposes_opening(self):
        for field,value in [('companyId',9),('supplierId',9),('projectName','Другой'),
                            ('invoiceId',9),('amount','201'),('paidAmount','0'),('registered',True)]:
            invoice,warehouse=self.pair();warehouse[field]=value
            with self.subTest(field=field):
                result=mixed_reconciliation_preview(invoice,[warehouse],self.items())
                self.assertEqual(result['scenario'],'blocked');self.assertNotIn('openingPaid',result)
        invoice,warehouse=self.pair()
        self.assertEqual(mixed_reconciliation_preview(invoice,[warehouse,warehouse],self.items())['scenario'],'blocked')
