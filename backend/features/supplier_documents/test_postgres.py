"""Opt-in local-only SQL checks. All fixture tables live in pg_temp."""
import os
import unittest

from fastapi import HTTPException

from .test_routes import FakeApp
from .routes import register_supplier_documents_module


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DOCUMENT_PG_TESTS') == '1', 'local PostgreSQL opt-in')
class SupplierDocumentPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg2
        from backend.db import DB_CONFIG
        if DB_CONFIG.get('host') not in ('localhost', '127.0.0.1', '::1'):
            self.fail('Refusing non-local database')
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.addCleanup(self.conn.close)
        self.conn.autocommit = True
        cur = self.conn.cursor()
        cur.execute('SET search_path TO pg_temp')
        cur.execute('''CREATE TEMP TABLE supplier_documents (
            id SERIAL PRIMARY KEY, supplier_id INTEGER, company_id INTEGER,
            doc_type TEXT, title TEXT, file_url TEXT, status TEXT,
            signed_at DATE, expires_at DATE, notes TEXT, uploaded_by TEXT,
            created_at TIMESTAMP DEFAULT NOW(), archived_at TIMESTAMP)''')
        cur.execute('CREATE TEMP TABLE suppliers (id INTEGER PRIMARY KEY)')
        cur.execute('INSERT INTO suppliers VALUES (5)')
        cur.execute('''INSERT INTO supplier_documents (supplier_id,company_id,title)
                       VALUES (5,12,'Customer A'), (5,99,'Customer B'), (5,NULL,'Unassigned')''')
        cur.close()
        actual = self.conn

        class BorrowedConnection:
            def cursor(self):
                return actual.cursor()

            def commit(self):
                actual.commit()

            def close(self):
                pass  # Fixture cleanup owns the connection and its temporary tables.

        self.app = FakeApp()
        register_supplier_documents_module(self.app, {
            'get_db': BorrowedConnection,
            'get_current_user': lambda: {},
            'current_supplier_ids': lambda cur, user: [5],
            'supplier_related_ids': lambda cur, sid: [sid],
            'resolve_work_company_context': lambda cur, user, *args, **kw: {
                'mode': 'company', 'companyId': user['companyId'], 'role': user['role']},
            'effective_company_actors': lambda user, ctx: [{**user, **ctx}],
        })
        self.user = {'role': 'бухгалтер', 'companyId': 12, 'name': 'Test actor'}

    def test_real_select_excludes_foreign_and_unassigned_rows(self):
        rows = self.app.routes[('GET', '/supplier-documents')](current_user=self.user)
        self.assertEqual([r['title'] for r in rows], ['Customer A'])
        other = self.app.routes[('GET', '/supplier-documents')](
            current_user={**self.user, 'companyId': 99})
        self.assertEqual([r['title'] for r in other], ['Customer B'])

    def test_foreign_archive_fails_and_own_archive_keeps_row(self):
        archive = self.app.routes[('DELETE', '/supplier-documents/{id}')]
        with self.assertRaises(HTTPException):
            archive(id=2, current_user=self.user)
        archive(id=1, current_user=self.user)
        rows = self.app.routes[('GET', '/supplier-documents')](current_user=self.user)
        self.assertEqual(rows, [])
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*),count(archived_at) FROM supplier_documents')
            self.assertEqual(cur.fetchone(), (3, 1))

    def test_create_stores_verified_company_and_actor(self):
        result = self.app.routes[('POST', '/supplier-documents')](
            {'supplierId': 5, 'title': 'New contract', 'uploadedBy': 'Spoof'},
            current_user=self.user)
        with self.conn.cursor() as cur:
            cur.execute('SELECT company_id,uploaded_by FROM supplier_documents WHERE id=%s', (result['id'],))
            self.assertEqual(cur.fetchone(), (12, 'Test actor'))
