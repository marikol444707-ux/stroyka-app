"""Opt-in packaging key protocol exercised through real history-merge HTTP."""
import importlib
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event, Barrier
from types import SimpleNamespace
from unittest.mock import patch
from psycopg2 import errors

from . import history_merge
from . import test_history_merge_server_schema_postgres as server_tests
from ..material_packaging import test_history_lock_postgres as writer_tests
from ..material_packaging.history_lock import PACKAGING_HISTORY_NAMESPACE


FLAG = 'PARTICIPANT_PACKAGING_HISTORY_LOCKS_ENABLED'


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PackagingMergeLockTests(unittest.TestCase):
    sql = server_tests.ServerSchemaMergeTests.sql
    api = server_tests.ServerSchemaMergeTests.api
    pair = server_tests.ServerSchemaMergeTests.pair
    seed = server_tests.ServerSchemaMergeTests.seed
    path = server_tests.ServerSchemaMergeTests.path
    review = server_tests.ServerSchemaMergeTests.review
    confirm = server_tests.ServerSchemaMergeTests.confirm
    prepare = server_tests.ServerSchemaMergeTests.prepare
    insert = server_tests.ServerSchemaMergeTests.insert
    assert_not_applied = server_tests.ServerSchemaMergeTests.assert_not_applied
    wait_for_blocker = server_tests.ServerSchemaMergeTests.wait_for_blocker
    body = writer_tests.PackagingWriterLockTests.body
    save = writer_tests.PackagingWriterLockTests.save

    @classmethod
    def setUpClass(cls):
        server_tests.ServerSchemaMergeTests.setUpClass.__func__(cls)
        cls.migration = importlib.import_module('migrations.versions.0100_packaging_history_guard')
        conn = cls.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur, patch.object(cls.migration, 'op', SimpleNamespace(execute=cur.execute)):
                cls.migration.upgrade()
            conn.commit()
        finally:
            conn.close()
        enabled = patch.dict(os.environ, {FLAG: '1'})
        enabled.start()
        cls.addClassCleanup(enabled.stop)

    @contextmanager
    def paused_confirmation(self, state, plan):
        entered, release = Event(), Event()
        holder = []
        original = history_merge.inventory
        def pause(cur, *args, **kwargs):
            cur.execute('SELECT pg_backend_pid() AS pid')
            holder.append(cur.fetchone()['pid'])
            entered.set()
            if not release.wait(8):
                raise AssertionError('Merge was not released')
            return original(cur, *args, **kwargs)
        with patch.object(history_merge, 'inventory', pause), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.confirm, state['source'], plan)
            try:
                self.assertTrue(entered.wait(5))
                yield holder[0], future
            finally:
                release.set()

    def write(self, state):
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='10s'")
                row = self.insert(cur, 'material_packaging_rules', state)
            conn.commit()
            return row
        finally:
            conn.close()

    def test_source_waits_but_other_company_http_writers_pass(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        original_invoice = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (state['invoice'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.paused_confirmation(state, plan) as (holder, confirmation):
                self.assertEqual(self.sql('''SELECT mode FROM pg_locks
                    WHERE pid=%s AND locktype='relation' AND mode='RowExclusiveLock'
                      AND relation='material_packaging_rules'::regclass''', (holder,)), [('RowExclusiveLock',)])
                shared = self.sql('''SELECT c.relname FROM pg_locks l JOIN pg_class c ON c.oid=l.relation
                    WHERE l.pid=%s AND l.granted AND l.mode='ShareLock' ''', (holder,))
                self.assertEqual({row[0] for row in shared},
                                 server_tests.SERVER_TABLES-{'material_packaging_rules'})
                self.assertEqual(self.sql('''SELECT mode FROM pg_locks WHERE pid=%s AND granted
                    AND locktype='advisory' AND classid=%s::oid AND objid=%s::oid AND objsubid=2''',
                    (holder, PACKAGING_HISTORY_NAMESPACE, state['source'])), [('ExclusiveLock',)])
                writing = pool.submit(self.write, dict(state, company=3))
                self.wait_for_blocker(holder)
                for actor, company, supplier in (
                    ('director', 2, state['target']),
                    ('stranger', 3, state['target']),
                    ('stranger', 3, None),
                ):
                    body = self.body()
                    body['supplierId'] = supplier
                    saved = self.save(body, actor=actor, company=company)
                    self.assertEqual(saved['supplierId'], supplier)
                self.assertFalse(writing.done())
            self.assertTrue(confirmation.result(timeout=10)['ok'])
            row = writing.result(timeout=10)
        self.assertEqual(self.sql('SELECT company_id FROM material_packaging_rules WHERE id=%s', (row,)), [(3,)])
        self.assertEqual(original_invoice, self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (state['invoice'],)))

    def test_uncommitted_source_writer_commit_invalidates_plan_and_rollback_allows_it(self):
        for committed, company in ((True,2), (False,2), (True,3)):
            with self.subTest(committed=committed, company=company):
                state = self.prepare('material_packaging_rules')
                plan = self.review(state['source'], state['target'])
                writer = self.main.get_db()
                try:
                    writer.autocommit = False
                    with writer.cursor() as cur:
                        row_id = self.insert(cur, 'material_packaging_rules', dict(state, company=company))
                        cur.execute('SELECT pg_backend_pid()')
                        blocker = cur.fetchone()[0]
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        confirmation = pool.submit(self.confirm, state['source'], plan,
                                                   expected=409 if committed else 200)
                        try:
                            self.wait_for_blocker(blocker)
                            self.assertEqual(self.sql('''SELECT 1 FROM pg_locks WHERE NOT granted
                                AND locktype='advisory' AND classid=%s::oid AND objid=%s::oid
                                AND mode='ExclusiveLock' ''', (PACKAGING_HISTORY_NAMESPACE, state['source'])), [(1,)])
                        finally:
                            writer.commit() if committed else writer.rollback()
                        result = confirmation.result(timeout=10)
                    if committed:
                        self.assertTrue(result['detail'])
                        if company==2:
                            self.assertIn('изменились', result['detail'])
                        self.assert_not_applied(state, plan)
                        self.assertEqual(self.sql('SELECT content_quantity FROM material_packaging_rules WHERE id=%s', (row_id,)), [(25,)])
                    else:
                        self.assertTrue(result['ok'])
                finally:
                    writer.rollback()
                    writer.close()

    def test_disabled_flag_and_unavailable_guard_keep_the_original_table_lock(self):
        from ..material_packaging.history_lock_schema import GUARD_SQL
        for mode in ('unset', 'disabled', 'missing_guard'):
            with self.subTest(mode=mode), patch.dict(os.environ):
                if mode=='unset':
                    os.environ.pop(FLAG, None)
                elif mode=='disabled':
                    os.environ[FLAG]='0'
                else:
                    self.sql('ALTER TABLE material_packaging_rules DISABLE TRIGGER material_packaging_history_writer_guard')
                try:
                    state = self.prepare('material_packaging_rules')
                    plan = self.review(state['source'], state['target'])
                    with self.paused_confirmation(state, plan) as (holder, confirmation):
                        self.assertEqual(self.sql('''SELECT mode FROM pg_locks WHERE pid=%s
                            AND relation='material_packaging_rules'::regclass AND mode='ShareLock' ''', (holder,)), [('ShareLock',)])
                        body = self.body()
                        body['supplierId'] = None
                        self.save(body, actor='stranger', company=3, expected=409)
                    self.assertTrue(confirmation.result(timeout=10)['ok'])
                finally:
                    if mode=='missing_guard':
                        self.sql(GUARD_SQL)

    def test_source_timeout_keeps_owner_plan_and_audit_unchanged_then_retry_succeeds(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        writer = self.main.get_db()
        try:
            writer.autocommit = False
            with writer.cursor() as cur:
                self.insert(cur, 'material_packaging_rules', state)
            response = self.confirm(state['source'], plan, expected=409)
            self.assertIn('Повторите проверку и объединение', response['detail'])
            self.assert_not_applied(state, plan)
        finally:
            writer.rollback()
            writer.close()
        self.assertTrue(self.confirm(state['source'], plan)['ok'])

    def test_admin_revoked_while_waiting_cannot_apply_the_plan(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        actor_id = self.fixture['users']['admin']['id']
        writer = self.main.get_db()
        try:
            writer.autocommit = False
            with writer.cursor() as cur:
                self.insert(cur, 'material_packaging_rules', state)
                cur.execute('SELECT pg_backend_pid()')
                blocker = cur.fetchone()[0]
            with ThreadPoolExecutor(max_workers=1) as pool:
                confirmation = pool.submit(self.confirm, state['source'], plan, expected=403)
                try:
                    self.wait_for_blocker(blocker)
                    self.sql('UPDATE users SET active=FALSE WHERE id=%s', (actor_id,))
                finally:
                    writer.rollback()
                confirmation.result(timeout=10)
            self.assert_not_applied(state, plan)
        finally:
            writer.rollback()
            writer.close()
            self.sql('UPDATE users SET active=TRUE WHERE id=%s', (actor_id,))

    def test_source_http_write_times_out_safely_and_can_save_after_merge(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        body = self.body()
        body['supplierId'] = state['source']
        with self.paused_confirmation(state, plan) as (_, confirmation):
            self.save(body, expected=409)
            self.assertEqual(self.sql('SELECT count(*) FROM material_packaging_rules WHERE material_name=%s',
                                      (body['materialName'],)), [(0,)])
        self.assertTrue(confirmation.result(timeout=10)['ok'])
        self.save(body)

    def test_concurrent_confirmation_retries_keep_one_owner_and_one_audit(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        barrier = Barrier(2)
        token = self.main.create_auth_token(self.fixture['users']['admin'], two_factor_passed=True)
        def confirm():
            from fastapi.testclient import TestClient
            with TestClient(self.main.app) as client:
                barrier.wait(timeout=5)
                return client.post(self.path(state['source'])+f"/{plan['id']}/confirm",
                    json=dict(confirmed=True, reason='Проверено юрлицо и принадлежность старых документов'),
                    headers={'Authorization': 'Bearer '+token})
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(confirm) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertIn(200, [result.status_code for result in results])
        self.assertTrue(all(result.status_code in (200,409) for result in results))
        repeated = self.confirm(state['source'], plan)
        for result in results:
            if result.status_code==200:
                self.assertEqual(repeated, result.json())
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_history_merged' AND entity_id=%s",
                                  (state['source'],)), [(1,)])

    def test_failure_after_owner_change_rolls_back_and_releases_packaging_key(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        original = history_merge.apply_pair
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('Synthetic failure after ownership change')
        with patch.object(history_merge, 'apply_pair', fail):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic failure'):
                self.confirm(state['source'], plan)
        self.assert_not_applied(state, plan)
        body = self.body()
        body['supplierId'] = state['source']
        self.save(body)
        self.confirm(state['source'], plan, expected=409)
        fresh = self.review(state['source'], state['target'])
        self.assertTrue(self.confirm(state['source'], fresh)['ok'])

    def test_guard_replacement_waits_until_confirmation_finishes(self):
        from ..material_packaging.history_lock_schema import GUARD_SQL, GUARD_BODY
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        function_sql = GUARD_SQL.split('DROP TRIGGER', 1)[0]
        changed = function_sql.replace(f'pg_advisory_xact_lock_shared({PACKAGING_HISTORY_NAMESPACE},selected_supplier)',
                                      f'pg_advisory_xact_lock_shared({PACKAGING_HISTORY_NAMESPACE+1},selected_supplier)')
        def ddl():
            conn = self.main.get_db()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='10s'")
                    cur.execute(changed)
                return 'completed'
            except errors.InternalError_ as exc:
                if exc.diag.message_primary == 'tuple concurrently updated':
                    return 'retry'
                raise
            finally:
                conn.rollback()
                conn.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.paused_confirmation(state, plan) as (holder, confirmation):
                altering = pool.submit(ddl)
                self.wait_for_blocker(holder)
                self.assertFalse(altering.done())
            self.assertTrue(confirmation.result(timeout=10)['ok'])
            self.assertIn(altering.result(timeout=10), ('completed', 'retry'))
        self.assertEqual(self.sql("SELECT prosrc FROM pg_proc WHERE oid='public.material_packaging_history_writer_guard()'::regprocedure"),
                         [(GUARD_BODY,)])
        # An administrator can retry DDL with a fresh transaction after merge.
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(changed)
        finally:
            conn.rollback()
            conn.close()

    def test_reverse_order_deadlock_rolls_back_and_can_be_retried(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        writer = self.main.get_db()
        try:
            writer.autocommit = False
            with writer.cursor() as cur:
                cur.execute("SET LOCAL deadlock_timeout='5s'; SET LOCAL statement_timeout='8s'")
                row_id = self.insert(cur, 'material_packaging_rules', state)
                cur.execute('SELECT pg_backend_pid()')
                blocker = cur.fetchone()[0]
            with ThreadPoolExecutor(max_workers=1) as pool:
                confirmation = pool.submit(self.confirm, state['source'], plan, expected=409)
                try:
                    self.wait_for_blocker(blocker)
                    with writer.cursor() as cur:
                        cur.execute('''UPDATE company_supplier_links SET version=version
                            WHERE company_id=2 AND supplier_id=%s''', (state['source'],))
                    self.assertIn('Повторите проверку и объединение', confirmation.result(timeout=10)['detail'])
                    self.assert_not_applied(state, plan)
                finally:
                    writer.rollback()
        finally:
            writer.rollback()
            writer.close()
        self.assertEqual(self.sql('SELECT id FROM material_packaging_rules WHERE id=%s', (row_id,)), [])
        self.assertTrue(self.confirm(state['source'], plan)['ok'])
