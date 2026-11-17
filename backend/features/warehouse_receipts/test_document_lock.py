import unittest
from unittest.mock import Mock
from .document_lock import lock_physical_document


class PhysicalDocumentLockTests(unittest.TestCase):
    def key(self, company=2, **changes):
        cur=Mock()
        document={'supplierInn':'1234567890','buyerInn':'9876543210',
                  'waybillNumber':'Накладная № A-12','waybillDate':'18.10.2026',
                  'documentType':'waybill'}
        document.update(changes)
        lock_physical_document(cur,company,document)
        self.assertIn('pg_advisory_xact_lock',cur.execute.call_args.args[0])
        return cur.execute.call_args.args[1]

    def test_equivalent_header_and_waybill_type_use_same_lock(self):
        self.assertEqual(self.key(),self.key(waybillNumber='A12',waybillDate='2026-10-18',documentType='upd'))

    def test_company_and_legal_party_boundaries_remain_separate(self):
        self.assertNotEqual(self.key(),self.key(company=3))
        self.assertNotEqual(self.key(),self.key(supplierInn='1111111111'))
        self.assertNotEqual(self.key(),self.key(buyerInn='2222222222'))

    def test_batch_selection_and_actual_quantity_do_not_change_document_lock(self):
        self.assertEqual(self.key(),self.key(selectedBatchId=98,lines=[{'quantity':3}]))
