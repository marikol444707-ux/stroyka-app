import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend/main.py"


class SupplierInvoiceDuplicateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        cls.module_source = ast.unparse(tree)
        cls.functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_main_imports_the_canonical_supplier_document_guard(self):
        self.assertIn("build_supplier_invoice_lock_keys", self.module_source)
        self.assertIn("match_supplier_invoice_duplicate", self.module_source)

    def test_duplicate_lookup_locks_before_reading_and_normalizes_document_number(self):
        source = self.functions["_find_existing_supplier_invoice_duplicate"]

        self.assertIn("build_supplier_invoice_lock_keys", source)
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertLess(
            source.index("pg_advisory_xact_lock"),
            source.index("FROM supplier_invoices"),
        )
        self.assertIn("build_invoice_number_lookup_keys", source)
        self.assertIn("normalize_invoice_date", source)
        self.assertIn("regexp_replace", source)
        self.assertIn("match_supplier_invoice_duplicate", source)

    def test_amount_alone_is_never_supplier_document_identity(self):
        source = self.functions["_find_existing_supplier_invoice_duplicate"]

        self.assertNotIn("amount_matches", source)

    def test_supply_delivery_invoice_is_serialized_by_exact_delivery(self):
        source = self.functions["_ensure_supply_delivery_invoice"]

        self.assertIn("pg_advisory_xact_lock", source)
        self.assertLess(
            source.index("pg_advisory_xact_lock"),
            source.index("SELECT id FROM warehouse_invoices"),
        )
        self.assertNotIn("SUPPLY INVOICE CHECK ERROR", source)


if __name__ == "__main__":
    unittest.main()
