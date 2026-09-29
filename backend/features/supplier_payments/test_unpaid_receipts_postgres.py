"""Real postpayment shipment/receipt before any cash operation, isolated DB."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from . import test_partial_receipt_runtime_postgres as partial
from . import test_invoice_line_creation_postgres as invoices


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class UnpaidReceiptTests(unittest.TestCase):
    sql = partial.PartialReceiptRuntimeTests.sql
    create_offer = partial.PartialReceiptRuntimeTests.create_offer
    check_contract = partial.PartialReceiptRuntimeTests.check_contract
    raw_sources = partial.PartialReceiptRuntimeTests.raw_sources
    create = partial.PartialReceiptRuntimeTests.create
    ship = partial.PartialReceiptRuntimeTests.ship
    receive = partial.PartialReceiptRuntimeTests.receive
    pay = partial.PartialReceiptRuntimeTests.pay

    @classmethod
    def setUpClass(cls):
        partial.PartialReceiptRuntimeTests.setUpClass.__func__(cls)

    def api(self, actor, method, path, data=None, **kw):
        if path.startswith('/companies/'):
            return partial.PartialReceiptRuntimeTests.api(self, actor, method, path, data, **kw)
        if method == 'POST' and path.endswith('/contracts') and data:
            event='before_shipment' if getattr(self,'prepayment',False) else 'after_acceptance'
            data = dict(data, paymentTerms='Предоплата' if event=='before_shipment' else 'Постоплата', paymentSchedule={'schemaVersion':1,
                'stages':[{'title':'После приёмки','percentBasisPoints':10000,
                           'event':event,'daysAfter':0}]})
        with patch.dict(os.environ, SUPPLIER_PAYMENT_SCHEDULES_ENABLED='1'):
            return invoices.InvoiceLineCreationPostgresTests.api(self, actor, method, path, data, **kw)

    def setUp(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        flags=patch.dict(os.environ, SUPPLIER_PAYMENTS_ENABLED='1',
            SUPPLIER_PARTIAL_RECEIPTS_ENABLED='1', SUPPLIER_UNPAID_RECEIPTS_ENABLED='1',
            OWNED_DELIVERY_SOURCES_ENABLED='1', OWNED_DELIVERY_QUALITY_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)
        self.invoice=self.create()['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})

    def records(self):
        return self.sql("SELECT opening_paid FROM supplier_payment_documents WHERE company_id=2 AND document_kind='invoice' AND document_id=%s", (self.invoice,))

    def test_receipt_before_first_payment_creates_one_debt_and_no_cash(self):
        self.assertEqual(self.records(), [])
        cash=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        warehouse_ids=[]
        for _ in range(2):
            delivery=self.ship()
            accepted=self.receive(delivery)
            warehouse_ids.append(accepted['invoiceId'])
            self.assertTrue(self.receive(delivery)['alreadyReceived'])
        self.assertEqual(self.records(), [(0,)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),cash)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=ANY(%s)', (warehouse_ids,)),[(None,),(None,)])
        snapshot=self.api('accountant','GET',f'/companies/2/supplier-payment-documents/invoice/{self.invoice}')
        self.assertEqual(snapshot['remainingAmount'],'200.00')
        self.pay('200.00')
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,)])

    def test_failed_shipment_rolls_back_baseline(self):
        self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=9999,waybillNumber='TOO-MUCH'),expected=409)
        self.assertEqual(self.records(),[])

    def test_registration_does_not_bypass_required_prepayment(self):
        self.prepayment=True
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        self.invoice=self.create()['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=1,waybillNumber='NEEDS-PAYMENT'),expected=400)
        self.assertEqual(self.records(),[])

    def test_default_off_probe_never_creates_a_baseline(self):
        from psycopg2.extras import RealDictCursor
        from .partial_receipt_runtime import supports_managed_receipts
        conn=self.main.get_db()
        try:
            with conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
                with patch.dict(os.environ,SUPPLIER_UNPAID_RECEIPTS_ENABLED='0'):
                    self.assertFalse(supports_managed_receipts(cur,2,self.invoice))
        finally:
            conn.close()
        self.assertEqual(self.records(),[])

    def test_payment_after_shipment_before_receipt_uses_same_baseline(self):
        delivery=self.ship()
        self.pay('200.00')
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        self.receive(delivery)
        self.assertEqual(self.records(),[(0,)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)

    def test_foreign_actor_cannot_register_unpaid_invoice(self):
        self.api('stranger','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=1,waybillNumber='FOREIGN'),expected=403)
        self.assertEqual(self.records(),[])

    def test_historical_paid_amount_is_not_silently_imported(self):
        self.sql('UPDATE supplier_invoices SET paid_amount=10 WHERE id=%s',(self.invoice,))
        self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=1,waybillNumber='HISTORICAL'),expected=409)
        self.assertEqual(self.records(),[])

    def test_unapproved_invoice_is_not_registered(self):
        self.sql("UPDATE supplier_invoices SET status='На проверке' WHERE id=%s",(self.invoice,))
        self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=1,waybillNumber='UNAPPROVED'),expected=409)
        self.assertEqual(self.records(),[])
