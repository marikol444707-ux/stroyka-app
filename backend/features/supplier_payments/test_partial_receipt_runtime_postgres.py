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
                migration(cur, '0053_supplier_receipt_exceptions.py')
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

    def test_rejected_receipt_creates_claim_and_quality_but_not_stock_or_payment(self):
        did=self.ship()
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        accepted=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(
            receivedQuantity=1,qualityStatus='Брак'))
        self.assertTrue(accepted['claimId']);self.assertTrue(accepted['invoiceId'])
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s",(did,)),[(0,)])
        self.assertEqual(self.sql('SELECT rejected_quantity,shortage_quantity FROM supplier_receipt_exceptions WHERE delivery_id=%s',(did,)),[(1,0)])
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        state=self.physical_state()
        replay=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        self.assertTrue(replay['alreadyReceived']);self.assertEqual(self.physical_state(),state)

    def test_shortage_registers_only_accepted_quantity_with_claim(self):
        did=self.ship()
        response=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(
            receivedQuantity=0.5,qualityStatus='Недостача'))
        self.assertTrue(response['claimId'])
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s",(did,)),[(0.5,)])
        self.assertEqual(self.sql('SELECT p.quantity,p.amount FROM supplier_receipt_line_proofs p JOIN supplier_payment_receipt_relations r ON r.id=p.receipt_relation_id WHERE r.source_delivery_id=%s',(did,)),[(0.5,50)])
        self.assertTrue(self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=0.5,qualityStatus='Недостача'))['alreadyReceived'])

    def test_zero_receipt_creates_claim_without_invoice_stock_or_quality_quantity(self):
        did=self.ship()
        response=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=0,qualityStatus='Недостача'))
        self.assertTrue(response['claimId']);self.assertIsNone(response['invoiceId'])
        self.assertEqual(self.sql('SELECT rejected_quantity,shortage_quantity FROM supplier_receipt_exceptions WHERE delivery_id=%s',(did,)),[(0,1)])
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s",(did,)),[(0,)])
        self.assertTrue(self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=0,qualityStatus='Недостача'))['alreadyReceived'])

    def test_nonconforming_material_is_not_available_stock(self):
        did=self.ship()
        response=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Несоответствие'))
        self.assertTrue(response['claimId'])
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s",(did,)),[(0,)])
        listed=self.api('director','GET','/warehouse-invoices')
        invoice=next(row for row in listed if row['id']==response['invoiceId'])
        self.assertEqual((invoice['settlementInvoiceId'],invoice['receiptAccepted'],invoice['receiptQualityStatus']),
                         (self.invoice,False,'Несоответствие'))
        from .contract_context import load_invoice_contract,load_invoice_receipts
        from psycopg2.extras import RealDictCursor
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
                state=load_invoice_receipts(cur,load_invoice_contract(cur,self.invoice,2))
                self.assertEqual(state['acceptedAmount'],0);self.assertTrue(state['hasProblem'])
        finally:conn.close()

    def test_exception_failure_rolls_back_claim_and_quality_too(self):
        from fastapi import HTTPException
        did=self.ship();before=self.physical_state()
        claims=self.sql('SELECT count(*) FROM supply_claims')
        with patch('backend.features.supplier_payments.receipt_exceptions.register_receipt_exception',
                   side_effect=HTTPException(409,'Synthetic late rejection conflict')):
            self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'),expected=409)
        self.assertEqual(self.physical_state(),before)
        self.assertEqual(self.sql('SELECT count(*) FROM supply_claims'),claims)

    def test_exception_sources_and_claim_identity_are_immutable(self):
        from psycopg2 import Error
        did=self.ship()
        result=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        for query,params in (
            ('UPDATE supply_deliveries SET received_quantity=0 WHERE id=%s',(did,)),
            ('UPDATE warehouse_invoices SET paid_amount=100 WHERE id=%s',(result['invoiceId'],)),
            ('DELETE FROM supplier_receipt_exceptions WHERE delivery_id=%s',(did,)),
            ('UPDATE supply_claims SET received_quantity=0 WHERE id=%s',(result['claimId'],)),
            ('TRUNCATE supply_claims',()),
        ):
            with self.subTest(query=query),self.assertRaises(Error):self.sql(query,params)
        # Resolving a claim may change its workflow status, never its source quantities.
        self.sql("UPDATE supply_claims SET status='Закрыта' WHERE id=%s",(result['claimId'],))

    def test_rejected_warehouse_cannot_be_paid_even_by_finance(self):
        did=self.ship()
        result=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        self.api('accountant','POST','/companies/2/supplier-payments',dict(requestId=str(uuid4()),
            documentKind='warehouse',documentId=result['invoiceId'],kind='payment',amount='100.00',
            paidAt='2026-09-28',reason='Rejected warehouse must not be payable'),expected=409)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(40,)])

    def test_rejected_receipt_is_not_a_stock_source_or_separate_payment_baseline(self):
        from fastapi import HTTPException
        from psycopg2 import Error
        from psycopg2.extras import RealDictCursor
        from .receipt_exceptions import assert_stock_source
        did=self.ship()
        result=self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                with self.assertRaises(HTTPException) as error:
                    assert_stock_source(cur,company_id=2,warehouse_id=result['invoiceId'])
                self.assertEqual(error.exception.status_code,409)
        finally:conn.rollback();conn.close()
        with self.assertRaises(Error):
            self.sql("""INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                SELECT company_id,'warehouse',%s,payer_company_id,supplier_id,project_name,work_package,100,0
                FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s""",(result['invoiceId'],self.invoice))

    def test_exception_migration_downgrade_refuses_to_discard_evidence(self):
        from .test_cancellations_postgres import migration
        from psycopg2 import Error
        did=self.ship()
        self.api('foreman','PUT',f'/supply-deliveries/{did}/receive',dict(receivedQuantity=1,qualityStatus='Брак'))
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn.cursor() as cur,self.assertRaises(Error):
                migration(cur,'0053_supplier_receipt_exceptions.py','downgrade')
        finally:conn.rollback();conn.close()

    def test_managed_shipment_requires_owned_quality_runtime(self):
        before=self.physical_state()
        with patch.dict(os.environ,OWNED_DELIVERY_QUALITY_ENABLED='0'):
            self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),shippedQuantity=1),expected=503)
        self.assertEqual(self.physical_state(),before)
