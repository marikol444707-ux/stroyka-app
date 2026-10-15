"""Server-discovered relations: real DDL and SQL-level merge/writer races.

These tests cover manifest invalidation and table locks, not every production
writer's authorization or the complete deployed migration history.
"""
import importlib
import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from . import test_history_merge_postgres as merge_tests


EXTRA_TABLES = (
    'material_packaging_rules', 'supplier_material_capability_assertions',
    'supplier_payment_documents', 'supplier_payment_operations',
)
SERVER_TABLES = set('''company_supplier_links file_ownership invite_codes
material_packaging_rules supplier_aliases supplier_catalog supplier_contract_registry
supplier_contract_registry_versions supplier_contract_versions supplier_customer_assignments
supplier_deal_parties supplier_documents supplier_invoice_templates supplier_invoices
supplier_material_capability_assertions supplier_offer_assignments supplier_offers
supplier_payment_documents supplier_payment_operations supplier_subscriptions
supplier_team_invites supplier_team_members supplier_team_operations supply_claims
supply_deliveries supply_history supply_request_recipients supply_requests
warehouse_invoices'''.split())


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ServerSchemaMergeTests(unittest.TestCase):
    sql = merge_tests.SupplierHistoryMergePostgresTests.sql
    api = merge_tests.SupplierHistoryMergePostgresTests.api
    pair = merge_tests.SupplierHistoryMergePostgresTests.pair
    seed = merge_tests.SupplierHistoryMergePostgresTests.seed
    path = merge_tests.SupplierHistoryMergePostgresTests.path
    review = merge_tests.SupplierHistoryMergePostgresTests.review
    confirm = merge_tests.SupplierHistoryMergePostgresTests.confirm

    @classmethod
    def setUpClass(cls):
        merge_tests.SupplierHistoryMergePostgresTests.setUpClass.__func__(cls)
        from ..material_packaging.routes import ensure_packaging_schema
        from ..supply_recommendation_preview.material_capability_schema_contract import CREATE_STEPS
        payment = importlib.import_module('migrations.versions.0045_supplier_payment_ledger')
        conn = cls.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                ensure_packaging_schema(cur)
                for step in CREATE_STEPS:
                    cur.execute(step['sql'])
                with patch.object(payment, 'op', SimpleNamespace(execute=cur.execute)):
                    payment.upgrade()
            conn.commit()
        finally:
            conn.close()

    def prepare(self, table, company=2):
        source, target = self.pair()
        invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,amount,paid_amount,project_name,work_package)
            VALUES(%s,%s,200,50,'Synthetic server schema','') RETURNING id''',
            (company if table.startswith('supplier_payment_') else 2, source))[0][0]
        state = dict(source=source, target=target, invoice=invoice, company=company)
        if table == 'supplier_payment_operations':
            conn = self.main.get_db()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    state['document'] = self.insert_payment_document(cur, state)
                conn.commit()
            finally:
                conn.close()
        elif table == 'supplier_material_capability_assertions':
            # A valid old confirmation can survive a later removal of its account.
            # Append a revocation after review; never bypass the immutable triggers.
            user = self.sql('''INSERT INTO users(name,email,password,role,active)
                VALUES('Synthetic past supplier',%s,'unused','поставщик',TRUE) RETURNING id''',
                (str(uuid.uuid4())+'@local.invalid',))[0][0]
            self.sql("UPDATE suppliers SET user_id=%s,status='Активный' WHERE id=%s", (user, source))
            links = self.sql('SELECT id FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',
                             (company, source))
            state['link'] = links[0][0] if links else self.sql('''INSERT INTO company_supplier_links
                (company_id,platform_account_id,supplier_id) VALUES(%s,1,%s) RETURNING id''',
                (company, source))[0][0]
            state['actor'], state['membership'] = self.sql('''SELECT u.id,r.id FROM users u
                JOIN user_company_roles r ON r.user_id=u.id
                WHERE r.company_id=%s AND r.role='директор' AND r.active LIMIT 1''', (company,))[0]
            state['subject'] = uuid.uuid4().hex * 2
            conn = self.main.get_db()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    state['assertion'] = self.insert_assertion(cur, state, revoke=False)
                conn.commit()
            finally:
                conn.close()
            self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s', (source,))
            if not links:
                self.sql('DELETE FROM company_supplier_links WHERE id=%s', (state['link'],))
        return state

    def insert_payment_document(self, cur, state):
        cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,
             project_name,work_package,amount,opening_paid)
            VALUES(%s,'invoice',%s,%s,%s,'Synthetic server schema','',200,50) RETURNING id''',
            (state['company'], state['invoice'], state['company'], state['source']))
        return cur.fetchone()[0]

    def insert_assertion(self, cur, state, *, revoke=True):
        cur.execute('''INSERT INTO supplier_material_capability_assertions
            (confirmation_version,event_kind,company_id,company_supplier_link_id,supplier_id,
             material_identity_sha256,confirmation_subject_sha256,actor_membership_id,
             actor_user_id,actor_role,source_kind,revokes_assertion_id)
            VALUES(1,%s,%s,%s,%s,%s,%s,%s,%s,'директор','director_manual',%s) RETURNING id''',
            ('revoked' if revoke else 'confirmed', state['company'], state['link'],
             state['source'], 'a'*64, state['subject'], state['membership'], state['actor'],
             state['assertion'] if revoke else None))
        return cur.fetchone()[0]

    def insert(self, cur, table, state):
        if table == 'supplier_payment_documents':
            return self.insert_payment_document(cur, state)
        if table == 'supplier_material_capability_assertions':
            return self.insert_assertion(cur, state)
        if table == 'material_packaging_rules':
            cur.execute('''INSERT INTO material_packaging_rules
                (company_id,supplier_id,material_key,material_name,document_unit,base_unit,content_quantity)
                VALUES(%s,%s,%s,'Synthetic packaging','меш','кг',25) RETURNING id''',
                (state['company'], state['source'], str(uuid.uuid4())))
            return cur.fetchone()[0]
        actor = self.fixture['users']['accountant']['id']
        cur.execute('''INSERT INTO project_payments(company_id,project_name,work_package,amount,note,date,added_by)
            VALUES(%s,'Synthetic server schema','',1,'Synthetic evidence','2026-10-15','Synthetic accountant')
            RETURNING id''', (state['company'],))
        payment = cur.fetchone()[0]
        cur.execute('''INSERT INTO supplier_payment_operations
            (company_id,request_id,fingerprint,document_kind,document_id,kind,amount,
             payer_company_id,supplier_id,project_payment_id,actor_id,actor_name,reason,payment_date)
            VALUES(%s,%s,'synthetic','invoice',%s,'payment',1,%s,%s,%s,%s,
                   'Synthetic accountant','Synthetic evidence','2026-10-15') RETURNING id''',
            (state['company'], str(uuid.uuid4()), state['invoice'], state['company'],
             state['source'], payment, actor))
        operation = cur.fetchone()[0]
        cur.execute('''INSERT INTO supplier_payment_impacts(operation_id,document_record_id,company_id,delta)
            VALUES(%s,%s,%s,1)''', (operation, state['document'], state['company']))
        return operation

    def assert_not_applied(self, state, plan):
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (state['source'],)), [(None,)])
        self.assertEqual(self.sql('SELECT applied_at FROM supplier_history_merge_plans WHERE id=%s', (plan['id'],)), [(None,)])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_history_merged' AND entity_id=%s",
                                  (state['source'],)), [(0,)])

    def wait_for_blocker(self, blocker, relation=None):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            rows = self.sql('''SELECT l.pid FROM pg_locks l
                WHERE NOT l.granted AND %s=ANY(pg_blocking_pids(l.pid))
                  AND (%s::text IS NULL OR l.relation=to_regclass(%s))''',
                (blocker, relation, relation))
            if rows:
                return
            time.sleep(0.01)
        self.fail('Expected a PostgreSQL lock wait, not a timing-based race')

    def test_manifest_matches_the_29_server_discovered_relations(self):
        source, target, _ = self.seed()
        plan = self.review(source, target)
        manifest = self.sql('SELECT manifest FROM supplier_history_merge_plans WHERE id=%s', (plan['id'],))[0][0]
        self.assertEqual(set(manifest['tables']), SERVER_TABLES)

    def test_each_committed_insert_invalidates_the_review_without_changing_originals(self):
        for table in EXTRA_TABLES:
            with self.subTest(table=table):
                state = self.prepare(table)
                plan = self.review(state['source'], state['target'])
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        row_id = self.insert(cur, table, state)
                    conn.commit()
                finally:
                    conn.close()
                original = self.sql('SELECT to_jsonb(t) FROM '+table+' t WHERE id=%s', (row_id,))
                result = self.confirm(state['source'], plan, expected=409)
                self.assertIn('изменились', result['detail'])
                self.assert_not_applied(state, plan)
                self.assertEqual(original, self.sql('SELECT to_jsonb(t) FROM '+table+' t WHERE id=%s', (row_id,)))

    def test_uncommitted_writer_blocks_confirm_and_commit_rejects_stale_plan(self):
        for table in EXTRA_TABLES:
            with self.subTest(table=table):
                state = self.prepare(table)
                plan = self.review(state['source'], state['target'])
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        cur.execute('SELECT pg_backend_pid()')
                        writer = cur.fetchone()[0]
                        self.insert(cur, table, state)
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(self.confirm, state['source'], plan, expected=409)
                        try:
                            self.wait_for_blocker(writer, table)
                        finally:
                            conn.commit()
                        self.assertIn('изменились', future.result(timeout=10)['detail'])
                finally:
                    conn.rollback()
                    conn.close()
                self.assert_not_applied(state, plan)

    def test_rollback_of_each_waiting_writer_allows_the_unchanged_plan(self):
        for table in EXTRA_TABLES:
            with self.subTest(table=table):
                state = self.prepare(table)
                plan = self.review(state['source'], state['target'])
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        cur.execute('SELECT pg_backend_pid()')
                        writer = cur.fetchone()[0]
                        row_id = self.insert(cur, table, state)
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(self.confirm, state['source'], plan)
                        try:
                            self.wait_for_blocker(writer, table)
                        finally:
                            conn.rollback()
                        self.assertTrue(future.result(timeout=10)['ok'])
                finally:
                    conn.rollback()
                    conn.close()
                self.assertEqual(self.sql('SELECT count(*) FROM '+table+' WHERE id=%s', (row_id,)), [(0,)])

    def test_lock_timeout_leaves_owner_plan_and_audit_unapplied(self):
        state = self.prepare('material_packaging_rules')
        plan = self.review(state['source'], state['target'])
        conn = self.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                self.insert(cur, 'material_packaging_rules', state)
            result = self.confirm(state['source'], plan, expected=409)
            self.assertIn('История сейчас изменяется', result['detail'])
            self.assert_not_applied(state, plan)
        finally:
            conn.rollback()
            conn.close()
        self.assertTrue(self.confirm(state['source'], plan)['ok'])

    def test_existing_packaging_rule_change_invalidates_the_plan(self):
        state = self.prepare('material_packaging_rules')
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                row_id = self.insert(cur, 'material_packaging_rules', state)
        finally:
            conn.close()
        plan = self.review(state['source'], state['target'])
        self.sql('UPDATE material_packaging_rules SET content_quantity=30 WHERE id=%s', (row_id,))
        self.confirm(state['source'], plan, expected=409)
        self.assert_not_applied(state, plan)
        self.assertEqual(self.sql('SELECT content_quantity FROM material_packaging_rules WHERE id=%s', (row_id,)), [(30,)])

    def test_foreign_history_without_catalog_link_never_grants_ownership(self):
        for table in EXTRA_TABLES:
            with self.subTest(table=table):
                state = self.prepare(table, company=3)
                conn = self.main.get_db()
                try:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        row_id = self.insert(cur, table, state)
                    conn.commit()
                finally:
                    conn.close()
                self.assertEqual(self.sql('''SELECT count(*) FROM company_supplier_links
                    WHERE supplier_id=%s AND company_id=3''', (state['source'],)), [(0,)])
                before = self.sql('SELECT to_jsonb(t) FROM '+table+' t WHERE id=%s', (row_id,))
                response = self.review(state['source'], state['target'], expected=409)
                self.assertIn('компании-владельца', response['detail'])
                self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (state['source'],)), [(None,)])
                self.assertEqual(before, self.sql('SELECT to_jsonb(t) FROM '+table+' t WHERE id=%s', (row_id,)))

    def test_confirm_holds_all_four_table_locks_until_ownership_is_applied(self):
        from . import history_merge
        original_inventory = history_merge.inventory
        for table in EXTRA_TABLES:
            with self.subTest(table=table):
                state = self.prepare(table)
                plan = self.review(state['source'], state['target'])
                entered, release = Event(), Event()
                holder = []
                def held_inventory(cur, *args, **kwargs):
                    cur.execute('SELECT pg_backend_pid() AS pid')
                    holder.append(cur.fetchone()['pid'])
                    entered.set()
                    if not release.wait(8):
                        raise AssertionError('Confirmation was not released')
                    return original_inventory(cur, *args, **kwargs)
                def write():
                    conn = self.main.get_db()
                    try:
                        conn.autocommit = False
                        with conn.cursor() as cur:
                            cur.execute("SET LOCAL statement_timeout='10s'")
                            row_id = self.insert(cur, table, state)
                        conn.commit()
                        return row_id
                    finally:
                        conn.close()
                with patch.object(history_merge, 'inventory', held_inventory), ThreadPoolExecutor(max_workers=2) as pool:
                    confirmation = pool.submit(self.confirm, state['source'], plan)
                    try:
                        self.assertTrue(entered.wait(5))
                        writing = pool.submit(write)
                        self.wait_for_blocker(holder[0], table)
                        self.assertFalse(writing.done())
                    finally:
                        release.set()
                    self.assertTrue(confirmation.result(timeout=10)['ok'])
                    row_id = writing.result(timeout=10)
                self.assertEqual(self.sql('SELECT count(*) FROM '+table+' WHERE id=%s', (row_id,)), [(1,)])
