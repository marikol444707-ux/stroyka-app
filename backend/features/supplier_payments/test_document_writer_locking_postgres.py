"""Real transaction ordering and rollback; never contacts production."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi import HTTPException

from . import test_document_writer_guards_postgres as routes
from .guards import lock_document_writer, require_unmanaged_document


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DocumentWriterLockingTests(unittest.TestCase):
    setUpClass = classmethod(routes.DocumentWriterGuardTests.setUpClass.__func__)
    setUp = routes.DocumentWriterGuardTests.pair
    sql = routes.DocumentWriterGuardTests.sql
    api = routes.DocumentWriterGuardTests.api
    seed_warehouse = routes.DocumentWriterGuardTests.seed_warehouse
    snapshot = routes.DocumentWriterGuardTests.snapshot

    def race(self, mutate):
        first = self.main.get_db()
        first.autocommit = False
        ready = Event()
        worker_pid = []
        def waiting_writer():
            conn = self.main.get_db()
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT pg_backend_pid()')
                    worker_pid.append(cur.fetchone()[0])
                    ready.set()
                    lock_document_writer(cur, 'invoice', self.invoice)
                    require_unmanaged_document(cur, 'invoice', self.invoice)
            finally:
                conn.close()
        try:
            with first.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                pending = pool.submit(waiting_writer)
                try:
                    self.assertTrue(ready.wait(3))
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        state = self.sql('SELECT wait_event FROM pg_stat_activity WHERE pid=%s', (worker_pid[0],))
                        if state == [('advisory',)]:
                            break
                        time.sleep(0.01)
                    self.assertEqual(state, [('advisory',)])
                    mutate(cur)
                    first.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=3)
                    self.assertEqual(error.exception.status_code, 409)
                finally:
                    # Unblock the worker even if an assertion fails.
                    first.rollback()
        finally:
            first.close()

    def test_registration_committed_while_writer_waits_is_not_missed(self):
        def register(cur):
            cur.execute('''INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                SELECT company_id,'invoice',id,company_id,supplier_id,project_name,'',amount,paid_amount
                FROM supplier_invoices WHERE id=%s''', (self.invoice,))
        self.race(register)

    def test_ownership_change_while_waiting_requires_retry(self):
        self.race(lambda cur: cur.execute('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (self.invoice,)))

    def test_autocommit_and_stale_snapshot_are_not_accepted(self):
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                with self.assertRaises(RuntimeError):
                    lock_document_writer(cur, 'invoice', self.invoice)
                conn.autocommit = False
                cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                with self.assertRaises(HTTPException):
                    lock_document_writer(cur, 'invoice', self.invoice)
        finally:
            conn.close()

    def test_supplier_update_late_failure_rolls_back_both_documents(self):
        import psycopg2
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_writer_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic writer failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_writer_failure BEFORE UPDATE ON warehouse_invoices
            FOR EACH ROW EXECUTE FUNCTION synthetic_writer_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.api('director', 'PUT', f'/supplier-invoices/{self.invoice}', {'paidAmount': 1})
        finally:
            self.sql('DROP TRIGGER synthetic_writer_failure ON warehouse_invoices')
            self.sql('DROP FUNCTION synthetic_writer_failure()')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql('SELECT pg_try_advisory_xact_lock(%s,%s)', (1735289201, 2)), [(True,)])
