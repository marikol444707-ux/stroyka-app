"""Read-only legacy inventory against real, isolated invoice fixtures."""
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
