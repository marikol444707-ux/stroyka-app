"""Legacy binding integration; prepayment without sealed lines remains a release gap.

The blocking test preserves the current safe boundary, not a completed workflow.
All originals, invoices, stock and cash in these tests are disposable fixtures.
"""
import os, unittest
from unittest.mock import patch
from uuid import uuid4
from backend.features.supplier_payments import test_unpaid_receipts_postgres as unpaid
from backend.features.supplier_payments import test_invoice_line_creation_postgres as invoices
from backend.features.supplier_payments.test_cancellations_postgres import migration
from backend.features.supplier_deal_parties.legacy_binding_routes import register_legacy_binding_routes

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyContractChainTests(unittest.TestCase):
    api = unpaid.UnpaidReceiptTests.api
    sql = unpaid.UnpaidReceiptTests.sql
    create_offer = unpaid.UnpaidReceiptTests.create_offer
    check_contract = unpaid.UnpaidReceiptTests.check_contract
    raw_sources = unpaid.UnpaidReceiptTests.raw_sources
    create = unpaid.UnpaidReceiptTests.create
    pay = unpaid.UnpaidReceiptTests.pay
    @classmethod
    def setUpClass(cls):
        unpaid.UnpaidReceiptTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0062_supplier_legacy_contract_binding.py')
        finally:conn.close()
        register_legacy_binding_routes(cls.main.app,cls.main.supplier_deal_dependencies)
    def setUp(self):
        invoices.InvoiceLineCreationPostgresTests.setUp(self)
        flags=patch.dict(os.environ,SUPPLIER_PAYMENTS_ENABLED='1',SUPPLIER_PARTIAL_RECEIPTS_ENABLED='1',SUPPLIER_UNPAID_RECEIPTS_ENABLED='1',OWNED_DELIVERY_SOURCES_ENABLED='1',OWNED_DELIVERY_QUALITY_ENABLED='1')
        flags.start();self.addCleanup(flags.stop)
        self.invoice=self.sql("""INSERT INTO supplier_invoices(company_id,supplier_id,offer_id,request_id,project_name,work_package,status,amount,paid_amount)
            SELECT company_id,supplier_id,id,request_id,%s,%s,'На утверждении',200,0 FROM supplier_offers WHERE id=%s RETURNING id""",(self.fixture['project'],self.fixture['workPackage'],self.offer_id))[0][0]
        self.api('director','POST',f'/supplier-invoices/{self.invoice}/legacy-contract-binding',dict(requestId=str(uuid4()),contractVersionId=self.contract_id,expectedAmount='200.00',reason='Synthetic legacy review',confirmed=True))
        self.api('director','PUT',f'/supplier-invoices/{self.invoice}',{'status':'Утверждён'})
    def test_legacy_postpayment_after_waybill_review(self):
        delivery=self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),shippedQuantity=2,waybillNumber='LEGACY-ALL'))['id']
        accepted=self.api('foreman','PUT',f'/supply-deliveries/{delivery}/receive',dict(receivedQuantity=2,qualityStatus='Принято',receivedBy='Synthetic receiver'))
        self.assertTrue(accepted['invoiceId'])
        token=self.main.create_auth_token(self.fixture['users']['accountant'],two_factor_passed=True)
        upload=self.client.post('/upload-photo',files={'file':('waybill.txt',b'Synthetic waybill: 2 units, 200 total.','text/plain')},data={'context':'warehouse-invoice'},headers={'Authorization':'Bearer '+token,'X-Company-Id':'2','X-Company-Mode':'company'})
        self.assertEqual(upload.status_code,200,upload.text)
        self.api('accountant','PUT',f"/warehouse-invoices/{accepted['invoiceId']}/accounting",{'accountingStatus':'К оплате','photos':[upload.json()['url']]})
        self.pay('200.00')
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_invoice_line_specs WHERE invoice_id=%s',(self.invoice,)),[(0,)])
    def test_legacy_prepayment_without_sealed_lines_still_blocks_shipment(self):
        self.pay('200.00')
        before=self.sql('SELECT count(*) FROM supply_deliveries')
        rejection=self.api('supplier','POST',self.path+'/ship',dict(requestId=str(uuid4()),shippedQuantity=2,waybillNumber='LEGACY-PREPAID'),expected=409)
        self.assertIn('Отгрузка заблокирована',rejection['detail'])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_deliveries'),before)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(200,)])
