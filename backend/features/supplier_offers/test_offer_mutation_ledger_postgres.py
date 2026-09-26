"""Isolated PG regressions for offer edits and shipping around registered invoices."""
import os
import json
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from . import test_invoice_ledger_guards_postgres as invoice_tests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class OfferMutationLedgerTests(unittest.TestCase):
    setUpClass = classmethod(invoice_tests.OfferInvoiceLedgerTests.setUpClass.__func__)
    sql = invoice_tests.OfferInvoiceLedgerTests.sql
    api = invoice_tests.OfferInvoiceLedgerTests.api
    register = invoice_tests.OfferInvoiceLedgerTests.register

    def setUp(self):
        invoice_tests.OfferInvoiceLedgerTests.setUp(self)
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s WHERE id=%s',
                 (self.offer, self.request, self.invoice))

    def call(self, kind, data=None, actor='director'):
        path = '/supplier-offers/{id}' + ('/ship' if kind == 'ship' else '')
        method = 'POST' if kind == 'ship' else 'PUT'
        endpoint = next(r.endpoint for r in self.main.app.routes
                        if getattr(r, 'path', '') == path and method in r.methods)
        return endpoint(self.offer, data or ({'shippedQuantity': 2} if kind == 'ship' else {'action': 'reject'}),
                        x_company_id=None, x_company_mode=None, _current_user=self.fixture['users'][actor])

    def snapshot(self):
        return {table: self.sql(f'SELECT * FROM {table} ORDER BY id') for table in
                ('supplier_offers', 'supply_requests', 'supply_request_recipients',
                 'supply_deliveries', 'supplier_invoices', 'warehouse_invoices', 'supplier_offer_events')}

    def test_managed_offer_edits_and_ship_are_denied_without_writes(self):
        self.register()
        for kind, payload in [
            ('update', {'action': 'respond', 'pricePerUnit': 150, 'totalPrice': 300}),
            ('update', {'action': 'reject'}), ('update', {'status': 'Получено'}),
            ('update', {'deliveryStatus': 'Отменено'}), ('ship', {'shippedQuantity': 2}),
        ]:
            with self.subTest(kind=kind, payload=payload):
                before = self.snapshot()
                with self.assertRaises(HTTPException) as error:
                    self.call(kind, payload)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(self.snapshot(), before)

    def test_response_replay_after_invoice_registration_is_readonly(self):
        from uuid import uuid4
        self.sql("UPDATE supplier_offers SET status='Ожидает ответа' WHERE id=%s", (self.offer,))
        command = dict(action='respond', requestId=str(uuid4()), expectedRespondedAt=None,
                       pricePerUnit=100, totalPrice=200, paymentTerms='Постоплата')
        self.call('update', command)
        self.sql("UPDATE supplier_offers SET status='Утверждено' WHERE id=%s", (self.offer,))
        self.register()
        before = self.snapshot()
        replay = self.call('update', command)
        self.assertTrue(replay['submissionAccepted'])
        self.assertEqual(replay['status'], 'Утверждено')
        for changed in (dict(command, totalPrice=201), dict(command, requestId=str(uuid4()))):
            with self.assertRaises(HTTPException) as error:
                self.call('update', changed)
            self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException) as error:
            self.call('update', command, actor='stranger')
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_update_event_keeps_allowlist_and_discards_unexpected_private_fields(self):
        self.call('update', {'action': 'reject', 'supplierMessage': 'Synthetic public note',
                             'unexpectedPrivateField': 'SYNTHETIC-NOT-A-REAL-SECRET'})
        payload = self.sql('SELECT payload_json FROM supplier_offer_events WHERE offer_id=%s',
                           (self.offer,))
        self.assertEqual(len(payload), 1)
        self.assertEqual(json.loads(payload[0][0]),
                         {'action': 'reject', 'supplierMessage': 'Synthetic public note'})

    def test_missing_serializer_dependency_never_falls_back_to_raw_payload(self):
        from inspect import getclosurevars
        from fastapi import FastAPI
        from .routes import register_supplier_offers_module
        endpoint = next(r.endpoint for r in self.main.app.routes
                        if getattr(r, 'path', '') == '/supplier-offers/{id}' and 'PUT' in r.methods)
        minimal_deps = dict(getclosurevars(endpoint).nonlocals['deps'])
        minimal_deps.pop('_supplier_offer_event_payload', None)
        app = FastAPI()
        register_supplier_offers_module(app, minimal_deps)
        update = next(r.endpoint for r in app.routes
                      if getattr(r, 'path', '') == '/supplier-offers/{id}' and 'PUT' in r.methods)
        update(self.offer, {'action': 'reject', 'unexpectedPrivateField': 'SYNTHETIC-PRIVATE'},
               x_company_id=None, x_company_mode=None, _current_user=self.fixture['users']['director'])
        self.assertEqual(self.sql('SELECT payload_json FROM supplier_offer_events WHERE offer_id=%s',
                                  (self.offer,)), [('{}',)])

    def test_request_only_registered_invoice_blocks_offer_edit_and_ship(self):
        self.sql('UPDATE supplier_invoices SET offer_id=NULL WHERE id=%s', (self.invoice,))
        self.register()
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind):
                with self.assertRaises(HTTPException) as error:
                    self.call(kind)
                self.assertEqual(error.exception.status_code, 409)

    def test_registered_other_offer_of_request_blocks_selection(self):
        self.register()
        self.offer = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,
            price_per_unit,total_price,status) VALUES(2,%s,%s,100,200,'Получено') RETURNING id''',
            (self.request, self.fixture['supplierId']))[0][0]
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.call('update', {'action': 'select'})
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_approval_role_denial_precedes_managed_conflict(self):
        self.register()
        self.sql("UPDATE supplier_offers SET status='Получено' WHERE id=%s", (self.offer,))
        for payload in ({'action': 'select'}, {'status': 'Утверждено'}):
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPException) as error:
                    self.call('update', payload, actor='accountant')
                self.assertEqual(error.exception.status_code, 403)

    def test_supplier_visibility_still_precedes_managed_conflict(self):
        self.sql('''UPDATE supply_requests SET prorab_confirmed_at=NOW(),director_approved_at=NOW(),
                    selected_suppliers=%s WHERE id=%s''', ([self.fixture['supplierId']], self.request))
        self.register()
        for kind, payload in [('update', {'action': 'respond'}), ('ship', {'shippedQuantity': 2})]:
            for actor, status in [('supplier', 409), ('stranger_supplier', 403)]:
                with self.subTest(kind=kind, actor=actor):
                    with self.assertRaises(HTTPException) as error:
                        self.call(kind, payload, actor=actor)
                    self.assertEqual(error.exception.status_code, status)

    def test_reverse_managed_warehouse_blocks_both_writers(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,
            total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(2,%s,%s,200,0,'Принята',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], self.invoice))[0][0]
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'warehouse',id,company_id,supplier_id,project,'',total_with_vat,paid_amount
            FROM warehouse_invoices WHERE id=%s''', (warehouse,))
        before = self.snapshot()
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind):
                with self.assertRaises(HTTPException) as error:
                    self.call(kind)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(self.snapshot(), before)

    def test_unmanaged_ship_and_offer_changes_keep_legacy_behavior(self):
        self.assertTrue(self.call('ship')['id'])
        self.call('update', {'action': 'reject'})
        self.assertEqual(self.sql('SELECT status FROM supplier_offers WHERE id=%s', (self.offer,)), [('Отклонено',)])

    def test_update_event_failure_rolls_back_offer_and_recipients(self):
        import psycopg2
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_offer_edit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'Synthetic event failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_offer_edit_failure BEFORE INSERT ON supplier_offer_events
                    FOR EACH ROW EXECUTE FUNCTION synthetic_offer_edit_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.call('update')
        finally:
            self.sql('DROP TRIGGER synthetic_offer_edit_failure ON supplier_offer_events')
            self.sql('DROP FUNCTION synthetic_offer_edit_failure()')
        self.assertEqual(self.snapshot(), before)

    def test_ship_late_failure_rolls_back_new_deliveries(self):
        import psycopg2
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_ship_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'Synthetic ship failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_ship_failure BEFORE UPDATE ON supplier_offers
                    FOR EACH ROW EXECUTE FUNCTION synthetic_ship_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.call('ship')
        finally:
            self.sql('DROP TRIGGER synthetic_ship_failure ON supplier_offers')
            self.sql('DROP FUNCTION synthetic_ship_failure()')
        self.assertEqual(self.snapshot(), before)

    def test_strangers_get_access_denial_before_managed_conflict(self):
        self.register()
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind), self.assertRaises(HTTPException) as error:
                self.call(kind, actor='stranger')
            self.assertEqual(error.exception.status_code, 403)

    def wait_race(self, kind, mutate, expected):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.call, kind)
                try:
                    deadline = time.monotonic() + 3
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql('''SELECT pid FROM pg_stat_activity
                            WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))''', (blocker,))
                        if waiting or pending.done():
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting, 'company lock must precede offer/request/invoice locks')
                    for table, row_id in [('supplier_offers', self.offer), ('supply_requests', self.request),
                                          ('supplier_invoices', self.invoice)]:
                        cur.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE NOWAIT', (row_id,))
                    mutate(cur)
                    conn.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=4)
                    self.assertEqual(error.exception.status_code, expected)
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_registration_during_company_wait_is_seen_by_both_writers(self):
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind):
                self.setUp()
                self.wait_race(kind, self.register, 409)

    def test_revoked_membership_during_wait_is_not_cached(self):
        actor = self.fixture['users']['director']['id']
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind):
                try:
                    self.wait_race(kind, lambda cur: cur.execute(
                        'UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (actor,)), 403)
                finally:
                    self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (actor,))

    def test_no_runtime_ddl_with_ledger_for_both_writers(self):
        for kind in ('update', 'ship'):
            with self.subTest(kind=kind):
                self.setUp()
                conn = self.main.get_db()
                conn.autocommit = False
                try:
                    with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                        cur.execute('''LOCK TABLE supplier_invoices,supply_requests,supplier_offers,
                            supply_deliveries,supply_request_recipients,supplier_offer_events IN ACCESS SHARE MODE''')
                        pending = pool.submit(self.call, kind)
                        try:
                            pending.result(timeout=3)
                        finally:
                            conn.rollback()
                finally:
                    conn.close()


if __name__ == '__main__':
    unittest.main()
