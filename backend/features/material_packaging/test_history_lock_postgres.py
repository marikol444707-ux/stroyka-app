"""Real packaging HTTP writer: transaction scope and supplier lock preparation."""
import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event
from unittest.mock import patch

from ..supplier_access import test_postgres_chain as chain
from .history_lock import PACKAGING_HISTORY_NAMESPACE


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackagingWriterLockTests(unittest.TestCase):
    sql, api = chain.PostgresSupplyChainTests.sql, chain.PostgresSupplyChainTests.api

    @classmethod
    def setUpClass(cls):
        chain.PostgresSupplyChainTests.setUpClass.__func__(cls)
        from .routes import ensure_packaging_schema
        from ..api_error_ownership.migration import _ensure_schema as error_schema
        conn = cls.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                error_schema(cur)
                ensure_packaging_schema(cur)
            conn.commit()
        finally:
            conn.close()

    def body(self):
        return dict(materialName='Synthetic packaging '+uuid.uuid4().hex,
                    documentUnit='меш', baseUnit='кг', contentQuantity=25,
                    supplierId=self.fixture['supplierId'])

    def save(self, body, *, actor='director', company=2, expected=200):
        return self.api(actor, 'POST', '/material-packaging-rules', body, expected=expected,
                        **{'X-Company-Id': str(company), 'X-Company-Mode': 'company'})

    @contextmanager
    def supplier_gate(self, supplier):
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',
                            (PACKAGING_HISTORY_NAMESPACE, supplier))
            yield conn
        finally:
            conn.rollback()
            conn.close()

    def wait_for_writer(self, supplier):
        deadline = time.monotonic()+2
        while time.monotonic() < deadline:
            if self.sql('''SELECT 1 FROM pg_locks WHERE locktype='advisory'
                AND classid=%s::oid AND objid=%s::oid AND objsubid=2
                AND mode='ShareLock' AND NOT granted''', (PACKAGING_HISTORY_NAMESPACE, supplier)):
                return
            time.sleep(0.01)
        self.fail('Packaging HTTP writer did not wait on the supplier key')

    def try_exclusive(self, supplier):
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_xact_lock(%s,%s)',
                            (PACKAGING_HISTORY_NAMESPACE, supplier))
                return cur.fetchone()[0]
        finally:
            conn.rollback()
            conn.close()

    def test_same_supplier_waits_before_write_then_saves_after_release(self):
        body = self.body()
        with self.supplier_gate(body['supplierId']) as gate, ThreadPoolExecutor(max_workers=1) as pool:
            writing = pool.submit(self.save, body)
            try:
                self.wait_for_writer(body['supplierId'])
                self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_name=%s',
                                          (body['materialName'],)), [(0,)])
            finally:
                gate.rollback()
            result = writing.result(timeout=10)
        self.assertEqual(self.sql('SELECT company_id,content_quantity FROM material_packaging_rules WHERE id=%s',
                                  (result['id'],)), [(2,25)])

    def test_other_supplier_and_unscoped_rule_can_save_under_unrelated_gate(self):
        other = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic independent packaging supplier') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)', (other,))
        with self.supplier_gate(self.fixture['supplierId']):
            for supplier in (other, None):
                with self.subTest(supplier=supplier):
                    body = self.body()
                    body['supplierId'] = supplier
                    result = self.save(body, actor='stranger', company=3)
                    self.assertEqual(self.sql('SELECT company_id,supplier_id FROM material_packaging_rules WHERE id=%s',
                                              (result['id'],)), [(3,supplier)])

    def test_shared_key_is_held_through_transaction_and_allows_other_shared_writers(self):
        from . import routes
        body = self.body()
        entered, release = Event(), Event()
        original = routes.material_key
        def pause(name):
            entered.set()
            if not release.wait(8):
                raise AssertionError('Packaging writer was not released')
            return original(name)
        with patch.object(routes, 'material_key', pause), ThreadPoolExecutor(max_workers=1) as pool:
            writing = pool.submit(self.save, body)
            try:
                self.assertTrue(entered.wait(5))
                self.assertFalse(self.try_exclusive(body['supplierId']))
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        cur.execute('SELECT pg_try_advisory_xact_lock_shared(%s,%s)',
                                    (PACKAGING_HISTORY_NAMESPACE, body['supplierId']))
                        self.assertTrue(cur.fetchone()[0])
                finally:
                    conn.rollback()
                    conn.close()
            finally:
                release.set()
            writing.result(timeout=10)
        self.assertTrue(self.try_exclusive(body['supplierId']))

    def test_timeout_returns_retry_without_creating_a_rule(self):
        body = self.body()
        with self.supplier_gate(body['supplierId']):
            result = self.save(body, expected=409)
            self.assertIn('Повторите сохранение', result['detail'])
            self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_name=%s',
                                      (body['materialName'],)), [(0,)])
        self.assertTrue(self.try_exclusive(body['supplierId']))
        self.save(body)

    def test_company_denial_and_internal_error_release_the_key(self):
        from . import routes
        body = self.body()
        self.save(body, company=3, expected=403)
        self.assertTrue(self.try_exclusive(body['supplierId']))
        with patch.object(routes, 'material_key', side_effect=RuntimeError('Synthetic packaging failure')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic packaging failure'):
                self.save(body)
        self.assertTrue(self.try_exclusive(body['supplierId']))
        self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_name=%s',
                                  (body['materialName'],)), [(0,)])

    def test_membership_revoked_during_wait_is_rechecked_before_write(self):
        body = self.body()
        actor = self.fixture['users']['director']['id']
        try:
            with self.supplier_gate(body['supplierId']) as gate, ThreadPoolExecutor(max_workers=1) as pool:
                writing = pool.submit(self.save, body, expected=403)
                try:
                    self.wait_for_writer(body['supplierId'])
                    self.sql("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (actor,))
                finally:
                    gate.rollback()
                writing.result(timeout=10)
        finally:
            self.sql("UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2", (actor,))
        self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_name=%s',
                                  (body['materialName'],)), [(0,)])
        self.assertTrue(self.try_exclusive(body['supplierId']))

    def test_existing_rule_update_keeps_one_exact_company_record(self):
        body = self.body()
        first = self.save(body)
        second = self.save(dict(body, contentQuantity=30))
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(self.sql('''SELECT company_id,supplier_id,content_quantity
            FROM material_packaging_rules WHERE material_name=%s''', (body['materialName'],)),
            [(2,body['supplierId'],30)])

    def test_database_failure_rolls_back_update_and_releases_supplier_key(self):
        from psycopg2.errors import RaiseException
        body = self.body()
        row = self.save(body)
        self.sql('''CREATE FUNCTION synthetic_packaging_failure() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic packaging database failure'; END $$;
            CREATE TRIGGER synthetic_packaging_failure AFTER UPDATE ON material_packaging_rules
            FOR EACH ROW EXECUTE FUNCTION synthetic_packaging_failure()''')
        try:
            with self.assertRaises(RaiseException):
                self.save(dict(body, contentQuantity=77))
        finally:
            self.sql('''DROP TRIGGER synthetic_packaging_failure ON material_packaging_rules;
                DROP FUNCTION synthetic_packaging_failure()''')
        self.assertEqual(self.sql('SELECT content_quantity FROM material_packaging_rules WHERE id=%s',
                                  (row['id'],)), [(25,)])
        self.assertTrue(self.try_exclusive(body['supplierId']))

    def test_independent_http_writers_do_not_hold_bootstrap_ddl_during_the_write(self):
        from . import routes
        from fastapi.testclient import TestClient
        other = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic parallel packaging supplier') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)', (other,))
        barrier = Barrier(2)
        original = routes.material_key
        def pause(name):
            barrier.wait(timeout=5)
            return original(name)
        def save(actor, company, supplier):
            body = self.body()
            body['supplierId'] = supplier
            token = self.main.create_auth_token(self.fixture['users'][actor], two_factor_passed=True)
            with TestClient(self.main.app) as client:
                response = client.post('/material-packaging-rules', json=body, headers={
                    'Authorization': 'Bearer '+token, 'X-Company-Id': str(company), 'X-Company-Mode': 'company'})
                self.assertEqual(response.status_code, 200, response.text)
                return response.json()
        with patch.object(routes, 'material_key', pause), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(save, 'director', 2, self.fixture['supplierId'])
            second = pool.submit(save, 'stranger', 3, other)
            rows = [first.result(timeout=15), second.result(timeout=15)]
        self.assertEqual(len({row['id'] for row in rows}), 2)
