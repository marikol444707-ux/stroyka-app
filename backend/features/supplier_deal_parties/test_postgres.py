"""Local-only rehearsal: production SQL against isolated pg_temp tables."""
import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2
from psycopg2 import sql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..company_context.service import resolve_resource_company_actor
from .routes import register_supplier_deal_parties_module
from .test_migration import migration_statements


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS') == '1', 'local PostgreSQL opt-in')
class PartiesPostgresTest(unittest.TestCase):
    def setUp(self):
        from backend.db import DB_CONFIG
        if DB_CONFIG.get('host') not in ('localhost', '127.0.0.1', '::1'):
            self.fail('Refusing non-local database')
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.addCleanup(self.conn.close)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute('SET search_path TO pg_temp')
            cur.execute('''CREATE TEMP TABLE companies (
                id INTEGER PRIMARY KEY, platform_account_id INTEGER, name TEXT,
                short_name TEXT, active BOOLEAN DEFAULT TRUE, plan TEXT DEFAULT 'pro',
                trial_until DATE, plan_expires_at DATE, payment_status TEXT DEFAULT 'active', suspended_at TIMESTAMP)''')
            cur.execute("INSERT INTO companies (id,platform_account_id,name) VALUES (12,7,'A'),(99,7,'B'),(101,8,'Foreign')")
            cur.execute('''CREATE TEMP TABLE user_company_roles (
                id SERIAL PRIMARY KEY, user_id INTEGER, company_id INTEGER, staff_id INTEGER,
                platform_account_id INTEGER, role TEXT, assigned_projects JSONB DEFAULT '[]',
                assigned_packages JSONB DEFAULT '[]', active BOOLEAN DEFAULT TRUE, is_default BOOLEAN DEFAULT FALSE)''')
            cur.execute('''INSERT INTO user_company_roles (user_id,company_id,platform_account_id,role,is_default)
                VALUES (8,12,7,'бухгалтер',TRUE),(8,99,7,'бухгалтер',FALSE),
                       (9,99,7,'бухгалтер',TRUE),(8,101,8,'бухгалтер',FALSE)''')
            cur.execute('''CREATE TEMP TABLE supply_requests (id INTEGER PRIMARY KEY, company_id INTEGER,
                project TEXT, work_package TEXT)''')
            cur.execute("INSERT INTO supply_requests VALUES (20,12,'Object A','Основная')")
            cur.execute('''CREATE TEMP TABLE supplier_offers (id INTEGER PRIMARY KEY, company_id INTEGER,
                request_id INTEGER, supplier_id INTEGER, status TEXT)''')
            cur.execute("INSERT INTO supplier_offers VALUES (40,12,20,5,'Утверждено')")
            for sql in migration_statements('upgrade'):
                cur.execute(sql.replace('public.', 'pg_temp.'))
        actual = self.conn

        class BorrowedConnection:
            @property
            def autocommit(self):
                return actual.autocommit

            @autocommit.setter
            def autocommit(self, value):
                actual.autocommit = value

            def cursor(self, **kw):
                return actual.cursor(**kw)

            def commit(self):
                actual.commit()

            def rollback(self):
                actual.rollback()

            def close(self):
                actual.rollback()
                actual.autocommit = True

        self.user = {'id':8, 'name':'Анна', 'role':'бухгалтер', 'companyId':12, 'platformAccountId':7}
        app = FastAPI()
        self.deps = {
            'get_db': BorrowedConnection, 'get_current_user': lambda: self.user,
            'resolve_resource_company_actor': resolve_resource_company_actor,
            'current_supplier_ids': lambda cur, user: [],
            'require_project_access': lambda actor, project: None,
            'has_package_access': lambda actor, package: True,
            'platform_staff_roles': (), 'client_account_roles': (),
        }
        register_supplier_deal_parties_module(app, self.deps)
        self.client = TestClient(app)

    def put(self, version=0, payer=99):
        return self.client.put('/supplier-offers/40/parties', json={
            'buyerCompanyId':12, 'payerCompanyId':payer, 'expectedVersion':version, 'reason':'Плательщик по договору'})

    def test_versioned_history_and_pagination_preserve_original_owner(self):
        first = self.put()
        self.assertEqual(first.status_code, 200, first.text)
        second = self.put(1, 12)
        self.assertEqual(second.status_code, 200, second.text)
        history = self.client.get('/supplier-offers/40/parties/history?limit=1').json()
        self.assertEqual(history['items'][0]['payerCompanyId'], 12)
        self.assertEqual(history['nextBeforeVersion'], 2)
        older = self.client.get('/supplier-offers/40/parties/history?beforeVersion=2').json()
        self.assertEqual(older['items'][0]['payerCompanyId'], 99)
        self.assertIsNone(older['nextBeforeVersion'])
        with self.conn.cursor() as cur:
            cur.execute('SELECT company_id,supplier_id,request_id FROM supplier_offers WHERE id=40')
            self.assertEqual(cur.fetchone(), (12,5,20))

    def test_payer_membership_does_not_grant_owner_document_access(self):
        self.assertEqual(self.put().status_code, 200)
        self.user = {**self.user, 'id':9, 'companyId':99}
        self.assertEqual(self.client.get('/supplier-offers/40/parties').status_code, 403)

    def test_cross_account_payer_and_stale_write_leave_no_extra_versions(self):
        self.assertEqual(self.put(payer=101).status_code, 403)
        self.assertEqual(self.put().status_code, 200)
        self.assertEqual(self.put().status_code, 409)
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM supplier_deal_parties')
            self.assertEqual(cur.fetchone()[0], 1)

    def test_schema_rejects_cross_supplier_link_and_destructive_downgrade(self):
        self.assertEqual(self.put().status_code, 200)
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                cur.execute('''INSERT INTO supplier_deal_parties
                    (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,
                     version,reason,created_by_id,created_by)
                    VALUES (40,12,20,6,12,12,2,'Invalid identity',8,'Test')''')
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(migration_statements('downgrade')[0].replace('public.', 'pg_temp.'))
            cur.execute('SELECT count(*) FROM supplier_deal_parties')
            self.assertEqual(cur.fetchone()[0], 1)

    def test_concurrent_writers_produce_one_version(self):
        from backend.db import DB_CONFIG
        schema = 'supplier_deal_test_' + uuid.uuid4().hex
        # Only this generated fixture namespace is created/dropped; no application table is changed.
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            with self.conn.cursor() as cur:
                for table in ('companies', 'user_company_roles', 'supply_requests', 'supplier_offers'):
                    cur.execute(sql.SQL('CREATE TABLE {}.{} (LIKE pg_temp.{} INCLUDING ALL)').format(
                        sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
                    cur.execute(sql.SQL('INSERT INTO {}.{} SELECT * FROM pg_temp.{}').format(
                        sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
                for statement in migration_statements('upgrade'):
                    cur.execute(statement.replace('public.', schema + '.'))
            ready = threading.Barrier(2, timeout=10)

            def connection():
                conn = psycopg2.connect(**DB_CONFIG)
                conn.autocommit = True
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                        cur.execute("SET statement_timeout = '10s'")
                    ready.wait()
                    return conn
                except Exception:
                    conn.close()
                    raise

            app = FastAPI()
            register_supplier_deal_parties_module(app, {**self.deps, 'get_db': connection})

            def save():
                with TestClient(app) as client:
                    return client.put('/supplier-offers/40/parties', json={
                        'buyerCompanyId':12, 'payerCompanyId':99, 'expectedVersion':0,
                        'reason':'Concurrent proposal'}).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: save(), range(2)))
            self.assertEqual(sorted(results), [200, 409])
            with self.conn.cursor() as cur:
                cur.execute(sql.SQL('SELECT count(*),max(version) FROM {}.supplier_deal_parties').format(sql.Identifier(schema)))
                self.assertEqual(cur.fetchone(), (1,1))
        finally:
            with self.conn.cursor() as cur:
                cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
