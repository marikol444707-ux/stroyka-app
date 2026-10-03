import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0091_warehouse_stock_chain_indexes.py"


class WarehouseStockChainOwnerMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_adds_only_missing_owner_indexes(self):
        namespace, statements = self.load()
        self.assertEqual(namespace["down_revision"], "0090_tool_responsibility_idx")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 3)
        self.assertIn("warehouse_main(company_id,id)", sql)
        self.assertIn("warehouse_movements(company_id,id DESC)", sql)
        self.assertIn("warehouse_receipt_lots(company_id,project_id,id)", sql)
        self.assertIn("WHERE project_id IS NOT NULL", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 3)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
