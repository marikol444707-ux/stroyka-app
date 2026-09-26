"""Read shape only; transaction guarantees are tested against PostgreSQL."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from . import allocation_store as store
from .allocation_projection import Scope, Payment, Receipt


class AllocationReadShapeTests(TestCase):
    def test_editable_map_excludes_reversed_payment_but_keeps_its_history(self):
        scope = Scope(2, 2, 6, 9)
        snapshot = dict(scope=scope, invoice_amount='100', opening_paid='0',
                        payments=[Payment(scope, 1, '30', True), Payment(scope, 2, '20')],
                        receipts=[Receipt(scope, 3, '100')])
        rows = [dict(paymentId=1, receiptId=3, amount='30'),
                dict(paymentId=2, receiptId=3, amount='10')]
        cur = SimpleNamespace(execute=lambda *args: None, fetchall=lambda: rows)
        with patch.object(store, '_enter'), patch.object(store, '_snapshot', return_value=snapshot), \
                patch.object(store, '_latest', return_value=dict(id=5, version=2, row_count=2)):
            result = store.read_allocations_in_transaction(cur, lambda *args: None, 4, 2, 7)
        self.assertEqual(result['allocations'], [dict(paymentId=2, receiptId=3, amount='10.00')])
        self.assertEqual(result['reversedAllocations'], [dict(paymentId=1, receiptId=3, amount='30.00')])
        self.assertEqual(result['invoiceRemaining'], '80.00')
        self.assertEqual(rows[0]['amount'], '30')

    def test_empty_history_exposes_empty_editable_map(self):
        snapshot = dict(scope=Scope(2, 2, 6, 9), invoice_amount='100', opening_paid='0',
                        payments=[], receipts=[])
        with patch.object(store, '_enter'), patch.object(store, '_snapshot', return_value=snapshot), \
                patch.object(store, '_latest', return_value=None):
            result = store.read_allocations_in_transaction(None, lambda *args: None, 4, 2, 7)
        self.assertEqual(result['allocations'], [])
        self.assertEqual(result['reversedAllocations'], [])
        self.assertEqual(result['version'], 0)
