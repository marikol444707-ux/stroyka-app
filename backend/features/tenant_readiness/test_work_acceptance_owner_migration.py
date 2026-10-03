import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0088_work_acceptance_indexes.py"


class WorkAcceptanceOwnerMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_adds_only_company_leading_indexes(self):
        namespace, statements = self.load()
        self.assertEqual(namespace["down_revision"], "0087_work_material_indexes")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 3)
        self.assertIn("work_acceptance_reviews(company_id,project_id,journal_id)", sql)
        self.assertIn("work_rework_links(company_id,journal_id,review_id)", sql)
        self.assertIn("work_rework_submissions(company_id,journal_id,operation_id)", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 3)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
