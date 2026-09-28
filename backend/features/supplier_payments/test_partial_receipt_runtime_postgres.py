"""Real HTTP payment -> partial shipments -> receipt -> settlement, isolated DB."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from . import test_invoice_line_creation_postgres as base
from .test_receipt_line_proofs_postgres import ReceiptLineProofTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PartialReceiptRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flags=patch.dict(os.environ, SUPPLIER_PAYMENT_SCHEDULES_ENABLED='1')
        flags.start(); cls.addClassCleanup(flags.stop)
        ReceiptLineProofTests.setUpClass.__func__(cls)
        from .test_cancellations_postgres import migration
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                cls.main._ensure_journal_source_columns(cur)
                migration(cur, '0023_quality_journal_owners.py')
        finally:
            conn.close()
    sql = base.InvoiceLineCreationPostgresTests.sql
    create_offer = base.InvoiceLineCreationPostgresTests.create_offer
    check_contract = base.InvoiceLineCreationPostgresTests.check_contract
    raw_sources = base.InvoiceLineCreationPostgresTests.raw_sources
    create = base.InvoiceLineCreationPostgresTests.create

    def api(self, actor, method, path, data=None, **kw):
        if method == 'POST' and path.endswith('/contracts') and data:
            data = dict(data, paymentTerms='Предоплата 20%, остаток после поставки',
                paymentSchedule={'schemaVersion':1, 'stages':[
                    {'title':'Аванс', 'percentBasisPoints':2000, 'event':'before_shipment', 'daysAfter':0},
                    {'title':'Остаток', 'percentBasisPoints':8000, 'event':'after_acceptance', 'daysAfter':0}]})
        if path.startswith('/companies/'):
            token = self.main.create_auth_token(self.fixture['users'][actor], two_factor_passed=True)
            response = self.client.request(method, path, json=data, headers={
                'Authorization': 'Bearer '+token, 'X-Company-Id': '2', 'X-Company-Mode': 'company'})
            self.assertEqual(response.status_code, kw.get('expected',200), response.text)
            return response.json()
        with patch.dict(os.environ, SUPPLIER_PAYMENT_SCHEDULES_ENABLED='1'):
            return base.InvoiceLineCreationPostgresTests.api(self, actor, method, path, data, **kw)

    def setUp(self):
        base.InvoiceLineCreationPostgresTests.setUp(self)
        flags = patch.dict(os.environ, SUPPLIER_PAYMENTS_ENABLED='1',
            SUPPLIER_PARTIAL_RECEIPTS_ENABLED='1', OWNED_DELIVERY_SOURCES_ENABLED='1',
            OWNED_DELIVERY_QUALITY_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)
        self.invoice = self.create()['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        self.pay('40.00')

    def pay(self, amount):
        return self.api('accountant','POST','/companies/2/supplier-payments',dict(
            requestId=str(uuid4()),documentKind='invoice',documentId=self.invoice,kind='payment',
            amount=amount,paidAt='2026-09-28',reason='Synthetic full HTTP chain'))

    def ship(self):
        return self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),
            shippedQuantity=1,waybillNumber='PARTIAL-'+uuid4().hex))['id']

    def receive(self, delivery, **kw):
        return self.api('foreman','PUT',f'/supply-deliveries/{delivery}/receive',dict(
            receivedQuantity=1,qualityStatus='Принято',receivedBy='Synthetic receiver'),**kw)

    def test_two_receipts_replay_and_final_payment(self):
        before = self.sql('SELECT count(*),sum(amount) FROM project_payments')
        stock_before = self.sql('SELECT COALESCE(sum(quantity),0) FROM materials WHERE company_id=2 AND project=%s AND name=%s', (self.fixture['project'],self.fixture['materialName']))[0][0]
        deliveries=[]; warehouses=[]
        for _ in range(2):
            did=self.ship();deliveries.append(did)
            accepted=self.receive(did);warehouses.append(accepted['invoiceId'])
            again=self.receive(did)
            self.assertTrue(again['alreadyReceived'])
            self.assertEqual(again['invoiceId'],accepted['invoiceId'])
        self.assertEqual(len(set(warehouses)),2)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT paid_amount,warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)),[(40,None)])
        self.assertEqual(self.sql('SELECT count(*),sum(p.quantity),sum(p.amount) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',
                                 (self.invoice,)),[(2,2,200)])
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_history WHERE source_type=\'supply_delivery\' AND source_id=ANY(%s)',
                                 (deliveries,)),[(2,)])
        self.assertEqual(self.sql('SELECT supplier_invoice_id,paid_amount FROM warehouse_invoices WHERE id=ANY(%s)',
                                 (warehouses,)),[(None,0),(None,0)])
        listed = self.api('director','GET','/warehouse-invoices')
        self.assertEqual({row['id']:row.get('settlementInvoiceId') for row in listed if row['id'] in warehouses},
                         {wid:self.invoice for wid in warehouses})
        self.assertEqual(self.sql('SELECT COALESCE(sum(quantity),0) FROM materials WHERE company_id=2 AND project=%s AND name=%s',
                                 (self.fixture['project'],self.fixture['materialName']))[0][0], stock_before+2)
        self.assertEqual(self.sql('SELECT company_id,project_id,quantity FROM material_inspection_journal WHERE delivery_id=ANY(%s)',
                                 (deliveries,)),[(2,self.fixture['projectId'],1)]*2)
        self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s',(self.request_id,)),[('Поставлено',)])
        self.pay('160.00')
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)),[(200,'Оплачен')])

    def physical_state(self):
        return {table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id') for table in (
            'supply_deliveries','warehouse_invoices','warehouse_history','materials',
            'material_inspection_journal','supplier_invoices','project_payments')}

    def test_late_proof_failure_rolls_back_stock_quality_and_documents(self):
        from fastapi import HTTPException
        did=self.ship();before=self.physical_state()
        with patch('backend.features.supplier_payments.receipt_line_proofs.register_receipt_line',
                   side_effect=HTTPException(409,'Synthetic late proof conflict')):
            self.receive(did,expected=409)
        self.assertEqual(self.physical_state(),before)
        self.receive(did)

    def test_foreign_actor_and_warehouse_payment_cannot_bypass_invoice(self):
        did=self.ship();before=self.physical_state()
        self.api('stranger','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1),expected=403)
        self.assertEqual(self.physical_state(),before)
        wid=self.receive(did)['invoiceId'];before=self.physical_state()
        response=self.api('accountant','POST','/companies/2/supplier-payments',dict(
            requestId=str(uuid4()),documentKind='warehouse',documentId=wid,kind='payment',
            amount='100.00',paidAt='2026-09-28',reason='Must not create second debt'),expected=409)
        self.assertIn('общему счёту',response['detail'])
        self.assertEqual(self.physical_state(),before)
        foreign=self.api('stranger','GET','/warehouse-invoices')
        self.assertNotIn(wid,[row['id'] for row in foreign])

    def test_default_off_still_blocks_managed_shipment(self):
        before=self.physical_state()
        with patch.dict(os.environ,SUPPLIER_PARTIAL_RECEIPTS_ENABLED='0'):
            self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),shippedQuantity=1),expected=409)
        self.assertEqual(self.physical_state(),before)

    def test_problem_receipt_is_not_silently_registered_as_accepted(self):
        did=self.ship();before=self.physical_state()
        self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(
            receivedQuantity=1,qualityStatus='Брак'),expected=409)
        self.assertEqual(self.physical_state(),before)
