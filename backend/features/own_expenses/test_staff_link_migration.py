import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    PROJECT_ROOT / "migrations" / "versions" / "0006_user_company_staff_links.py"
)
MIGRATION_README_PATH = PROJECT_ROOT / "migrations" / "README.md"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_0006_user_company_staff_links",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = types.SimpleNamespace(execute=lambda _sql: None)
    with mock.patch.dict(sys.modules, {"alembic": fake_alembic}):
        spec.loader.exec_module(module)
    return module


class UserCompanyStaffLinkMigrationTests(unittest.TestCase):
    def test_upgrade_adds_nullable_tenant_safe_staff_link_without_data_writes(self):
        migration = _load_migration()
        executed = []

        with mock.patch.object(
            migration.op, "execute", side_effect=executed.append,
        ):
            migration.upgrade()

        combined = "\n".join(executed)
        self.assertEqual(migration.revision, "0006_user_company_staff_links")
        self.assertEqual(migration.down_revision, "0005_platform_client_contracts")
        self.assertIn(
            "ALTER TABLE public.user_company_roles "
            "ADD COLUMN IF NOT EXISTS staff_id INTEGER",
            " ".join(combined.split()),
        )
        self.assertIn("FOREIGN KEY (company_id, staff_id)", combined)
        self.assertIn("REFERENCES public.staff(company_id, id)", combined)
        self.assertIn(
            "WHERE staff_id IS NOT NULL AND COALESCE(active, TRUE) IS TRUE",
            combined,
        )
        self.assertNotRegex(
            combined.upper(),
            r"\b(INSERT|UPDATE|DELETE FROM|TRUNCATE)\b",
        )

    def test_migration_is_documented(self):
        self.assertIn(
            "0006_user_company_staff_links",
            MIGRATION_README_PATH.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
