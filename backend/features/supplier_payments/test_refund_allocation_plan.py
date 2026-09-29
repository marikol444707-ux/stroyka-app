"""Exact refund planning; no implicit choice of payment or receipt."""
from dataclasses import replace
from decimal import Decimal
import unittest
from .allocation_projection import Scope, Payment, Receipt, Allocation
from .refund_allocation_plan import Refund, Release, refund_projection, plan_refund


class RefundAllocationPlanTests(unittest.TestCase):
    def setUp(self):
        self.scope=Scope(2,3,4,5)
        self.snapshot=dict(scope=self.scope,invoice_amount='200.00',opening_paid='0.00',
            payments=[Payment(self.scope,10,'100.00'),Payment(self.scope,20,'20.00')],
            receipts=[Receipt(self.scope,30,'100.00'),Receipt(self.scope,40,'100.00')],
            allocations=[Allocation(self.scope,1,10,30,'60.00'),Allocation(self.scope,2,10,40,'20.00'),
                         Allocation(self.scope,3,20,40,'20.00')],refunds=[])

    def plan(self,amount='25.00',releases=None,free='5.00',**changes):
        return plan_refund(**{**self.snapshot,**changes},
            refund=Refund(self.scope,50,10,amount),
            releases=[Release(30,'20.00')] if releases is None else releases,
            unallocated_amount=free)

    def test_partial_refund_changes_only_selected_coverage(self):
        result=self.plan()
        self.assertEqual(result['after']['paid'],'95.00')
        self.assertEqual(result['after']['invoiceRemaining'],'105.00')
        self.assertEqual(result['after']['allocated'],'80.00')
        self.assertEqual(result['after']['unallocatedPayments'],'15.00')
        self.assertEqual([r['allocated'] for r in result['after']['receipts']],['40.00','40.00'])
        self.assertEqual(self.snapshot['allocations'][0].amount,'60.00')
        self.assertIn(dict(paymentId=20,receiptId=40,amount='20.00'),result['rows'])

    def test_unallocated_refund_does_not_touch_receipts(self):
        result=self.plan(amount='20.00',releases=[],free='20.00')
        self.assertEqual(result['before']['receipts'],result['after']['receipts'])
        self.assertEqual(result['after']['unallocatedPayments'],'0.00')

    def test_complete_refund_keeps_other_payment(self):
        result=self.plan(amount='100.00',releases=[Release(30,'60'),Release(40,'20')],free='20')
        self.assertEqual(result['after']['paid'],'20.00')
        self.assertEqual(result['rows'],[dict(paymentId=20,receiptId=40,amount='20.00')])

    def test_prior_refunds_reduce_capacity(self):
        earlier=self.plan()
        snapshot={**self.snapshot,'refunds':[Refund(self.scope,50,10,'25')],
            'allocations':[Allocation(self.scope,i+1,r['paymentId'],r['receiptId'],r['amount']) for i,r in enumerate(earlier['rows'])]}
        result=plan_refund(**snapshot,refund=Refund(self.scope,51,10,'15'),releases=[],unallocated_amount='15')
        self.assertEqual(result['after']['paid'],'80.00')
        self.assertEqual(result['after']['unallocatedPayments'],'0.00')

    def test_reversal_of_refund_restores_free_money_not_receipt_designations(self):
        plan=self.plan()
        current={**self.snapshot,'refunds':[Refund(self.scope,50,10,'25',reversed=True)],
            'allocations':[Allocation(self.scope,i+1,r['paymentId'],r['receiptId'],r['amount']) for i,r in enumerate(plan['rows'])]}
        result=refund_projection(**current)
        self.assertEqual(result['paid'],'120.00')
        self.assertEqual(result['allocated'],'80.00')
        self.assertEqual(result['unallocatedPayments'],'40.00')

    def test_reversed_payment_with_live_refund_is_rejected(self):
        with self.assertRaises(ValueError):
            refund_projection(**{**self.snapshot,'payments':[replace(self.snapshot['payments'][0],reversed=True),self.snapshot['payments'][1]],
                'refunds':[Refund(self.scope,50,10,'1')]})

    def test_missing_release_and_overrelease_fail(self):
        for releases,free in [([], '0'),([Release(30,'61')],'0'),([Release(40,'25')],'0'),
                              ([Release(99,'20')],'5'),([Release(30,'10'),Release(30,'10')],'5')]:
            with self.subTest(releases=releases),self.assertRaises(ValueError):
                self.plan(releases=releases,free=free)

    def test_cannot_refund_free_money_from_another_payment_or_opening(self):
        with self.assertRaises(ValueError):
            self.plan(releases=[],free='25',opening_paid='40',allocations=self.snapshot['allocations'][:2])

    def test_foreign_scopes_and_dangling_or_duplicate_refunds_fail(self):
        for field in ('company_id','payer_company_id','supplier_id','invoice_id'):
            with self.subTest(field=field),self.assertRaises(ValueError):
                refund_projection(**{**self.snapshot,'refunds':[Refund(replace(self.scope,**{field:99}),50,10,'1')]})
        for refunds in ([Refund(self.scope,50,999,'1')], [Refund(self.scope,10,10,'1')],
                        [Refund(self.scope,50,10,'1')]*2):
            with self.assertRaises(ValueError):
                refund_projection(**{**self.snapshot,'refunds':refunds})

    def test_invalid_amounts_and_boolean_flags_fail(self):
        for amount in ('0','-1','0.001','NaN','Infinity',True,0.1,None):
            with self.subTest(amount=amount),self.assertRaises(ValueError):
                self.plan(amount=amount)
        with self.assertRaises(ValueError):
            refund_projection(**{**self.snapshot,'refunds':[Refund(self.scope,50,10,'1',reversed=1)]})

    def test_many_cent_splits_conserve_all_three_balances(self):
        for cents in range(1,101):
            amount=format(Decimal(cents)/100,'.2f')
            result=self.plan(amount=amount,releases=[Release(30,amount)],free='0')
            before,after=result['before'],result['after']
            self.assertEqual(Decimal(before['paid'])-Decimal(after['paid']),Decimal(amount))
            self.assertEqual(Decimal(before['allocated'])-Decimal(after['allocated']),Decimal(amount))
            self.assertEqual(before['unallocatedPayments'],after['unallocatedPayments'])

    def test_superseded_duplicate_designations_are_not_merged(self):
        with self.assertRaises(ValueError):
            self.plan(allocations=self.snapshot['allocations']+[Allocation(self.scope,4,10,30,'1')])
