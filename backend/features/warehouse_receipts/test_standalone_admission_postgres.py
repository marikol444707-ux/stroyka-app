"""Standalone document upload -> receipt -> durable originals, real HTTP/SQL."""
import os
import unittest
from uuid import uuid4

from ..supplier_payments import test_partial_receipt_runtime_postgres as partial
from .test_http_support import upload_receipt_document


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class StandaloneAdmissionPostgresTests(unittest.TestCase):
    setUpClass = classmethod(partial.PartialReceiptRuntimeTests.setUpClass.__func__)
    setUp = partial.PartialReceiptRuntimeTests.setUp
    sql, api = partial.PartialReceiptRuntimeTests.sql, partial.PartialReceiptRuntimeTests.api
    create_offer, check_contract, raw_sources = partial.PartialReceiptRuntimeTests.create_offer, partial.PartialReceiptRuntimeTests.check_contract, partial.PartialReceiptRuntimeTests.raw_sources
    create, pay, ship = partial.PartialReceiptRuntimeTests.create, partial.PartialReceiptRuntimeTests.pay, partial.PartialReceiptRuntimeTests.ship

    def document(self):
        document = dict(documentType='waybill', waybillNumber='STANDALONE-'+uuid4().hex,
            waybillDate='2026-09-28', supplierInn='7701234567', buyerInn='7702222222',
            lines=[dict(materialName=self.fixture['materialName'], unit='шт', quantity=1)])
        original = upload_receipt_document(self, 'director', 2, self.fixture['project'], document)
        return dict(companyId=2, project=self.fixture['project'], location=self.fixture['project'],
            supplierId=self.fixture['supplierId'], supplierName='SUPPLY CHAIN legal supplier',
            supplierInn=document['supplierInn'], number=document['waybillNumber'], date=document['waybillDate'],
            vat='Без НДС', totalBase=100, totalVat=0, totalWithVat=100,
            items=[dict(name=self.fixture['materialName'], unit='шт',quantity=1,price=100,total=100,
                        workPackage=self.fixture['workPackage'])],
            receiptDocument=document, originalUrls=[original], physicalReceiptConfirmed=True,
            newDocumentConfirmed=True, warehouseTarget='object')

    def test_confirmed_original_posts_once_and_retry_retains_saved_invoice(self):
        payload=self.document()
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        saved=self.api('director','POST','/warehouse-invoices',payload)
        self.assertTrue(saved['ok'])
        rows=self.sql('SELECT company_id,photo_url,photo_urls,pages_count FROM warehouse_invoices WHERE id=%s',(saved['id'],))
        import json
        self.assertEqual(rows[0][0],2)
        self.assertEqual(rows[0][1],payload['originalUrls'][0])
        self.assertEqual(json.loads(rows[0][2]),payload['originalUrls'])
        self.assertEqual(rows[0][3],1)
        stock=self.sql('SELECT to_jsonb(t) FROM materials t ORDER BY id')
        self.api('director','POST','/warehouse-invoices',payload,expected=409)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM materials t ORDER BY id'),stock)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)

    def test_payment_invoice_cannot_be_relabelled_as_physical_confirmation(self):
        payload=self.document();payload['receiptDocument']['documentType']='payment_invoice'
        before=self.sql('SELECT to_jsonb(t) FROM warehouse_invoices t ORDER BY id')
        self.api('director','POST','/warehouse-invoices',payload,expected=409)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM warehouse_invoices t ORDER BY id'),before)
