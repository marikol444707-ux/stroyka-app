"""Opt-in migration checks on a fresh supply_chain_test_* Unix-only database."""
import os
import unittest
from uuid import uuid4

from .test_payment_ledger_migration import migration_statements


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentLedgerMigrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ..supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                for sql in migration_statements()[1]:
                    cur.execute(sql)
                # Empty downgrade/re-upgrade must be reproducible without losing old tables.
                for sql in migration_statements('downgrade')[1]:
                    cur.execute(sql)
                for sql in migration_statements()[1]:
                    cur.execute(sql)
        finally:
            conn.close()

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor()
        self.supplier = self.fixture['supplierId']
        self.actor = self.fixture['users']['director']['id']
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount) VALUES(2,%s,'Synthetic ledger','',10,2) RETURNING id''', (self.supplier,))
        self.invoice = self.cur.fetchone()[0]

    def document(self, **changes):
        values = dict(company=2, kind='invoice', target=self.invoice, payer=2, supplier=self.supplier,
                      project='Synthetic ledger', package='', amount='10', paid='2')
        values.update(changes)
        self.cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(%(company)s,%(kind)s,%(target)s,%(payer)s,%(supplier)s,%(project)s,%(package)s,%(amount)s,%(paid)s) RETURNING id''', values)
        return self.cur.fetchone()[0]

    def operation(self, *, reverse=None, amount='1', reason='Synthetic test', project='Synthetic ledger', creation_xid=None):
        self.cur.execute('''INSERT INTO project_payments(company_id,project_name,work_package,amount,date,added_by)
            VALUES(2,%s,'',%s,'2026-09-18','Synthetic actor') RETURNING id''',
            (project, '-' + amount if reverse else amount))
        payment = self.cur.fetchone()[0]
        self.cur.execute('''INSERT INTO supplier_payment_operations
            (company_id,request_id,fingerprint,document_kind,document_id,kind,amount,payer_company_id,
             supplier_id,project_payment_id,reverses_id,actor_id,actor_name,reason,payment_date,creation_xid)
            VALUES(2,%s,'test','invoice',%s,%s,%s,2,%s,%s,%s,%s,'Synthetic actor',%s,'2026-09-18',
                   COALESCE(%s::xid8,pg_current_xact_id())) RETURNING id''',
            (str(uuid4()), self.invoice, 'reversal' if reverse else 'payment', amount, self.supplier,
             payment, reverse, self.actor, reason, creation_xid))
        return self.cur.fetchone()[0]

    def impact(self, operation, document, delta='1'):
        self.cur.execute('INSERT INTO supplier_payment_impacts VALUES(%s,%s,2,%s)', (operation, document, delta))

    def rejects(self, action):
        import psycopg2
        self.cur.execute('SAVEPOINT rejected_case')
        try:
            with self.assertRaises(psycopg2.Error):
                action()
        finally:
            self.cur.execute('ROLLBACK TO SAVEPOINT rejected_case')

    def test_valid_payment_and_full_reversal(self):
        document = self.document()
        original = self.operation()
        self.impact(original, document)
        reversal = self.operation(reverse=original)
        self.impact(reversal, document, '-1')
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.cur.execute('SELECT sum(delta) FROM supplier_payment_impacts WHERE operation_id IN (%s,%s)', (original, reversal))
        self.assertEqual(self.cur.fetchone()[0], 0)

    def test_baseline_rejects_forged_identity_or_amount(self):
        for changes in ({'company': 1}, {'target': 2147483647}, {'amount': '11'},
                        {'paid': '1'}, {'project': 'Other'}, {'package': 'Other'}, {'kind': 'warehouse'}):
            with self.subTest(changes=changes):
                self.rejects(lambda: self.document(**changes))

    def test_warehouse_base_fallback_and_location(self):
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,location,
            total_with_vat,total_base,paid_amount) VALUES(2,%s,'','Synthetic ledger',0,10,2) RETURNING id''', (self.supplier,))
        self.document(kind='warehouse', target=self.cur.fetchone()[0])

    def test_impact_requires_exact_signed_amount_and_project(self):
        document = self.document()
        operation = self.operation()
        for delta in ('0', '0.50', '-1', 'NaN'):
            with self.subTest(delta=delta):
                self.rejects(lambda: self.impact(operation, document, delta))
        wrong_project = self.operation(project='Other')
        self.rejects(lambda: self.impact(wrong_project, document))

    def test_operation_without_impact_cannot_finish(self):
        self.document()
        self.operation()
        self.rejects(lambda: self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE'))

    def test_reversal_requires_original_amount_and_reason(self):
        document = self.document()
        operation = self.operation()
        self.impact(operation, document)
        self.rejects(lambda: self.operation(reverse=operation, amount='0.50'))
        self.rejects(lambda: self.operation(reverse=operation, reason=' '))

    def test_history_is_immutable_and_nonempty_downgrade_refused(self):
        document = self.document()
        operation = self.operation()
        self.impact(operation, document)
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        for table in ('supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts'):
            for command in (f'UPDATE {table} SET company_id=company_id', f'DELETE FROM {table}', f'TRUNCATE {table} CASCADE'):
                with self.subTest(command=command):
                    self.rejects(lambda: self.cur.execute(command))
        self.rejects(lambda: [self.cur.execute(sql) for sql in migration_statements('downgrade')[1]])

    def test_baseline_alone_prevents_downgrade(self):
        self.document()
        self.rejects(lambda: [self.cur.execute(sql) for sql in migration_statements('downgrade')[1]])

    def test_cross_company_and_different_payer_impacts_are_rejected(self):
        self.cur.execute("INSERT INTO companies(name) VALUES('Synthetic foreign ledger') RETURNING id")
        foreign_company = self.cur.fetchone()[0]
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount) VALUES(%s,%s,'Synthetic ledger','',10,2) RETURNING id''',
            (foreign_company, self.supplier))
        foreign_doc = self.document(company=foreign_company, target=self.cur.fetchone()[0], payer=foreign_company)
        self.document()
        operation = self.operation()
        self.rejects(lambda: self.impact(operation, foreign_doc))
        self.rejects(lambda: self.cur.execute('INSERT INTO supplier_payment_impacts VALUES(%s,%s,%s,1)',
                                             (operation, foreign_doc, foreign_company)))
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount) VALUES(2,%s,'Synthetic ledger','',10,2) RETURNING id''', (self.supplier,))
        other_payer_doc = self.document(target=self.cur.fetchone()[0], payer=foreign_company)
        self.rejects(lambda: self.impact(operation, other_payer_doc))

    def second_document(self):
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount) VALUES(2,%s,'Synthetic ledger','',10,2) RETURNING id''', (self.supplier,))
        return self.document(target=self.cur.fetchone()[0])

    def test_committed_operation_cannot_gain_another_impact(self):
        document = self.document()
        extra_document = self.second_document()
        operation = self.operation()
        self.impact(operation, document)
        self.conn.commit()
        self.rejects(lambda: self.impact(operation, extra_document))
        self.cur.execute('SELECT count(*) FROM supplier_payment_impacts WHERE operation_id=%s', (operation,))
        self.assertEqual(self.cur.fetchone()[0], 1)

    def test_committed_reversal_group_cannot_be_invalidated(self):
        document = self.document()
        extra_document = self.second_document()
        operation = self.operation()
        self.impact(operation, document)
        self.conn.commit()
        reversal = self.operation(reverse=operation)
        self.impact(reversal, document, '-1')
        self.conn.commit()
        self.rejects(lambda: self.impact(operation, extra_document))
        self.rejects(lambda: self.impact(reversal, extra_document, '-1'))

    def test_same_transaction_impacts_across_savepoints_are_allowed(self):
        document = self.document()
        extra_document = self.second_document()
        self.cur.execute('SAVEPOINT operation_creation')
        operation = self.operation()
        self.cur.execute('RELEASE SAVEPOINT operation_creation')
        self.impact(operation, document)
        self.cur.execute('SAVEPOINT second_impact')
        self.impact(operation, extra_document)
        self.cur.execute('RELEASE SAVEPOINT second_impact')
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_creation_transaction_cannot_be_forged_by_insert(self):
        document = self.document()
        operation = self.operation(creation_xid='1')
        self.cur.execute('SELECT creation_xid=pg_current_xact_id() FROM supplier_payment_operations WHERE id=%s', (operation,))
        self.assertTrue(self.cur.fetchone()[0])
        self.impact(operation, document)
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
