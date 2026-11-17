"""Recognized standalone receipt -> accounting/stock, without changing supplier profile."""
import os
import unittest
from backend.features.warehouse_receipts.test_standalone_admission_postgres import StandaloneAdmissionPostgresTests as Receipt

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ScanReceiptPostgresTests(unittest.TestCase):
    setUpClass = classmethod(Receipt.setUpClass.__func__)
    setUp = Receipt.setUp
    api, sql, document = Receipt.api, Receipt.sql, Receipt.document
    create_offer, check_contract, raw_sources = Receipt.create_offer, Receipt.check_contract, Receipt.raw_sources
    create, pay, ship = Receipt.create, Receipt.pay, Receipt.ship

    def test_scan_receipt_does_not_enrich_existing_supplier_from_ocr(self):
        payload=self.document()
        payload.update(sourceType='scan_project_invoice',supplierKpp='770201001')
        self.sql("UPDATE suppliers SET kpp='' WHERE id=%s",(payload['supplierId'],))
        before=self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id')
        saved=self.api('director','POST','/warehouse-invoices',payload)
        self.assertTrue(saved['ok'])
        self.assertEqual(self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id'),before)
        self.assertTrue(saved['supplierInvoiceId'])

    def test_scan_receipt_rejects_supplier_id_from_other_company_without_any_posting(self):
        payload=self.document()
        foreign=self.sql("INSERT INTO suppliers(name,inn) VALUES('Foreign supplier','7709999999') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id) VALUES(3,%s)',(foreign,))
        payload.update(sourceType='scan_project_invoice',supplierId=foreign)
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in ('suppliers','warehouse_invoices','materials','warehouse_history','supplier_invoices')}
        self.api('director','POST','/warehouse-invoices',payload,expected=403)
        for table,rows in before.items():self.assertEqual(self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'),rows,table)

    def test_inconsistent_scan_amounts_cannot_post_stock_or_accounting(self):
        payload=self.document();payload.update(sourceType='scan_project_invoice')
        payload['items'][0].update(price=100,lineTotal=70,total=70)
        before=self.sql('SELECT count(*) FROM warehouse_invoices')
        self.api('director','POST','/warehouse-invoices',payload,expected=422)
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_invoices'),before)
        payload['items'][0].update(lineTotal=100,total=100)
        payload.update(totalWithVat=90,totalBase=90)
        self.api('director','POST','/warehouse-invoices',payload,expected=422)
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_invoices'),before)

    def test_name_only_supplier_remains_unassigned_instead_of_global_name_match(self):
        payload=self.document()
        payload.update(sourceType='scan_project_invoice',supplierId=None,supplierInn='',supplierName='Unreviewed supplier name')
        saved=self.api('director','POST','/warehouse-invoices',payload)
        self.assertTrue(saved['ok'])
        self.assertEqual(self.sql('SELECT supplier_id FROM warehouse_invoices WHERE id=%s',(saved['id'],)),[(None,)])
        self.assertTrue(saved['supplierInvoiceId'])

    def test_selected_owned_supplier_with_conflicting_inn_is_rejected(self):
        payload=self.document();payload.update(sourceType='scan_project_invoice',supplierInn='7709999999')
        before=self.sql('SELECT count(*) FROM warehouse_invoices')
        self.api('director','POST','/warehouse-invoices',payload,expected=409)
        self.assertEqual(self.sql('SELECT count(*) FROM warehouse_invoices'),before)
