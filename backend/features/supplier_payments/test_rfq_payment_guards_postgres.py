"""RFQ offer recycling must not rewrite registered financial evidence."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import HTTPException

from . import test_accounting_sync_guards_postgres as sync
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class RFQGuardTests(unittest.TestCase):
    setUpClass = classmethod(sync.AccountingSyncGuardTests.setUpClass.__func__)
    sql = sync.AccountingSyncGuardTests.sql
    api = sync.AccountingSyncGuardTests.api
    snapshot = sync.AccountingSyncGuardTests.snapshot

    def setUp(self):
        self.supplier = self.fixture['supplierId']
        self.request = self.sql('''INSERT INTO supply_requests(company_id,project,material_name,
            quantity,unit,status,prorab_confirmed_at,director_approved_at)
            VALUES(2,%s,'Synthetic RFQ',2,'шт','Утверждена',NOW(),NOW()) RETURNING id''',
            (self.fixture['project'],))[0][0]
        self.offer = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,
            status,total_price,price_per_unit,payment_terms)
            VALUES(2,%s,%s,'Отозвано',200,100,'Аванс 100%%') RETURNING id''',
            (self.request, self.supplier))[0][0]
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,
            request_id,project_name,work_package,amount,paid_amount,status)
            VALUES(2,%s,%s,%s,%s,'',200,0,'Аннулирован') RETURNING id''',
            (self.supplier, self.offer, self.request, self.fixture['project']))[0][0]
        self.addCleanup(patch.stopall)
        patch.object(self.main, '_send_email', side_effect=AssertionError('No external email')).start()

    def register(self, cur=None):
        query = '''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'invoice',id,company_id,supplier_id,project_name,'',amount,paid_amount
            FROM supplier_invoices WHERE id=%s'''
        (cur.execute if cur else self.sql)(query, (self.invoice,))

    def request_kp(self, expected=200, actor='director'):
        return self.api(actor, 'POST', f'/supply-requests/{self.request}/request-kp',
                        dict(supplierIds=[self.supplier]), expected=expected)

    def direct(self):
        return self.main.request_kp_from_suppliers(self.request, dict(supplierIds=[self.supplier]),
            x_company_id=None, x_company_mode=None, _current_user=self.fixture['users']['director'])

    def deny_unchanged(self, expected=409, actor='director'):
        before = self.snapshot()
        self.request_kp(expected, actor)
        self.assertEqual(self.snapshot(), before)

    def test_registered_invoice_denies_recycling_even_cancelled_zero_paid(self):
        self.register()
        self.deny_unchanged()

    def test_registered_request_only_invoice_denies_reset_unchanged(self):
        self.sql('UPDATE supplier_invoices SET offer_id=NULL WHERE id=%s', (self.invoice,))
        self.register()
        self.deny_unchanged()

    def test_registered_reverse_warehouse_denies_rejected_offer(self):
        self.sql("UPDATE supplier_offers SET status='Отклонено' WHERE id=%s", (self.offer,))
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,
            total_with_vat,paid_amount,supplier_invoice_id) VALUES(2,%s,%s,200,0,%s) RETURNING id''',
            (self.supplier, self.fixture['project'], self.invoice))[0][0]
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'warehouse',%s,2,%s,%s,'',200,0)''',
            (warehouse, self.supplier, self.fixture['project']))
        self.deny_unchanged()

    def test_all_bound_invoices_checked_not_only_latest(self):
        self.register()
        self.sql('''INSERT INTO supplier_invoices(company_id,offer_id,amount,status)
                    VALUES(2,%s,200,'Утверждён')''', (self.offer,))
        self.deny_unchanged()

    def test_registered_forward_warehouse_reference_denied(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,
            total_with_vat,paid_amount) VALUES(2,%s,%s,200,0) RETURNING id''',
            (self.supplier, self.fixture['project']))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, self.invoice))
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'warehouse',%s,2,%s,%s,'',200,0)''',
            (warehouse, self.supplier, self.fixture['project']))
        self.deny_unchanged()

    def test_foreign_bound_invoice_denied_without_reset(self):
        self.sql('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (self.invoice,))
        self.deny_unchanged()

    def test_foreign_offer_not_reassigned(self):
        self.sql('UPDATE supplier_offers SET company_id=3 WHERE id=%s', (self.offer,))
        self.deny_unchanged()

    def test_auth_precedes_ledger_denial(self):
        self.register()
        self.deny_unchanged(expected=403, actor='stranger')

    def test_unmanaged_offer_recycled(self):
        result = self.request_kp()
        self.assertEqual(result['ids'], [self.offer])
        self.assertEqual(self.sql('SELECT status,total_price,payment_terms FROM supplier_offers WHERE id=%s',
                                 (self.offer,)), [('Ожидает ответа', None, 'Постоплата')])

    def test_ledger_path_has_no_runtime_ddl_in_nested_helpers(self):
        with patch.object(self.main, '_ensure_supply_runtime_columns', side_effect=AssertionError('runtime DDL')), \
             patch.object(self.main, '_ensure_supply_request_recipients_table', side_effect=AssertionError('recipient DDL')), \
             patch.object(self.main, '_ensure_supply_notification_messenger_tables', side_effect=AssertionError('messenger DDL')):
            self.assertTrue(self.direct()['ok'])

    def wait_race(self, mutate, expected):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(1735289201,2)')
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.direct)
                try:
                    waiting = []
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting:
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting, 'Company serialization must precede request row lock/DDL')
                    cur.execute('SELECT id FROM supply_requests WHERE id=%s FOR UPDATE NOWAIT', (self.request,))
                    mutate(cur)
                    conn.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=4)
                    self.assertEqual(error.exception.status_code, expected)
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_registration_during_company_wait_prevents_reset(self):
        self.wait_race(self.register, 409)

    def test_changed_request_company_after_wait_rejected(self):
        self.wait_race(lambda cur: cur.execute('UPDATE supply_requests SET company_id=3 WHERE id=%s', (self.request,)), 409)

    def test_revoked_membership_after_wait_rejected(self):
        actor = self.fixture['users']['director']['id']
        try:
            self.wait_race(lambda cur: cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (actor,)), 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (actor,))

    def test_disabled_user_after_wait_rejected(self):
        actor = self.fixture['users']['director']['id']
        try:
            self.wait_race(lambda cur: cur.execute('UPDATE users SET active=FALSE WHERE id=%s', (actor,)), 403)
        finally:
            self.sql('UPDATE users SET active=TRUE WHERE id=%s', (actor,))


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class RFQPreledgerTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    setUp = RFQGuardTests.setUp
    sql = RFQGuardTests.sql
    api = RFQGuardTests.api
    request_kp = RFQGuardTests.request_kp
    test_unmanaged_offer_recycled = RFQGuardTests.test_unmanaged_offer_recycled
