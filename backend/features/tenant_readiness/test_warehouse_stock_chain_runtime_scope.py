import ast
from pathlib import Path
import unittest


MAIN = Path(__file__).resolve().parents[2] / "main.py"


class WarehouseStockChainRuntimeScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def function_source(self, name):
        node = next(
            item for item in self.tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
        )
        return ast.get_source_segment(self.source, node)

    def test_stock_check_scopes_request_and_every_main_warehouse_read(self):
        source = self.function_source("supply_request_stock_check")
        self.assertIn("request_scope_sql", source)
        self.assertIn("FROM supply_requests WHERE id=%s", source)
        warehouse_queries = [
            node.value for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "FROM warehouse_main" in node.value
        ]
        self.assertEqual(len(warehouse_queries), 2)
        self.assertTrue(all("company_id=%s" in query for query in warehouse_queries))

    def test_ai_context_scopes_main_warehouse_to_accessible_companies(self):
        source = self.function_source("ai_chat")
        self.assertIn("warehouse_visibility_sql", source)
        self.assertIn('FROM warehouse_main WHERE TRUE" + warehouse_visibility_sql', source)


if __name__ == "__main__":
    unittest.main()
