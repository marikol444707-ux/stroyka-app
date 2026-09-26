"""Allocation is a designation of existing money, never a second expense."""
import datetime as dt
from dataclasses import replace
from decimal import Decimal
import unittest

from .allocation_projection import (
    Allocation, Payment, Receipt, Scope, allocation_projection,
)


class AllocationProjectionTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope(2, 4, 6, 9)
        self.receipts = [Receipt(self.scope, 11, '40000.00', dt.date(2026, 10, 1)),
                         Receipt(self.scope, 12, '60000.00', dt.date(2026, 10, 10))]
        self.payments = [Payment(self.scope, 21, '30000.00')]

    def project(self, allocations=(), **kwargs):
        return allocation_projection(
            scope=self.scope, invoice_amount='100000.00', opening_paid='0.00',
            payments=kwargs.pop('payments', self.payments),
            receipts=kwargs.pop('receipts', self.receipts),
            allocations=allocations, **kwargs)

    def test_payment_without_allocation_reduces_invoice_not_receipts(self):
        result = self.project()
        self.assertEqual(result['invoiceRemaining'], '70000.00')
        self.assertEqual(result['unallocatedPayments'], '30000.00')
        self.assertEqual([r['remaining'] for r in result['receipts']], ['40000.00', '60000.00'])
        self.assertTrue(result['needsAllocation'])

    def test_confirmation_changes_receipt_not_invoice_debt(self):
        result = self.project([Allocation(self.scope, 31, 21, 11, '30000.00')])
        self.assertEqual(result['invoiceRemaining'], '70000.00')
        self.assertEqual(result['allocated'], '30000.00')
        self.assertEqual(result['unallocatedPayments'], '0.00')
        self.assertEqual([r['remaining'] for r in result['receipts']], ['10000.00', '60000.00'])

    def test_multiple_installments_and_split_payment_preserve_cents(self):
        result = self.project([
            Allocation(self.scope, 31, 21, 11, '29999.99'),
            Allocation(self.scope, 32, 21, 12, '0.01'),
            Allocation(self.scope, 33, 22, 12, '100.01'),
        ], payments=self.payments + [Payment(self.scope, 22, '100.02')])
        self.assertEqual(result['invoiceRemaining'], '69899.98')
        self.assertEqual(result['unallocatedPayments'], '0.01')
        self.assertEqual(result['allocated'], '30100.01')

    def test_reversal_removes_only_its_allocations_without_mutation(self):
        allocations = [Allocation(self.scope, 31, 21, 11, '30000.00'),
                       Allocation(self.scope, 32, 22, 12, '100.00')]
        payments = [replace(self.payments[0], reversed=True), Payment(self.scope, 22, '100.00')]
        result = self.project(allocations, payments=payments)
        self.assertEqual(result['invoiceRemaining'], '99900.00')
        self.assertEqual([r['remaining'] for r in result['receipts']], ['40000.00', '59900.00'])
        self.assertEqual(allocations[0].amount, '30000.00')
        self.assertEqual(result['suggestions'], [])

    def test_opening_paid_is_not_fabricated_as_allocatable_payment(self):
        result = allocation_projection(scope=self.scope, invoice_amount='100000',
            opening_paid='20000', payments=self.payments, receipts=self.receipts, allocations=[])
        self.assertEqual(result['invoiceRemaining'], '50000.00')
        self.assertEqual(result['openingPaidUnallocated'], '20000.00')
        self.assertEqual(result['unallocatedPayments'], '30000.00')
        self.assertEqual(sum(Decimal(s['amount']) for s in result['suggestions']), Decimal('30000'))
        self.assertTrue(result['needsAllocation'])

    def test_suggestion_is_earliest_due_without_confirming_or_changing_dates(self):
        later_first = list(reversed(self.receipts))
        result = self.project(receipts=later_first)
        self.assertEqual(result['suggestions'], [{'paymentId': 21, 'receiptId': 11, 'amount': '30000.00'}])
        self.assertEqual(result['allocated'], '0.00')
        self.assertEqual(later_first[1].due_date, dt.date(2026, 10, 1))

    def test_confirmed_allocation_never_moves_when_an_earlier_receipt_appears(self):
        result = self.project([Allocation(self.scope, 31, 21, 12, '30000')])
        self.assertEqual([r['allocated'] for r in result['receipts']], ['0.00', '30000.00'])
        self.assertEqual(result['suggestions'], [])

    def test_payment_before_any_receipt_stays_unallocated(self):
        result = self.project(receipts=[])
        self.assertEqual(result['invoiceRemaining'], '70000.00')
        self.assertEqual(result['unallocatedPayments'], '30000.00')
        self.assertEqual(result['suggestions'], [])

    def test_suggestions_split_to_capacity_and_leave_unreceived_advance_free(self):
        receipts = [replace(self.receipts[0], amount='10000'), replace(self.receipts[1], amount='5000')]
        result = self.project(receipts=receipts)
        self.assertEqual([s['amount'] for s in result['suggestions']], ['10000.00', '5000.00'])
        self.assertEqual(result['unallocatedPayments'], '30000.00')

    def test_undated_receipts_last_and_ties_deterministic(self):
        receipts = [replace(self.receipts[0], due_date=None), self.receipts[1]]
        self.assertEqual(self.project(receipts=receipts)['suggestions'][0]['receiptId'], 12)
        receipts = [replace(self.receipts[1], due_date=self.receipts[0].due_date), self.receipts[0]]
        self.assertEqual(self.project(receipts=receipts)['suggestions'][0]['receiptId'], 11)

    def test_same_amount_payments_are_not_deduplicated(self):
        result = self.project(payments=self.payments + [Payment(self.scope, 22, '30000')])
        self.assertEqual(result['paid'], '60000.00')
        self.assertEqual(result['invoiceRemaining'], '40000.00')

    def test_cross_scope_rows_fail_closed(self):
        for field in ('company_id', 'payer_company_id', 'supplier_id', 'invoice_id'):
            scope = replace(self.scope, **{field: 999})
            for key, rows in [('receipts', [replace(self.receipts[0], scope=scope)]),
                              ('payments', [replace(self.payments[0], scope=scope)])]:
                with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                    self.project(**{key: rows})
            with self.assertRaises(ValueError):
                self.project([Allocation(scope, 31, 21, 11, '1')])

    def test_duplicate_ids_and_dangling_allocations_fail_closed(self):
        for rows in (self.payments * 2, [replace(self.payments[0], id=True)]):
            with self.assertRaises(ValueError):
                self.project(payments=rows)
        with self.assertRaises(ValueError):
            self.project(receipts=self.receipts * 2)
        allocation = Allocation(self.scope, 31, 21, 11, '1')
        for rows in ([allocation, allocation], [replace(allocation, payment_id=999)],
                     [replace(allocation, receipt_id=999)]):
            with self.assertRaises(ValueError):
                self.project(rows)

    def test_overallocation_of_payment_or_receipt_fails(self):
        for rows in ([Allocation(self.scope, 31, 21, 11, '30000.01')],
                     [Allocation(self.scope, 31, 21, 11, '30000'),
                      Allocation(self.scope, 32, 22, 11, '10000.01')]):
            with self.assertRaises(ValueError):
                self.project(rows, payments=self.payments + [Payment(self.scope, 22, '20000')])

    def test_invalid_money_is_not_rounded_or_clamped(self):
        for value in ('NaN', 'Infinity', '-1', '0.001', True, None, '100000.01'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.project(payments=[replace(self.payments[0], amount=value)])

    def test_receipts_cannot_exceed_invoice(self):
        with self.assertRaises(ValueError):
            self.project(receipts=[replace(self.receipts[0], amount='100000.01')])

    def test_projection_identity_holds_for_many_partial_payments(self):
        payments = [Payment(self.scope, n, '0.01') for n in range(1, 51)]
        result = self.project(payments=payments)
        self.assertEqual(result['paid'], '0.50')
        self.assertEqual(Decimal(result['paid']),
                         Decimal(result['allocated']) + Decimal(result['unallocatedPayments']))

    def test_boolean_scope_ids_are_not_equal_to_real_company_ids(self):
        scope = replace(self.scope, company_id=1)
        with self.assertRaises(ValueError):
            allocation_projection(scope=scope, invoice_amount='100', opening_paid='0',
                payments=[Payment(replace(scope, company_id=True), 1, '1')],
                receipts=[], allocations=[])

    def test_real_last_calendar_date_precedes_unknown_due_date(self):
        receipts = [replace(self.receipts[0], due_date=None),
                    replace(self.receipts[1], due_date=dt.date.max)]
        self.assertEqual(self.project(receipts=receipts)['suggestions'][0]['receiptId'], 12)

    def test_invalid_historical_allocation_is_not_hidden_by_reversal(self):
        with self.assertRaises(ValueError):
            self.project([Allocation(self.scope, 31, 21, 11, '30000')],
                payments=[replace(self.payments[0], reversed=True)],
                receipts=[replace(self.receipts[0], amount='1')])

    def test_invalid_flags_dates_and_nonpositive_allocation_are_rejected(self):
        for flag in (0, 1, 'false', None):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.project(payments=[replace(self.payments[0], reversed=flag)])
        for date in ('2026-10-01', dt.datetime(2026, 10, 1)):
            with self.subTest(date=date), self.assertRaises(ValueError):
                self.project(receipts=[replace(self.receipts[0], due_date=date)])
        for amount in ('0', '-1', '0.001', 0.1):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.project([Allocation(self.scope, 31, 21, 11, amount)])

    def test_permutation_does_not_change_projection_or_suggestion(self):
        payments = self.payments + [Payment(self.scope, 22, '20000')]
        self.assertEqual(self.project(payments=payments),
                         self.project(payments=list(reversed(payments)), receipts=list(reversed(self.receipts))))


if __name__ == '__main__':
    unittest.main()
