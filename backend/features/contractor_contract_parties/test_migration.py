import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MIGRATION = Path(__file__).resolve().parents[3] / "migrations" / "versions" / "0076_contractor_contract_parties.py"


class ContractorContractMigrationTests(unittest.TestCase):
    def test_migration_adds_snapshot_and_immutable_guard(self):
        spec = importlib.util.spec_from_file_location("migration_0076", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        statements = []
        with patch.object(module.op, "execute", side_effect=statements.append):
            module.upgrade()
        sql = "\n".join(statements)
        self.assertIn("contract_scan_url", sql)
        self.assertIn("party_snapshot_json", sql)
        self.assertIn("contractor_contract_party_snapshot_guard", sql)
        self.assertIn("contract_scan_url IS DISTINCT", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS signatory_name", sql)


if __name__ == "__main__":
    unittest.main()
