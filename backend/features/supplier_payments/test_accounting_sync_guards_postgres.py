"""Real PostgreSQL guards for accounting sync and atomic manual receipt creation."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import HTTPException
from psycopg2 import sql as sql_composition

from . import test_engine_postgres as ledger
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AccountingSyncGuardTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        ledger.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        self.number = 'SYNC-' + uuid4().hex
        self.material = 'Synthetic sync stock ' + uuid4().hex
        self.supplier = self.fixture['supplierId']
        self.supplier_name = self.sql('SELECT name FROM suppliers WHERE id=%s', (self.supplier,))[0][0]

    def invoice(self, *, date='2026-09-18', registered=True):
        invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,supplier_name,
            project_name,work_package,invoice_number,invoice_date,amount,paid_amount,status)
            VALUES(2,%s,%s,'','',%s,%s,200,0,'Утверждён') RETURNING id''',
            (self.supplier, self.supplier_name, self.number, date))[0][0]
        if registered:
            self.sql('''INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                VALUES(2,'invoice',%s,2,%s,'','',200,0)''', (invoice, self.supplier))
        return invoice

    def warehouse(self, *, date='2026-09-18', registered=False, linked=None):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,supplier_name,
            project,location,number,date,total_base,total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(2,%s,%s,'','Основной склад',%s,%s,200,200,0,'Принята',%s) RETURNING id''',
            (self.supplier, self.supplier_name, self.number, date, linked))[0][0]
        if registered:
            self.sql('''INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                VALUES(2,'warehouse',%s,2,%s,'Основной склад','',200,0)''', (warehouse, self.supplier))
        return warehouse

    def snapshot(self):
        # Compare all public table rows, including supplier enrichment, journals,
        # receipt lots and AI side effects; sequences are intentionally excluded.
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                tables = [row[0] for row in cur.fetchall()]
                result = {}
                for table in tables:
                    cur.execute(sql_composition.SQL('SELECT to_jsonb(t) FROM public.{} t ORDER BY to_jsonb(t)::text')
                                .format(sql_composition.Identifier(table)))
                    result[table] = cur.fetchall()
                return result
        finally:
            conn.close()

    def denied_sync(self, warehouse, payload=None):
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.main._sync_supplier_invoice_from_warehouse(
                warehouse, payload or {}, self.fixture['users']['director'])
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def payload(self):
        return dict(companyId=2, location='Основной склад', warehouseTarget='main',
                    supplierId=self.supplier, supplierName=self.supplier_name,
                    number=self.number, date='2026-09-18', vat='Без НДС',
                    items=[dict(name=self.material, unit='шт', quantity=2, price=100)],
                    syncSupplierInvoice=True)

    def test_sync_rejects_registered_warehouse_without_writes(self):
        self.denied_sync(self.warehouse(registered=True))

    def test_sync_rejects_registered_normalized_duplicate_invoice(self):
        self.invoice()
        self.number = self.number.replace('-', '')
        self.denied_sync(self.warehouse())

    def test_sync_rejects_registered_reuse_candidate_with_missing_date(self):
        self.invoice(date=None)
        self.denied_sync(self.warehouse(date=None))

    def test_sync_does_not_bypass_guard_via_already_linked_invoice(self):
        invoice = self.invoice()
        warehouse = self.warehouse(linked=invoice)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, invoice))
        self.denied_sync(warehouse)

    def test_payload_company_cannot_override_warehouse_even_on_existing_link(self):
        for linked in (False, True):
            with self.subTest(linked=linked):
                invoice = self.invoice(registered=False) if linked else None
                warehouse = self.warehouse(linked=invoice)
                if linked:
                    self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, invoice))
                self.denied_sync(warehouse, {'companyId': 3})

    def test_existing_link_requires_live_same_company_reciprocal_invoice(self):
        for change in ('company_id=3', "status='Аннулирован'", 'warehouse_invoice_id=NULL'):
            with self.subTest(change=change):
                invoice = self.invoice(registered=False)
                warehouse = self.warehouse(linked=invoice)
                self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, invoice))
                self.sql(f'UPDATE supplier_invoices SET {change} WHERE id=%s', (invoice,))
                self.denied_sync(warehouse)
        self.denied_sync(self.warehouse(linked=2147483647))

    def test_manual_implicit_sync_conflict_rolls_back_receipt_stock_and_history(self):
        self.invoice()
        before = self.snapshot()
        self.api('director', 'POST', '/warehouse-invoices', self.payload(), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_manual_explicit_registered_invoice_link_rolls_back_everything(self):
        invoice = self.invoice()
        before = self.snapshot()
        self.api('director', 'POST', '/warehouse-invoices',
                 {**self.payload(), 'supplierInvoiceId': invoice}, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_manual_explicit_registered_link_rejected_even_with_sync_disabled(self):
        invoice = self.invoice()
        before = self.snapshot()
        self.api('director', 'POST', '/warehouse-invoices',
                 {**self.payload(), 'supplierInvoiceId': invoice, 'syncSupplierInvoice': False}, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_unmanaged_sync_reuses_candidate(self):
        invoice = self.invoice(registered=False)
        warehouse = self.warehouse()
        result = self.main._sync_supplier_invoice_from_warehouse(
            warehouse, {}, self.fixture['users']['director'])
        self.assertEqual(result['id'], invoice)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(invoice,)])

    def test_unmanaged_manual_receipt_creates_stock_and_accounting_invoice(self):
        result = self.api('director', 'POST', '/warehouse-invoices', self.payload())
        self.assertNotIn('accountingWarning', result)
        self.assertTrue(result['supplierInvoiceId'])
        self.assertEqual(self.sql('SELECT quantity FROM warehouse_main WHERE company_id=2 AND name=%s',
                                 (self.material,)), [(2,)])
        self.assertEqual(self.sql('SELECT amount,warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                 (result['supplierInvoiceId'],)), [(200, result['id'])])
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_history WHERE company_id=2 AND material=%s',
                                 (self.material,)), [(1,)])

    def test_explicit_link_rechecks_cancellation_after_company_lock_wait(self):
        invoice = self.invoice(registered=False)
        before = self.snapshot()
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.main._create_warehouse_invoice_record,
                    {**self.payload(), 'supplierInvoiceId': invoice, 'syncSupplierInvoice': False},
                    self.fixture['users']['director'])
                try:
                    deadline = time.monotonic() + 4
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql('''SELECT pid FROM pg_stat_activity
                            WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))''', (blocker,))
                        if waiting:
                            break
                        time.sleep(0.01)
                    self.assertTrue(waiting, 'Receipt must wait before any document mutation')
                    cur.execute("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s", (invoice,))
                    conn.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=5)
                    self.assertEqual(error.exception.status_code, 409)
                finally:
                    conn.rollback()
        finally:
            conn.close()
        after = self.snapshot()
        self.assertEqual({k: v for k, v in before.items() if k != 'supplier_invoices'},
                         {k: v for k, v in after.items() if k != 'supplier_invoices'})
        self.assertEqual(self.sql('SELECT status,warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                 (invoice,)), [('Аннулирован', None)])
