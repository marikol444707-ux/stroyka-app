"""Permanent request cancellation, isolated PG only; no routes or notifications."""
import ast
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException

from . import test_attachments_postgres as attachment_tests
from . import test_engine_postgres as engine_tests


def migration(cur, filename='0048_supplier_payment_cancellations.py', method='upgrade'):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions' / filename
    tree = ast.parse(path.read_text())
    namespace = {'op': SimpleNamespace(execute=cur.execute), '__file__': str(path)}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                            type_ignores=[]), str(path), 'exec'), namespace)
    namespace[method]()
    return namespace


class CancellationMigrationSourceTests(unittest.TestCase):
    def test_additive_immutable_table_and_parent(self):
        statements = []
        namespace = migration(SimpleNamespace(execute=statements.append))
        self.assertEqual(namespace['down_revision'], '0047_supplier_payment_packages')
        self.assertLessEqual(len(namespace['revision']), 32)
        sql = '\n'.join(statements)
        for required in ('UNIQUE(company_id,request_id)', 'BEFORE UPDATE OR DELETE', 'BEFORE TRUNCATE',
                         'REFERENCES public.companies', 'REFERENCES public.users', 'fingerprint', 'cancelled_at'):
            self.assertIn(required, sql)
        self.assertFalse(any(s.lstrip().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for s in statements))


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CancellationTests(unittest.TestCase):
    sql = attachment_tests.AttachmentTests.sql
    policy = engine_tests.LedgerTests.policy

    @classmethod
    def setUpClass(cls):
        attachment_tests.AttachmentTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0047_supplier_payment_packages.py')
                migration(cur)
        finally:
            conn.close()

    def setUp(self):
        self.actor = self.fixture['users']['accountant']['id']
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount,status) VALUES(2,%s,%s,'',200,0,'Утверждён') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]

    def resolver(self):
        from .access import build_payment_access
        from .documents import build_document_resolver
        deps = dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
                    finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
                    client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
                    require_project_access=self.main.require_project_access, has_package_access=self.main.has_package_access)
        return build_document_resolver(build_payment_access(deps))

    def body(self, **extra):
        body = dict(requestId=str(uuid4()),kind='payment',documentKind='invoice',documentId=self.invoice,
                    amount='10.00',paidAt='2026-09-18',reason='Synthetic attempt')
        return {**body, **extra}

    def pay(self, body, resolver=None):
        from .engine import execute
        from .policy import validate_new_payment
        return execute(self.main.get_db, resolver or self.resolver(), self.actor, 2, body,
                       validate_new=validate_new_payment)

    def cancel(self, body, resolver=None):
        from .cancellations import cancel_request
        return cancel_request(self.main.get_db, resolver or self.resolver(), self.actor, 2, body)

    def financial_snapshot(self):
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text')
                for table in ('supplier_invoices','warehouse_invoices','project_payments',
                              'supplier_payment_operations','supplier_payment_documents','supplier_payment_impacts',
                              'supplier_payment_attachments')}

    def test_cancel_replay_and_late_original_no_financial_writes(self):
        body = self.body()
        before = self.financial_snapshot()
        result = self.cancel(body)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(self.cancel(body), result)
        with self.assertRaises(HTTPException) as error:
            self.pay(body)
        self.assertEqual(error.exception.detail['code'], 'request_cancelled')
        self.assertEqual(self.financial_snapshot(), before)

    def test_committed_payment_returns_confirmed_never_tombstone(self):
        body = self.body()
        paid = self.pay(body)
        before = self.financial_snapshot()
        self.assertEqual(self.cancel(body), dict(status='confirmed',requestId=body['requestId'],result=paid))
        self.assertEqual(self.sql('SELECT id FROM supplier_payment_request_cancellations WHERE request_id=%s',
                                 (body['requestId'],)), [])
        self.assertEqual(self.financial_snapshot(), before)
        with self.assertRaises(HTTPException) as error:
            self.cancel({**body, 'amount': '11'})
        self.assertEqual(error.exception.detail['code'], 'request_id_conflict')

    def test_changed_payload_and_actor_conflict(self):
        body = self.body()
        self.cancel(body)
        for run in (lambda: self.cancel({**body,'amount':'11'}), lambda: self.pay({**body,'reason':'Other'})):
            with self.assertRaises(HTTPException) as error:
                run()
            self.assertEqual(error.exception.status_code, 409)
        self.actor = self.fixture['users']['director']['id']
        with self.assertRaises(HTTPException) as error:
            self.cancel(body)
        self.assertEqual(error.exception.status_code, 409)

    def test_current_auth_required_even_cancel_replay(self):
        body = self.body()
        self.cancel(body)
        try:
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.actor,))
            with self.assertRaises(HTTPException) as error:
                self.cancel(body)
            self.assertEqual(error.exception.status_code, 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (self.actor,))

    def test_pending_status_does_not_block_cancellation(self):
        self.sql("UPDATE supplier_invoices SET status='На утверждении' WHERE id=%s", (self.invoice,))
        self.assertEqual(self.cancel(self.body())['status'], 'cancelled')

    def test_commit_failure_rolls_back_tombstone_without_financial_writes(self):
        body = self.body()
        before = self.financial_snapshot()
        self.sql('''CREATE FUNCTION synthetic_cancel_commit_failure() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred failure'; END $$ LANGUAGE plpgsql''')
        self.sql('''CREATE CONSTRAINT TRIGGER synthetic_cancel_failure
            AFTER INSERT ON supplier_payment_request_cancellations DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION synthetic_cancel_commit_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.cancel(body)
            self.assertEqual(self.sql('SELECT id FROM supplier_payment_request_cancellations WHERE request_id=%s',
                                     (body['requestId'],)), [])
            self.assertEqual(self.financial_snapshot(), before)
        finally:
            self.sql('DROP TRIGGER synthetic_cancel_failure ON supplier_payment_request_cancellations')
            self.sql('DROP FUNCTION synthetic_cancel_commit_failure()')

    def test_cancel_reversal_attempt_does_not_reverse_payment(self):
        payment = self.pay(self.body())
        reverse = self.body(kind='reversal',reversesId=payment['operationId'])
        reverse.pop('amount')
        before = self.financial_snapshot()
        self.cancel(reverse)
        with self.assertRaises(HTTPException) as error:
            self.pay(reverse)
        self.assertEqual(error.exception.detail['code'], 'request_cancelled')
        self.assertEqual(self.financial_snapshot(), before)

    def ordered_race(self, cancel_first):
        body = self.body()
        entered, release = Event(), Event()
        pids = []
        authorize = self.resolver()
        def pause(cur, *args):
            context = authorize(cur, *args)
            cur.execute('SELECT pg_backend_pid() AS pid')
            pids.append(cur.fetchone()['pid'])
            entered.set()
            if not release.wait(5):
                raise AssertionError('Race release timed out')
            return context
        first, second = (self.cancel, self.pay) if cancel_first else (self.pay, self.cancel)
        with ThreadPoolExecutor(max_workers=2) as pool:
            leader = pool.submit(first, body, pause)
            try:
                self.assertTrue(entered.wait(4))
                follower = pool.submit(second, body)
                waiting = []
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (pids[0],))
                    if waiting:
                        break
                    time.sleep(.01)
                self.assertTrue(waiting, 'Follower must block on the same company lock')
            finally:
                release.set()
            first_result = leader.result(timeout=4)
            if cancel_first:
                self.assertEqual(first_result['status'], 'cancelled')
                with self.assertRaises(HTTPException) as error:
                    follower.result(timeout=4)
                self.assertEqual(error.exception.detail['code'], 'request_cancelled')
                self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(0,)])
            else:
                self.assertEqual(follower.result(timeout=4)['result'], first_result)
                self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(10,)])

    def test_cancel_wins_real_company_lock_race(self):
        self.ordered_race(True)

    def test_payment_wins_real_company_lock_race(self):
        self.ordered_race(False)

    def test_tombstone_immutable_and_nonempty_downgrade_refused(self):
        self.cancel(self.body())
        for sql in ('UPDATE supplier_payment_request_cancellations SET fingerprint=fingerprint',
                    'DELETE FROM supplier_payment_request_cancellations',
                    'TRUNCATE supplier_payment_request_cancellations'):
            with self.subTest(sql=sql), self.assertRaises(psycopg2.Error):
                self.sql(sql)
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur, self.assertRaises(psycopg2.Error):
                migration(cur, method='downgrade')
        finally:
            conn.close()

    def test_namespace_probe_rejects_repeatable_read(self):
        from .cancellations import require_uncancelled
        for isolation in ('REPEATABLE READ', 'SERIALIZABLE'):
            conn = self.main.get_db()
            try:
                with self.subTest(isolation=isolation), conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL ' + isolation)
                    with self.assertRaises(HTTPException) as error:
                        require_uncancelled(cur, 2, str(uuid4()), '0' * 64)
                    self.assertEqual(error.exception.status_code, 409)
            finally:
                conn.close()

    def attachment(self, request_id):
        from .attachments import attach_receipt
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,0,'Принята',%s) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse,self.invoice))
        pair = engine_tests.LedgerTests.pair_policy(self, warehouse)
        # Existing synthetic attachment fixture proves namespace admission only;
        # cancellation and payment themselves use the real current auth/resolver.
        before = self.financial_snapshot()
        run = lambda: attach_receipt(self.main.get_db, pair, self.actor, 2,
            dict(requestId=request_id,invoiceId=self.invoice,warehouseId=warehouse,reason='Synthetic receipt'),
            validate_new=lambda *args: None)
        return run, before

    def test_cancelled_uuid_cannot_be_used_by_attachment_worker(self):
        body = self.body()
        self.cancel(body)
        self.pay(self.body())
        attach, before = self.attachment(body['requestId'])
        with self.assertRaises(HTTPException) as error:
            attach()
        self.assertEqual(error.exception.detail['code'], 'request_id_conflict')
        self.assertEqual(self.financial_snapshot(), before)

    def test_existing_attachment_uuid_cannot_be_cancelled_as_payment(self):
        self.pay(self.body())
        body = self.body()
        attach, _ = self.attachment(body['requestId'])
        attach()
        before = self.financial_snapshot()
        with self.assertRaises(HTTPException) as error:
            self.cancel(body)
        self.assertEqual(error.exception.detail['code'], 'request_id_conflict')
        self.assertEqual(self.financial_snapshot(), before)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CancellationMissingMigrationTests(unittest.TestCase):
    setUpClass = classmethod(engine_tests.LedgerTests.setUpClass.__func__)
    setUp = CancellationTests.setUp
    sql = CancellationTests.sql
    resolver = CancellationTests.resolver
    body = CancellationTests.body
    pay = CancellationTests.pay
    cancel = CancellationTests.cancel

    def test_cancel_fails_closed_without_0020_but_old_payment_still_works(self):
        body = self.body()
        with self.assertRaises(HTTPException) as error:
            self.cancel(body)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_documents'), [(0,)])
        self.pay(body)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(10,)])


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CancellationSchemaTests(unittest.TestCase):
    setUpClass = classmethod(CancellationTests.setUpClass.__func__)

    def test_empty_downgrade_and_reupgrade(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                migration(cur, method='downgrade')
                cur.execute("SELECT to_regclass('public.supplier_payment_request_cancellations')")
                self.assertEqual(cur.fetchone(), (None,))
                migration(cur)
                cur.execute('SELECT count(*) FROM supplier_payment_request_cancellations')
                self.assertEqual(cur.fetchone(), (0,))
        finally:
            conn.rollback()
            conn.close()

    def test_constraints_and_company_uuid_uniqueness(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                values = [2, str(uuid4()), 'a' * 64, self.fixture['users']['accountant']['id'], 'invoice', 1]
                sql = '''INSERT INTO supplier_payment_request_cancellations
                    (company_id,request_id,fingerprint,actor_id,document_kind,document_id)
                    VALUES(%s,%s,%s,%s,%s,%s) RETURNING cancelled_at'''
                cur.execute(sql, values)
                self.assertIsNotNone(cur.fetchone()[0])
                for index, invalid in ((0, 2147483647), (1, 'bad'), (2, ''), (3, 2147483647),
                                       (4, 'other'), (5, 0), (5, -1), (5, None)):
                    with self.subTest(index=index, invalid=invalid):
                        cur.execute('SAVEPOINT invalid_row')
                        candidate = list(values)
                        candidate[1] = str(uuid4())
                        candidate[index] = invalid
                        with self.assertRaises(psycopg2.Error):
                            cur.execute(sql, candidate)
                        cur.execute('ROLLBACK TO SAVEPOINT invalid_row')
                cur.execute('SAVEPOINT duplicate')
                with self.assertRaises(psycopg2.errors.UniqueViolation):
                    cur.execute(sql, values)
                cur.execute('ROLLBACK TO SAVEPOINT duplicate')
        finally:
            conn.rollback()
            conn.close()
