"""HTTP -> actual authority/schema/store -> isolated PG, not session/CSRF proof.

Uses the reviewed bound-contract store fixture and synthetic admitted receipt
relations. A fresh explicit supply_chain_test_* database is required per class.
No runtime receipt-registration endpoint or production app mount is exercised.
"""
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from . import test_allocation_store_postgres as base
from .allocation_access import build_allocation_access
from .allocation_routes import register_supplier_allocation_routes
from .allocation_schema import require_allocation_schema


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationHTTPPostgresTests(unittest.TestCase):
    sql = base.AllocationStorePostgresTests.sql
    api = base.AllocationStorePostgresTests.api
    create_offer = base.AllocationStorePostgresTests.create_offer
    check_contract = base.AllocationStorePostgresTests.check_contract
    seed_receipt = base.AllocationStorePostgresTests.seed_receipt
    pay = base.AllocationStorePostgresTests.pay
    body = base.AllocationStorePostgresTests.body
    snapshot = base.AllocationStorePostgresTests.snapshot

    @classmethod
    def setUpClass(cls):
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        base.AllocationStorePostgresTests.setUp(self)
        access_deps = dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access, has_package_access=self.main.has_package_access)
        app = FastAPI()
        register_supplier_allocation_routes(app, dict(get_db=self.main.get_db,
            get_current_user=lambda: {'id': self.actor},
            authorize_allocation_write=build_allocation_access(access_deps, operation='update'),
            authorize_allocation_read=build_allocation_access(access_deps, operation='read'),
            require_allocation_schema=require_allocation_schema))
        self.http = TestClient(app); self.addCleanup(self.http.close)
        flags = patch.dict(os.environ, SUPPLIER_PAYMENTS_ENABLED='1', SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)
        self.post_path = '/companies/2/supplier-payments/allocations'
        self.get_path = f'/companies/2/supplier-payments/allocation-groups/{self.group}'
        self.headers = {'X-Company-Id': '2', 'X-Company-Mode': 'company'}

    def post(self, body, status=200):
        response = self.http.post(self.post_path, json=body, headers=self.headers)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def get(self, status=200):
        response = self.http.get(self.get_path, headers=self.headers)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def test_save_read_correct_and_exact_historical_replay_never_mutate_finances(self):
        finances = self.snapshot()
        original = self.body(); first = self.post(original)
        projection = self.get()
        self.assertEqual((projection['companyId'], projection['version'], projection['allocated']), (2, 1, '40.00'))
        self.assertEqual(projection['allocations'], original['rows'])
        correction = self.body(version=1, rows=[dict(paymentId=self.second_payment,
            receiptId=self.receipts[1]['id'], amount='20.00')])
        second = self.post(correction)
        self.assertEqual(second['version'], 2)
        self.assertEqual(self.post(original), first)
        self.assertEqual(self.post(correction), second)
        self.assertEqual(self.get()['allocations'], correction['rows'])
        self.assertEqual(self.sql('SELECT version,previous_revision_id FROM supplier_payment_allocation_revisions '
                                 'WHERE group_id=%s ORDER BY version', (self.group,)), [(1, None), (2, first['revisionId'])])
        self.post({**original, 'reason': 'Changed payload'}, status=409)
        self.post(self.body(version=0), status=409)
        self.assertEqual(self.snapshot(), finances)

    def test_revoked_current_membership_denies_saved_replay_and_read(self):
        body = self.body(); saved = self.post(body)
        finances, revisions = self.snapshot(), self.snapshot(allocations=True)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        try:
            self.post(body, status=403); self.get(status=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.assertEqual(self.post(body), saved)
        self.assertEqual(self.snapshot(allocations=True), revisions)
        self.assertEqual(self.snapshot(), finances)

    def test_disabled_trigger_blocks_read_saved_replay_and_new_revision_until_restored(self):
        body = self.body(); saved = self.post(body)
        finances, revisions = self.snapshot(), self.snapshot(allocations=True)
        self.sql('ALTER TABLE supplier_payment_allocation_rows DISABLE TRIGGER allocation_insert')
        try:
            self.post(body, status=503)
            self.post(self.body(version=1), status=503)
            self.get(status=503)
        finally:
            self.sql('ALTER TABLE supplier_payment_allocation_rows ENABLE TRIGGER allocation_insert')
        self.assertEqual(self.post(body), saved)
        self.assertEqual(self.snapshot(allocations=True), revisions)
        self.assertEqual(self.snapshot(), finances)

    def test_cross_company_and_foreign_receipt_rejected_without_any_financial_changes(self):
        finances, revisions = self.snapshot(), self.snapshot(allocations=True)
        response = self.http.get(self.get_path.replace('/companies/2/', '/companies/3/'),
                                 headers={'X-Company-Id': '3', 'X-Company-Mode': 'company'})
        self.assertEqual(response.status_code, 403, response.text)
        self.post(self.body(rows=[dict(paymentId=self.payment, receiptId=9223372036854775807, amount='1.00')]), status=409)
        self.assertEqual(self.snapshot(allocations=True), revisions)
        self.assertEqual(self.snapshot(), finances)

    def test_revoked_membership_is_denied_even_when_allocation_group_table_is_missing(self):
        body = self.body(); self.post(body)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.sql('ALTER TABLE supplier_payment_allocation_groups RENAME TO synthetic_missing_allocation_groups')
        try:
            self.post(body, status=403); self.get(status=403)
        finally:
            self.sql('ALTER TABLE synthetic_missing_allocation_groups RENAME TO supplier_payment_allocation_groups')
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))

    def test_cancelled_invoice_does_not_hide_historical_replay_or_current_projection(self):
        body = self.body(); saved = self.post(body)
        self.sql("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s", (self.invoice,))
        finances, revisions = self.snapshot(), self.snapshot(allocations=True)
        self.assertEqual(self.post(body), saved)
        self.assertEqual(self.get()['version'], 1)
        self.post(self.body(version=1), status=409)
        self.assertEqual(self.snapshot(allocations=True), revisions)
        self.assertEqual(self.snapshot(), finances)
