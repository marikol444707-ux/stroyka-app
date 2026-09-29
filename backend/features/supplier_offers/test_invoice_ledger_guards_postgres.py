"""Opt-in real PostgreSQL coverage for the offer invoice writer."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi import HTTPException

from ..supplier_payments import test_engine_postgres as ledger
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class OfferInvoiceLedgerTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        ledger.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        self.number = 'OFFER-GUARD-' + uuid4().hex
        self.request = self.sql('''INSERT INTO supply_requests(company_id,project,material_name,
            quantity,unit,work_package,status) VALUES(2,%s,'Synthetic',2,'шт','','В работе') RETURNING id''',
            (self.fixture['project'],))[0][0]
        self.offer = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,
            price_per_unit,total_price,status) VALUES(2,%s,%s,100,200,'Утверждено') RETURNING id''',
            (self.request, self.fixture['supplierId']))[0][0]
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,supplier_name,
            project_name,work_package,invoice_number,invoice_date,amount,paid_amount,status)
            SELECT 2,id,name,%s,'',%s,'2026-09-18',200,0,'Утверждён' FROM suppliers WHERE id=%s RETURNING id''',
            (self.fixture['project'], self.number, self.fixture['supplierId']))[0][0]

    def register(self, cur=None):
        query = '''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'invoice',id,company_id,supplier_id,project_name,'',amount,paid_amount
            FROM supplier_invoices WHERE id=%s'''
        (cur.execute if cur else self.sql)(query, (self.invoice,))

    def create(self, actor='director', expected=200):
        return self.api(actor, 'POST', f'/supplier-offers/{self.offer}/create-invoice',
                        dict(invoiceNumber=self.number, invoiceDate='2026-09-18', amount=200, vatAmount=0),
                        expected=expected)

    def snapshot(self):
        return {table: self.sql(f'SELECT * FROM {table} ORDER BY id') for table in
                ('supplier_invoices', 'warehouse_invoices', 'supplier_offer_events', 'supplier_payment_documents')}

    def test_registered_duplicate_is_not_enriched(self):
        self.register()
        before = self.snapshot()
        self.create(expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_unmanaged_duplicate_is_reused(self):
        self.assertEqual(self.create()['id'], self.invoice)
        self.assertEqual(self.sql('SELECT offer_id,request_id FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(self.offer, self.request)])

    def test_registered_same_offer_replay_is_readonly_and_authorized(self):
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s WHERE id=%s',
                 (self.offer, self.request, self.invoice))
        self.register()
        before = self.snapshot()
        self.assertEqual(self.create()['id'], self.invoice)
        self.create(actor='stranger', expected=403)
        self.assertEqual(self.snapshot(), before)

    def endpoint(self):
        return next(route.endpoint for route in self.main.app.routes
                    if getattr(route, 'path', '') == '/supplier-offers/{id}/create-invoice')

    def direct_create(self):
        return self.endpoint()(self.offer,
            dict(invoiceNumber=self.number, invoiceDate='2026-09-18', amount=200, vatAmount=0),
            x_company_id=None, x_company_mode=None, _current_user=self.fixture['users']['director'])

    def wait_race(self, mutate, expected):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.direct_create)
                try:
                    deadline = time.monotonic() + 4
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql('''SELECT pid FROM pg_stat_activity
                            WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))''', (blocker,))
                        if waiting:
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting, 'Writer must wait for company before row locks')
                    cur.execute('SELECT id FROM supplier_offers WHERE id=%s FOR UPDATE NOWAIT', (self.offer,))
                    cur.execute('SELECT id FROM supply_requests WHERE id=%s FOR UPDATE NOWAIT', (self.request,))
                    mutate(cur)
                    conn.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=4)
                    self.assertEqual(error.exception.status_code, expected)
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_registration_while_waiting_is_seen_before_duplicate_update(self):
        self.wait_race(self.register, 409)
        self.assertEqual(self.sql('SELECT offer_id FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(None,)])

    def test_offer_owner_change_while_waiting_is_rejected(self):
        self.wait_race(lambda cur: cur.execute('UPDATE supplier_offers SET company_id=3 WHERE id=%s', (self.offer,)), 409)

    def test_revoked_membership_cannot_replay_using_legacy_role(self):
        self.sql('UPDATE supplier_invoices SET offer_id=%s WHERE id=%s', (self.offer, self.invoice))
        self.register()
        actor = self.fixture['users']['director']['id']
        try:
            self.wait_race(lambda cur: cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (actor,)), 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (actor,))

    def test_disabled_user_after_wait_cannot_replay(self):
        self.sql('UPDATE supplier_invoices SET offer_id=%s WHERE id=%s', (self.offer, self.invoice))
        self.register()
        actor = self.fixture['users']['director']['id']
        try:
            self.wait_race(lambda cur: cur.execute('UPDATE users SET active=FALSE WHERE id=%s', (actor,)), 403)
        finally:
            self.sql('UPDATE users SET active=TRUE WHERE id=%s', (actor,))

    def test_no_runtime_ddl_with_ledger_schema(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                # These permit normal DML, but block ALTER/CREATE TABLE helpers.
                cur.execute('''LOCK TABLE supplier_invoices,supply_requests,supplier_offers,
                    supply_request_recipients,supplier_offer_events IN ACCESS SHARE MODE''')
                pending = pool.submit(self.direct_create)
                try:
                    self.assertEqual(pending.result(timeout=4)['id'], self.invoice)
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_registered_reverse_warehouse_reference_is_protected(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,
            total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(2,%s,%s,200,0,'Принята',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], self.invoice))[0][0]
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'warehouse',id,company_id,supplier_id,project,'',total_with_vat,paid_amount
            FROM warehouse_invoices WHERE id=%s''', (warehouse,))
        before = self.snapshot()
        self.create(expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_broken_unmanaged_reciprocal_link_is_rejected(self):
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=2147483647 WHERE id=%s', (self.invoice,))
        before = self.snapshot()
        self.create(expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_supplier_visibility_and_readonly_registered_replay(self):
        self.sql('''UPDATE supply_requests SET prorab_confirmed_at=NOW(),director_approved_at=NOW(),
                    selected_suppliers=%s WHERE id=%s''', ([self.fixture['supplierId']], self.request))
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s WHERE id=%s',
                 (self.offer, self.request, self.invoice))
        self.register()
        before = self.snapshot()
        self.assertEqual(self.create(actor='supplier')['id'], self.invoice)
        self.create(actor='stranger_supplier', expected=403)
        self.assertEqual(self.snapshot(), before)

    def test_new_invoice_and_event_remain_atomic(self):
        self.number = 'NEW-' + uuid4().hex
        created = self.create()['id']
        self.assertNotEqual(created, self.invoice)
        self.assertEqual(self.sql('SELECT company_id,offer_id,request_id FROM supplier_invoices WHERE id=%s',
                                 (created,)), [(2, self.offer, self.request)])
        self.assertEqual(self.sql('SELECT event_type FROM supplier_offer_events WHERE offer_id=%s',
                                 (self.offer,)), [('invoice_created',)])

    def test_event_failure_rolls_back_duplicate_enrichment(self):
        import psycopg2
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_offer_event_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'Synthetic event failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_offer_event_failure BEFORE INSERT ON supplier_offer_events
                    FOR EACH ROW EXECUTE FUNCTION synthetic_offer_event_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.direct_create()
        finally:
            self.sql('DROP TRIGGER synthetic_offer_event_failure ON supplier_offer_events')
            self.sql('DROP FUNCTION synthetic_offer_event_failure()')
        self.assertEqual(self.snapshot(), before)
