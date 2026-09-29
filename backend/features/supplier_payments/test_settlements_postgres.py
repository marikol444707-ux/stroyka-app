"""Actual HTTP credits/refunds, no production data or money transfers."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from . import test_claim_fulfilment_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SettlementTests(unittest.TestCase):
    sql=base.ClaimFulfilmentTests.sql
    api=base.ClaimFulfilmentTests.api
    create_offer=base.ClaimFulfilmentTests.create_offer
    check_contract=base.ClaimFulfilmentTests.check_contract
    raw_sources=base.ClaimFulfilmentTests.raw_sources
    create=base.ClaimFulfilmentTests.create
    pay=base.ClaimFulfilmentTests.pay
    ship=base.ClaimFulfilmentTests.ship
    receive=base.ClaimFulfilmentTests.receive

    @classmethod
    def setUpClass(cls):
        base.ClaimFulfilmentTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0055_supplier_settlements.py')
                migration(cur,'0055_supplier_settlements.py',method='downgrade')
                migration(cur,'0055_supplier_settlements.py')
        finally:
            conn.close()

    def setUp(self):
        base.ClaimFulfilmentTests.setUp(self)
        flags=patch.dict(os.environ,SUPPLIER_SETTLEMENTS_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)

    def operation(self,kind,amount=None,original=None,expected=200,actor='accountant',body=None):
        body=body or dict(requestId=str(uuid4()),documentKind='invoice',documentId=self.invoice,
            kind=kind,paidAt='2026-09-28',reason='Synthetic credit note / bank statement',
            **({'reversesId':original} if kind=='reversal' else {'amount':str(amount)}))
        return self.api(actor,'POST','/companies/2/supplier-payments',body,expected=expected),body

    def snapshot(self):
        return self.api('accountant','GET',f'/companies/2/supplier-payment-documents/invoice/{self.invoice}')

    def test_credit_creates_no_cash_and_refund_reduces_cash_separately(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        stamp=self.sql('SELECT paid_at,paid_by FROM supplier_invoices WHERE id=%s',(self.invoice,))
        credit,body=self.operation('credit','180')
        self.assertIsNone(credit['projectPaymentId']);self.assertTrue(credit['nonCash'])
        self.assertEqual(self.operation('credit',body=body)[0],credit)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT paid_at,paid_by FROM supplier_invoices WHERE id=%s',(self.invoice,)),stamp)
        self.assertEqual(self.sql('SELECT amount,paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,40)])
        snapshot=self.snapshot()
        self.assertEqual([snapshot[k] for k in ('effectiveAmount','paidAmount','remainingAmount','overpaidAmount')],['20.00','40.00','0.00','20.00'])
        refund,body=self.operation('refund','20')
        self.assertEqual(self.operation('refund',body=body)[0],refund)
        self.assertEqual(self.snapshot()['overpaidAmount'],'0.00')
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s',(refund['projectPaymentId'],)),[(-20,)])
        self.operation('payment','1',expected=400)
        history=self.api('accountant','GET',f'/companies/2/supplier-payments?documentKind=invoice&documentId={self.invoice}')
        self.assertEqual([(r['kind'],r['signedAmount']) for r in history['items']],[('refund','-20.00'),('credit','0.00'),('payment','40.00')])
        listed=next(row for row in self.api('director','GET','/supplier-invoices') if row['id']==self.invoice)
        self.assertEqual((listed['amount'],listed['effectiveAmount'],listed['creditAmount'],listed['remainingAmount']),
                         (200,20,180,0))

    def test_credit_and_refund_can_be_reversed_without_rewriting_history(self):
        credit,_=self.operation('credit','180')
        refund,_=self.operation('refund','20')
        undone,_=self.operation('reversal',original=refund['operationId'])
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s',(undone['projectPaymentId'],)),[(20,)])
        before=self.sql('SELECT count(*) FROM project_payments')
        undone,_=self.operation('reversal',original=credit['operationId'])
        self.assertTrue(undone['nonCash'])
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'),before)
        self.assertEqual(self.snapshot()['remainingAmount'],'160.00')
        self.operation('reversal',original=credit['operationId'],expected=409)

    def test_limits_access_and_disabled_flag(self):
        self.operation('refund','40.01',expected=400)
        self.operation('credit','200.01',expected=409)
        self.operation('credit','10',actor='supplier',expected=403)
        self.operation('credit','10',actor='stranger',expected=403)
        with patch.dict(os.environ,SUPPLIER_SETTLEMENTS_ENABLED='0'):
            self.operation('refund','1',expected=409)
            self.operation('credit','1',expected=409)
        self.assertEqual(self.snapshot()['paidAmount'],'40.00')
        self.assertEqual(self.snapshot()['creditAmount'],'0.00')

    def test_partial_refund_can_be_followed_by_new_payment(self):
        self.operation('refund','15')
        self.assertEqual(self.snapshot()['remainingAmount'],'175.00')
        self.pay('175.00')
        self.assertEqual(self.snapshot()['paidAmount'],'200.00')

    def test_corrected_advance_allows_receipt_without_duplicate_cash_or_debt(self):
        self.operation('credit','180')
        self.operation('refund','20')
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        delivery=self.ship()
        accepted=self.receive(delivery)
        self.assertTrue(self.receive(delivery)['alreadyReceived'])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.snapshot()['remainingAmount'],'0.00')
        self.assertEqual(self.snapshot()['paidAmount'],'20.00')
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',
                                 (accepted['invoiceId'],)),[(None,)])

    def test_cancel_committed_credit_and_cancel_unsubmitted_refund(self):
        credit,body=self.operation('credit','20')
        result=self.api('accountant','POST','/companies/2/supplier-payments/cancel-request',body)
        self.assertEqual(result['status'],'confirmed');self.assertTrue(result['result']['nonCash'])
        unsubmitted={**body,'requestId':str(uuid4()),'kind':'refund','amount':'10'}
        cancelled=self.api('accountant','POST','/companies/2/supplier-payments/cancel-request',unsubmitted)
        self.assertEqual(cancelled['status'],'cancelled')
        self.operation('refund',body=unsubmitted,expected=409)
        with patch.dict(os.environ,SUPPLIER_SETTLEMENTS_ENABLED='0'):
            self.assertEqual(self.operation('credit',body=body)[0],credit)
        self.operation('credit',body={**body,'amount':'21'},expected=409)

    def test_competing_credits_cannot_reduce_below_zero(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(_):
            token=self.main.create_auth_token(self.fixture['users']['accountant'],two_factor_passed=True)
            return self.client.post('/companies/2/supplier-payments',headers={'Authorization':'Bearer '+token,
                'X-Company-Id':'2','X-Company-Mode':'company'},json=dict(requestId=str(uuid4()),documentKind='invoice',
                    documentId=self.invoice,kind='credit',amount='150',paidAt='2026-09-28',reason='Synthetic race')).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt,range(2))),[200,409])
        self.assertEqual(self.snapshot()['creditAmount'],'150.00')

    def test_late_database_failure_rolls_back_cash_operation_and_balance(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        self.sql("CREATE FUNCTION reject_test_settlement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic late failure' USING ERRCODE='23514'; END $$")
        self.sql(f'CREATE TRIGGER z_test_settlement BEFORE UPDATE ON supplier_invoices FOR EACH ROW WHEN (OLD.id={self.invoice}) EXECUTE FUNCTION reject_test_settlement()')
        try:
            self.operation('refund','10',expected=409)
            self.operation('credit','190',expected=409)
        finally:
            self.sql('DROP TRIGGER z_test_settlement ON supplier_invoices')
            self.sql('DROP FUNCTION reject_test_settlement()')
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual((self.snapshot()['paidAmount'],self.snapshot()['creditAmount']),('40.00','0.00'))

    def test_allocated_payment_requires_release_before_refund_or_credit(self):
        self.receive(self.ship())
        group,relation,payment=self.sql('''SELECT g.id,r.id,o.id FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
            JOIN supplier_payment_receipt_relations r ON r.group_id=g.id
            JOIN supplier_payment_operations o ON o.document_id=d.document_id AND o.document_kind='invoice' AND o.company_id=d.company_id
            WHERE d.document_id=%s AND o.kind='payment' ''',(self.invoice,))[0]
        conn=self.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                cur.execute('''INSERT INTO supplier_payment_allocation_revisions(group_id,company_id,version,request_id,fingerprint,actor_id,reason,row_count)
                    VALUES(%s,2,1,%s,%s,%s,'Synthetic allocation',1) RETURNING id''',
                    (group,str(uuid4()),'a'*64,self.fixture['users']['accountant']['id']))
                revision=cur.fetchone()[0]
                cur.execute('''INSERT INTO supplier_payment_allocation_rows(revision_id,group_id,company_id,payment_operation_id,receipt_relation_id,amount)
                    VALUES(%s,%s,2,%s,%s,20)''',(revision,group,payment,relation))
        finally:
            conn.close()
        self.operation('refund','1',expected=409)
        self.operation('credit','1',expected=409)

    def test_evidence_is_immutable_and_downgrade_refuses_credit(self):
        import psycopg2
        credit,_=self.operation('credit','20')
        with self.assertRaises(psycopg2.Error):
            self.sql('UPDATE supplier_payment_operations SET amount=1 WHERE id=%s',(credit['operationId'],))
        conn=self.main.get_db()
        try:
            with self.assertRaises(psycopg2.Error),conn,conn.cursor() as cur:
                migration(cur,'0055_supplier_settlements.py',method='downgrade')
        finally:
            conn.close()
