import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0089_work_contract_act_indexes.py"


class WorkContractActOwnerMigrationTests(unittest.TestCase):
    def load(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_upgrade_adds_only_company_leading_indexes(self):
        namespace, statements = self.load()
        self.assertEqual(namespace["down_revision"], "0088_work_acceptance_indexes")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 5)
        self.assertIn("work_contract_acts(company_id,contract_id,act_id)", sql)
        self.assertIn("work_contract_act_items(company_id,act_id,journal_id)", sql)
        self.assertIn("work_contract_fine_allocations(company_id,act_id,defect_id)", sql)
        self.assertIn("work_contract_act_signatures(company_id,act_id,operation_id)", sql)
        self.assertIn("work_contract_act_payments(company_id,act_id,payment_id)", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 5)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
