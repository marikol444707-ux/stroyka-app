import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from backend.features.accounting_exception_checks.link_integrity_schema import (
    build_accounting_link_integrity_schema_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "migrations"
    / "versions"
    / "0003_accounting_link_integrity.py"
)
MIGRATION_README_PATH = PROJECT_ROOT / "migrations" / "README.md"
CI_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_0003_accounting_link_integrity",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = types.SimpleNamespace(execute=lambda _sql: None)
    with mock.patch.dict(sys.modules, {"alembic": fake_alembic}):
        spec.loader.exec_module(module)
    return module


def _normalized(sql):
    normalized = " ".join(str(sql).split())
    normalized = re.sub(r"\(\s+", "(", normalized)
    normalized = re.sub(r"\s+\)", ")", normalized)
    return normalized


class AccountingLinkIntegrityAlembicMigrationTests(unittest.TestCase):
    def test_migration_is_documented_and_every_revision_is_compiled_in_ci(self):
        readme = MIGRATION_README_PATH.read_text(encoding="utf-8")
        ci = CI_PATH.read_text(encoding="utf-8")

        self.assertIn("0003_accounting_link_integrity", readme)
        self.assertIn("migrations/versions/*.py", ci)

    def test_upgrade_is_the_exact_frozen_idempotent_plan(self):
        migration = _load_migration()
        executed = []

        with mock.patch.object(
            migration.op, "execute", side_effect=executed.append,
        ):
            migration.upgrade()

        plan = build_accounting_link_integrity_schema_plan()
        self.assertEqual(migration.revision, "0003_accounting_link_integrity")
        self.assertEqual(migration.down_revision, "0002_ops_error_logging")
        self.assertEqual(
            [_normalized(sql) for sql in executed],
            [_normalized(change["sql"]) for change in plan["changes"]],
        )
        combined = "\n".join(executed).upper()
        self.assertNotRegex(
            combined, re.compile(r"\b(INSERT|UPDATE|DELETE FROM|TRUNCATE)\b"),
        )
        self.assertNotIn("DROP ", combined)

    def test_downgrade_removes_only_the_two_named_constraints(self):
        migration = _load_migration()
        executed = []

        with mock.patch.object(
            migration.op, "execute", side_effect=executed.append,
        ):
            migration.downgrade()

        self.assertEqual(len(executed), 2)
        combined = "\n".join(_normalized(sql) for sql in executed)
        self.assertIn(
            "ALTER TABLE public.warehouse_invoices DROP CONSTRAINT IF EXISTS "
            "fk_a11_warehouse_invoices_supplier_invoice",
            combined,
        )
        self.assertIn(
            "ALTER TABLE public.supplier_invoices DROP CONSTRAINT IF EXISTS "
            "fk_a11_supplier_invoices_warehouse_invoice",
            combined,
        )
        self.assertNotRegex(
            combined.upper(),
            re.compile(r"\b(DROP TABLE|DROP COLUMN|INSERT|UPDATE|DELETE FROM)\b"),
        )


if __name__ == "__main__":
    unittest.main()
