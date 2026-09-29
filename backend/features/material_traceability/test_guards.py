from decimal import Decimal
import unittest
from fastapi import HTTPException
from .guards import close_receipt_lots_for_cancellation, guard_main_stock_edit, lock_distribution_compatible_stock


class Cursor:
    def __init__(self, rows=(), exists=True):
        self.rows, self.exists, self.calls = rows, exists, []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
    def fetchone(self):
        return {'present': self.exists}
    def fetchall(self):
        return self.rows


class GuardTests(unittest.TestCase):
    def test_compatibility_lock_supports_tuple_receipt_cursor(self):
        for present in (True, False):
            with self.subTest(present=present):
                cur = Cursor()
                cur.fetchone = lambda: (present,)
                lock_distribution_compatible_stock(cur)
                self.assertEqual(len(cur.calls), 3 if present else 1)

    def test_compatibility_lock_is_schema_gated_not_feature_gated(self):
        cur = Cursor()
        lock_distribution_compatible_stock(cur)
        self.assertEqual(cur.calls[-1][0], 'LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
        absent = Cursor(exists=False)
        lock_distribution_compatible_stock(absent)
        self.assertEqual(len(absent.calls), 1)

    def test_consumed_lot_blocks_cancellation_without_closing_it(self):
        cur = Cursor([{'received_quantity': Decimal('10'), 'available_quantity': Decimal('9')}])
        with self.assertRaises(HTTPException):
            close_receipt_lots_for_cancellation(cur, 2, 7)
        self.assertIn('FOR UPDATE', cur.calls[1][0])
        self.assertFalse(any('UPDATE warehouse_receipt_lots' in sql for sql, _ in cur.calls))

    def test_fully_returned_lot_is_closed_inside_callers_transaction(self):
        cur = Cursor([{'received_quantity': Decimal('10'), 'available_quantity': Decimal('10')}])
        close_receipt_lots_for_cancellation(cur, 2, 7)
        self.assertIn("status='cancelled'", cur.calls[-1][0])
        self.assertEqual(cur.calls[-1][1], (2, 7))

    def test_missing_schema_does_not_introduce_runtime_ddl(self):
        cur = Cursor(exists=False)
        close_receipt_lots_for_cancellation(cur, 2, 7)
        self.assertEqual(len(cur.calls), 1)

    def test_tracked_main_stock_cannot_be_overwritten_by_manual_edit(self):
        row = {'company_id': 2, 'name': 'Кабель', 'unit': 'м', 'quantity': 10}
        with self.assertRaises(HTTPException):
            guard_main_stock_edit(Cursor(), row, name='Кабель', unit='м', quantity=9)
        cur = Cursor()
        guard_main_stock_edit(cur, row, name='Кабель', unit='м', quantity=10)
        self.assertEqual(cur.calls, [])


if __name__ == '__main__':
    unittest.main()
