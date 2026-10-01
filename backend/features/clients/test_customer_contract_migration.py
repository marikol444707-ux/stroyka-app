import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


MIGRATION = Path(__file__).resolve().parents[3] / "migrations" / "versions" / "0075_customer_contract_parties.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0075_customer_contract_parties", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = types.SimpleNamespace(execute=lambda _sql: None)
    with mock.patch.dict(sys.modules, {"alembic": fake_alembic}):
        spec.loader.exec_module(module)
    return module


class CustomerContractMigrationTest(unittest.TestCase):
    def test_schema_adds_exact_customer_ownership_and_immutable_contract_snapshot(self):
        migration = load_migration()
        statements = []
        with mock.patch.object(migration.op, "execute", side_effect=statements.append):
            migration.upgrade()
        sql = re.sub(r"\s+", " ", "\n".join(statements))
        self.assertEqual(migration.down_revision, "0074_offer_party_snapshots")
        self.assertIn("ALTER TABLE clients ADD COLUMN IF NOT EXISTS company_id INTEGER", sql)
        self.assertIn("FOREIGN KEY (client_id,company_id) REFERENCES clients(id,company_id)", sql)
        self.assertIn("party_snapshot_json JSONB", sql)
        self.assertIn("customer_client_id INTEGER", sql)
        self.assertIn("contract_version INTEGER", sql)
        self.assertIn("revises_document_id INTEGER", sql)
        self.assertIn("Customer contract party snapshot is immutable", sql)
        self.assertNotIn("UPDATE clients SET", sql)
        self.assertNotIn("UPDATE projects SET", sql)
        self.assertNotIn("UPDATE project_documents SET", sql)


if __name__ == "__main__":
    unittest.main()
