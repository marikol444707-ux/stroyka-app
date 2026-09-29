"""Real receipt HTTP/SQL; deterministic boundary hooks, no fake stock/auth.

Requires a fresh explicit Unix-socket test database. Registration below uses
the engine's company-lock protocol and real baseline INSERT, not a payment API.
"""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from . import test_delivery_payment_guards_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DeliverySourceLockingTests(unittest.TestCase):
    setUpClass = classmethod(support.DeliveryPaymentGuardTests.setUpClass.__func__)
    setUp = support.DeliveryPaymentGuardTests.setUp
    sql = support.DeliveryPaymentGuardTests.sql
    api = support.DeliveryPaymentGuardTests.api
    receive = support.DeliveryPaymentGuardTests.receive
    snapshot = support.DeliveryPaymentGuardTests.snapshot

    def candidate_at_prepared_boundary(self, *, no_source=False, replay=False):
        if no_source:
            self.sql('DELETE FROM supplier_invoices WHERE id=%s', (self.invoice,))
        prior = self.receive() if replay else None
        original = self.main._ensure_supply_delivery_invoice_prepared
        resolver = self.main._find_supplier_invoice_for_supply
        inserted = []

        def inject(cur, delivery, *args, **kwargs):
            # Separate committed writer deliberately does NOT cooperate with the
            # company advisory lock, like a not-yet-audited legacy writer.
            inserted.append(self.sql('''INSERT INTO supplier_invoices
                (company_id,supplier_id,project_name,request_id,offer_id,work_package,amount,paid_amount,status)
                VALUES(2,%s,%s,%s,%s,'Основная',200,0,'Утверждён') RETURNING id''',
                (self.fixture['supplierId'], self.project, self.request_id, self.offer))[0][0])
            return original(cur, delivery, *args, **kwargs)

        with patch.object(self.main, '_ensure_supply_delivery_invoice_prepared', side_effect=inject), \
                patch.object(self.main, '_find_supplier_invoice_for_supply', wraps=resolver) as lookup:
            result = self.receive()
        warehouse = result['invoiceId']
        expected_source = None if no_source else self.invoice
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',
                                  (warehouse,)), [(expected_source,)])
        self.assertEqual(self.sql('SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                  (inserted[0],)), [(None,)])
        self.assertEqual(lookup.call_count, 2, 'entry guard + wrapper guard only; no lookup after validation')
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2 AND project=%s',
                                  (self.project,)), [(2,)])
        if prior:
            self.assertEqual(warehouse, prior['invoiceId'])
            self.assertTrue(result['alreadyReceived'])

    def test_new_receipt_pins_validated_source_despite_new_candidate(self):
        self.candidate_at_prepared_boundary()

    def test_new_receipt_pins_explicit_absence_despite_new_candidate(self):
        self.candidate_at_prepared_boundary(no_source=True)

    def test_replay_pins_validated_source_despite_new_candidate(self):
        self.candidate_at_prepared_boundary(replay=True)

    def wait_for_blocker(self, blocker_pid, waiter_pid=None):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            rows = self.sql('''SELECT pid FROM pg_stat_activity
                WHERE datname=current_database() AND wait_event='advisory'
                  AND %s=ANY(pg_blocking_pids(pid)) AND (%s IS NULL OR pid=%s)''',
                (blocker_pid, waiter_pid, waiter_pid))
            if rows:
                return rows[0][0]
            time.sleep(.01)
        self.fail('Expected actual advisory wait confirmed by pg_blocking_pids')

    def insert_baseline(self, cur):
        cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'invoice',id,company_id,supplier_id,project_name,work_package,amount,paid_amount
            FROM supplier_invoices WHERE id=%s''', (self.invoice,))

    def test_receipt_waits_for_registration_then_denies_without_partial_writes(self):
        first = self.main.get_db()
        first.autocommit = False
        try:
            with first.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                pending = pool.submit(self.receive, expected=409)
                try:
                    self.wait_for_blocker(first.get_backend_pid())
                    self.insert_baseline(cur)
                    first.commit()
                    before = self.snapshot()
                    pending.result(timeout=10)
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(self.sql('SELECT status,received_quantity FROM supply_deliveries WHERE id=%s',
                                              (self.delivery,)), [('Отгружено', 0)])
                finally:
                    first.rollback()
        finally:
            first.close()

    def test_registration_waits_for_receipt_and_observes_committed_link(self):
        at_boundary, release, registering = Event(), Event(), Event()
        receipt_pid, registration_pid = [], []
        original = self.main._ensure_supply_delivery_invoice_prepared

        def pause(cur, *args, **kwargs):
            receipt_pid.append(cur.connection.get_backend_pid())
            at_boundary.set()
            if not release.wait(8):
                raise AssertionError('Test failed to release receipt boundary')
            return original(cur, *args, **kwargs)

        def register():
            conn = self.main.get_db()
            conn.autocommit = False
            try:
                with conn, conn.cursor() as cur:
                    registration_pid.append(conn.get_backend_pid())
                    registering.set()
                    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                    cur.execute('SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s FOR UPDATE',
                                (self.invoice,))
                    linked = cur.fetchone()[0]
                    self.insert_baseline(cur)
                    return linked
            finally:
                conn.close()

        with patch.object(self.main, '_ensure_supply_delivery_invoice_prepared', side_effect=pause), \
                ThreadPoolExecutor(max_workers=2) as pool:
            receipt = pool.submit(self.receive)
            try:
                self.assertTrue(at_boundary.wait(3))
                registration = pool.submit(register)
                self.assertTrue(registering.wait(3))
                self.wait_for_blocker(receipt_pid[0], registration_pid[0])
            finally:
                release.set()
            result = receipt.result(timeout=10)
            self.assertEqual(registration.result(timeout=10), result['invoiceId'])
        before = self.snapshot()
        self.receive(expected=409)
        self.assertEqual(self.snapshot(), before)
