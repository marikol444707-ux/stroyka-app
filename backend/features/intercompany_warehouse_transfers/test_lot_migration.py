import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


def module():
    path = Path(__file__).resolve().parents[3] / "migrations/versions/0083_intercompany_lot_lineage.py"
    spec = importlib.util.spec_from_file_location("intercompany_lot_migration", path)
    value = importlib.util.module_from_spec(spec)
    alembic = ModuleType("alembic")
    alembic.op = None
    with patch.dict("sys.modules", {"alembic": alembic}):
        spec.loader.exec_module(value)
    return value


class IntercompanyLotMigrationTests(unittest.TestCase):
    def test_upgrade_requires_empty_registry_and_adds_exact_lineage(self):
        migration = module()
        statements = []
        with patch.object(migration, "op", SimpleNamespace(execute=statements.append)):
            migration.upgrade()
        sql = "\n".join(statements)
        self.assertEqual(migration.down_revision, "0082_intercompany_transfers")
        self.assertIn("Cannot add exact lot lineage to existing intercompany transfers", sql)
        self.assertIn("source_lot_id INTEGER NOT NULL", sql)
        self.assertIn("destination_receipt_id", sql)
        self.assertIn("destination_lot_id", sql)
        self.assertIn("NEW.source_lot_id<>OLD.source_lot_id", sql)

    def test_downgrade_refuses_to_discard_lineage(self):
        migration = module()
        statements = []
        with patch.object(migration, "op", SimpleNamespace(execute=statements.append)):
            migration.downgrade()
        self.assertIn("Cannot discard intercompany lot lineage", "\n".join(statements))


if __name__ == "__main__":
    unittest.main()
