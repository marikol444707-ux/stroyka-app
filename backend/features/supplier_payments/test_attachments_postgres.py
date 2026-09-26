"""Internal full-invoice attachment; synthetic policy, not runtime authorization."""
import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from . import test_engine_postgres as base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AttachmentTests(unittest.TestCase):
    sql = base.LedgerTests.sql
    body = base.LedgerTests.body
    policy = base.LedgerTests.policy
    execute = base.LedgerTests.execute
    pair_policy = base.LedgerTests.pair_policy
    seed_warehouse = base.LedgerTests.seed_warehouse

    @classmethod
    def setUpClass(cls):
        base.LedgerTests.setUpClass.__func__(cls)
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0046_supplier_payment_attachments.py'
        tree = ast.parse(path.read_text())
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                namespace = {'op': SimpleNamespace(execute=cur.execute)}
                exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                                        type_ignores=[]), str(path), 'exec'), namespace)
                namespace['upgrade']()
        finally:
            conn.close()

    def setUp(self):
        base.LedgerTests.setUp(self)
        self.advance = self.execute(self.body('40'))
        self.warehouse = self.seed_warehouse()
        self.sql('UPDATE warehouse_invoices SET paid_amount=0 WHERE id=%s', (self.warehouse,))
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (self.warehouse, self.invoice))
        self.pair = self.pair_policy(self.warehouse)

    def attachment_body(self):
        return dict(requestId=str(uuid4()), invoiceId=self.invoice, warehouseId=self.warehouse,
                    reason='Synthetic full receipt after advance')

    def attach(self, body=None, actor=None):
        from .attachments import attach_receipt
        return attach_receipt(self.main.get_db, self.pair, self.actor if actor is None else actor,
                              2, body or self.attachment_body(), validate_new=lambda *args: None)

    def test_advance_attachment_remaining_and_old_advance_reversal(self):
        original = self.sql('SELECT * FROM supplier_payment_impacts WHERE operation_id=%s', (self.advance['operationId'],))
        before = self.sql('SELECT count(*) FROM project_payments')
        stock = self.sql('SELECT id,quantity FROM materials ORDER BY id')
        body = self.attachment_body()
        attachment = self.attach(body)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(60,)])
        self.execute(self.body('140'), policy=self.pair)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(200,)])
        self.assertEqual(self.attach(body), attachment)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(200,)])
        reverse = {key: value for key, value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal', reversesId=self.advance['operationId'])
        self.execute(reverse, policy=self.pair)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(160,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(160,)])
        self.assertEqual(self.sql('SELECT * FROM supplier_payment_impacts WHERE operation_id=%s', (self.advance['operationId'],)), original)
        self.assertEqual(self.sql('SELECT id,quantity FROM materials ORDER BY id'), stock)
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_payment_impacts i JOIN supplier_payment_documents d
            ON d.id=i.document_record_id WHERE d.document_kind='warehouse' AND d.document_id=%s''', (self.warehouse,)), [(0,)])

    def test_replay_conflict_revoked_actor_and_uuid_namespace(self):
        body = self.attachment_body(); first = self.attach(body)
        self.assertEqual(self.attach(body), first)
        for action, code in ((lambda: self.attach({**body, 'reason': 'Changed'}), 409),
                             (lambda: self.attach(body, actor=self.fixture['users']['stranger']['id']), 403),
                             (lambda: self.execute({**self.body(), 'requestId': body['requestId']}, policy=self.pair), 409)):
            with self.assertRaises(HTTPException) as error:
                action()
            self.assertEqual(error.exception.status_code, code)

    def test_parallel_attachment_is_one_event(self):
        body = self.attachment_body()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.attach, [body, body]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_attachments WHERE request_id=%s', (body['requestId'],)), [(1,)])

    def test_attachment_and_payment_serialize_without_lost_balance(self):
        # The synthetic resolver chooses the current registered group under the
        # company lock, just as a future real resolver must do, not before it.
        def live_policy(cur, actor_id, company_id, command):
            cur.execute('''SELECT a.id FROM supplier_payment_attachments a
                JOIN supplier_payment_documents d ON d.id=a.invoice_record_id
                WHERE a.company_id=%s AND d.document_id=%s''', (company_id, self.invoice))
            policy = self.pair if cur.fetchone() else self.policy
            return policy(cur, actor_id, company_id, command)
        before = self.sql('SELECT count(*) FROM project_payments')[0][0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            attached = pool.submit(self.attach)
            payment = pool.submit(self.execute, self.body('10'), live_policy)
            attached.result(); payment.result()
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), [(before + 1,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(70,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(70,)])

    def test_unknown_paid_amount_and_partial_receipt_are_not_guessed(self):
        self.sql('UPDATE warehouse_invoices SET paid_amount=5 WHERE id=%s', (self.warehouse,))
        with self.assertRaises(HTTPException):
            self.attach()
        self.sql('UPDATE warehouse_invoices SET paid_amount=0,total_with_vat=100 WHERE id=%s', (self.warehouse,))
        with self.assertRaises(HTTPException):
            self.attach()
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_documents WHERE document_kind=\'warehouse\' AND document_id=%s',
                                  (self.warehouse,)), [(0,)])

    def test_attached_mirror_cannot_be_omitted_or_drift(self):
        self.attach()
        with self.assertRaises(HTTPException):
            self.execute(self.body())
        self.sql('UPDATE warehouse_invoices SET paid_amount=61 WHERE id=%s', (self.warehouse,))
        with self.assertRaises(HTTPException):
            self.execute(self.body(), policy=self.pair)

    def test_copied_advance_is_not_double_counted(self):
        self.sql('UPDATE warehouse_invoices SET paid_amount=60 WHERE id=%s', (self.warehouse,))
        self.attach()
        self.execute(self.body('10'), policy=self.pair)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(70,)])
        self.assertEqual(self.sql('''SELECT opening_paid FROM supplier_payment_documents
            WHERE document_kind='warehouse' AND document_id=%s''', (self.warehouse,)), [(60,)])

    def test_changed_reciprocal_link_blocks_future_payments(self):
        self.attach()
        self.sql('UPDATE warehouse_invoices SET supplier_invoice_id=NULL WHERE id=%s', (self.warehouse,))
        before = self.sql('SELECT count(*) FROM project_payments')
        with self.assertRaises(HTTPException):
            self.execute(self.body(), policy=self.pair)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before)

    def test_attached_warehouse_is_not_an_independent_payment_root(self):
        self.attach()
        def warehouse_policy(cur, actor_id, company_id, command):
            return self.pair(cur, actor_id, company_id, {**command, 'documentId': self.invoice})
        body = {**self.body(), 'documentKind': 'warehouse', 'documentId': self.warehouse}
        with self.assertRaises(HTTPException) as error:
            self.execute(body, policy=warehouse_policy)
        self.assertEqual(error.exception.status_code, 409)

    def test_cancelled_mirror_and_changed_total_block_new_payments(self):
        self.attach()
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=%s", (self.warehouse,))
        with self.assertRaises(HTTPException):
            self.execute(self.body(), policy=self.pair)
        self.sql("UPDATE warehouse_invoices SET status='Проведена',total_with_vat=201 WHERE id=%s", (self.warehouse,))
        with self.assertRaises(HTTPException):
            self.execute(self.body(), policy=self.pair)

    def test_cancelled_attached_group_can_reverse_without_reopening_payment(self):
        from .engine import execute
        from .policy import validate_new_payment
        self.attach()
        self.sql("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s", (self.invoice,))
        self.sql('''UPDATE warehouse_invoices SET status='Аннулирована',
                    accounting_status='Нужно уточнение',items='[{"workPackage":""}]' WHERE id=%s''',
                 (self.warehouse,))
        reverse = {key: value for key, value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal', reversesId=self.advance['operationId'])
        execute(self.main.get_db, self.pair, self.actor, 2, reverse, validate_new=validate_new_payment)
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(20, 'Аннулирован')])
        self.assertEqual(self.sql('SELECT paid_amount,status,accounting_status FROM warehouse_invoices WHERE id=%s',
                                 (self.warehouse,)), [(20, 'Аннулирована', 'Нужно уточнение')])
        with self.assertRaises(HTTPException) as error:
            execute(self.main.get_db, self.pair, self.actor, 2, self.body(), validate_new=validate_new_payment)
        self.assertEqual(error.exception.status_code, 409)

    def test_cancelled_attached_reversal_still_rejects_broken_reciprocal_link(self):
        self.attach()
        self.sql('''UPDATE warehouse_invoices SET status='Аннулирована',supplier_invoice_id=NULL
                    WHERE id=%s''', (self.warehouse,))
        before = self.sql('SELECT count(*) FROM supplier_payment_operations')
        reverse = {key: value for key, value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal', reversesId=self.advance['operationId'])
        with self.assertRaises(HTTPException) as error:
            self.execute(reverse, policy=self.pair)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_operations'), before)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(60,)])

    def test_payment_uuid_cannot_be_reused_for_attachment(self):
        body = self.body('10')
        self.execute(body)
        with self.assertRaises(HTTPException) as error:
            self.attach({**self.attachment_body(), 'requestId': body['requestId']})
        self.assertEqual(error.exception.status_code, 409)

    def test_post_attachment_reversal_and_replay(self):
        self.attach()
        body = self.body('15')
        payment = self.execute(body, policy=self.pair)
        reverse = {key: value for key, value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal', reversesId=payment['operationId'])
        result = self.execute(reverse, policy=self.pair)
        self.assertEqual(self.execute(reverse, policy=self.pair), result)
        self.assertEqual(self.execute(body, policy=self.pair), payment)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(60,)])

    def test_business_policy_rejection_does_not_create_baseline(self):
        from .attachments import attach_receipt
        def reject(*args):
            raise HTTPException(409, 'Synthetic provenance not proven')
        with self.assertRaises(HTTPException):
            attach_receipt(self.main.get_db, self.pair, self.actor, 2, self.attachment_body(), validate_new=reject)
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_payment_documents
            WHERE document_kind='warehouse' AND document_id=%s''', (self.warehouse,)), [(0,)])

    def test_baseline_only_invoice_requires_separate_workflow(self):
        from .engine import _baseline
        from psycopg2.extras import RealDictCursor
        base.LedgerTests.setUp(self)
        self.warehouse = self.seed_warehouse()
        self.sql('UPDATE warehouse_invoices SET paid_amount=0 WHERE id=%s', (self.warehouse,))
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (self.warehouse, self.invoice))
        self.pair = self.pair_policy(self.warehouse)
        conn = self.main.get_db()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                context = self.policy(cur, self.actor, 2, self.body())
                _baseline(cur, context['documents'][0], 2)
        finally:
            conn.close()
        with self.assertRaises(HTTPException) as error:
            self.attach()
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_payment_documents
            WHERE document_kind='warehouse' AND document_id=%s''', (self.warehouse,)), [(0,)])

    def test_registered_warehouse_is_not_silently_reused(self):
        from .engine import _baseline
        from psycopg2.extras import RealDictCursor
        conn = self.main.get_db()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                context = self.pair(cur, self.actor, 2, self.body())
                _baseline(cur, context['documents'][1], 2)
        finally:
            conn.close()
        with self.assertRaises(HTTPException) as error:
            self.attach()
        self.assertEqual(error.exception.status_code, 409)

    def test_late_attachment_failure_rolls_back_everything(self):
        import psycopg2
        self.sql('''CREATE FUNCTION synthetic_attachment_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'Synthetic attachment failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_attachment_failure BEFORE UPDATE ON warehouse_invoices
                    FOR EACH ROW EXECUTE FUNCTION synthetic_attachment_failure()''')
        before = self.sql('SELECT count(*) FROM project_payments')
        try:
            with self.assertRaises(psycopg2.Error):
                self.attach()
        finally:
            self.sql('DROP TRIGGER synthetic_attachment_failure ON warehouse_invoices')
            self.sql('DROP FUNCTION synthetic_attachment_failure()')
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(0,)])
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before)
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_payment_documents WHERE document_kind='warehouse' AND document_id=%s''',
                                  (self.warehouse,)), [(0,)])
