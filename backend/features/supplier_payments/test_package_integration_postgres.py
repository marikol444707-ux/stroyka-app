"""0019 with real document access/resolver/payment policy; no runtime routes."""
import json
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .test_attachments_postgres import AttachmentTests
from .test_documents_postgres import DocumentTests
from .test_packages_migration_postgres import PackageMigrationTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackageIntegrationTests(unittest.TestCase):
    sql = AttachmentTests.sql
    authorization = DocumentTests.authorization
    migration = PackageMigrationTests.migration

    @classmethod
    def setUpClass(cls):
        AttachmentTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                cls('runTest').migration(cur)
        finally:
            conn.close()

    def setUp(self):
        self.actor = self.fixture['users']['accountant']['id']
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount,status) VALUES(2,%s,%s,'Основная',200,0,'Утверждён') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]

    def warehouse(self, linked=True, paid=0, package='Основная'):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status,supplier_invoice_id)
            VALUES(2,%s,%s,%s,200,%s,'Принята','К оплате',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], json.dumps([{'workPackage': package}]),
             paid, self.invoice if linked else None))[0][0]
        if linked:
            self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, self.invoice))
        return warehouse

    def body(self, **extra):
        return dict(requestId=str(uuid4()),kind='payment',documentKind='invoice',documentId=self.invoice,
                    amount='10.00',paidAt='2026-09-18',reason='Actual payment', **extra)

    def execute(self, body):
        from .documents import build_document_resolver
        from .engine import execute
        from .policy import validate_new_payment
        return execute(self.main.get_db, build_document_resolver(self.authorization()), self.actor, 2,
                       body, validate_new=validate_new_payment)

    def history(self):
        return {table:self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text') for table in
                ('supplier_payment_documents','supplier_payment_operations','supplier_payment_impacts',
                 'supplier_payment_attachments','project_payments')}

    def test_full_pair_payment_and_replay_use_exact_package(self):
        warehouse = self.warehouse()
        body = self.body()
        result = self.execute(body)
        before = self.history()
        self.assertEqual(self.execute(body), result)
        self.assertEqual(self.history(), before)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(10,)])
        self.assertEqual(self.sql('SELECT work_package FROM supplier_payment_documents WHERE document_id=%s AND document_kind=%s',
                                 (warehouse, 'warehouse')), [('Основная',)])

    def test_standalone_warehouse_payment(self):
        warehouse = self.warehouse(linked=False)
        body = {**self.body(), 'documentKind':'warehouse', 'documentId':warehouse}
        self.execute(body)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(10,)])

    def test_attachment_next_payment_and_cancelled_reversal_preserve_identity(self):
        from .attachments import attach_receipt
        from .documents import build_document_resolver
        self.execute(self.body())
        warehouse = self.warehouse(paid=10)
        before_expenses = self.sql('SELECT count(*) FROM project_payments')
        body = dict(requestId=str(uuid4()),invoiceId=self.invoice,warehouseId=warehouse,reason='Full receipt')
        # Attachment provenance eligibility is still an unimplemented adapter;
        # actor/document resolution and subsequent payment policy are real.
        attach = lambda: attach_receipt(self.main.get_db, build_document_resolver(self.authorization()),
            self.actor, 2, body, validate_new=lambda *args: None)
        result = attach()
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before_expenses)
        payment_body = self.body()
        payment = self.execute(payment_body)
        history = self.history()
        self.assertEqual(attach(), result)
        self.assertEqual(self.execute(payment_body), payment)
        self.assertEqual(self.history(), history)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(20,)])
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=%s", (warehouse,))
        reverse = self.body(); reverse.pop('amount')
        reverse.update(kind='reversal',reversesId=payment['operationId'])
        self.execute(reverse)
        self.assertEqual(self.sql('SELECT paid_amount,status FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(10,'Аннулирована')])

    def test_sql_validation_parity_and_409_keep_transaction_usable(self):
        from .documents import _snapshot
        warehouse = self.warehouse(linked=False)
        conn = self.main.get_db(); conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT * FROM warehouse_invoices WHERE id=%s FOR UPDATE', (warehouse,))
                row = cur.fetchone()
                for package in ('', 'Основная', 'Раздел 2'):
                    raw = json.dumps([{'workPackage':package,'work_package':package}])
                    cur.execute('SELECT public.supplier_payment_warehouse_package(%s) AS package', (raw,))
                    expected = cur.fetchone()['package']
                    self.assertEqual(_snapshot('warehouse', {**row,'items':raw}, 2, cur=cur)['workPackage'],
                                     expected)
                for raw in ('[]','[{}]','[null]','[{"workPackage":false}]','not json',
                            '[{"workPackage":"A","work_package":"B"}]',
                            '[{"workPackage":"A"},{"workPackage":"B"}]',
                            '[{"workPackage":" A"}]','[{"workPackage":"A","workPackage":"B"}]'):
                    with self.subTest(raw=raw), self.assertRaises(HTTPException) as error:
                        _snapshot('warehouse', {**row,'items':raw}, 2, cur=cur)
                    self.assertEqual(error.exception.status_code, 409)
                    cur.execute('SELECT 1 AS usable')
                    self.assertEqual(cur.fetchone()['usable'], 1)
        finally:
            conn.rollback(); conn.close()

    def test_mixed_packages_fail_before_baseline_or_expense(self):
        warehouse = self.warehouse()
        self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                 (json.dumps([{'workPackage':'Основная'},{'workPackage':'Other'}]), warehouse))
        before = self.history()
        with self.assertRaises(HTTPException) as error:
            self.execute(self.body())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.history(), before)

    def test_existing_empty_baseline_never_adopts_nonempty_live_package(self):
        warehouse = self.warehouse(linked=False, package='')
        self.sql('''INSERT INTO supplier_payment_documents(company_id,document_kind,document_id,
            payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'warehouse',%s,2,%s,%s,'',200,0)''',
            (warehouse,self.fixture['supplierId'],self.fixture['project']))
        self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s', (json.dumps([{'workPackage':'Основная'}]),warehouse))
        before = self.history()
        with self.assertRaises(HTTPException) as error:
            self.execute({**self.body(),'documentKind':'warehouse','documentId':warehouse})
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(self.history(),before)
