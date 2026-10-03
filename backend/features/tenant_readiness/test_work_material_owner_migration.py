import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0087_work_material_owner_indexes.py"


class WorkMaterialOwnerMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_adds_only_company_leading_indexes(self):
        namespace, statements = self.load()
        self.assertEqual(namespace["down_revision"], "0086_counterparty_doc_owners")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 3)
        self.assertIn("work_material_accounts(company_id,project_id,journal_id)", sql)
        self.assertIn("work_material_defect_items(company_id,defect_id,entry_id)", sql)
        self.assertIn("work_material_defect_decisions(company_id,defect_id,id DESC)", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 3)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
