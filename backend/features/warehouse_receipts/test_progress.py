import os
import unittest
from unittest.mock import Mock,patch
from .progress import invoice_progress

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.batch={'companyId':2,'documentParties':{'sourceInvoiceId':9},'lines':[{'id':3}]}
        self.cur=Mock(); self.cur.fetchone.return_value={'ready':True}
        self.cur.fetchall.return_value=[{'delivery_id':3,'line_id':4,'quantity':'10','accepted':'6'}]

    def test_disabled_preview_does_not_register_or_read_baseline(self):
        with patch.dict(os.environ,{'SUPPLIER_PARTIAL_RECEIPTS_ENABLED':'0'}):
            self.assertEqual(invoice_progress(self.cur,self.batch),{})
        self.cur.execute.assert_not_called()

    def test_exact_authorized_source_line_quantities(self):
        with patch.dict(os.environ,{'SUPPLIER_PARTIAL_RECEIPTS_ENABLED':'1'}):
            result=invoice_progress(self.cur,self.batch)
        self.assertEqual(result[3]['remainingQuantity'],'4')
        self.assertEqual(self.cur.execute.call_args.args[1],(2,9,[3]))
        self.assertTrue(all('SELECT' in c.args[0] and 'INSERT' not in c.args[0] for c in self.cur.execute.call_args_list))

    def test_ambiguous_or_overconsumed_line_is_not_projected(self):
        for rows in ([self.cur.fetchall.return_value[0]]*2,[{'delivery_id':3,'line_id':4,'quantity':'10','accepted':'11'}]):
            self.cur.fetchall.return_value=rows
            with patch.dict(os.environ,{'SUPPLIER_PARTIAL_RECEIPTS_ENABLED':'1'}):
                self.assertEqual(invoice_progress(self.cur,self.batch),{})
