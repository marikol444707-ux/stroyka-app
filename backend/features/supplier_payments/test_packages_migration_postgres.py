"""0019 SQL contract in isolated PostgreSQL; runtime adapters remain unregistered."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from .test_attachments_postgres import AttachmentTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackageMigrationTests(unittest.TestCase):
    sql = AttachmentTests.sql
    body = AttachmentTests.body
    execute = AttachmentTests.execute

    @classmethod
    def setUpClass(cls):
        AttachmentTests.setUpClass.__func__(cls)
        cls.old_functions = dict(cls.sql_static('''SELECT proname,prosrc FROM pg_proc
            WHERE pronamespace='public'::regnamespace AND proname IN
            ('supplier_payment_document_guard','supplier_payment_attachment_guard')'''))

    @classmethod
    def sql_static(cls, query):
        return cls.sql(cls, query)

    def migration(self, cur, method='upgrade'):
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0047_supplier_payment_packages.py'
        tree = ast.parse(path.read_text())
        namespace = {'op': SimpleNamespace(execute=cur.execute), '__file__': str(path)}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                                type_ignores=[]), str(path), 'exec'), namespace)
        namespace[method]()

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        self.migration(self.cur)

    def seed_pair(self, package='Основная', paid=0):
        supplier = self.fixture['supplierId']
        project = self.fixture['project']
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount,status) VALUES(2,%s,%s,%s,200,%s,'Утверждён') RETURNING id''',
            (supplier, project, package, paid))
        invoice = self.cur.fetchone()['id']
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(2,%s,%s,%s,200,0,'Принята',%s) RETURNING id''',
            (supplier, project, json.dumps([{'workPackage': package}, {'work_package': package}]), invoice))
        warehouse = self.cur.fetchone()['id']
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, invoice))
        return invoice, warehouse

    def baseline(self, kind, document, package='Основная', paid=0):
        self.cur.execute('''INSERT INTO supplier_payment_documents(company_id,document_kind,document_id,
            payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,%s,%s,2,%s,%s,%s,200,%s) RETURNING id''',
            (kind, document, self.fixture['supplierId'], self.fixture['project'], package, paid))
        return self.cur.fetchone()['id']

    def reject_sql(self, query, params=()):
        self.cur.execute('SAVEPOINT rejected')
        try:
            with self.assertRaises(psycopg2.errors.CheckViolation):
                self.cur.execute(query, params)
        finally:
            self.cur.execute('ROLLBACK TO SAVEPOINT rejected')

    def test_ordinary_same_package_pair_baselines(self):
        invoice, warehouse = self.seed_pair()
        self.baseline('invoice', invoice)
        self.baseline('warehouse', warehouse)
        self.cur.execute('SELECT work_package FROM supplier_payment_documents ORDER BY id')
        self.assertEqual([r['work_package'] for r in self.cur.fetchall()], ['Основная', 'Основная'])

    def test_direct_helper_validates_all_items_without_default_or_trim(self):
        for package in ('', 'Основная', 'Раздел 2'):
            self.cur.execute('SELECT public.supplier_payment_warehouse_package(%s) AS package',
                (json.dumps([{'workPackage': package, 'work_package': package}, {'workPackage': package}]),))
            self.assertEqual(self.cur.fetchone()['package'], package)
        for raw in (None, 'not json', 'null', '{}', '[]', '[null]', '[1]', '[{}]',
                    '[{"workPackage":null}]', '[{"workPackage":12}]', '[{"workPackage":true}]',
                    '[{"workPackage":"A"},{"workPackage":"B"}]',
                    '[{"workPackage":"A","work_package":"B"}]',
                    '[{"workPackage":" Основная"}]', '[{"workPackage":"Основная "}]',
                    '[{"workPackage":"A","workPackage":"B"}]'):
            with self.subTest(raw=raw):
                self.reject_sql('SELECT public.supplier_payment_warehouse_package(%s)', (raw,))

    def test_baseline_cannot_erase_package_or_default_missing_items(self):
        _, warehouse = self.seed_pair()
        self.cur.execute('SAVEPOINT erase')
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.baseline('warehouse', warehouse, '')
        self.cur.execute('ROLLBACK TO SAVEPOINT erase')
        self.cur.execute("UPDATE warehouse_invoices SET items='[{}]' WHERE id=%s", (warehouse,))
        self.cur.execute('SAVEPOINT missing')
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.baseline('warehouse', warehouse)
        self.cur.execute('ROLLBACK TO SAVEPOINT missing')

    def test_nonempty_full_attachment_and_deferred_identity_check(self):
        invoice, warehouse = self.seed_pair(paid=40)
        source = self.baseline('invoice', invoice, paid=40)
        target = self.baseline('warehouse', warehouse)
        self.cur.execute('''INSERT INTO supplier_payment_attachments(company_id,request_id,fingerprint,
            invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(2,%s,'synthetic',%s,%s,40,%s,'Test','Full receipt')''',
            (str(uuid4()), source, target, self.fixture['users']['accountant']['id']))
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=40 WHERE id=%s', (warehouse,))
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.cur.execute('SELECT count(*) AS n FROM supplier_payment_impacts')
        self.assertEqual(self.cur.fetchone()['n'], 0)
        self.reject_sql('UPDATE supplier_payment_documents SET work_package=%s WHERE id=%s', ('Other', source))

    def test_attachment_rechecks_item_package_before_insert(self):
        invoice, warehouse = self.seed_pair()
        source = self.baseline('invoice', invoice)
        target = self.baseline('warehouse', warehouse)
        self.cur.execute('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                         (json.dumps([{'workPackage': 'Other'}]), warehouse))
        self.reject_sql('''INSERT INTO supplier_payment_attachments(company_id,request_id,fingerprint,
            invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(2,%s,'synthetic',%s,%s,0,%s,'Test','Full receipt')''',
            (str(uuid4()), source, target, self.fixture['users']['accountant']['id']))

    def test_deferred_attachment_rejects_package_change_after_insert(self):
        invoice, warehouse = self.seed_pair()
        source = self.baseline('invoice', invoice)
        target = self.baseline('warehouse', warehouse)
        self.cur.execute('''INSERT INTO supplier_payment_attachments(company_id,request_id,fingerprint,
            invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(2,%s,'synthetic',%s,%s,0,%s,'Test','Full receipt')''',
            (str(uuid4()), source, target, self.fixture['users']['accountant']['id']))
        self.cur.execute('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                         (json.dumps([{'workPackage': 'Other'}]), warehouse))
        self.reject_sql('SET CONSTRAINTS ALL IMMEDIATE')

    def test_downgrade_rejects_stale_transaction_snapshot(self):
        self.conn.rollback()
        self.cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        self.cur.execute('SAVEPOINT downgrade')
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.migration(self.cur, 'downgrade')
        self.cur.execute('ROLLBACK TO SAVEPOINT downgrade')

    def test_downgrade_refuses_nonempty_warehouse_baseline(self):
        _, warehouse = self.seed_pair()
        self.baseline('warehouse', warehouse)
        self.cur.execute('SAVEPOINT downgrade')
        with self.assertRaises(psycopg2.Error):
            self.migration(self.cur, 'downgrade')
        self.cur.execute('ROLLBACK TO SAVEPOINT downgrade')
        self.cur.execute('SELECT work_package FROM supplier_payment_documents')
        self.assertEqual(self.cur.fetchone()['work_package'], 'Основная')

    def test_empty_history_unchanged_upgrade_and_exact_repeatable_downgrade(self):
        self.migration(self.cur, 'downgrade')
        _, warehouse = self.seed_pair('Основная')
        record = self.baseline('warehouse', warehouse, '')  # Existing 0017 history.
        self.cur.execute('SELECT to_jsonb(d) AS row FROM supplier_payment_documents d WHERE id=%s', (record,))
        before = self.cur.fetchone()['row']
        for _ in range(2):
            self.migration(self.cur)
            self.cur.execute('SELECT to_jsonb(d) AS row FROM supplier_payment_documents d WHERE id=%s', (record,))
            self.assertEqual(self.cur.fetchone()['row'], before)
            self.reject_sql('UPDATE supplier_payment_documents SET work_package=%s WHERE id=%s', ('Основная', record))
            self.migration(self.cur, 'downgrade')
            self.cur.execute('''SELECT proname,prosrc FROM pg_proc WHERE pronamespace='public'::regnamespace
                AND proname IN ('supplier_payment_document_guard','supplier_payment_attachment_guard')''')
            self.assertEqual({r['proname']: r['prosrc'] for r in self.cur.fetchall()}, self.old_functions)
        self.migration(self.cur, 'downgrade')  # Safe repeat, no DROP failure.


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackageEngineReplayTests(unittest.TestCase):
    """Real transaction engine/0019, explicitly synthetic authorization/policy."""
    sql = AttachmentTests.sql
    body = AttachmentTests.body
    execute = AttachmentTests.execute
    migration = PackageMigrationTests.migration

    @classmethod
    def setUpClass(cls):
        AttachmentTests.setUpClass.__func__(cls)
        instance = cls('runTest')
        conn = cls.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                instance.migration(cur)
        finally:
            conn.close()

    def test_paired_package_payment_replay_preserves_baselines_and_one_expense(self):
        from .test_engine_postgres import LedgerTests
        LedgerTests.setUp(self)
        warehouse = LedgerTests.seed_warehouse(self)
        self.sql("UPDATE supplier_invoices SET work_package='Основная',warehouse_invoice_id=%s WHERE id=%s",
                 (warehouse, self.invoice))
        self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                 (json.dumps([{'workPackage': 'Основная'}]), warehouse))

        def policy(cur, actor, company, command):
            context = LedgerTests.policy(self, cur, actor, company, command)
            cur.execute('SELECT work_package FROM supplier_invoices WHERE id=%s', (self.invoice,))
            context['documents'][0]['workPackage'] = cur.fetchone()['work_package']
            cur.execute('''SELECT *,public.supplier_payment_warehouse_package(items) AS package
                FROM warehouse_invoices WHERE id=%s AND company_id=%s FOR UPDATE''', (warehouse, company))
            row = cur.fetchone()
            context['documents'].append(dict(kind='warehouse', id=row['id'], companyId=company,
                payerCompanyId=company, supplierId=row['supplier_id'], projectName=row['project'],
                workPackage=row['package'], amount=row['total_with_vat'], paidAmount=row['paid_amount']))
            return context

        self.policy = policy
        body = self.body('10')
        before = self.sql('SELECT count(*) FROM project_payments')[0][0]
        first = self.execute(body)
        baseline = self.sql('SELECT * FROM supplier_payment_documents ORDER BY id')
        impacts = self.sql('SELECT * FROM supplier_payment_impacts ORDER BY document_record_id')
        self.assertEqual(self.execute(body), first)
        self.assertEqual(self.sql('SELECT * FROM supplier_payment_documents ORDER BY id'), baseline)
        self.assertEqual(self.sql('SELECT * FROM supplier_payment_impacts ORDER BY document_record_id'), impacts)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), [(before + 1,)])
        self.assertEqual(self.sql('SELECT work_package FROM supplier_payment_documents ORDER BY id'),
                         [('Основная',), ('Основная',)])
