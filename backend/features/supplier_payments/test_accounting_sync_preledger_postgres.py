"""Pre-0017 accounting sync remains usable and manual receipts stay atomic."""
import os
import unittest

import psycopg2

from . import test_accounting_sync_guards_postgres as guarded


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AccountingSyncPreledgerTests(unittest.TestCase):
    sql = guarded.AccountingSyncGuardTests.sql
    api = guarded.AccountingSyncGuardTests.api
    payload = guarded.AccountingSyncGuardTests.payload
    snapshot = guarded.AccountingSyncGuardTests.snapshot
    test_unmanaged_manual_receipt_creates_stock_and_accounting_invoice = (
        guarded.AccountingSyncGuardTests.test_unmanaged_manual_receipt_creates_stock_and_accounting_invoice)

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from ..supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        guarded.AccountingSyncGuardTests.setUp(self)
        self.assertEqual(self.sql('''SELECT to_regclass('public.supplier_payment_documents'),
            to_regclass('public.supplier_payment_operations'),to_regclass('public.supplier_payment_impacts')'''),
            [(None, None, None)])

    def test_linked_sync_replay_preserves_all_rows(self):
        result = self.api('director', 'POST', '/warehouse-invoices', self.payload())
        before = self.snapshot()
        replay = self.main._sync_supplier_invoice_from_warehouse(
            result['id'], {}, self.fixture['users']['director'])
        self.assertTrue(replay['alreadyExists'])
        self.assertEqual(replay['id'], result['supplierInvoiceId'])
        self.assertEqual(self.snapshot(), before)

    def test_late_invoice_sql_failure_rolls_back_receipt_stock_and_history(self):
        self.sql('''CREATE FUNCTION synthetic_preledger_invoice_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic late invoice failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_preledger_invoice_failure AFTER INSERT ON supplier_invoices
            FOR EACH ROW EXECUTE FUNCTION synthetic_preledger_invoice_failure()''')
        try:
            before = self.snapshot()
            with self.assertRaises(psycopg2.Error) as error:
                self.main._create_warehouse_invoice_record(
                    self.payload(), self.fixture['users']['director'],
                    x_company_id='2', x_company_mode='company')
            self.assertIn('Synthetic late invoice failure', str(error.exception))
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('DROP TRIGGER synthetic_preledger_invoice_failure ON supplier_invoices')
            self.sql('DROP FUNCTION synthetic_preledger_invoice_failure()')
