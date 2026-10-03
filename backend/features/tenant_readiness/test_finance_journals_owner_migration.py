import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0093_finance_journal_indexes.py"
REGISTRY = ROOT / "docs/m6-tenant-registry.json"


FINANCE_JOURNAL_TABLES = {
    "company_payments",
    "project_payments",
    "brigade_payments",
    "brigade_acts",
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "salary_payments",
    "own_expenses",
    "expenses",
}


class FinanceJournalsOwnerMigrationTests(unittest.TestCase):
    def load_migration(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        statements = []
        namespace = {"op": SimpleNamespace(execute=statements.append)}
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MIGRATION), "exec"), namespace)
        return namespace, statements

    def test_registry_classifies_finance_journals_without_guessing_legacy_owners(self):
        entries = json.loads(REGISTRY.read_text(encoding="utf-8"))["entries"]
        by_resource = {entry["resource"]: entry for entry in entries}

        self.assertEqual(FINANCE_JOURNAL_TABLES - set(by_resource), set())
        for resource in FINANCE_JOURNAL_TABLES:
            self.assertEqual(by_resource[resource]["stage"], "M7m10")

        self.assertEqual(by_resource["company_payments"]["companyState"], "stored")
        self.assertEqual(by_resource["brigade_acts"]["companyState"], "missing")
        for resource in FINANCE_JOURNAL_TABLES - {"company_payments", "brigade_acts"}:
            self.assertEqual(by_resource[resource]["companyState"], "legacy_default")
            self.assertIn("verified", by_resource[resource]["accessState"])

    def test_upgrade_adds_only_missing_lookup_indexes(self):
        namespace, statements = self.load_migration()
        self.assertEqual(namespace["down_revision"], "0092_warehouse_operations_idx")

        namespace["upgrade"]()
        sql = "\n".join(statements)

        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 2)
        self.assertIn("company_payments(company_id,id)", sql)
        self.assertIn("brigade_acts(contract_id,id)", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT ", sql)
        self.assertNotIn("DELETE ", sql)

    def test_downgrade_removes_only_the_new_indexes(self):
        namespace, statements = self.load_migration()
        namespace["downgrade"]()
        self.assertEqual(len(statements), 2)
        self.assertTrue(all(statement.startswith("DROP INDEX IF EXISTS") for statement in statements))


if __name__ == "__main__":
    unittest.main()
