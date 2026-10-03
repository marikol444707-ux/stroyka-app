import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0086_counterparty_document_owners.py"


class CounterpartyDocumentOwnerMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_removes_defaults_and_adds_explicit_document_scope(self):
        namespace, statements = self.load()
        self.assertEqual(namespace["down_revision"], "0085_supplier_contract_indexes")
        namespace["upgrade"]()
        sql = "\n".join(statements)
        self.assertEqual(sql.count("ALTER COLUMN company_id DROP DEFAULT"), 3)
        self.assertEqual(sql.count("ALTER COLUMN company_id SET NOT NULL"), 3)
        self.assertIn("ADD COLUMN IF NOT EXISTS owner_scope", sql)
        self.assertIn("ck_supplier_documents_owner", sql)
        self.assertIn("fk_supplier_documents_supplier", sql)
        self.assertNotIn("SETcompany_id=1", sql.replace(" ", ""))

    def test_project_launch_bootstrap_requires_explicit_company(self):
        schema = (ROOT / "backend/features/project_launch/schema.py").read_text(encoding="utf-8")

        self.assertNotIn("company_id INT DEFAULT 1", schema)
        self.assertEqual(
            schema.count("company_id INT NOT NULL REFERENCES companies(id)"),
            3,
        )

    def test_downgrade_removes_only_the_new_scope_and_constraints(self):
        namespace, statements = self.load()
        namespace["downgrade"]()
        sql = "\n".join(statements)
        self.assertIn("DROP COLUMN owner_scope", sql)
        self.assertEqual(sql.count("ALTER COLUMN company_id SET DEFAULT 1"), 3)


if __name__ == "__main__":
    unittest.main()
