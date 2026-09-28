"""Matched historical invoice/receipt openings remain one financial obligation."""
import os
from unittest.mock import patch
from uuid import uuid4
from .test_openings_postgres import OpeningTests
from .test_cancellations_postgres import migration


class PairedOpeningTests(OpeningTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0058_supplier_paired_openings.py')
                migration(cur,'0058_supplier_paired_openings.py',method='downgrade')
                migration(cur,'0058_supplier_paired_openings.py')
        finally:
            conn.close()

    def pair(self):
        flags=patch.dict(os.environ,SUPPLIER_PAIRED_OPENINGS_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)
        warehouse=self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,paid_amount,supplier_invoice_id,accounting_status)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,200,50,%s,'Частично оплачена') RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(warehouse,self.invoice))
        return warehouse

    def test_pair_opening_payment_and_reversal_never_double_cash(self):
        warehouse=self.pair()
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        body=self.body(); result=self.confirm(body)
        self.assertEqual(result['openingPaid'],'50.00')
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.confirm(body),result)
        payment=dict(requestId=str(uuid4()),kind='payment',documentKind='invoice',documentId=self.invoice,
                     amount='20.00',paidAt='2026-09-28',reason='Доплата по паре')
        operation=self.api('accountant','POST','/companies/2/supplier-payments',payment)
        for kind,document in [('invoice',self.invoice),('warehouse',warehouse)]:
            balance=self.api('accountant','GET',f'/companies/2/supplier-payment-documents/{kind}/{document}')
            self.assertEqual(balance['remainingAmount'],'130.00')
            self.assertEqual(balance['paidAmount'],'70.00')
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),[(before[0][0]+1,(before[0][1] or 0)+20)])
        self.api('accountant','POST','/companies/2/supplier-payments',dict(requestId=str(uuid4()),
            kind='reversal',documentKind='invoice',documentId=self.invoice,reversesId=operation['operationId'],
            paidAt='2026-09-28',reason='Сторно тестовой доплаты'))
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(50,)])

    def test_changed_receipt_after_review_rolls_back_both_baselines(self):
        warehouse=self.pair();body=self.body()
        self.sql("UPDATE warehouse_invoices SET accounting_status='К оплате' WHERE id=%s",(warehouse,))
        self.confirm(body,expected=409)
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE (document_kind='invoice' AND document_id=%s) OR (document_kind='warehouse' AND document_id=%s)",(self.invoice,warehouse)),[])

    def test_disagreeing_paid_amount_is_not_aligned_automatically(self):
        warehouse=self.pair()
        self.sql('UPDATE warehouse_invoices SET paid_amount=49 WHERE id=%s',(warehouse,))
        self.preview(expected=409)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(49,)])

    def test_pair_evidence_failure_rolls_back_both_inserted_baselines(self):
        from . import openings
        warehouse=self.pair();body=self.body()
        original=openings.candidate
        def corrupt_evidence(*args):
            result=original(*args)
            result[3]['source']='{}'
            return result
        with patch.object(openings,'candidate',side_effect=corrupt_evidence):
            self.confirm(body,expected=409)
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE (document_kind='invoice' AND document_id=%s) OR (document_kind='warehouse' AND document_id=%s)",(self.invoice,warehouse)),[])

    def test_pair_downgrade_cannot_discard_receipt_evidence(self):
        import psycopg2
        warehouse=self.pair();result=self.confirm(self.body())
        self.assertEqual(result['warehouseId'],warehouse)
        conn=self.main.get_db()
        try:
            with self.assertRaises(psycopg2.errors.CheckViolation):
                with conn,conn.cursor() as cur:
                    migration(cur,'0058_supplier_paired_openings.py',method='downgrade')
        finally:
            conn.close()

    def test_one_sided_pair_is_not_repaired_by_confirmation(self):
        warehouse=self.pair()
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE id=%s',(self.invoice,))
        self.preview(expected=409)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(self.invoice,)])
