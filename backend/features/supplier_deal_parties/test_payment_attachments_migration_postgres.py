"""Opt-in synthetic schema checks for immutable invoice/warehouse attachment."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import uuid4

from . import test_payment_ledger_migration_postgres as ledger_tests


def attachment_statements(direction='upgrade'):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0046_supplier_payment_attachments.py'
    tree = ast.parse(path.read_text())
    statements = []
    namespace = {'op': SimpleNamespace(execute=statements.append)}
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                            type_ignores=[]), str(path), 'exec'), namespace)
    namespace[direction]()
    return statements


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentAttachmentsMigrationTests(unittest.TestCase):
    document = ledger_tests.PaymentLedgerMigrationPostgresTests.document
    operation = ledger_tests.PaymentLedgerMigrationPostgresTests.operation
    impact = ledger_tests.PaymentLedgerMigrationPostgresTests.impact
    rejects = ledger_tests.PaymentLedgerMigrationPostgresTests.rejects
    second_document = ledger_tests.PaymentLedgerMigrationPostgresTests.second_document

    @classmethod
    def setUpClass(cls):
        ledger_tests.PaymentLedgerMigrationPostgresTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                for direction in ('upgrade', 'downgrade', 'upgrade'):
                    for sql in attachment_statements(direction):
                        cur.execute(sql)
        finally:
            conn.close()

    def setUp(self):
        ledger_tests.PaymentLedgerMigrationPostgresTests.setUp(self)
        self.invoice_record = self.document()
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,
            total_with_vat,total_base,paid_amount,supplier_invoice_id)
            VALUES(2,%s,'Synthetic ledger',10,10,0,%s) RETURNING id''', (self.supplier, self.invoice))
        self.warehouse = self.cur.fetchone()[0]
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',
                         (self.warehouse, self.invoice))
        self.warehouse_record = self.document(kind='warehouse', target=self.warehouse, paid='0')

    def attach(self, *, initialize=True, **changes):
        values = dict(company=2, request=str(uuid4()), fingerprint='synthetic', invoice=self.invoice_record,
                      warehouse=self.warehouse_record, paid='2', actor=self.actor, name='Synthetic actor', reason='Attach')
        values.update(changes)
        self.cur.execute('''INSERT INTO supplier_payment_attachments
            (company_id,request_id,fingerprint,invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(%(company)s,%(request)s,%(fingerprint)s,%(invoice)s,%(warehouse)s,%(paid)s,%(actor)s,%(name)s,%(reason)s)
            RETURNING id''', values)
        attachment = self.cur.fetchone()[0]
        if initialize:
            self.cur.execute('''UPDATE warehouse_invoices SET paid_amount=%s WHERE id=(
                SELECT document_id FROM supplier_payment_documents WHERE id=%s)''',
                (values['paid'], values['warehouse']))
        return attachment

    def test_accepts_zero_target_and_invoice_only_history(self):
        operation = self.operation()
        self.impact(operation, self.invoice_record)
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.attach(paid='3')
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_accepts_equal_target_paid(self):
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,total_with_vat,
            paid_amount,supplier_invoice_id) VALUES(2,%s,'Synthetic ledger',10,2,%s) RETURNING id''',
            (self.supplier, self.invoice))
        target = self.cur.fetchone()[0]
        record = self.document(kind='warehouse', target=target, paid='2')
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (target, self.invoice))
        self.attach(warehouse=record)

    def test_scope_kinds_and_evidence_values_fail_closed(self):
        for changes in ({'company': 3}, {'invoice': self.warehouse_record}, {'warehouse': self.invoice_record},
                        {'invoice': 2147483647}, {'paid': '1'}, {'paid': '-1'}, {'paid': 'NaN'},
                        {'reason': ' '}, {'name': ' '}, {'fingerprint': ''}):
            with self.subTest(changes=changes):
                self.rejects(lambda: self.attach(**changes))

    def test_physical_drift_and_nonreciprocal_links_rejected(self):
        cases = (
            ('supplier_invoices', self.invoice, 'company_id=3'),
            ('supplier_invoices', self.invoice, 'amount=11'),
            ('supplier_invoices', self.invoice, "project_name='Other'"),
            ('supplier_invoices', self.invoice, "work_package='Other'"),
            ('supplier_invoices', self.invoice, 'supplier_id=NULL'),
            ('supplier_invoices', self.invoice, 'warehouse_invoice_id=NULL'),
            ('supplier_invoices', self.invoice, 'paid_amount=3'),
            ('supplier_invoices', self.invoice, "status='Аннулирован'"),
            ('warehouse_invoices', self.warehouse, 'company_id=3'),
            ('warehouse_invoices', self.warehouse, 'total_with_vat=11'),
            ('warehouse_invoices', self.warehouse, "project='Other'"),
            ('warehouse_invoices', self.warehouse, 'supplier_id=NULL'),
            ('warehouse_invoices', self.warehouse, 'supplier_invoice_id=NULL'),
            ('warehouse_invoices', self.warehouse, 'paid_amount=1'),
            ('warehouse_invoices', self.warehouse, 'paid_amount=2'),
            ('warehouse_invoices', self.warehouse, "status='Аннулирована'"),
        )
        for table, row_id, change in cases:
            with self.subTest(table=table, change=change):
                self.cur.execute('SAVEPOINT drift')
                self.cur.execute(f'UPDATE {table} SET {change} WHERE id=%s', (row_id,))
                self.rejects(self.attach)
                self.cur.execute('ROLLBACK TO SAVEPOINT drift')

    def test_different_payer_baseline_rejected(self):
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,total_with_vat,
            paid_amount,supplier_invoice_id) VALUES(2,%s,'Synthetic ledger',10,0,%s) RETURNING id''',
            (self.supplier, self.invoice))
        target = self.cur.fetchone()[0]
        record = self.document(kind='warehouse', target=target, paid='0', payer=3)
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (target, self.invoice))
        self.rejects(lambda: self.attach(warehouse=record))

    def test_warehouse_history_and_multi_document_invoice_history_rejected(self):
        operation = self.operation()
        self.impact(operation, self.invoice_record)
        self.impact(operation, self.warehouse_record)
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.rejects(lambda: self.attach(paid='3'))

    def test_unselected_sibling_in_invoice_history_rejected(self):
        sibling = self.second_document()
        operation = self.operation()
        self.impact(operation, self.invoice_record)
        self.impact(operation, sibling)
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.rejects(lambda: self.attach(paid='3'))

    def test_immutable_unique_and_nonempty_downgrade(self):
        self.attach()
        self.rejects(self.attach)
        for sql in ('UPDATE supplier_payment_attachments SET reason=reason',
                    'DELETE FROM supplier_payment_attachments', 'TRUNCATE supplier_payment_attachments'):
            self.rejects(lambda: self.cur.execute(sql))
        self.rejects(lambda: [self.cur.execute(sql) for sql in attachment_statements('downgrade')])

    def test_attachment_rolls_back_with_transaction(self):
        self.cur.execute('SAVEPOINT attachment')
        attachment = self.attach()
        self.cur.execute('ROLLBACK TO SAVEPOINT attachment')
        self.cur.execute('SELECT id FROM supplier_payment_attachments WHERE id=%s', (attachment,))
        self.assertIsNone(self.cur.fetchone())

    def test_attached_warehouse_rejects_new_direct_impacts(self):
        operation = self.operation()
        self.impact(operation, self.invoice_record)
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.attach(paid='3')
        self.rejects(lambda: self.impact(operation, self.warehouse_record))
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_committed_attachment_rejects_direct_warehouse_but_allows_root_payment(self):
        self.attach()
        self.conn.commit()
        operation = self.operation()
        self.impact(operation, self.invoice_record)
        self.rejects(lambda: self.impact(operation, self.warehouse_record))
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=3 WHERE id=%s', (self.warehouse,))
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_wrong_canonical_operation_root_rejected(self):
        sibling = self.second_document()
        self.cur.execute('SELECT document_id FROM supplier_payment_documents WHERE id=%s', (sibling,))
        original_invoice = self.invoice
        self.invoice = self.cur.fetchone()[0]
        operation = self.operation()
        self.invoice = original_invoice
        self.impact(operation, self.invoice_record)
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.rejects(lambda: self.attach(paid='3'))

    def test_commit_requires_physical_mirror_initialization(self):
        self.attach(initialize=False)
        self.rejects(lambda: self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE'))

    def test_commit_rechecks_invoice_paid(self):
        self.attach()
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=3 WHERE id=%s', (self.invoice,))
        self.rejects(lambda: self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE'))

    def test_repeatable_read_snapshot_before_attachment_cannot_commit_warehouse_impact(self):
        from psycopg2.errors import CheckViolation
        self.conn.commit()
        stale = self.main.get_db()
        stale.autocommit = False
        original_cursor = self.cur
        try:
            with stale.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                cursor.execute('SELECT count(*) FROM supplier_payment_attachments WHERE warehouse_record_id=%s',
                               (self.warehouse_record,))
                self.assertEqual(cursor.fetchone()[0], 0)
                self.attach()
                self.conn.commit()
                # The original transaction retains its pre-attachment snapshot.
                cursor.execute('SELECT count(*) FROM supplier_payment_attachments WHERE warehouse_record_id=%s',
                               (self.warehouse_record,))
                self.assertEqual(cursor.fetchone()[0], 0)
                self.cur = cursor
                with self.assertRaises(CheckViolation) as error:
                    operation = self.operation()
                    self.impact(operation, self.invoice_record)
                    self.impact(operation, self.warehouse_record)
                    stale.commit()
                self.assertIn('READ COMMITTED', str(error.exception))
        finally:
            self.cur = original_cursor
            stale.rollback()
            stale.close()
        self.cur.execute('SELECT count(*) FROM supplier_payment_impacts WHERE document_record_id=%s',
                         (self.warehouse_record,))
        self.assertEqual(self.cur.fetchone()[0], 0)

    def test_serializable_impacts_require_read_committed_too(self):
        from psycopg2.errors import CheckViolation
        self.conn.commit()
        self.cur.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        operation = self.operation()
        with self.assertRaises(CheckViolation) as error:
            self.impact(operation, self.invoice_record)
        self.assertIn('READ COMMITTED', str(error.exception))
