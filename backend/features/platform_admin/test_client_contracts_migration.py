import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "migrations"
    / "versions"
    / "0005_platform_client_contracts.py"
)
MIGRATION_README_PATH = PROJECT_ROOT / "migrations" / "README.md"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_0005_platform_client_contracts",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = types.SimpleNamespace(execute=lambda _sql: None)
    with mock.patch.dict(sys.modules, {"alembic": fake_alembic}):
        spec.loader.exec_module(module)
    return module


def _normalized(sql):
    return re.sub(r"\s+", " ", str(sql)).strip()


class PlatformClientContractsMigrationTests(unittest.TestCase):
    def test_upgrade_adds_contract_tables_without_mutating_existing_rows(self):
        migration = _load_migration()
        executed = []

        with mock.patch.object(
            migration.op,
            "execute",
            side_effect=executed.append,
        ):
            migration.upgrade()

        self.assertEqual(migration.revision, "0005_platform_client_contracts")
        self.assertEqual(
            migration.down_revision,
            "0004_active_estimate_snapshots",
        )
        combined = "\n".join(_normalized(sql) for sql in executed)

        self.assertIn(
            "CREATE TABLE IF NOT EXISTS public.platform_licensor_profiles",
            combined,
        )
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS public.platform_client_contracts",
            combined,
        )
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS client_contract_id INTEGER",
            combined,
        )
        self.assertIn(
            "fk_platform_billing_documents_client_contract_company",
            combined,
        )
        self.assertIn(
            "FOREIGN KEY (client_contract_id, company_id) REFERENCES "
            "public.platform_client_contracts(id, company_id)",
            combined,
        )
        self.assertIn(
            "fk_company_payments_client_contract_company",
            combined,
        )
        self.assertIn(
            "chk_platform_client_contracts_status",
            combined,
        )
        self.assertIn(
            "uq_platform_client_contracts_idempotency",
            combined,
        )
        self.assertIn(
            "uq_platform_client_contracts_number",
            combined,
        )
        self.assertNotRegex(
            combined.upper(),
            re.compile(r"\b(INSERT|UPDATE|DELETE FROM|TRUNCATE)\b"),
        )

    def test_downgrade_refuses_to_destroy_contract_business_data(self):
        migration = _load_migration()
        executed = []

        with mock.patch.object(
            migration.op,
            "execute",
            side_effect=executed.append,
        ):
            migration.downgrade()

        combined = "\n".join(_normalized(sql) for sql in executed)
        self.assertIn("platform_client_contracts is not empty", combined)
        self.assertIn("platform_licensor_profiles is not empty", combined)
        self.assertLess(
            combined.index("platform_client_contracts is not empty"),
            combined.index("DROP TABLE IF EXISTS public.platform_client_contracts"),
        )
        self.assertIn(
            "DROP COLUMN IF EXISTS client_contract_id",
            combined,
        )
        self.assertNotRegex(
            combined.upper(),
            re.compile(r"\b(DELETE|UPDATE|TRUNCATE)\b"),
        )

    def test_migration_is_documented(self):
        readme = MIGRATION_README_PATH.read_text(encoding="utf-8")
        self.assertIn("0005_platform_client_contracts", readme)


if __name__ == "__main__":
    unittest.main()
