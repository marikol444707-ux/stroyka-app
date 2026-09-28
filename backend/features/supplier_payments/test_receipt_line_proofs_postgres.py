"""Future-only receipt proof registration on disposable full-schema PostgreSQL."""
import os
import unittest
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from psycopg2 import Error
from psycopg2.extras import RealDictCursor
from . import test_invoice_line_creation_postgres as base
from .test_cancellations_postgres import migration
from .receipt_line_proofs import register_receipt_line


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ReceiptLineProofTests(unittest.TestCase):
    sql = base.InvoiceLineCreationPostgresTests.sql
    api = base.InvoiceLineCreationPostgresTests.api
    create_offer = base.InvoiceLineCreationPostgresTests.create_offer
    check_contract = base.InvoiceLineCreationPostgresTests.check_contract
    raw_sources = base.InvoiceLineCreationPostgresTests.raw_sources
    create = base.InvoiceLineCreationPostgresTests.create

    @classmethod
    def setUpClass(cls):
        base.InvoiceLineCreationPostgresTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0052_supplier_receipt_lines.py')
        finally:
            conn.close()

    def setUp(self):
        base.InvoiceLineCreationPostgresTests.setUp(self)
        self.request_items = [dict(self.request_items[0],materialName='Receipt A'),
                              dict(self.request_items[0],materialName='Receipt B')]
        self.kp_items = [dict(row,pricePerUnit='50.00',totalPrice='100.00') for row in self.request_items]
        self.raw_sources(self.request_items,self.kp_items)
        self.invoice = self.create()['id']
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
        self.api('accountant','POST','/companies/2/supplier-payments',dict(requestId=str(uuid4()),
            documentKind='invoice',documentId=self.invoice,kind='payment',amount='40.00',
            paidAt='2026-09-28',reason='Synthetic advance'),expected=404)
        from .access import build_payment_access
        from .documents import build_document_resolver
        from .engine import execute
        from .policy import validate_new_payment
        access=build_payment_access(dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES,platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,require_project_access=self.main.require_project_access,
            has_package_access=self.main.has_package_access))
        execute(self.main.get_db,build_document_resolver(access),self.fixture['users']['accountant']['id'],2,
            dict(requestId=str(uuid4()),documentKind='invoice',documentId=self.invoice,kind='payment',
                 amount='40.00',paidAt='2026-09-28',reason='Synthetic advance'),validate_new=validate_new_payment)
        self.conn=self.main.get_db();self.conn.autocommit=False
        self.addCleanup(self.conn.close);self.addCleanup(self.conn.rollback)
        self.cur=self.conn.cursor(cursor_factory=RealDictCursor);self.addCleanup(self.cur.close)
        self.cur.execute('SELECT pg_advisory_xact_lock(1735289201,2)')

    def receipt(self,name='Receipt A',qty='1',price='50'):
        self.cur.execute('''INSERT INTO supply_deliveries
            (company_id,offer_id,request_id,supplier_id,project,work_package,contract_version_id,
             source_supplier_invoice_id,status,quality_status,received_at,received_quantity,
             shipped_quantity,planned_quantity,price_per_unit,material_name,unit)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,contract_version_id,
                id,'Принято','Принято',NOW(),%s,%s,2,%s,%s,'шт'
            FROM supplier_invoices WHERE id=%s RETURNING id''',(qty,qty,price,name,self.invoice))
        delivery=self.cur.fetchone()['id'];amount=Decimal(qty)*Decimal(price)
        self.cur.execute('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,total_vat,paid_amount,status,
             supply_delivery_id,source_type,source_id,supply_request_id)
            SELECT company_id,supplier_id,project_name,
                json_build_array(json_build_object('workPackage',work_package,'quantity',%s::numeric,
                    'price',%s::numeric,'name',%s::text,'unit','шт'))::text,
                %s,%s,0,0,'Принята',%s,'supply_delivery',%s,request_id
            FROM supplier_invoices WHERE id=%s RETURNING id''',
            (qty,price,name,amount,amount,delivery,str(delivery),self.invoice))
        return self.cur.fetchone()['id']

    def register(self,wid):
        return register_receipt_line(self.cur,company_id=2,invoice_id=self.invoice,warehouse_id=wid)

    def test_partial_lines_and_replay_do_not_duplicate_money(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        a=self.receipt();first=self.register(a)
        self.assertEqual(self.register(a),first)
        self.register(self.receipt());self.register(self.receipt('Receipt B',qty='2'))
        self.conn.commit()
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(40,)])
        self.assertEqual(self.sql('SELECT sum(p.quantity),sum(p.amount) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',(self.invoice,)),[(4,200)])

    def test_cumulative_quantity_is_capped_per_line_not_only_invoice_total(self):
        self.register(self.receipt());self.register(self.receipt())
        self.conn.commit()
        with self.assertRaises(HTTPException) as caught:
            self.register(self.receipt())  # 150 < total 200, but 3 units > 2 on this line.
        self.assertEqual(caught.exception.status_code,409)
        self.conn.rollback()
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_receipt_line_proofs p JOIN supplier_invoice_lines l ON l.id=p.invoice_line_id JOIN supplier_invoice_line_specs s ON s.id=l.spec_id WHERE s.invoice_id=%s',(self.invoice,)),[(2,)])

    def test_wrong_price_or_material_has_no_matching_line(self):
        for kw in ({'price':'49'},{'name':'Another material'}):
            with self.subTest(kw=kw):
                self.cur.execute('SAVEPOINT invalid_receipt')
                with self.assertRaises(HTTPException):self.register(self.receipt(**kw))
                self.cur.execute('ROLLBACK TO SAVEPOINT invalid_receipt')

    def test_group_cannot_commit_an_unproven_extra_receipt(self):
        first=self.register(self.receipt());self.conn.commit()
        wid=self.receipt('Receipt B')
        self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (company_id,group_id,warehouse_invoice_id,amount,provenance) VALUES(2,%s,%s,50,NULL)''',
            (first['groupId'],wid))
        with self.assertRaises(Error):self.conn.commit()
        self.conn.rollback()

    def test_proof_is_immutable_and_cannot_be_reassigned(self):
        first=self.register(self.receipt());self.conn.commit()
        for query in ('UPDATE supplier_receipt_line_proofs SET quantity=2 WHERE receipt_relation_id=%s',
                      'DELETE FROM supplier_receipt_line_proofs WHERE receipt_relation_id=%s'):
            with self.assertRaises(Error):self.cur.execute(query,(first['receiptRelationId'],))
            self.conn.rollback()

    def test_concurrent_receipts_cannot_consume_the_same_remaining_quantity(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        self.register(self.receipt());self.conn.commit()
        barrier=Barrier(2)
        def receive():
            conn=self.main.get_db();conn.autocommit=False
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    barrier.wait(timeout=10)
                    worker=object.__new__(type(self));worker.cur=cur;worker.invoice=self.invoice
                    wid=worker.receipt()
                    register_receipt_line(cur,company_id=2,invoice_id=self.invoice,warehouse_id=wid)
                    conn.commit()
                    return 200
            except HTTPException as error:
                conn.rollback();return error.status_code
            finally:conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:receive(),range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_deliveries WHERE source_supplier_invoice_id=%s',(self.invoice,)),[(2,)])

    def test_database_rejects_forged_line_identity(self):
        first=self.register(self.receipt());self.conn.commit()
        wid=self.receipt()
        self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (company_id,group_id,warehouse_invoice_id,amount,provenance)
            VALUES(2,%s,%s,50,NULL) RETURNING id''',(first['groupId'],wid))
        relation=self.cur.fetchone()['id']
        self.cur.execute('''SELECT l.id FROM supplier_invoice_lines l JOIN supplier_invoice_line_specs s
            ON s.id=l.spec_id WHERE s.invoice_id=%s AND l.material_name='Receipt B' ''',(self.invoice,))
        wrong_line=self.cur.fetchone()['id']
        with self.assertRaises(Error):
            self.cur.execute('''INSERT INTO supplier_receipt_line_proofs
                (receipt_relation_id,invoice_line_id,company_id,quantity,amount) VALUES(%s,%s,2,1,50)''',
                (relation,wrong_line))
        self.conn.rollback()

    def test_downgrade_refuses_to_discard_recorded_receipt_proofs(self):
        self.register(self.receipt());self.conn.commit()
        with self.assertRaises(Error):
            migration(self.cur,'0052_supplier_receipt_lines.py',method='downgrade')
        self.conn.rollback()
        self.cur.execute('SELECT count(*) FROM supplier_receipt_line_proofs')
        self.assertGreater(self.cur.fetchone()['count'],0)


from . import test_allocation_store_postgres as legacy

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ReceiptProofLegacyCompatibilityTests(legacy.AllocationStorePostgresTests):
    @classmethod
    def setUpClass(cls):
        legacy.AllocationStorePostgresTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                for name in ('0050_supplier_invoice_line_specs.py','0051_supplier_offer_item_scopes.py',
                             '0052_supplier_receipt_lines.py'):
                    migration(cur,name)
        finally:conn.close()
