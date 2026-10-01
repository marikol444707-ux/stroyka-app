import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


PATH = Path(__file__).parents[3] / "migrations" / "versions" / "0077_customer_act_contract_basis.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0077_customer_act_contract_basis", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomerActMigrationTest(unittest.TestCase):
    def test_adds_exact_company_contract_link_and_immutable_guard(self):
        migration = load_migration()
        statements = []
        with patch.object(migration.op, "execute", side_effect=statements.append):
            migration.upgrade()
        sql = "\n".join(statements)
        self.assertEqual(migration.revision, "0077_customer_act_contract_basis")
        self.assertEqual(migration.down_revision, "0076_contractor_contract_parties")
        self.assertIn("basis_contract_document_id", sql)
        self.assertIn("UNIQUE(id,company_id,project_id)", sql)
        self.assertIn("FOREIGN KEY (basis_contract_document_id,company_id,project_id)", sql)
        self.assertIn("NEW.basis_contract_document_id IS DISTINCT FROM", sql)
        self.assertIn("Customer document party snapshot is immutable", sql)

    def test_downgrade_refuses_to_erase_used_links(self):
        migration = load_migration()
        statements = []
        with patch.object(migration.op, "execute", side_effect=statements.append):
            migration.downgrade()
        sql = "\n".join(statements)
        self.assertLess(sql.index("Cannot discard signed customer act contract links"),
                        sql.index("DROP COLUMN basis_contract_document_id"))


if __name__ == "__main__":
    unittest.main()
