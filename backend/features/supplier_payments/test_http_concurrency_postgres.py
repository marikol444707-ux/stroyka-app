"""Concurrent HTTP writes through real authentication, policy and PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest

from .test_routes_postgres import PaymentHTTPTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentHTTPConcurrencyTests(unittest.TestCase):
    setUpClass = classmethod(PaymentHTTPTests.setUpClass.__func__)
    setUp = PaymentHTTPTests.setUp
    sql = PaymentHTTPTests.sql
    api = PaymentHTTPTests.api
    call = PaymentHTTPTests.call
    body = PaymentHTTPTests.body
    doc = PaymentHTTPTests.doc
    snapshot = PaymentHTTPTests.snapshot
    create_offer = PaymentHTTPTests.create_offer
    check_contract = PaymentHTTPTests.check_contract
    change_snapshot = PaymentHTTPTests.change_snapshot

    def concurrent_payments(self, bodies):
        control = self.main.get_db()
        control.autocommit = False
        try:
            with control.cursor() as cur:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(1735289201,2)')
                blocker = cur.fetchone()[0]
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = [pool.submit(self.call, 'POST', body=body) for body in bodies]
                try:
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event='advisory'
                            AND %s=ANY(pg_blocking_pids(pid))""", (blocker,))
                        if len(waiting) == 2:
                            break
                        time.sleep(.02)
                    self.assertEqual(len(waiting), 2, 'Both HTTP writes must overlap at the company lock')
                finally:
                    control.rollback()
                return [future.result(timeout=15) for future in pending]
        finally:
            control.close()

    def assert_accounting(self, results, amount, status, operations):
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                  (self.invoice,)), [(amount, status)])
        self.assertEqual(self.sql('''SELECT count(*),sum(amount) FROM supplier_payment_operations
            WHERE company_id=2 AND document_kind='invoice' AND document_id=%s''',
                                  (self.invoice,)), [(operations, amount)])
        ids = list({result['projectPaymentId'] for result in results})
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments WHERE id=ANY(%s)',
                                  (ids,)), [(operations, amount)])
        history = self.call(path=self.path + '?documentKind=invoice&documentId=' + str(self.invoice))
        self.assertEqual({row['operationId'] for row in history['items']},
                         {result['operationId'] for result in results})

    def test_concurrent_same_uuid_records_one_payment_and_one_project_total(self):
        body = self.body()
        results = self.concurrent_payments([body, body])
        self.assertEqual(results[0], results[1])
        self.assert_accounting(results, 10, 'Частично оплачен', 1)
        self.assertEqual(self.call('POST', body=body), results[0])
        self.assert_accounting(results, 10, 'Частично оплачен', 1)

    def test_concurrent_distinct_uuids_keep_equal_installments(self):
        bodies = [{**self.body(), 'amount': '100.00'} for _ in range(2)]
        results = self.concurrent_payments(bodies)
        self.assertNotEqual(results[0]['operationId'], results[1]['operationId'])
        self.assert_accounting(results, 200, 'Оплачен', 2)
        before = self.snapshot()
        self.call('POST', body=self.body(), expected=400)
        self.assertEqual(self.snapshot(), before)

    def test_failed_write_then_exact_retry_records_one_payment(self):
        body = self.body()
        self.sql('''CREATE FUNCTION synthetic_atomic_retry_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic payment update failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_atomic_retry_failure BEFORE UPDATE ON supplier_invoices
            FOR EACH ROW EXECUTE FUNCTION synthetic_atomic_retry_failure()''')
        before = self.snapshot()
        try:
            result = self.call('POST', body=body, expected=503)
            self.assertIn('UUID', result['detail'])
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('DROP FUNCTION synthetic_atomic_retry_failure() CASCADE')
        saved = self.call('POST', body=body)
        self.assertEqual(self.call('POST', body=body), saved)
        self.assert_accounting([saved], 10, 'Частично оплачен', 1)
