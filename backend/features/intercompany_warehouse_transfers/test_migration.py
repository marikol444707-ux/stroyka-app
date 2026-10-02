import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


def _module():
    path = Path(__file__).resolve().parents[3] / "migrations/versions/0082_intercompany_warehouse_transfers.py"
    spec = importlib.util.spec_from_file_location("intercompany_transfer_migration", path)
    module = importlib.util.module_from_spec(spec)
    alembic = ModuleType("alembic")
    alembic.op = None
    with patch.dict("sys.modules", {"alembic": alembic}):
        spec.loader.exec_module(module)
    return module


class IntercompanyTransferMigrationTests(unittest.TestCase):
    def test_migration_is_after_current_head_and_creates_paired_transfer_registry(self):
        module = _module()
        statements = []
        with patch.object(module, "op", SimpleNamespace(execute=statements.append)):
            module.upgrade()
        sql = "\n".join(statements)
        self.assertEqual(module.down_revision, "0081_supply_project_id")
        self.assertIn("CREATE TABLE intercompany_warehouse_transfers", sql)
        self.assertIn("source_company_id", sql)
        self.assertIn("destination_company_id", sql)
        self.assertIn("source_document_json", sql)
        self.assertIn("destination_document_json", sql)
        self.assertIn("decision_company_id=destination_company_id", sql)
        self.assertIn("decision_company_id=source_company_id", sql)
        self.assertIn("CREATE TABLE intercompany_warehouse_transfer_events", sql)
        self.assertIn("source_company_id<>destination_company_id", sql)
        self.assertIn("cannot be deleted", sql.lower())

    def test_downgrade_refuses_to_discard_recorded_transfers(self):
        module = _module()
        statements = []
        with patch.object(module, "op", SimpleNamespace(execute=statements.append)):
            module.downgrade()
        sql = "\n".join(statements)
        self.assertIn("EXISTS(SELECT 1 FROM intercompany_warehouse_transfers)", sql)
        self.assertIn("Cannot discard intercompany warehouse transfer history", sql)
