import importlib.util
from pathlib import Path
import unittest


class WarehouseMovementMigrationTest(unittest.TestCase):
    def test_revision_follows_m15_and_guards_document_fields(self):
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0079_warehouse_movement_document.py"
        spec = importlib.util.spec_from_file_location("movement_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.down_revision, "0078_material_transfer_parties")
        self.assertIn("document_snapshot_json", module.upgrade.__code__.co_consts[1])
        self.assertIn("NEW.quantity IS DISTINCT FROM OLD.quantity", module.upgrade.__code__.co_consts[1])
        self.assertIn("Cannot discard frozen M-11 documents", module.downgrade.__code__.co_consts[2])


if __name__ == "__main__":
    unittest.main()
