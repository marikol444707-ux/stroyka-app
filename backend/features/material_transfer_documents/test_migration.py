import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


PATH = Path(__file__).parents[3] / "migrations" / "versions" / "0078_material_transfer_parties.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0078_material_transfer_parties", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaterialTransferPartiesMigrationTest(unittest.TestCase):
    def test_adds_complete_snapshots_and_immutable_core(self):
        migration = load_migration()
        statements = []
        with patch.object(migration.op, "execute", side_effect=statements.append):
            migration.upgrade()
        sql = "\n".join(statements)
        self.assertEqual(migration.revision, "0078_material_transfer_parties")
        self.assertEqual(migration.down_revision, "0077_customer_act_contract_basis")
        self.assertIn("issue_party_snapshot_json", sql)
        self.assertIn("receipt_party_snapshot_json", sql)
        self.assertIn("NEW.quantity IS DISTINCT FROM OLD.quantity", sql)
        self.assertIn("Signed material receipt snapshot is immutable", sql)

    def test_downgrade_refuses_to_erase_frozen_documents(self):
        migration = load_migration()
        statements = []
        with patch.object(migration.op, "execute", side_effect=statements.append):
            migration.downgrade()
        sql = "\n".join(statements)
        self.assertLess(sql.index("Cannot discard frozen material transfer documents"),
                        sql.index("DROP COLUMN receipt_party_snapshot_frozen_at"))


if __name__ == "__main__":
    unittest.main()
