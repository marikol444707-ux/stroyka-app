import ast
from pathlib import Path
import unittest

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend/main.py"


class LinkedInvoiceSupplierResolutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        cls.functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_linked_invoice_resolution_is_explicit_and_deduplicated(self):
        source = self.functions["_resolve_or_create_linked_invoice_supplier"]
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertIn("allow_name_match=True", source)
        self.assertIn("'На проверке'", source)
        self.assertIn("'linked_supplier_invoice'", source)
        self.assertNotIn("has_legal_supplier_identity", source)

    def test_accounting_route_only_allows_it_for_a_linked_invoice(self):
        source = self.functions["update_warehouse_invoice_accounting"]
        self.assertIn("resolveLinkedSupplier", source)
        self.assertIn("supplier_invoice_row", source)
        self.assertIn("_resolve_or_create_linked_invoice_supplier", source)
        self.assertIn("supplierNeedsReview", source)


class _Cursor:
    def __init__(self):
        self.calls = []
        self.created = {"id": 91, "name": 'ООО "Новый поставщик"'}

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.created


class LinkedInvoiceSupplierResolutionBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_resolve_or_create_linked_invoice_supplier"
        )
        cls.function_node = function

    def load_function(self, matched=None):
        aliases = []
        namespace = {
            "HTTPException": HTTPException,
            "_normalize_supplier_name_key": lambda value: "новый-поставщик" if value else "",
            "_supplier_find_match": lambda *args, **kwargs: matched,
            "_remember_supplier_alias": lambda *args, **kwargs: aliases.append((args, kwargs)),
            "_row_get": lambda row, key, index, fallback: row.get(key, fallback),
        }
        module = ast.Module(body=[self.function_node], type_ignores=[])
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        return namespace["_resolve_or_create_linked_invoice_supplier"], aliases

    def test_existing_name_is_reused_after_the_transaction_lock(self):
        matched = {"id": 17, "name": 'ООО "Новый поставщик"'}
        resolve, aliases = self.load_function(matched=matched)
        cursor = _Cursor()

        result = resolve(cursor, {"supplier_name": matched["name"]}, warehouse_invoice_id=14555)

        self.assertEqual(17, result["id"])
        self.assertFalse(result["created"])
        self.assertFalse(result["needsReview"])
        self.assertIn("pg_advisory_xact_lock", cursor.calls[0][0])
        self.assertFalse(any("INSERT INTO suppliers" in sql for sql, _ in cursor.calls))
        self.assertEqual(1, len(aliases))

    def test_unknown_name_creates_one_provisional_review_card(self):
        resolve, aliases = self.load_function(matched=None)
        cursor = _Cursor()

        result = resolve(
            cursor,
            {"supplier_name": 'ООО "Новый поставщик"'},
            warehouse_invoice_id=14555,
        )

        self.assertEqual(91, result["id"])
        self.assertTrue(result["created"])
        self.assertTrue(result["needsReview"])
        inserts = [(sql, params) for sql, params in cursor.calls if "INSERT INTO suppliers" in sql]
        self.assertEqual(1, len(inserts))
        self.assertIn("'На проверке'", inserts[0][0])
        self.assertEqual("linked_supplier_invoice", inserts[0][1][2])
        self.assertEqual(1, len(aliases))

    def test_missing_supplier_name_is_rejected(self):
        resolve, _aliases = self.load_function(matched=None)
        with self.assertRaises(HTTPException) as error:
            resolve(_Cursor(), {}, fallback_name="")
        self.assertEqual(422, error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
