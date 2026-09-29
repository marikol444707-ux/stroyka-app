"""Separate fresh-database class proving dedupe still supports pre-0017 schema."""
import os
import unittest
from unittest.mock import patch

from .test_dedupe_guards_postgres import DedupeFixture


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PreledgerDedupeTests(DedupeFixture, unittest.TestCase):
    ledger_present = False

    def test_legacy_ddl_precedes_company_lock_like_other_preledger_writers(self):
        original = self.main._ensure_invoice_document_link_columns
        def ensure(cur):
            cur.execute("""SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid()
                AND locktype='advisory' AND classid=1735289201 AND objid=2) AS held""")
            self.assertFalse(cur.fetchone()['held'], 'Legacy DDL must precede the company advisory lock')
            original(cur)
        with patch.object(self.main, '_ensure_invoice_document_link_columns', side_effect=ensure):
            self.assertEqual(self.dedupe()['annulledRows'], 1)

    def test_unmanaged_merge_and_dry_run_without_ledger(self):
        self.assertEqual(self.sql("SELECT to_regclass('public.supplier_payment_documents')"), [(None,)])
        warehouse = self.warehouse(linked=self.duplicate)
        before = self.snapshot()
        preview = self.dedupe(payload={'supplierInvoiceIds': [self.canonical]})
        self.assertEqual(preview['checkedGroups'], 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.dedupe()['annulledRows'], 1)
        self.assertEqual(self.sql('SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(self.canonical,)])

    def test_foreign_reverse_neighbor_still_denied_without_ledger(self):
        self.warehouse(company=3, linked=self.duplicate)
        self.assert_denied_unchanged()
