"""Opt-in authenticated dedupe regressions; a fresh isolated DB per test class."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import psycopg2

from . import test_engine_postgres as ledger
from ..supplier_access import test_postgres_chain as chain


class DedupeFixture:
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api
    ledger_present = True

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        if cls.ledger_present:
            ledger.LedgerTests.setUpClass.__func__(cls)
        else:
            from ..supplier_access.test_postgres_chain_support import build_fixture
            cls.main, cls.fixture, cleanup = build_fixture()
            cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        self.number = 'DEDUPE-' + uuid4().hex
        self.canonical = self.invoice()
        self.duplicate = self.invoice()

    def invoice(self, company=2, **changes):
        row = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,supplier_name,invoice_number,invoice_date,
             project_name,amount,paid_amount,status)
            VALUES(%s,%s,'Synthetic dedupe',%s,'2026-09-18','',200,0,'Новый') RETURNING id''',
            (company, self.fixture['supplierId'], self.number))[0][0]
        for column, value in changes.items():
            self.sql(f'UPDATE supplier_invoices SET {column}=%s WHERE id=%s', (value, row))
        return row

    def warehouse(self, company=2, linked=None):
        return self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,supplier_name,number,date,project,location,
             total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES(%s,%s,'Synthetic dedupe',%s,'2026-09-18','','Основной склад',200,0,'Принята',%s)
            RETURNING id''', (company, self.fixture['supplierId'], self.number, linked))[0][0]

    def register(self, kind, document):
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,
             project_name,work_package,amount,opening_paid)
            VALUES(2,%s,%s,2,%s,%s,'',200,0)''',
            (kind, document, self.fixture['supplierId'], 'Основной склад' if kind == 'warehouse' else ''))

    def snapshot(self):
        tables = ['supplier_invoices', 'warehouse_invoices', 'project_payments', 'warehouse_history']
        if self.ledger_present:
            tables += ['supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts']
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text') for table in tables}

    def dedupe(self, *, actor='director', payload=None, expected=200, company='2'):
        body = {'supplierInvoiceIds': [self.canonical], 'apply': True}
        if payload is not None:
            body = payload
        headers = {'X-Company-Mode': 'company', 'X-Company-Id': company}
        return self.api(actor, 'POST', '/supplier-documents/dedupe', body, expected=expected, **headers)

    def assert_denied_unchanged(self, **kwargs):
        before = self.snapshot()
        self.dedupe(expected=409, **kwargs)
        self.assertEqual(self.snapshot(), before)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DedupeGuardTests(DedupeFixture, unittest.TestCase):
    def test_malformed_seed_never_expands_to_company_wide_apply(self):
        for value in (True, 1.5, 'invalid', 0):
            with self.subTest(value=value):
                before = self.snapshot()
                self.dedupe(payload={'supplierInvoiceIds': [value], 'apply': True}, expected=422)
                self.assertEqual(self.snapshot(), before)

    def test_false_scalar_seed_never_becomes_unfiltered_discovery(self):
        for value in (False, 0, ''):
            with self.subTest(value=value):
                before = self.snapshot()
                self.dedupe(payload={'supplierInvoiceIds': value, 'apply': True}, expected=422)
                self.assertEqual(self.snapshot(), before)

    def test_claimed_company_cannot_replace_selected_company(self):
        self.assert_denied_unchanged(payload={'supplierInvoiceIds': [self.canonical], 'apply': True, 'companyId': 3})

    def test_every_group_is_preflighted_before_first_document_update(self):
        self.number = 'SECOND-' + uuid4().hex
        second = self.invoice()
        self.invoice()
        original = self.main._require_unmanaged_payment_document
        calls = []
        def guard(cur, kind, document, **kwargs):
            cur.execute("SELECT count(*) AS count FROM supplier_invoices WHERE id=ANY(%s) AND status='Аннулирован'",
                        ([self.canonical, self.duplicate, second],))
            self.assertEqual(cur.fetchone()['count'], 0, 'All guards must run before any group writes')
            calls.append((kind, document))
            return original(cur, kind, document, **kwargs)
        with patch.object(self.main, '_require_unmanaged_payment_document', side_effect=guard):
            result = self.dedupe(payload={'supplierInvoiceIds': [self.canonical, second], 'apply': True})
        self.assertEqual(result['annulledRows'], 2)
        self.assertGreaterEqual(len(calls), 4)

    def test_discovery_never_returns_foreign_company_groups(self):
        self.invoice(company=3)
        self.invoice(company=3)
        result = self.dedupe(payload={})
        self.assertTrue(result['groups'])
        self.assertEqual({group['companyId'] for group in result['groups']}, {2})

    def test_explicit_foreign_seed_is_denied_without_changes(self):
        foreign = self.invoice(company=3)
        self.invoice(company=3)
        self.assert_denied_unchanged(payload={'supplierInvoiceIds': [foreign], 'apply': True})

    def test_selected_membership_role_overrides_global_finance_role(self):
        actor = self.fixture['users']['director']['id']
        self.sql("INSERT INTO user_company_roles(user_id,company_id,role,active,is_default) VALUES(%s,3,'прораб',TRUE,FALSE)", (actor,))
        try:
            before = self.snapshot()
            self.dedupe(company='3', expected=403)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3', (actor,))

    def test_selected_finance_role_is_not_blocked_by_global_foreman_role(self):
        actor = self.fixture['users']['foreman']['id']
        self.sql("UPDATE user_company_roles SET role='бухгалтер' WHERE user_id=%s AND company_id=2", (actor,))
        try:
            self.assertEqual(self.dedupe(actor='foreman')['annulledRows'], 1)
        finally:
            self.sql("UPDATE user_company_roles SET role='прораб' WHERE user_id=%s AND company_id=2", (actor,))

    def test_revoked_membership_cannot_use_global_director_role(self):
        actor = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (actor,))
        try:
            before = self.snapshot()
            self.dedupe(expected=403)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (actor,))

    def test_registered_canonical_and_duplicate_reject_even_force_review(self):
        for canonical in (True, False):
            with self.subTest(canonical=canonical):
                self.setUp()
                self.register('invoice', self.canonical if canonical else self.duplicate)
                self.assert_denied_unchanged(payload={'supplierInvoiceIds': [self.canonical], 'apply': True, 'forceReview': True})

    def test_registered_reverse_warehouse_is_not_hidden_by_missing_forward_link(self):
        warehouse = self.warehouse(linked=self.duplicate)
        self.register('warehouse', warehouse)
        self.assert_denied_unchanged()

    def test_affected_reverse_warehouse_other_forward_neighbor_is_checked(self):
        neighbor = self.invoice(invoice_number='OTHER-' + self.number)
        warehouse = self.warehouse(linked=self.duplicate)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, neighbor))
        self.register('invoice', neighbor)
        self.assert_denied_unchanged()

    def test_foreign_reverse_warehouse_is_denied(self):
        self.warehouse(company=3, linked=self.duplicate)
        self.assert_denied_unchanged()

    def test_foreign_invoice_pointing_to_affected_warehouse_is_denied(self):
        neighbor = self.invoice(company=3, invoice_number='FOREIGN-' + self.number)
        warehouse = self.warehouse(linked=self.duplicate)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, neighbor))
        self.assert_denied_unchanged()

    def test_ledger_schema_never_runs_runtime_ddl_and_unmanaged_merge_still_works(self):
        warehouse = self.warehouse(linked=self.duplicate)
        with patch.object(self.main, '_ensure_invoice_document_link_columns', side_effect=AssertionError('runtime DDL')), \
             patch.object(self.main, '_ensure_warehouse_invoice_accounting_columns', side_effect=AssertionError('runtime DDL')):
            result = self.dedupe()
        self.assertEqual(result['annulledRows'], 1)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(self.canonical,)])

    def test_late_failure_rolls_back_canonical_annulment_and_reverse_rewrites(self):
        warehouse = self.warehouse(linked=self.duplicate)
        before = self.snapshot()
        self.sql('''CREATE FUNCTION synthetic_dedupe_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic dedupe failure'; END $$''')
        self.sql(f'''CREATE TRIGGER synthetic_dedupe_failure BEFORE UPDATE ON supplier_invoices
            FOR EACH ROW WHEN (NEW.id={self.duplicate}) EXECUTE FUNCTION synthetic_dedupe_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.dedupe()
        finally:
            self.sql('DROP TRIGGER synthetic_dedupe_failure ON supplier_invoices')
            self.sql('DROP FUNCTION synthetic_dedupe_failure()')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(self.duplicate,)])

    def test_company_lock_precedes_rows_and_groups_are_reread_after_wait(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.dedupe, expected=409)
                try:
                    deadline = time.monotonic() + 3
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting or pending.done():
                            break
                        time.sleep(0.01)
                    self.assertTrue(waiting, 'Dedupe must wait on company before DDL/row locks')
                    cur.execute('SELECT id FROM supplier_invoices WHERE id=ANY(%s) FOR UPDATE NOWAIT', ([self.canonical, self.duplicate],))
                    cur.execute('''INSERT INTO supplier_payment_documents
                        (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                        VALUES(2,'invoice',%s,2,%s,'','',200,0)''', (self.duplicate, self.fixture['supplierId']))
                    conn.commit()
                    pending.result(timeout=5)
                finally:
                    conn.rollback()
        finally:
            conn.close()
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (self.duplicate,)), [('Новый',)])

    def test_user_role_is_refreshed_after_company_lock_wait(self):
        actor = self.fixture['users']['director']['id']
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.dedupe, expected=403)
                try:
                    deadline = time.monotonic() + 3
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting or pending.done():
                            break
                        time.sleep(0.01)
                    self.assertTrue(waiting)
                    cur.execute('UPDATE users SET role=%s WHERE id=%s', (next(iter(self.main.PLATFORM_STAFF_ROLES)), actor))
                    conn.commit()
                    pending.result(timeout=5)
                finally:
                    conn.rollback()
        finally:
            conn.close()
            self.sql("UPDATE users SET role='директор' WHERE id=%s", (actor,))
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (self.duplicate,)), [('Новый',)])
