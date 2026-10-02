import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0085_supplier_contract_tenant_indexes.py"


class SupplierContractTenantIndexMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [
            node for node in tree.body
            if isinstance(node, (ast.Assign, ast.FunctionDef))
        ]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_adds_only_six_company_indexes(self):
        namespace, statements = self.load()

        self.assertEqual(namespace["revision"], "0085_supplier_contract_indexes")
        self.assertEqual(namespace["down_revision"], "0084_supplier_ledger_indexes")
        namespace["upgrade"]()

        self.assertEqual(len(statements), 6)
        self.assertTrue(all(statement.startswith("CREATE INDEX ") for statement in statements))
        self.assertTrue(all("company_id" in statement for statement in statements))
        self.assertFalse(any("INSERT " in statement or "UPDATE " in statement for statement in statements))

    def test_downgrade_removes_only_added_indexes(self):
        namespace, statements = self.load()

        namespace["downgrade"]()

        self.assertEqual(len(statements), 6)
        self.assertTrue(all(statement.startswith("DROP INDEX public.") for statement in statements))


if __name__ == "__main__":
    unittest.main()
