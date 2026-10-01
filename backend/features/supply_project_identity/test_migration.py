import ast
import unittest
from pathlib import Path


class SupplyProjectIdentityMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).parents[3] / "migrations/versions/0081_supply_request_project_identity.py"
        cls.source = cls.path.read_text()
        ast.parse(cls.source)

    def test_migration_adds_exact_owner_constraint_and_safe_downgrade(self):
        self.assertIn("ADD COLUMN IF NOT EXISTS project_id INTEGER", self.source)
        self.assertIn("FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)", self.source)
        self.assertIn("WHERE project_id IS NOT NULL", self.source)


if __name__ == "__main__":
    unittest.main()
