import unittest

from .legacy_line_state import legacy_line_review_allowed


class LegacyLineReviewStateTests(unittest.TestCase):
    def setUp(self):
        self.invoice = {
            'status': 'На утверждении',
            'paid_amount': 0,
            'warehouse_invoice_id': None,
        }

    def test_pending_and_approved_unused_invoices_are_allowed(self):
        for status in ('На утверждении', 'Утверждён'):
            with self.subTest(status=status):
                self.invoice['status'] = status
                self.assertTrue(legacy_line_review_allowed(self.invoice, used=False))

    def test_money_stock_and_other_statuses_remain_blocked(self):
        cases = (
            ({'paid_amount': 1}, False),
            ({'warehouse_invoice_id': 9}, False),
            ({'status': 'Оплачен'}, False),
            ({}, True),
        )
        for changes, used in cases:
            with self.subTest(changes=changes, used=used):
                invoice = {**self.invoice, **changes}
                self.assertFalse(legacy_line_review_allowed(invoice, used=used))
