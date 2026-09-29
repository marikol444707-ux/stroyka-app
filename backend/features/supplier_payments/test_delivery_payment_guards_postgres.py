"""Real-auth delivery receipt must not repair or mutate ledger-managed documents."""
import os
import unittest
from uuid import uuid4

from . import test_engine_postgres as ledger
from . import test_accounting_sync_guards_postgres as sync_tests
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DeliveryPaymentGuardTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api
    snapshot = sync_tests.AccountingSyncGuardTests.snapshot

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        ledger.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        f = self.fixture
        self.project = 'Synthetic delivery ledger ' + uuid4().hex
        project_id = self.sql("INSERT INTO projects(company_id,name,status) VALUES(2,%s,'В работе') RETURNING id",
                              (self.project,))[0][0]
        self.sql('''INSERT INTO estimates(company_id,project_id,project_name,name,version,sections_json,
            status,is_template,smeta_type,work_package)
            SELECT 2,%s,%s,name,version,sections_json,status,is_template,smeta_type,work_package
            FROM estimates WHERE id=%s''', (project_id, self.project, f['estimateId']))
        self.request_id = self.sql('''INSERT INTO supply_requests(company_id,project,material_name,
            quantity,unit,work_package,status) VALUES(2,%s,%s,2,'шт','Основная','В работе') RETURNING id''',
            (self.project, f['materialName']))[0][0]
        self.offer = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,
            price_per_unit,total_price,status) VALUES(2,%s,%s,100,200,'Выбрано') RETURNING id''',
            (self.request_id, f['supplierId']))[0][0]
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            request_id,offer_id,work_package,amount,paid_amount,status)
            VALUES(2,%s,%s,%s,%s,'Основная',200,200,'Оплачен') RETURNING id''',
            (f['supplierId'], self.project, self.request_id, self.offer))[0][0]
        self.delivery = self.sql('''INSERT INTO supply_deliveries(company_id,request_id,offer_id,supplier_id,
            project,work_package,material_name,planned_quantity,shipped_quantity,unit,price_per_unit,total_price,status)
            VALUES(2,%s,%s,%s,%s,'Основная',%s,2,2,'шт',100,200,'Отгружено') RETURNING id''',
            (self.request_id, self.offer, f['supplierId'], self.project, f['materialName']))[0][0]

    def register_invoice(self):
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'invoice',id,company_id,supplier_id,project_name,work_package,amount,paid_amount
            FROM supplier_invoices WHERE id=%s''', (self.invoice,))

    def register_warehouse(self, warehouse):
        self.sql('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'warehouse',id,company_id,supplier_id,project,'',total_with_vat,COALESCE(paid_amount,0)
            FROM warehouse_invoices WHERE id=%s''', (warehouse,))

    def receive(self, *, expected=200, actor='director'):
        return self.api(actor, 'PUT', f'/supply-deliveries/{self.delivery}/receive',
                        {'receivedQuantity': 2, 'qualityStatus': 'Принято', 'receivedBy': 'Synthetic director'},
                        expected=expected)

    def deny_unchanged(self, **kwargs):
        before = self.snapshot()
        self.receive(expected=409, **kwargs)
        self.assertEqual(self.snapshot(), before)

    def test_registered_source_invoice_blocks_first_receipt_atomically(self):
        self.register_invoice()
        self.deny_unchanged()

    def test_registered_existing_warehouse_blocks_replay_repairs(self):
        warehouse = self.receive()['invoiceId']
        self.register_warehouse(warehouse)
        # A replay would normally restore this link, despite a managed target.
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=NULL WHERE id=%s', (self.invoice,))
        self.deny_unchanged()

    def test_registered_source_invoice_blocks_already_received_repair(self):
        self.receive()
        self.register_invoice()
        self.deny_unchanged()

    def test_foreign_source_invoice_is_not_reassigned_on_receipt(self):
        self.sql('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (self.invoice,))
        self.deny_unchanged()

    def test_foreign_existing_warehouse_is_not_reassigned_on_replay(self):
        warehouse = self.receive()['invoiceId']
        self.sql('UPDATE warehouse_invoices SET company_id=3 WHERE id=%s', (warehouse,))
        self.deny_unchanged()

    def test_stranger_denied_before_ledger_conflict(self):
        self.register_invoice()
        before = self.snapshot()
        self.receive(expected=403, actor='stranger')
        self.assertEqual(self.snapshot(), before)

    def test_inactive_membership_cannot_receive(self):
        actor = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (actor,))
        try:
            before = self.snapshot()
            self.receive(expected=403)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (actor,))

    def test_unmanaged_receipt_and_repeat_preserve_exact_stock(self):
        receipt = self.receive()
        self.assertTrue(receipt['invoiceId'])
        before = self.snapshot()
        replay = self.receive()
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['invoiceId'], receipt['invoiceId'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql('SELECT quantity FROM materials WHERE company_id=2 AND project=%s',
                                 (self.project,)), [(2,)])
