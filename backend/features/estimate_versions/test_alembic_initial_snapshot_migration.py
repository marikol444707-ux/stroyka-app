import importlib.util
import json
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
    / "0004_active_estimate_initial_snapshots.py"
)
MIGRATION_README_PATH = PROJECT_ROOT / "migrations" / "README.md"


def _load_migration(fake_op):
    spec = importlib.util.spec_from_file_location(
        "migration_0004_active_estimate_initial_snapshots",
        MIGRATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op
    with mock.patch.dict(sys.modules, {"alembic": fake_alembic}):
        spec.loader.exec_module(module)
    return module


class FakeResult:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)


class FakeBind:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def exec_driver_sql(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, params))
        if normalized.startswith("SELECT e.id"):
            return FakeResult(self.rows)
        return FakeResult()


class ActiveEstimateInitialSnapshotMigrationTests(unittest.TestCase):
    def test_upgrade_adds_hash_guards_and_backfills_only_selected_missing_rows(self):
        sections = [{
            "name": "Раздел",
            "items": [{
                "name": "Работа",
                "quantity": 2,
                "priceWork": 125,
                "priceMaterial": 25,
            }],
        }]
        bind = FakeBind([{
            "id": 17,
            "version": "2.0",
            "sections_json": json.dumps(sections, ensure_ascii=False),
        }])
        executed = []
        fake_op = types.SimpleNamespace(
            execute=executed.append,
            get_bind=lambda: bind,
        )
        migration = _load_migration(fake_op)

        migration.upgrade()

        self.assertEqual(migration.revision, "0004_active_estimate_snapshots")
        self.assertEqual(migration.down_revision, "0003_accounting_link_integrity")
        ddl = "\n".join(str(sql) for sql in executed)
        self.assertIn("ADD COLUMN IF NOT EXISTS sections_sha256", ddl)
        self.assertIn("chk_estimate_versions_sections_sha256", ddl)
        self.assertIn("uq_estimate_versions_estimate_sections_sha256", ddl)

        select_sql = next(sql for sql, _params in bind.calls if sql.startswith("SELECT e.id"))
        self.assertIn("e.status='Активная'", select_sql)
        self.assertIn("COALESCE(e.smeta_type,'Заказчик')='Заказчик'", select_sql)
        self.assertIn("COALESCE(e.is_template,FALSE)=FALSE", select_sql)
        self.assertIn("NOT EXISTS", select_sql)

        insert_sql, insert_params = next(
            call for call in bind.calls
            if call[0].startswith("INSERT INTO public.estimate_versions")
        )
        self.assertIn("ON CONFLICT DO NOTHING", insert_sql)
        self.assertEqual(insert_params["estimate_id"], 17)
        self.assertEqual(insert_params["version_label"], "2.0")
        self.assertEqual(str(insert_params["total"]), "300")
        self.assertRegex(insert_params["sections_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            insert_params["comment"],
            "Автоматическая исходная версия активной сметы",
        )
        self.assertEqual(insert_params["created_by"], "system:migration:0004")

    def test_downgrade_never_deletes_immutable_business_snapshots(self):
        bind = FakeBind([])
        executed = []
        migration = _load_migration(types.SimpleNamespace(
            execute=executed.append,
            get_bind=lambda: bind,
        ))

        migration.downgrade()

        combined = "\n".join(str(sql) for sql in executed) + "\n" + "\n".join(
            sql for sql, _params in bind.calls
        )
        self.assertNotRegex(combined.upper(), r"\b(DELETE|DROP|TRUNCATE)\b")

    def test_migration_is_documented(self):
        readme = MIGRATION_README_PATH.read_text(encoding="utf-8")
        self.assertIn("0004_active_estimate_snapshots", readme)


if __name__ == "__main__":
    unittest.main()
