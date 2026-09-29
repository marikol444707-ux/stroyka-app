"""Caller-owned attachment transaction; synthetic adapters, no runtime activation."""
import os
import unittest

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from . import attachments
from . import test_attachments_postgres as existing


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AttachmentTransactionTests(unittest.TestCase):
    setUpClass = classmethod(existing.AttachmentTests.setUpClass.__func__)
    setUp = existing.AttachmentTests.setUp
    sql = existing.AttachmentTests.sql
    body = existing.AttachmentTests.body
    policy = existing.AttachmentTests.policy
    execute = existing.AttachmentTests.execute
    pair_policy = existing.AttachmentTests.pair_policy
    seed_warehouse = existing.AttachmentTests.seed_warehouse
    attachment_body = existing.AttachmentTests.attachment_body

    def financial_history(self):
        return {table: self.sql(f'SELECT * FROM {table} ORDER BY {order}') for table, order in
                (('project_payments', 'id'), ('supplier_payment_operations', 'id'),
                 ('supplier_payment_impacts', 'operation_id,document_record_id'))}

    def worker(self, cur, body=None, **callbacks):
        return attachments.attach_receipt_in_transaction(
            cur, callbacks.get('authorize', self.pair), self.actor, 2,
            body or self.attachment_body(), validate_new=callbacks.get('validate', lambda *args: None))

    def test_caller_failure_rolls_back_attachment_and_prior_caller_write(self):
        before = self.financial_history()
        original = self.sql('SELECT number,paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,))
        conn = self.main.get_db()
        conn.autocommit = False
        body = self.attachment_body()
        try:
            with self.assertRaisesRegex(RuntimeError, 'Synthetic caller failure'):
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute('UPDATE warehouse_invoices SET number=%s WHERE id=%s',
                                    ('SYNTHETIC-CALLER-WRITE', self.warehouse))
                        self.worker(cur, body)
                        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_attachments WHERE request_id=%s',
                                                  (body['requestId'],)), [(0,)])
                        raise RuntimeError('Synthetic caller failure after attachment')
                except Exception:
                    conn.rollback()
                    raise
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT number,paid_amount FROM warehouse_invoices WHERE id=%s',
                                  (self.warehouse,)), original)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_attachments WHERE request_id=%s',
                                  (body['requestId'],)), [(0,)])
        self.assertEqual(self.sql('''SELECT count(*) FROM supplier_payment_documents
            WHERE document_kind='warehouse' AND document_id=%s''', (self.warehouse,)), [(0,)])
        self.assertEqual(self.financial_history(), before)

    def test_caller_commit_and_replay_keep_auth_first_without_new_expense(self):
        before = self.financial_history()
        body = self.attachment_body()
        calls = []
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                def authorize(cursor, *args):
                    self.assertIs(cursor, cur)
                    calls.append('authorize')
                    return self.pair(cursor, *args)
                def validate(cursor, *args):
                    self.assertIs(cursor, cur)
                    calls.append('validate')
                first = self.worker(cur, body, authorize=authorize, validate=validate)
                self.assertEqual(self.worker(cur, body, authorize=authorize, validate=validate), first)
                self.assertEqual(calls, ['authorize', 'validate', 'authorize'])
                def revoked(*args):
                    raise HTTPException(403, 'Synthetic revoked access')
                with self.assertRaises(HTTPException) as error:
                    self.worker(cur, body, authorize=revoked)
                self.assertEqual(error.exception.status_code, 403)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',
                                  (self.warehouse,)), [(60,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_attachments WHERE request_id=%s',
                                  (body['requestId'],)), [(1,)])
        self.assertEqual(self.financial_history(), before)

    def test_worker_policy_failure_leaves_rollback_to_caller(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('UPDATE warehouse_invoices SET number=%s WHERE id=%s',
                            ('SYNTHETIC-PENDING', self.warehouse))
                def reject(*args):
                    raise HTTPException(409, 'Synthetic provenance failure')
                with self.assertRaises(HTTPException):
                    self.worker(cur, validate=reject)
                cur.execute('SELECT number FROM warehouse_invoices WHERE id=%s', (self.warehouse,))
                self.assertEqual(cur.fetchone()['number'], 'SYNTHETIC-PENDING')
                self.assertNotEqual(self.sql('SELECT number FROM warehouse_invoices WHERE id=%s',
                                             (self.warehouse,)), [('SYNTHETIC-PENDING',)])
            conn.rollback()
        finally:
            conn.close()

    def test_worker_requires_transaction_and_both_callbacks(self):
        conn = self.main.get_db()
        try:
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                with self.assertRaises(RuntimeError):
                    self.worker(cur)
            conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for callbacks in ({'authorize': None}, {'validate': None}):
                    with self.subTest(callbacks=callbacks), self.assertRaises(TypeError):
                        self.worker(cur, **callbacks)
        finally:
            conn.close()
