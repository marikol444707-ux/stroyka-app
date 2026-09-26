import datetime as dt
import unittest

from .payment_deferral import payment_deadline
from . import payment_deferral
from .test_payment_schedule import schedule


class PaymentDeferralTests(unittest.TestCase):
    def row(self, **changes):
        return dict(invoice_id=1, amount='200', paid_amount='100', status='Частично оплачен',
                    invoice_date='2026-09-01', accepted_at='2026-09-15',
                    snapshot_json={'paymentSchedule': schedule()}, **changes)

    def test_seven_days_today_and_overdue(self):
        for day, remaining in ((18, 7), (25, 0), (28, -3)):
            result = payment_deadline(self.row(), dt.date(2026, 9, day))
            self.assertEqual(result['stages'][0]['remainingDays'], remaining)
            self.assertEqual(result['stages'][0]['dueDate'], '2026-09-25')
            self.assertEqual(result['stages'][0]['amount'], '100.00')
            self.assertEqual(result['status'], 'active')

    def test_waits_for_acceptance(self):
        row = self.row(); row['accepted_at'] = None
        result = payment_deadline(row, dt.date(2026, 9, 18))
        self.assertEqual(result['status'], 'waiting_acceptance')
        self.assertIsNone(result['stages'][0]['remainingDays'])

    def test_paid_and_annulled_do_not_count_down(self):
        row = self.row(); row['paid_amount'] = '200'
        self.assertEqual(payment_deadline(row)['status'], 'paid')
        row['status'] = 'Аннулирован'
        self.assertEqual(payment_deadline(row)['status'], 'cancelled')

    def test_legacy_does_not_infer_from_text(self):
        row = self.row(); row['snapshot_json'] = {'paymentTerms': 'Оплата через 30 дней'}
        self.assertIsNone(payment_deadline(row))

    def test_paid_label_without_matching_money_requires_review(self):
        row = self.row(); row['status'] = 'Оплачен'
        self.assertEqual(payment_deadline(row)['status'], 'review_required')

    def test_invalid_money_or_schedule_requires_review(self):
        for field, value in [('amount', 'NaN'), ('paid_amount', '-1'), ('snapshot_json', {'paymentSchedule': {}})]:
            row = self.row(); row[field] = value
            self.assertEqual(payment_deadline(row)['status'], 'review_required')

    def test_invoice_batch_only_attaches_matching_authorized_identity(self):
        from unittest.mock import Mock
        cur = Mock()
        row = {**self.row(), 'company_id': 2, 'source_company_id': 2,
               'source_id': 1, 'saved_contract_id': 6}
        cur.fetchall.return_value = [row]
        invoices = [{'id': 1, 'company_id': 2}, {'id': 1, 'company_id': 3}, {'id': 99, 'company_id': 2}]
        payment_deferral.enrich_invoice_deadlines(cur, invoices)
        self.assertEqual(invoices[0]['paymentDeadline']['status'], 'active')
        self.assertIsNone(invoices[1]['paymentDeadline'])
        self.assertIsNone(invoices[2]['paymentDeadline'])

    def test_invoice_batch_broken_binding_requires_review(self):
        from unittest.mock import Mock
        cur = Mock()
        cur.fetchall.return_value = [{'source_id': 1, 'source_company_id': 2,
                                     'saved_contract_id': 6, 'invoice_id': None, 'company_id': None}]
        invoices = [{'id': 1, 'company_id': 2}]
        payment_deferral.enrich_invoice_deadlines(cur, invoices)
        self.assertEqual(invoices[0]['paymentDeadline']['status'], 'review_required')
        self.assertEqual(invoices[0]['paymentDeadline']['stages'], [])

    def test_warehouse_projection_only_enriches_authorized_company(self):
        from unittest.mock import Mock
        cur = Mock()
        cur.fetchall.return_value = [{**self.row(), 'warehouse_id': 42,
            'warehouse_company_id': 2, 'company_id': 2, 'linked_invoice_id': 1}]
        invoices = [{'id': 42, 'companyId': 2, 'supplierInvoiceId': 1}, {'id': 42, 'companyId': 3}]
        payment_deferral.enrich_warehouse_deadlines(cur, invoices)
        self.assertEqual(invoices[0]['paymentDeadline']['invoiceId'], 1)
        self.assertIsNone(invoices[1]['paymentDeadline'])

    def test_warehouse_broken_direct_link_requires_review_not_fallback(self):
        from unittest.mock import Mock
        cur = Mock()
        cur.fetchall.return_value = [{'warehouse_id': 42, 'warehouse_company_id': 2,
            'company_id': None, 'invoice_id': None, 'linked_invoice_id': 7}]
        invoices = [{'id': 42, 'companyId': 2, 'supplierInvoiceId': 7}]
        payment_deferral.enrich_warehouse_deadlines(cur, invoices)
        self.assertEqual(invoices[0]['paymentDeadline']['status'], 'review_required')
        self.assertIsNone(invoices[0]['paymentDeadline']['invoiceId'])

    def test_warehouse_unlinked_or_non_accounting_does_not_infer_deadline(self):
        from unittest.mock import Mock
        cur = Mock()
        cur.fetchall.return_value = [{'warehouse_id': 42, 'warehouse_company_id': 2,
            'company_id': None, 'invoice_id': None, 'linked_invoice_id': None},
            {**self.row(), 'warehouse_id': 43, 'warehouse_company_id': 2,
             'company_id': 2, 'linked_invoice_id': 1}]
        invoices = [{'id': 42, 'companyId': 2},
                    {'id': 43, 'companyId': 2, 'supplierInvoiceId': 1, 'accountingRequired': False}]
        payment_deferral.enrich_warehouse_deadlines(cur, invoices)
        self.assertTrue(all(row['paymentDeadline'] is None for row in invoices))

    def test_warehouse_identity_changed_after_visibility_check_is_not_enriched(self):
        from unittest.mock import Mock
        cur = Mock()
        cur.fetchall.return_value = [{**self.row(), 'warehouse_id': 42,
            'warehouse_company_id': 2, 'company_id': 2, 'linked_invoice_id': 1,
            'warehouse_project': 'Other project'}]
        invoices = [{'id': 42, 'companyId': 2, 'supplierInvoiceId': 1, 'project': 'Allowed project'}]
        payment_deferral.enrich_warehouse_deadlines(cur, invoices)
        self.assertIsNone(invoices[0]['paymentDeadline'])
