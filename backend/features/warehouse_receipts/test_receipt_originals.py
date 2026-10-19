"""Receipt evidence contracts; no database, server, or migration is run."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from .receipt_originals import persist_receipt_originals, require_receipt_originals_schema
from .receipt_originals_schema import SCHEMA_SQL


ROOT = Path(__file__).resolve().parents[3]
ORIGINALS = ['/tenant-files/78/content', '/tenant-files/77/content']


class ReceiptOriginalPersistenceTests(unittest.TestCase):
    def test_preserves_full_ordered_evidence_with_company_scoped_write_once(self):
        cur = Mock(rowcount=1)
        persist_receipt_originals(cur, 31, 2, ORIGINALS)
        sql, params = cur.execute.call_args.args
        self.assertIn('WHERE id=%s AND company_id=%s AND receipt_original_urls IS NULL', sql)
        self.assertEqual(params, (json.dumps(ORIGINALS), 31, 2))
        cur.fetchone.assert_not_called()
        cur.commit.assert_not_called()

    def test_exact_existing_evidence_is_replayed_without_an_update_to_it(self):
        cur = Mock(rowcount=0)
        cur.fetchone.return_value = {'receipt_original_urls': ORIGINALS}
        persist_receipt_originals(cur, 31, 2, ORIGINALS)
        self.assertEqual(cur.execute.call_count, 2)
        sql, params = cur.execute.call_args.args
        self.assertIn('WHERE id=%s AND company_id=%s', sql)
        self.assertEqual(params, (31, 2))

    def test_missing_foreign_or_changed_evidence_fails_without_replacing_it(self):
        for row in (None, {'receipt_original_urls': list(reversed(ORIGINALS))},
                    {'receipt_original_urls': ['/tenant-files/90/content']},
                    {'receipt_original_urls': None}):
            with self.subTest(row=row):
                cur = Mock(rowcount=0)
                cur.fetchone.return_value = row
                with self.assertRaises(HTTPException) as error:
                    persist_receipt_originals(cur, 31, 2, ORIGINALS)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(cur.execute.call_count, 2)

    def test_noncanonical_duplicate_and_empty_evidence_never_write(self):
        for originals in (None, [], 'url', [1], [{}], [None], ORIGINALS * 16,
                          [ORIGINALS[0], ORIGINALS[0]], ['/uploads/a.png'],
                          ['https://example.org/a.png'], ['/tenant-files/0/content'],
                          ['/tenant-files/77/content\n'], ['/tenant-files/77/content?download=1']):
            with self.subTest(originals=originals):
                cur = Mock()
                with self.assertRaises(HTTPException) as error:
                    persist_receipt_originals(cur, 31, 2, originals)
                self.assertEqual(error.exception.status_code, 400)
                cur.execute.assert_not_called()

    def test_missing_schema_is_read_only_and_reports_migration_needed(self):
        for row in (None, {'ready': False}, {'ready': True}):
            with self.subTest(row=row):
                cur = Mock()
                cur.fetchone.return_value = row
                if row and row['ready']:
                    require_receipt_originals_schema(cur)
                else:
                    with self.assertRaises(HTTPException) as error:
                        require_receipt_originals_schema(cur)
                    self.assertEqual(error.exception.status_code, 503)
                sql = cur.execute.call_args.args[0]
                self.assertTrue(sql.startswith('SELECT'))
                self.assertIn("to_regclass('supply_deliveries')", sql)
                self.assertIn("atttypid='jsonb'::regtype", sql)
                self.assertIn('convalidated', sql)
                self.assertIn("tgenabled IN ('O','A')", sql)
                self.assertIn("to_regprocedure('preserve_receipt_original_urls()')", sql)
                self.assertNotIn('public.', sql)
                cur.commit.assert_not_called()


class ReceiptOriginalMigrationContractTests(unittest.TestCase):
    def migration(self):
        path = ROOT / 'migrations/versions/0101_receipt_originals.py'
        tree = ast.parse(path.read_text())
        statements = []
        namespace = {'op': SimpleNamespace(execute=statements.append), 'SCHEMA_SQL': SCHEMA_SQL}
        exec(compile(ast.Module(body=[node for node in tree.body
            if isinstance(node, (ast.Assign, ast.FunctionDef))], type_ignores=[]), str(path), 'exec'), namespace)
        return namespace, statements

    def test_new_revision_keeps_existing_rows_unknown_and_downgrade_preserves_evidence(self):
        migration, statements = self.migration()
        self.assertEqual(migration['revision'], '0101_receipt_originals')
        self.assertLessEqual(len(migration['revision']), 32)
        self.assertEqual(migration['down_revision'], '0100_packaging_history_guard')
        migration['upgrade']()
        self.assertEqual(statements, [SCHEMA_SQL])
        self.assertIn('ADD COLUMN IF NOT EXISTS receipt_original_urls JSONB;', SCHEMA_SQL)
        self.assertNotRegex(SCHEMA_SQL, r'(?i)\b(?:UPDATE|DELETE FROM|INSERT INTO) supply_deliveries\b')
        self.assertNotIn('DEFAULT', SCHEMA_SQL)
        self.assertNotIn('NOT NULL', SCHEMA_SQL.split('CREATE OR REPLACE FUNCTION', 1)[0])
        statements.clear()
        migration['downgrade']()
        self.assertEqual(statements, [])

    def test_migration_checks_canonical_nonempty_unique_array_and_immutability(self):
        for condition in ("jsonb_typeof(originals) <> 'array'", 'NOT BETWEEN 1 AND 30',
                          "jsonb_typeof(item) <> 'string'", "^/tenant-files/[1-9][0-9]*/content$",
                          'url = ANY(seen)', 'OLD.receipt_original_urls IS NOT NULL',
                          'NEW.receipt_original_urls IS DISTINCT FROM OLD.receipt_original_urls',
                          "ERRCODE='23514'", 'BEFORE UPDATE ON supply_deliveries',
                          'NEW.id,NEW.company_id,NEW.supplier_id,NEW.offer_id,NEW.request_id',
                          'NEW.project,NEW.work_package,NEW.waybill_number,NEW.waybill_date',
                          "to_jsonb(NEW)->'source_supplier_invoice_id' IS DISTINCT FROM",
                          "to_jsonb(NEW)->'contract_version_id' IS DISTINCT FROM"):
            self.assertIn(condition, SCHEMA_SQL)

    def test_claim_delivery_and_resolver_projections_are_safe_before_migration(self):
        from ..supply_claim_cases.access import COLUMNS
        for source in (COLUMNS, (ROOT / 'backend/main.py').read_text(),
                       (ROOT / 'backend/features/warehouse_receipts/resolver.py').read_text()):
            self.assertIn("to_jsonb(d)->'receipt_original_urls'", source)


if __name__ == '__main__':
    unittest.main()
