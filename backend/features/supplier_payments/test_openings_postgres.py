"""Explicit legacy opening over real HTTP; disposable PostgreSQL only."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from . import test_receipt_vat_postgres as schema
from . import test_partial_receipt_runtime_postgres as http
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class OpeningTests(unittest.TestCase):
    sql=schema.ReceiptVatTests.sql
    api=http.PartialReceiptRuntimeTests.api
    create_offer=schema.ReceiptVatTests.create_offer
    check_contract=schema.ReceiptVatTests.check_contract

    @classmethod
    def setUpClass(cls):
        schema.ReceiptVatTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0057_supplier_opening_confirmations.py')
                migration(cur,'0057_supplier_opening_confirmations.py',method='downgrade')
                migration(cur,'0057_supplier_opening_confirmations.py')
        finally:
            conn.close()

    def setUp(self):
        flags=patch.dict(os.environ,SUPPLIER_PAYMENTS_ENABLED='1',SUPPLIER_OPENING_CONFIRMATIONS_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)
        self.invoice=self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,project_name,work_package,amount,paid_amount,status)
            VALUES(2,%s,%s,'',200,50,'Утверждён') RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project']))[0][0]
        self.path='/companies/2/supplier-opening-confirmations'

    def preview(self,**kw):
        return self.api('accountant','GET',self.path+'/preview/'+str(self.invoice),**kw)

    def body(self):
        return dict(invoiceId=self.invoice,requestId=str(uuid4()),reason='Сверено с историческими документами',
                    reviewedHash=self.preview()['reviewedHash'])

    def confirm(self,body,actor='accountant',**kw):
        return self.api(actor,'POST',self.path,body,**kw)

    def test_opening_no_new_cash_replay_and_subsequent_payment(self):
        cash=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        body=self.body()
        result=self.confirm(body)
        self.assertEqual(result['openingPaid'],'50.00')
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),cash)
        self.assertEqual(self.confirm(body),result)
        payment=dict(requestId=str(uuid4()),kind='payment',documentKind='invoice',documentId=self.invoice,
                     amount='20.00',paidAt='2026-09-28',reason='Доплата')
        self.api('accountant','POST','/companies/2/supplier-payments',payment)
        self.assertEqual(self.confirm(body),result)
        balance=self.api('accountant','GET',f'/companies/2/supplier-payment-documents/invoice/{self.invoice}')
        self.assertEqual(balance['remainingAmount'],'130.00')
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(70,)])

    def test_stale_review_creates_no_baseline(self):
        body=self.body()
        self.sql('UPDATE supplier_invoices SET paid_amount=51 WHERE id=%s',(self.invoice,))
        self.confirm(body,expected=409)
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s",(self.invoice,)),[])

    def test_new_uuid_after_confirmation_and_changed_replay_rejected(self):
        body=self.body();self.confirm(body)
        self.confirm(dict(body,requestId=str(uuid4())),expected=409)
        self.confirm(dict(body,reason='Другое основание'),expected=409)

    def test_access_checked_before_replay_and_flag_defaults_off(self):
        body=self.body();self.confirm(body)
        self.confirm(body,actor='foreman',expected=403)
        with patch.dict(os.environ,SUPPLIER_OPENING_CONFIRMATIONS_ENABLED='0'):
            self.preview(expected=404)
            self.confirm(body,expected=404)

    def test_unknown_paid_amount_is_not_silently_zero(self):
        self.sql('UPDATE supplier_invoices SET paid_amount=NULL WHERE id=%s',(self.invoice,))
        self.preview(expected=409)

    def test_evidence_is_immutable_and_downgrade_refuses_history(self):
        result=self.confirm(self.body())
        import psycopg2
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql('DELETE FROM supplier_opening_confirmations WHERE id=%s',(result['confirmationId'],))
        conn=self.main.get_db()
        try:
            with self.assertRaises(psycopg2.errors.CheckViolation):
                with conn,conn.cursor() as cur:
                    migration(cur,'0057_supplier_opening_confirmations.py',method='downgrade')
        finally:
            conn.close()

    def test_linked_invoice_requires_separate_reconciliation(self):
        warehouse=self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,paid_amount,supplier_invoice_id)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,200,50,%s) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(warehouse,self.invoice))
        self.preview(expected=409)

    def test_pending_invoice_and_wrong_company_are_rejected(self):
        self.sql("UPDATE supplier_invoices SET status='Новый' WHERE id=%s",(self.invoice,))
        self.preview(expected=409)
        self.api('accountant','GET',f'/companies/1/supplier-opening-confirmations/preview/{self.invoice}',expected=409)

    def test_concurrent_exact_confirmation_has_one_baseline(self):
        from concurrent.futures import ThreadPoolExecutor
        body=self.body()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda _:self.confirm(body),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_opening_confirmations WHERE company_id=2 AND request_id=%s',
                                  (body['requestId'],)),[(1,)])

    def test_sql_cannot_append_confirmation_for_an_old_baseline(self):
        import psycopg2
        result=self.confirm(self.body())
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql('''INSERT INTO supplier_opening_confirmations
                (company_id,request_id,fingerprint,document_record_id,actor_id,actor_name,reason,source_snapshot,reviewed_hash)
                SELECT company_id,%s,fingerprint,document_record_id,actor_id,actor_name,reason,source_snapshot,reviewed_hash
                FROM supplier_opening_confirmations WHERE id=%s''',(str(uuid4()),result['confirmationId']))

    def test_disabled_evidence_guard_rejects_preview_and_confirmation(self):
        body=self.body()
        self.sql('ALTER TABLE supplier_opening_confirmations DISABLE TRIGGER supplier_opening_insert')
        try:
            self.preview(expected=503)
            self.confirm(body,expected=503)
        finally:
            self.sql('ALTER TABLE supplier_opening_confirmations ENABLE TRIGGER supplier_opening_insert')
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s",(self.invoice,)),[])
