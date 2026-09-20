"""Opt-in ownership migration tests on a dedicated local PostgreSQL database."""
import importlib
import os
import unittest

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class OwnershipPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from backend.features.supplier_access.test_postgres_chain_support import connection_settings, _assert_empty_database
        cls.conn = psycopg2.connect(**connection_settings(os.environ))
        _assert_empty_database(cls.conn, connection_settings(os.environ))
        cls.conn.rollback()
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            cur.execute('CREATE TABLE projects(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, name TEXT, UNIQUE(id,company_id)); CREATE TABLE users(id INTEGER PRIMARY KEY)')
            for table in ('project_documents','project_letters','prescriptions','warranty_defects'):
                cur.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY, project_name TEXT)')
            cur.execute("INSERT INTO projects VALUES (1,1,'Лицей'),(2,2,'Лицей'); INSERT INTO project_documents VALUES(31,'Лицей'),(32,'Лицей')")
            migration = importlib.import_module('migrations.versions.0040_customer_record_owners')
            cur.execute(migration.SCHEMA_SQL)
        cls.conn.autocommit = False

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def tearDown(self):
        self.conn.rollback()

    def test_migration_does_not_guess_legacy_owners(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT company_id,project_id FROM project_documents ORDER BY id')
            self.assertEqual(cur.fetchall(), [(None,None),(None,None)])

    def test_wrong_project_company_pair_is_rejected(self):
        import psycopg2
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.IntegrityError):
                cur.execute('UPDATE project_documents SET company_id=2,project_id=1 WHERE id=31')

    def test_partial_owner_is_rejected(self):
        import psycopg2
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.IntegrityError):
                cur.execute('UPDATE project_documents SET company_id=1 WHERE id=31')

    def test_confirmed_ids_only_and_idempotent(self):
        from backend.features.customer_cabinet.ownership import assign_confirmed_documents
        with self.conn.cursor() as cur:
            for _ in range(2):
                self.assertEqual(assign_confirmed_documents(cur, company_id=1, project_id=1, project_name='Лицей', document_ids=[31]),1)
            cur.execute('SELECT id,company_id,project_id FROM project_documents ORDER BY id')
            self.assertEqual(cur.fetchall(),[(31,1,1),(32,None,None)])

    def test_changed_document_or_parent_aborts_without_writing(self):
        from backend.features.customer_cabinet.ownership import assign_confirmed_documents
        with self.conn.cursor() as cur:
            for changes in ({'company_id':2}, {'project_name':'Другой'}, {'document_ids':[31,999]}):
                args=dict(company_id=1,project_id=1,project_name='Лицей',document_ids=[31,32]); args.update(changes)
                with self.assertRaises(ValueError):
                    assign_confirmed_documents(cur, **args)
                cur.execute('SELECT count(*) FROM project_documents WHERE company_id IS NOT NULL')
                self.assertEqual(cur.fetchone()[0],0)

    def test_conflicting_existing_owner_aborts_entire_selection(self):
        from backend.features.customer_cabinet.ownership import assign_confirmed_documents
        with self.conn.cursor() as cur:
            cur.execute('UPDATE project_documents SET company_id=2,project_id=2 WHERE id=32')
            with self.assertRaises(ValueError):
                assign_confirmed_documents(cur, company_id=1,project_id=1,project_name='Лицей',document_ids=[31,32])
            cur.execute('SELECT company_id FROM project_documents WHERE id=31')
            self.assertIsNone(cur.fetchone()[0])
