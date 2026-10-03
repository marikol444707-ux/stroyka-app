import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0092_warehouse_operations_indexes.py"
REGISTRY = ROOT / "docs/m6-tenant-registry.json"


WAREHOUSE_OPERATION_TABLES = {
    "warehouse_distribution_operations",
    "warehouse_distribution_allocations",
    "warehouse_distribution_returns",
    "warehouse_distribution_transfers",
    "warehouse_distribution_transfer_receipts",
    "inventory_reconciliations",
    "inventory_reconciliation_events",
    "inventory_stock_adjustments",
    "intercompany_warehouse_transfers",
    "intercompany_warehouse_transfer_events",
    "warehouses",
    "warehouse_directory_events",
}


class WarehouseOperationsOwnerMigrationTests(unittest.TestCase):
    def load_migration(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_registry_classifies_every_remaining_warehouse_operation_table(self):
        entries = json.loads(REGISTRY.read_text(encoding="utf-8"))["entries"]
        by_resource = {entry["resource"]: entry for entry in entries}

        self.assertEqual(WAREHOUSE_OPERATION_TABLES - set(by_resource), set())
        for resource in WAREHOUSE_OPERATION_TABLES:
            self.assertEqual(by_resource[resource]["stage"], "M7m9")

        self.assertEqual(by_resource["intercompany_warehouse_transfers"]["companyState"], "missing")
        self.assertEqual(by_resource["warehouses"]["companyState"], "legacy_default")
        self.assertEqual(by_resource["warehouse_directory_events"]["companyState"], "stored")

    def test_upgrade_adds_only_missing_owner_indexes(self):
        namespace, statements = self.load_migration()
        self.assertEqual(namespace["down_revision"], "0091_warehouse_stock_chain_idx")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 4)
        self.assertIn("inventory_reconciliations(company_id,inventory_id)", sql)
        self.assertIn("inventory_reconciliations(company_id,project_id,inventory_id)", sql)
        self.assertIn("inventory_stock_adjustments(company_id,inventory_id,id)", sql)
        self.assertIn("intercompany_warehouse_transfer_events(company_id,transfer_id,id)", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)
        self.assertNotIn("DELETE ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load_migration()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 4)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
