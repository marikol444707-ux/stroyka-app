"""Synthetic real-auth HTTP regressions for legacy document ledger bypasses."""
import json
import os
import unittest
from uuid import uuid4

from . import test_engine_postgres as ledger
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DocumentWriterGuardTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api
    body = ledger.LedgerTests.body
    policy = ledger.LedgerTests.policy
    execute = ledger.LedgerTests.execute
    seed_warehouse = ledger.LedgerTests.seed_warehouse
    pair_policy = ledger.LedgerTests.pair_policy

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        ledger.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def pair(self):
        ledger.LedgerTests.setUp(self)
        self.warehouse = self.seed_warehouse()
        self.sql('UPDATE supplier_invoices SET paid_amount=0,warehouse_invoice_id=%s WHERE id=%s',
                 (self.warehouse, self.invoice))
        name = 'Synthetic guard material ' + str(uuid4())
        self.sql('''INSERT INTO materials(company_id,project,name,unit,quantity,work_package)
                    VALUES(2,%s,%s,'шт',5,'')''', (self.fixture['project'], name))
        self.sql('''UPDATE warehouse_invoices SET paid_amount=0,photo_url='/synthetic-invoice.jpg',items=%s WHERE id=%s''',
                 (json.dumps([dict(name=name, quantity=2, unit='шт', workPackage='')]),
                  self.warehouse))

    def register(self, kind):
        if kind == 'invoice':
            self.sql('''INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                SELECT company_id,'invoice',id,company_id,supplier_id,project_name,COALESCE(work_package,''),amount,paid_amount
                FROM supplier_invoices WHERE id=%s''', (self.invoice,))
        else:
            self.sql('''INSERT INTO supplier_payment_documents
                (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
                SELECT company_id,'warehouse',id,company_id,supplier_id,project,'',total_with_vat,paid_amount
                FROM warehouse_invoices WHERE id=%s''', (self.warehouse,))

    def request(self, route, *, actor='director', expected=409, extra=None):
        requests = {
            'supplier_put': ('PUT', f'/supplier-invoices/{self.invoice}', {'paidAmount': 1, 'status': 'Частично оплачен'}),
            'supplier_delete': ('DELETE', f'/supplier-invoices/{self.invoice}', None),
            'warehouse_put': ('PUT', f'/warehouse-invoices/{self.warehouse}/accounting',
                              {'paymentAmount': 1, 'accountingStatus': 'Частично оплачена'}),
            'warehouse_delete': ('DELETE', f'/warehouse-invoices/{self.warehouse}', None),
        }
        method, path, body = requests[route]
        if extra:
            body = {**(body or {}), **extra}
        return self.api(actor, method, path, body, expected=expected)

    def snapshot(self):
        return {table: self.sql(f'SELECT * FROM {table} ORDER BY id') for table in (
            'supplier_invoices', 'warehouse_invoices', 'project_payments', 'materials',
            'warehouse_main', 'warehouse_history')}

    def assert_denied_unchanged(self, route, **kwargs):
        before = self.snapshot()
        self.request(route, **kwargs)
        self.assertEqual(self.snapshot(), before)

    def test_all_four_routes_reject_direct_registered_document(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                self.register('invoice' if route.startswith('supplier') else 'warehouse')
                self.assert_denied_unchanged(route)

    def test_all_four_routes_reject_only_registered_counterpart(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                self.register('warehouse' if route.startswith('supplier') else 'invoice')
                self.assert_denied_unchanged(route)

    def test_reverse_only_links_cannot_hide_registered_counterpart(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                if route.startswith('supplier'):
                    self.register('warehouse')
                    self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE id=%s', (self.invoice,))
                else:
                    self.register('invoice')
                    self.sql('UPDATE warehouse_invoices SET supplier_invoice_id=NULL WHERE id=%s', (self.warehouse,))
                self.assert_denied_unchanged(route)

    def test_put_cannot_attach_proposed_registered_counterpart(self):
        for route in ('supplier_put', 'warehouse_put'):
            with self.subTest(route=route):
                self.pair()
                self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE id=%s', (self.invoice,))
                self.sql('UPDATE warehouse_invoices SET supplier_invoice_id=NULL WHERE id=%s', (self.warehouse,))
                self.register('warehouse' if route == 'supplier_put' else 'invoice')
                extra = {'warehouseInvoiceId': self.warehouse} if route == 'supplier_put' else {'supplierInvoiceId': self.invoice}
                self.assert_denied_unchanged(route, extra=extra)

    def test_reversed_to_zero_does_not_unlock_legacy_writes(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                policy = self.pair_policy(self.warehouse)
                paid = self.execute(self.body('10'), policy=policy)
                reverse = self.body()
                reverse.pop('amount')
                reverse.update(kind='reversal', reversesId=paid['operationId'])
                self.execute(reverse, policy=policy)
                self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(0,)])
                self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(0,)])
                self.assert_denied_unchanged(route)

    def test_strangers_receive_403_before_ledger_conflict(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                self.register('invoice')
                self.register('warehouse')
                self.assert_denied_unchanged(route, actor='stranger', expected=403)

    def test_cross_company_unlink_cannot_write_unlocked_counterpart(self):
        for route in ('supplier_put', 'warehouse_put'):
            with self.subTest(route=route):
                self.pair()
                table = 'warehouse_invoices' if route == 'supplier_put' else 'supplier_invoices'
                counterpart = self.warehouse if route == 'supplier_put' else self.invoice
                self.sql(f'UPDATE {table} SET company_id=3 WHERE id=%s', (counterpart,))
                extra = {'warehouseInvoiceId': 0} if route == 'supplier_put' else {'supplierInvoiceId': 0}
                self.assert_denied_unchanged(route, extra=extra)

    def test_unmanaged_documents_keep_all_four_legacy_routes(self):
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.pair()
                self.request(route, expected=200)
