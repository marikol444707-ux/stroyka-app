"""Database enforcement for direct SQL writers; no production activation."""
import importlib
import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from . import test_history_lock_postgres as writer_tests
from .schema import ensure_packaging_schema, packaging_schema_ready
from .history_lock import PACKAGING_HISTORY_NAMESPACE


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackagingDatabaseGuardTests(unittest.TestCase):
    sql = writer_tests.PackagingWriterLockTests.sql
    api = writer_tests.PackagingWriterLockTests.api
    body = writer_tests.PackagingWriterLockTests.body
    save = writer_tests.PackagingWriterLockTests.save
    supplier_gate = writer_tests.PackagingWriterLockTests.supplier_gate
    try_exclusive = writer_tests.PackagingWriterLockTests.try_exclusive

    @classmethod
    def setUpClass(cls):
        writer_tests.PackagingWriterLockTests.setUpClass.__func__(cls)
        cls.migration = importlib.import_module('migrations.versions.0100_packaging_history_guard')
        cls.migrate('upgrade')

    @classmethod
    def migrate(cls, direction):
        conn = cls.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur, patch.object(cls.migration, 'op', SimpleNamespace(execute=cur.execute)):
                getattr(cls.migration, direction)()
            conn.commit()
        finally:
            conn.close()

    def insert(self, cur, supplier, *, company=2):
        key = uuid.uuid4().hex
        cur.execute('''INSERT INTO material_packaging_rules
            (company_id,supplier_id,material_key,material_name,document_unit,base_unit,content_quantity)
            VALUES(%s,%s,%s,'Synthetic SQL packaging','меш','кг',25) RETURNING id''',
            (company, supplier, key))
        return cur.fetchone()[0]

    def rule(self, supplier):
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                row = self.insert(cur, supplier)
            conn.commit()
            return row
        finally:
            conn.close()

    def wait_for_blocker(self, blocker):
        deadline = time.monotonic()+2
        while time.monotonic() < deadline:
            if self.sql('SELECT 1 FROM pg_locks WHERE NOT granted AND %s=ANY(pg_blocking_pids(pid))', (blocker,)):
                return
            time.sleep(0.01)
        self.fail('Direct SQL did not wait for the held database lock')

    def test_00_migration_replay_downgrade_and_always_trigger_preserve_rows(self):
        self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules'), [(0,)])
        self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_reviews'), [(0,)])
        self.migrate('downgrade')
        self.sql('DROP TABLE material_packaging_reviews; DROP TABLE material_packaging_rules')
        self.migrate('upgrade')
        self.rule(self.fixture['supplierId'])
        before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id')
        self.migrate('upgrade')
        self.assertEqual(self.sql('''SELECT t.tgenabled,t.tgtype,p.prosecdef,p.proconfig
            FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
            WHERE t.tgrelid='public.material_packaging_rules'::regclass
              AND t.tgname='material_packaging_history_writer_guard' '''),
            [('A',31,False,['search_path=pg_catalog'])])
        self.migrate('downgrade')
        self.assertEqual(self.sql("SELECT to_regprocedure('public.material_packaging_history_writer_guard()')"), [(None,)])
        self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id'))
        self.migrate('upgrade')
        self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id'))

    def test_insert_update_delete_and_supplier_changes_hold_both_keys_until_rollback(self):
        source = self.fixture['supplierId']
        other = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic SQL independent') RETURNING id")[0][0]
        for operation, old, new in (
            ('insert',None,source), ('update',source,source), ('delete',source,None),
            ('update',source,other), ('update',other,source),
            ('update',None,source), ('update',source,None),
        ):
            with self.subTest(operation=operation, old=old, new=new):
                row = None if operation=='insert' else self.rule(old)
                before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row,))
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        if operation=='insert':
                            row = self.insert(cur, new)
                        elif operation=='delete':
                            cur.execute('DELETE FROM material_packaging_rules WHERE id=%s', (row,))
                        else:
                            cur.execute('UPDATE material_packaging_rules SET supplier_id=%s,content_quantity=30 WHERE id=%s',
                                        (new,row))
                    for supplier in {old,new}-{None}:
                        self.assertFalse(self.try_exclusive(supplier))
                finally:
                    conn.rollback()
                    conn.close()
                self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row,)))
                for supplier in {old,new}-{None}:
                    self.assertTrue(self.try_exclusive(supplier))

    def test_direct_sql_waits_for_supplier_even_in_another_company(self):
        supplier = self.fixture['supplierId']
        for operation in ('insert','update','delete'):
            with self.subTest(operation=operation):
                row = None if operation=='insert' else self.rule(supplier)
                before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row,))
                def write():
                    conn = self.main.get_db()
                    try:
                        conn.autocommit = False
                        with conn.cursor() as cur:
                            cur.execute("SET LOCAL statement_timeout='8s'")
                            if operation=='insert':
                                result = self.insert(cur, supplier, company=3)
                            elif operation=='update':
                                cur.execute('UPDATE material_packaging_rules SET content_quantity=30 WHERE id=%s', (row,))
                                result = row
                            else:
                                cur.execute('DELETE FROM material_packaging_rules WHERE id=%s', (row,))
                                result = row
                        conn.commit()
                        return result
                    finally:
                        conn.close()
                with self.supplier_gate(supplier) as gate, ThreadPoolExecutor(max_workers=1) as pool:
                    with gate.cursor() as cur:
                        cur.execute('SELECT pg_backend_pid()')
                        blocker = cur.fetchone()[0]
                    future = pool.submit(write)
                    try:
                        self.wait_for_blocker(blocker)
                        self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row,)))
                    finally:
                        gate.rollback()
                    result = future.result(timeout=10)
                expected = [] if operation=='delete' else [(25 if operation=='insert' else 30,)]
                self.assertEqual(self.sql('SELECT content_quantity FROM material_packaging_rules WHERE id=%s', (result,)), expected)

    def test_copy_and_replica_mode_still_take_the_supplier_key(self):
        supplier = self.fixture['supplierId']
        for replica in (False,True):
            with self.subTest(replica=replica):
                key = uuid.uuid4().hex
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        if replica:
                            # Only the disposable initdb role is used, never production.
                            cur.execute("SET LOCAL session_replication_role='replica'")
                        text = f'2\t{supplier}\t{key}\tSynthetic COPY\tмеш\tкг\t25\n'
                        cur.copy_expert('''COPY material_packaging_rules
                            (company_id,supplier_id,material_key,material_name,document_unit,base_unit,content_quantity)
                            FROM STDIN''', StringIO(text))
                    self.assertFalse(self.try_exclusive(supplier))
                finally:
                    conn.rollback()
                    conn.close()
                self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_key=%s', (key,)), [(0,)])
                self.assertTrue(self.try_exclusive(supplier))

    def test_weak_table_lock_pins_truncate_and_trigger_changes_without_losing_data(self):
        before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id')
        for statement in ('TRUNCATE material_packaging_rules',
                          'ALTER TABLE material_packaging_rules DISABLE TRIGGER material_packaging_history_writer_guard'):
            with self.subTest(statement=statement):
                holder = self.main.get_db()
                try:
                    holder.autocommit = False
                    with holder.cursor() as cur:
                        cur.execute('LOCK TABLE material_packaging_rules IN ROW EXCLUSIVE MODE')
                        cur.execute('SELECT pg_backend_pid()')
                        blocker = cur.fetchone()[0]
                    def ddl():
                        conn = self.main.get_db()
                        try:
                            conn.autocommit = False
                            with conn.cursor() as cur:
                                cur.execute("SET LOCAL statement_timeout='8s'")
                                cur.execute(statement)
                        finally:
                            conn.rollback()
                            conn.close()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(ddl)
                        try:
                            self.wait_for_blocker(blocker)
                            self.assertFalse(future.done())
                        finally:
                            holder.rollback()
                        future.result(timeout=10)
                finally:
                    holder.rollback()
                    holder.close()
                self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id'))
                self.assertEqual(self.sql('''SELECT tgenabled FROM pg_trigger
                    WHERE tgrelid='public.material_packaging_rules'::regclass
                      AND tgname='material_packaging_history_writer_guard' '''), [('A',)])

    def test_http_writer_and_other_supplier_remain_compatible_with_database_guard(self):
        row = self.save(self.body())
        self.assertEqual(self.sql('SELECT company_id FROM material_packaging_rules WHERE id=%s', (row['id'],)), [(2,)])
        other = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic SQL free supplier') RETURNING id")[0][0]
        with self.supplier_gate(self.fixture['supplierId']) as gate:
            with gate.cursor() as cur:
                cur.execute('LOCK TABLE material_packaging_rules IN ROW EXCLUSIVE MODE')
            free = self.rule(other)
            general = self.rule(None)
            # The real HTTP path must also pass: repeated bootstrap DDL used to
            # request a conflicting table lock before reaching the supplier key.
            for supplier in (other, None):
                body = self.body()
                body['supplierId'] = supplier
                saved = self.save(body)
                self.assertEqual(saved['supplierId'], supplier)
        self.assertEqual(self.sql('SELECT supplier_id FROM material_packaging_rules WHERE id=ANY(%s) ORDER BY id',
                                  ([free,general],)), [(other,),(None,)])

    def test_schema_check_preserves_legacy_bootstrap_and_does_not_mutate_rows(self):
        before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id')
        for statement in (
            'ALTER TABLE material_packaging_reviews DROP COLUMN review_decision',
            'DROP INDEX idx_material_packaging_rule_identity',
            'DROP INDEX idx_material_packaging_reviews_invoice',
            'DROP TABLE material_packaging_reviews',
        ):
            with self.subTest(statement=statement):
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        self.assertTrue(packaging_schema_ready(cur))
                        cur.execute(statement)
                        self.assertFalse(packaging_schema_ready(cur))
                        ensure_packaging_schema(cur)
                        self.assertTrue(packaging_schema_ready(cur))
                        cur.execute('SELECT to_jsonb(r) FROM material_packaging_rules r ORDER BY id')
                        self.assertEqual(before, cur.fetchall())
                finally:
                    conn.rollback()
                    conn.close()

    def test_http_deadlock_rolls_back_and_the_same_save_can_be_retried(self):
        body = self.body()
        row = self.save(body)
        before = self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row['id'],))
        holder = self.main.get_db()
        try:
            holder.autocommit = False
            with holder.cursor() as cur:
                # Let the HTTP connection detect the real cycle first. All
                # settings affect only this disposable database transaction.
                cur.execute("SET LOCAL deadlock_timeout='5s'; SET LOCAL statement_timeout='8s'")
                cur.execute('UPDATE material_packaging_rules SET content_quantity=29 WHERE id=%s', (row['id'],))
                cur.execute('SELECT pg_backend_pid()')
                blocker = cur.fetchone()[0]
            body['contentQuantity'] = 30
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.save, body, expected=409)
                try:
                    self.wait_for_blocker(blocker)
                    with holder.cursor() as cur:
                        # HTTP holds a shared supplier key and waits for our row;
                        # upgrading our key now completes the deadlock cycle.
                        cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',
                                    (PACKAGING_HISTORY_NAMESPACE, body['supplierId']))
                    self.assertIn('Повторите сохранение', future.result(timeout=10)['detail'])
                finally:
                    holder.rollback()
        finally:
            holder.rollback()
            holder.close()
        self.assertEqual(before, self.sql('SELECT to_jsonb(r) FROM material_packaging_rules r WHERE id=%s', (row['id'],)))
        self.assertTrue(self.try_exclusive(body['supplierId']))
        saved = self.save(body)
        self.assertEqual(saved['id'], row['id'])
        self.assertEqual(saved['contentQuantity'], 30)
