import ast
import importlib.util
import unittest
from pathlib import Path

from backend.features.explicit_company.company_backfill import (
    DROP_DEFAULTS_SQL,
    TABLES,
    apply_backfill,
    plan_backfill,
    unique_project_company_id,
)


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "0123_explicit_company_owner.py"
BACKFILL = ROOT / "backend" / "features" / "explicit_company" / "company_backfill.py"
MAIN = ROOT / "backend" / "main.py"


def projects_for(*rows):
    return [{"id": row[0], "company_id": row[1], "name": row[2]} for row in rows]


class ExplicitCompanyBackfillTests(unittest.TestCase):
    def test_original_company_keeps_blank_rows_when_other_companies_have_no_projects(self):
        tables = {
            "work_journal": [{"id": 1, "project": "Лицей", "company_id": None}],
            "materials": [{"id": 2, "project": "", "company_id": None}],
            "staff": [{"id": 3, "company_id": None, "name": "Иванов"}],
            "users": [{"id": 4, "company_id": 9}],
        }
        plan = plan_backfill(
            [{"id": 7, "name": "АльянсСтрой"}, {"id": 1, "name": "Новая"}],
            projects_for((12, 7, "Лицей")),
            tables,
        )
        assigned = {(row["table"], row["id"]): row["company_id"] for row in plan["assignments"]}
        self.assertEqual(plan["legacyCompanyId"], 7)
        self.assertEqual(assigned[("work_journal", 1)], 7)
        self.assertEqual(assigned[("materials", 2)], 7)
        self.assertEqual(assigned[("staff", 3)], 7)
        self.assertNotIn(("users", 4), assigned)
        self.assertNotIn(1, assigned.values())

    def test_exact_project_name_wins_and_a_shared_name_stays_hidden(self):
        tables = {
            "work_journal": [
                {"id": 1, "project": "Склад", "company_id": None},
                {"id": 2, "project": "Объект", "company_id": None},
                {"id": 3, "project": "Склад", "company_id": 7},
            ],
            "supplier_offers": [
                {"id": 8, "company_id": None, "request_id": 5},
                {"id": 9, "company_id": None, "request_id": None},
            ],
            "supply_requests": [{"id": 5, "project": "Склад", "company_id": 7}],
        }
        plan = plan_backfill(
            [{"id": 7, "name": "АльянсСтрой"}, {"id": 3, "name": "Другая"}],
            projects_for((12, 7, "Склад"), (20, 3, "Цех"), (21, 3, "Объект"), (22, 7, "Объект")),
            tables,
        )
        assigned = {(row["table"], row["id"]): row["company_id"] for row in plan["assignments"]}
        self.assertIsNone(plan["legacyCompanyId"])
        self.assertEqual(assigned[("work_journal", 1)], 7)
        self.assertNotIn(("work_journal", 2), assigned)
        self.assertNotIn(("work_journal", 3), assigned)
        self.assertEqual(plan["counts"]["work_journal"]["alreadyOwned"], 1)
        self.assertEqual(assigned[("supplier_offers", 8)], 7)
        self.assertNotIn(("supplier_offers", 9), assigned)
        self.assertIn("Объект", plan["ambiguousNames"])

    def test_same_project_name_does_not_cross_into_another_company(self):
        rows = [{"company_id": 7}, {"company_id": 3}]
        self.assertIsNone(unique_project_company_id(rows))
        self.assertEqual(unique_project_company_id([{"company_id": 7}, {"company_id": 7}]), 7)

    def test_person_name_is_not_a_source_of_ownership(self):
        source = BACKFILL.read_text(encoding="utf-8")
        self.assertNotIn("master_name", source)
        self.assertNotIn("created_by", source)
        self.assertNotIn("FROM users", source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)
        self.assertNotIn("DEFAULT 1", DROP_DEFAULTS_SQL)
        for table in TABLES:
            self.assertIn("'" + table + "'", DROP_DEFAULTS_SQL)

    def test_startup_schema_no_longer_defaults_company_to_one(self):
        source = MAIN.read_text(encoding="utf-8")
        self.assertNotIn("company_id INT DEFAULT 1", source)
        self.assertNotIn("company_id INT NOT NULL DEFAULT 1", source)
        self.assertNotIn("ALTER COLUMN company_id SET DEFAULT 1", source)
        self.assertNotIn("SET company_id=1 WHERE company_id IS NULL", source)
        self.assertIn("DROP_DEFAULTS_SQL", source)

    def test_migration_is_the_single_head(self):
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('revision = "0123_explicit_company_owner"', source)
        self.assertIn('down_revision = "0122_field_record_owners"', source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)
        tree = ast.parse(source)
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        self.assertIsInstance(downgrade.body[0], ast.Raise)
        spec = importlib.util.spec_from_file_location("explicit_company_owner", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0123_explicit_company_owner")
        self.assertLessEqual(len(module.revision), 32)
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        graph = ScriptDirectory.from_config(config)
        self.assertEqual(graph.get_heads(), ["0123_explicit_company_owner"])

    def test_apply_updates_only_blank_rows(self):
        class Cursor:
            def __init__(self):
                self.updates = []
                self.last = ""

            def execute(self, sql, params=()):
                self.last = " ".join(sql.split())
                self.updates.append((self.last, tuple(params)))

            def fetchall(self):
                sql = self.last
                if "FROM information_schema.tables" in sql:
                    return [(name,) for name in TABLES]
                if "FROM information_schema.columns" in sql:
                    return [(name,) for name in TABLES]
                if sql.startswith("SELECT id FROM companies"):
                    return [(7,), (1,)]
                if "FROM projects" in sql:
                    return [(12, 7, "Лицей")]
                if "FROM work_journal" in sql:
                    return [(1, None, "Лицей"), (2, 7, "Лицей")]
                if "FROM staff" in sql:
                    return [(3, None)]
                if "FROM supplier_offers" in sql:
                    return []
                if "FROM warehouse_movements" in sql:
                    return []
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=True)
        updates = [item for item in cursor.updates if item[0].startswith("UPDATE")]
        self.assertEqual(plan["legacyCompanyId"], 7)
        self.assertEqual(plan["applied"], len(updates))
        self.assertIn(
            ("UPDATE work_journal SET company_id=%s WHERE id=%s AND company_id IS NULL", (7, 1)),
            updates,
        )
        self.assertNotIn(2, [params[1] for _sql, params in updates if params and params[0] == 7 and _sql.startswith("UPDATE work_journal")])
        self.assertTrue(any(params == (7, 3) for _sql, params in updates))


if __name__ == "__main__":
    unittest.main()
