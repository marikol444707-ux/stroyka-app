"""Read-only legacy inventory against real, isolated invoice fixtures."""
import json
import os
import unittest
from unittest.mock import patch

from scripts.audit_supplier_legacy_invoices import audit
from . import test_invoice_line_creation_postgres as source


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyAuditTests(unittest.TestCase):
    sql = source.InvoiceLineCreationPostgresTests.sql
    api = source.InvoiceLineCreationPostgresTests.api
    create_offer = source.InvoiceLineCreationPostgresTests.create_offer
    check_contract = source.InvoiceLineCreationPostgresTests.check_contract
    raw_sources = source.InvoiceLineCreationPostgresTests.raw_sources
    create = source.InvoiceLineCreationPostgresTests.create
    setUp = source.InvoiceLineCreationPostgresTests.setUp

    @classmethod
    def setUpClass(cls):
        source.InvoiceLineCreationPostgresTests.setUpClass.__func__(cls)

    def report(self, company=2):
        connection = self.main.get_db()
        try:
            result = audit(connection, company)
            self.assertEqual(connection.get_transaction_status(), 0)
            return result
        finally:
            connection.close()

    def test_sealed_invoice_report_does_not_register_debt(self):
        invoice = self.create()['id']
        before = self.sql('SELECT count(*) FROM supplier_payment_documents')
        row = next(r for r in self.report()['invoices'] if r['invoiceId'] == invoice)
        self.assertEqual(row['category'], 'sealed')
        self.assertEqual(row['reasons'], [])
        self.assertFalse(row['ledgerRegistered'])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_documents'), before)
        self.assertFalse(self.report()['admissionGranted'])

    def test_legacy_paid_invoice_is_reported_without_repair(self):
        with patch.dict(os.environ, SUPPLIER_INVOICE_LINE_SPECS_ENABLED='0'):
            invoice = self.create()['id']
        self.sql('UPDATE supplier_invoices SET paid_amount=25 WHERE id=%s', (invoice,))
        before = self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (invoice,))
        row = next(r for r in self.report()['invoices'] if r['invoiceId'] == invoice)
        self.assertIn('missingOriginalLineEvidence', row['reasons'])
        self.assertIn('historicalPaymentWithoutLedger', row['reasons'])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), before)

    def test_company_filter_never_returns_other_company_invoice(self):
        invoice = self.create()['id']
        self.assertNotIn(invoice, [r['invoiceId'] for r in self.report(1)['invoices']])
        self.assertEqual(self.report(2147483647)['invoices'], [])

    def test_rejects_missing_scope_and_active_transaction(self):
        connection = self.main.get_db()
        try:
            for company in (None, True, 0, -1):
                with self.assertRaises(ValueError):
                    audit(connection, company)
            connection.autocommit = False
            with connection.cursor() as cur:
                cur.execute('SELECT 1')
            with self.assertRaises(ValueError):
                audit(connection, 2)
        finally:
            connection.rollback()
            connection.close()

    def legacy_pair(self):
        with patch.dict(os.environ, SUPPLIER_INVOICE_LINE_SPECS_ENABLED='0'):
            invoice = self.create()['id']
        warehouse = self.sql("""INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,paid_amount,supplier_invoice_id)
            VALUES(2,%s,%s,%s,200,200,50,%s) RETURNING id""",
            (self.fixture['supplierId'], self.fixture['project'],
             json.dumps([{'workPackage': self.fixture['workPackage']}]), invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET paid_amount=50,warehouse_invoice_id=%s WHERE id=%s',
                 (warehouse,invoice))
        return invoice,warehouse

    def test_pair_preview_never_doubles_original_payment(self):
        invoice,warehouse = self.legacy_pair()
        row = next(r for r in self.report()['invoices'] if r['invoiceId']==invoice)
        self.assertEqual(row['financialReview']['scenario'],'matchedLegacyPair')
        self.assertEqual(row['financialReview']['openingPaid'],'50.00')
        self.assertEqual(row['financialReview']['remainingAmount'],'150.00')
        self.assertEqual(row['financialReview']['newCashAmount'],'0.00')
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(50,)])

    def test_pair_disagreement_and_foreign_link_are_blocked(self):
        invoice,warehouse = self.legacy_pair()
        self.sql('UPDATE warehouse_invoices SET paid_amount=49 WHERE id=%s',(warehouse,))
        row = next(r for r in self.report()['invoices'] if r['invoiceId']==invoice)
        self.assertEqual(row['financialReview']['reason'],'receiptBalanceMismatch')
        # Isolated fixture only: model corruption predating the scope trigger.
        connection=self.main.get_db()
        connection.autocommit=False
        try:
            with connection,connection.cursor() as cur:
                cur.execute('ALTER TABLE warehouse_invoices DISABLE TRIGGER a_allocation_physical')
                cur.execute('UPDATE warehouse_invoices SET company_id=1 WHERE id=%s',(warehouse,))
                cur.execute('ALTER TABLE warehouse_invoices ENABLE TRIGGER a_allocation_physical')
        finally:
            connection.close()
        row = next(r for r in self.report()['invoices'] if r['invoiceId']==invoice)
        self.assertEqual(row['financialReview']['reason'],'receiptIdentityMismatch')
        self.assertNotIn('openingPaid',row['financialReview'])
        self.assertNotIn('warehouseId',row['financialReview'])

    def test_overpaid_old_invoice_is_not_a_valid_opening(self):
        with patch.dict(os.environ, SUPPLIER_INVOICE_LINE_SPECS_ENABLED='0'):
            invoice=self.create()['id']
        self.sql('UPDATE supplier_invoices SET paid_amount=201 WHERE id=%s',(invoice,))
        row=next(r for r in self.report()['invoices'] if r['invoiceId']==invoice)
        self.assertEqual(row['financialReview']['reason'],'paidExceedsOriginalAmount')

    def test_invalid_package_does_not_abort_other_invoice_results(self):
        invoice,warehouse=self.legacy_pair()
        self.sql("UPDATE warehouse_invoices SET items='[]' WHERE id=%s",(warehouse,))
        result=self.report()
        row=next(r for r in result['invoices'] if r['invoiceId']==invoice)
        self.assertEqual(row['financialReview']['reason'],'invalidReceiptPackage')
        self.assertGreater(len(result['invoices']),1)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyJsonAuditTests(LegacyAuditTests):
    """Run the same read-only contracts with production-style JSONB items."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection = cls.main.get_db()
        try:
            with connection, connection.cursor() as cur:
                cur.execute('ALTER TABLE warehouse_invoices ALTER COLUMN items DROP DEFAULT')
                cur.execute("ALTER TABLE warehouse_invoices ALTER COLUMN items TYPE jsonb USING NULLIF(items::text,'')::jsonb")
        finally:
            connection.close()
