"""Existing stock-only main-warehouse receipt requires an owned inventory act.

Real authenticated public API and PostgreSQL; no supplier identity is fabricated
for internal stock. The act is a reviewed original, not a payment document.
"""
import copy
import json
import os
import unittest
from uuid import uuid4

from . import test_document_admission_regression as admission
from .test_http_support import upload_receipt_document


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class InventoryAdmissionPostgresTests(unittest.TestCase):
    setUpClass = classmethod(admission.DocumentAdmissionRegressionTests.setUpClass.__func__)
    setUp = admission.DocumentAdmissionRegressionTests.setUp
    sql = admission.DocumentAdmissionRegressionTests.sql
    api = admission.DocumentAdmissionRegressionTests.api
    create_offer = admission.DocumentAdmissionRegressionTests.create_offer
    check_contract = admission.DocumentAdmissionRegressionTests.check_contract
    raw_sources = admission.DocumentAdmissionRegressionTests.raw_sources
    create = admission.DocumentAdmissionRegressionTests.create
    pay = admission.DocumentAdmissionRegressionTests.pay

    def state(self):
        return {table: self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY to_jsonb(t)::text')
                for table in ('suppliers','warehouse_main','materials','warehouse_invoices',
                              'warehouse_history','supplier_invoices','project_payments',
                              'supplier_payment_operations','supply_deliveries')}

    def act_payload(self):
        name = 'Synthetic owned stock ' + uuid4().hex
        document = dict(documentType='inventory_act', waybillNumber='ACT-'+uuid4().hex,
                        waybillDate='2026-09-28',
                        lines=[dict(materialName=name,quantity=2,unit='шт')])
        original = upload_receipt_document(self, 'director', 2, '', document)
        return dict(companyId=2,location='Основной склад',project='',warehouseTarget='main',
                    inventoryOnly=True,selectedAction='receive_stock_without_supplier',
                    number=document['waybillNumber'],date=document['waybillDate'],
                    receiptDocument=document, originalUrls=[original],
                    physicalReceiptConfirmed=True,newDocumentConfirmed=True,
                    vat='Без НДС',totalBase=200,totalVat=0,totalWithVat=200,
                    # Even a stale true accounting toggle must not create debt.
                    syncSupplierInvoice=True,
                    items=[dict(name=name,unit='шт',quantity=2,price=100,total=200)])

    def reject(self,payload,actor='director',expected=400):
        before=self.state()
        result=self.api(actor,'POST','/warehouse-invoices',payload,expected=expected)
        self.assertEqual(self.state(),before)
        return result

    def test_original_act_adds_owned_stock_once_without_supplier_or_debt(self):
        payload=self.act_payload();before=self.state()
        result=self.api('director','POST','/warehouse-invoices',payload)
        self.assertTrue(result['ok']);self.assertTrue(result['inventoryOnly'])
        self.assertFalse(result['accountingRequired'])
        self.assertEqual(self.sql('SELECT company_id,quantity FROM warehouse_main WHERE name=%s',
                                 (payload['items'][0]['name'],)),[(2,2)])
        invoice=self.sql('''SELECT company_id,supplier_id,supplier_invoice_id,photo_urls,selected_action
                           FROM warehouse_invoices WHERE id=%s''',(result['id'],))[0]
        self.assertEqual(invoice[:3],(2,None,None))
        self.assertEqual(json.loads(invoice[3]),payload['originalUrls'])
        self.assertEqual(invoice[4],'receive_stock_without_supplier')
        after=self.state()
        for table in ('suppliers','supplier_invoices','project_payments','supplier_payment_operations','supply_deliveries','materials'):
            self.assertEqual(after[table],before[table],table)
        self.reject(payload,expected=409)

    def test_no_original_is_not_an_inventory_exception(self):
        payload=self.act_payload();payload['originalUrls']=[]
        self.reject(payload)

    def test_physical_confirmation_is_required_for_inventory_act(self):
        payload=self.act_payload();payload['physicalReceiptConfirmed']=False
        self.reject(payload)

    def test_foreign_original_cannot_back_an_internal_act(self):
        payload=self.act_payload()
        foreign=upload_receipt_document(self,'stranger',3,'',payload['receiptDocument'])
        payload['originalUrls']=[foreign]
        self.reject(payload,expected=403)

    def test_stock_only_act_cannot_be_sent_to_project(self):
        payload=self.act_payload();payload.update(project=self.fixture['project'],location=self.fixture['project'],warehouseTarget='object')
        self.reject(payload)

    def test_foreman_cannot_post_stock_only_main_warehouse_act(self):
        self.reject(self.act_payload(),actor='foreman',expected=403)

    def test_procurement_references_cannot_be_hidden_by_inventory_flag(self):
        payload=self.act_payload()
        for patch in (dict(supplierId=self.fixture['supplierId']),
                      dict(supplierInvoiceId=self.invoice),
                      dict(sourceSupplierInvoiceId=self.invoice),
                      dict(supplyRequestId=self.request_id)):
            with self.subTest(patch=patch):
                self.reject({**copy.deepcopy(payload),**patch})

    def test_act_requires_real_number_date_and_positive_finite_quantity(self):
        payload=self.act_payload()
        changes=[dict(number=''),dict(date=''),dict(date='2026-99-28')]
        for value in (0,-1,'nan','Infinity'):
            changes.append(dict(items=[{**payload['items'][0],'quantity':value}]))
        for patch in changes:
            with self.subTest(patch=patch):
                self.reject({**copy.deepcopy(payload),**patch})
