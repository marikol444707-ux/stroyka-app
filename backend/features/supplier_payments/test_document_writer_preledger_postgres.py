"""Real authenticated legacy document writes with no 0017 ledger relations."""
import os
import unittest

from . import test_document_writer_guards_postgres as guards


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PreledgerDocumentWriterTests(unittest.TestCase):
    sql = guards.DocumentWriterGuardTests.sql
    api = guards.DocumentWriterGuardTests.api
    pair = guards.DocumentWriterGuardTests.pair
    seed_warehouse = guards.DocumentWriterGuardTests.seed_warehouse
    request = guards.DocumentWriterGuardTests.request

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from ..supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        self.assertEqual(self.sql('''SELECT to_regclass('public.supplier_payment_documents'),
            to_regclass('public.supplier_payment_operations'),to_regclass('public.supplier_payment_impacts')'''),
            [(None, None, None)])
        self.pair()

    def test_supplier_put_without_ledger_updates_payment(self):
        self.request('supplier_put', expected=200)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(1,)])

    def test_supplier_delete_without_ledger_cancels_and_unlinks(self):
        self.request('supplier_delete', expected=200)
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (self.invoice,)), [('Аннулирован',)])
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s',
                                 (self.warehouse,)), [(None,)])

    def test_warehouse_accounting_without_ledger_creates_real_expense(self):
        before = self.sql('SELECT count(*) FROM project_payments')[0][0]
        result = self.request('warehouse_put', expected=200)
        self.assertIsNotNone(result['paymentId'])
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s', (result['paymentId'],)), [(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), [(before + 1,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(1,)])

    def test_warehouse_delete_without_ledger_reverses_stock(self):
        before = self.sql('SELECT sum(quantity) FROM materials')[0][0]
        self.request('warehouse_delete', expected=200)
        self.assertEqual(self.sql('SELECT status FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [('Аннулирована',)])
        self.assertEqual(self.sql('SELECT sum(quantity) FROM materials'), [(before - 2,)])
