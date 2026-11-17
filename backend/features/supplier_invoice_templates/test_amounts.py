import unittest
from .amounts import scan_amount_errors

class ScanAmountsTests(unittest.TestCase):
    def payload(self, **item):
        return dict(items=[dict(name='Материал',quantity=2,price=10,lineTotal=20,**item)],totalBase=20,totalVat=0,totalWithVat=20)

    def test_consistent_and_printed_rounding_are_accepted(self):
        self.assertEqual(scan_amount_errors(self.payload()),[])
        self.assertEqual(scan_amount_errors(dict(items=[dict(quantity=3,price='3.33',lineTotal=10)],totalBase=10,totalVat=0,totalWithVat=10)),[])

    def test_invalid_and_nonfinite_numbers_are_rejected(self):
        for value in ('NaN','Infinity',True,'abc',-1):
            payload=self.payload();payload['items'][0]['quantity']=value
            self.assertTrue(scan_amount_errors(payload),value)

    def test_bad_line_and_tax_totals_are_rejected(self):
        payload=self.payload();payload['items'][0]['lineTotal']=19
        self.assertTrue(scan_amount_errors(payload))
        payload=self.payload();payload['totalVat']=3
        self.assertTrue(scan_amount_errors(payload))
