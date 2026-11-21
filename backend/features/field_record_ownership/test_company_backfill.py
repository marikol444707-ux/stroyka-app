import ast
import importlib.util
import unittest
from pathlib import Path

from backend.features.field_record_ownership.company_backfill import (
    ADD_COLUMNS_SQL,
    CONSTRAINTS_SQL,
    TABLES,
    apply_backfill,
    plan_backfill,
)


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "0122_field_record_owners.py"
BACKFILL = ROOT / "backend" / "features" / "field_record_ownership" / "company_backfill.py"


def owned(row_id, **extra):
    base = {"id": row_id, "company_id": None, "project_id": None, "owner_scope": None}
    base.update(extra)
    return base


def empty():
    return {table: [] for table in TABLES}


def only_company(company_id=1):
    return [{"id": company_id}]


def projects_for(*rows):
    return [{"id": project_id, "company_id": company_id, "name": name} for project_id, company_id, name in rows]


class FieldRecordBackfillTest(unittest.TestCase):
    def test_single_company_keeps_every_legacy_row_for_the_original_company(self):
        tables = empty()
        tables["contracts"] = [owned(1, project="Склад"), owned(2, project=""), owned(3, project="Объект")]
        tables["piecework"] = [owned(4, project="Склад"), owned(5, project="")]
        tables["project_checklists"] = [owned(6, project_name="Склад", project_id=12), owned(7, project_name="")]
        tables["checklist_items"] = [owned(8, checklist_id=6), owned(9, checklist_id=7)]
        tables["material_inspection_journal"] = [owned(10, project_name="Склад"), owned(11, project_name="")]
        tables["cable_journal"] = [owned(12, project_name="Объект")]
        tables["material_aliases"] = [owned(13, project_name=""), owned(14, project_name="Склад")]
        plan = plan_backfill(only_company(1), projects_for((12, 1, "Склад"), (13, 1, "Объект")), tables)
        assigned = {(row["table"], row["id"]): row["company_id"] for row in plan["assignments"]}
        self.assertEqual(plan["legacyCompanyId"], 1)
        self.assertTrue(assigned)
        self.assertTrue(all(company_id == 1 for company_id in assigned.values()))
        self.assertEqual(assigned[("contracts", 1)], 1)
        self.assertEqual(assigned[("piecework", 5)], 1)
        self.assertEqual(assigned[("material_inspection_journal", 11)], 1)
        self.assertEqual(assigned[("cable_journal", 12)], 1)
        self.assertEqual(assigned[("material_aliases", 13)], 1)
        self.assertEqual(assigned[("checklist_items", 8)], 1)

    def test_same_project_name_in_two_companies_stays_hidden(self):
        tables = empty()
        tables["contracts"] = [owned(1, project=""), owned(2, project="Склад"), owned(3, project="Объект")]
        tables["piecework"] = [owned(4, project="Объект")]
        tables["material_inspection_journal"] = [owned(5, project_name="Объект")]
        tables["material_aliases"] = [owned(6, project_name="Объект")]
        companies = [{"id": 1}, {"id": 5}]
        projects = projects_for((12, 1, "Склад"), (13, 1, "Объект"), (90, 5, "Цех"), (91, 5, "Объект"))
        plan = plan_backfill(companies, projects, tables)
        assigned = {(row["table"], row["id"]): row["company_id"] for row in plan["assignments"]}
        self.assertIsNone(plan["legacyCompanyId"])
        self.assertNotIn(("contracts", 1), assigned)
        self.assertEqual(assigned[("contracts", 2)], 1)
        self.assertNotIn(("contracts", 3), assigned)
        self.assertNotIn(("piecework", 4), assigned)
        self.assertNotIn(("material_inspection_journal", 5), assigned)
        self.assertNotIn(("material_aliases", 6), assigned)
        self.assertIn("Объект", plan["ambiguousNames"])

    def test_empty_extra_company_does_not_take_the_original_rows(self):
        tables = empty()
        tables["contracts"] = [owned(1, project=""), owned(2, project="Склад")]
        tables["cable_journal"] = [owned(3, project_name="")]
        plan = plan_backfill([{"id": 1}, {"id": 5}], projects_for((12, 1, "Склад")), tables)
        self.assertEqual(plan["legacyCompanyId"], 1)
        self.assertTrue(all(row["company_id"] == 1 for row in plan["assignments"]))
        self.assertFalse(any(row["company_id"] == 5 for row in plan["assignments"]))

    def test_ambiguous_piecework_keeps_the_linked_journal_company(self):
        tables = empty()
        tables["piecework"] = [owned(4, project="Объект", work_journal_id=9), owned(5, project="Цех", work_journal_id=9)]
        tables["work_journal"] = [{"id": 9, "company_id": 1, "project": "Объект"}]
        plan = plan_backfill(
            [{"id": 1}, {"id": 5}],
            projects_for((12, 1, "Объект"), (91, 5, "Объект"), (90, 5, "Цех")),
            tables,
        )
        assigned = {row["id"]: row for row in plan["assignments"] if row["table"] == "piecework"}
        self.assertEqual((assigned[4]["company_id"], assigned[4]["project_id"], assigned[4]["owner_scope"]), (1, 12, "project"))
        self.assertNotIn(5, assigned)
        self.assertEqual(plan["counts"]["piecework"]["conflict"], 1)

    def test_a_row_that_already_has_a_company_keeps_it(self):
        tables = empty()
        tables["material_inspection_journal"] = [
            owned(1, project_name="Склад", company_id=1, project_id=12),
            owned(2, project_name="Склад", company_id=4, project_id=90, owner_scope="project"),
        ]
        tables["contracts"] = [owned(3, project="Склад", company_id=4, project_id=90, owner_scope="project")]
        plan = plan_backfill([{"id": 1}, {"id": 4}], projects_for((12, 1, "Склад"), (90, 4, "Склад")), tables)
        self.assertEqual(plan["assignments"], [])
        self.assertEqual(len(plan["scopeFills"]), 1)
        self.assertEqual(plan["scopeFills"][0]["company_id"], 1)
        self.assertEqual(plan["counts"]["material_inspection_journal"]["alreadyOwned"], 2)
        self.assertEqual(plan["counts"]["contracts"]["alreadyOwned"], 1)

    def test_checklist_project_link_wins_when_the_name_is_shared(self):
        tables = empty()
        tables["project_checklists"] = [owned(1, project_name="Объект", project_id=12)]
        tables["checklist_items"] = [owned(2, checklist_id=1)]
        plan = plan_backfill(
            [{"id": 1}, {"id": 5}],
            projects_for((12, 1, "Объект"), (91, 5, "Объект")),
            tables,
        )
        assigned = {(row["table"], row["id"]): (row["company_id"], row["project_id"]) for row in plan["assignments"]}
        self.assertEqual(assigned[("project_checklists", 1)], (1, 12))
        self.assertEqual(assigned[("checklist_items", 2)], (1, 12))

    def test_person_name_is_not_a_source_of_ownership(self):
        source = BACKFILL.read_text(encoding="utf-8")
        self.assertNotIn("master_name", source)
        self.assertNotIn("created_by", source)
        self.assertNotIn("FROM users", source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)

    def test_migration_is_the_single_head_and_does_not_guess_company_one(self):
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('revision = "0122_field_record_owners"', source)
        self.assertIn('down_revision = "0121_tool_inventory_owners"', source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)
        self.assertNotIn("created_by", source)
        self.assertIn("ck_contracts_owner", CONSTRAINTS_SQL)
        self.assertIn("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS company_id INTEGER", ADD_COLUMNS_SQL)
        self.assertNotIn("DEFAULT 1", ADD_COLUMNS_SQL)
        tree = ast.parse(source)
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        self.assertIsInstance(downgrade.body[0], ast.Raise)
        spec = importlib.util.spec_from_file_location("field_record_owners", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0122_field_record_owners")
        self.assertLessEqual(len(module.revision), 32)
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        graph = ScriptDirectory.from_config(config)
        self.assertEqual(graph.get_heads(), ["0122_field_record_owners"])

    def test_apply_labels_an_existing_journal_and_assigns_only_blank_rows(self):
        class Cursor:
            def __init__(self):
                self.updates = []
                self.last = ""

            def execute(self, sql, params=()):
                self.last = " ".join(sql.split())
                self.updates.append((self.last, tuple(params)))

            def fetchall(self):
                sql = self.last
                if sql.startswith("SELECT id FROM companies"):
                    return [(1,), (4,)]
                if "FROM projects" in sql:
                    return [(12, 1, "Склад"), (90, 4, "Цех")]
                if "FROM contracts" in sql:
                    return [(1, "Склад", None, None, None)]
                if "FROM piecework" in sql:
                    return []
                if "FROM project_checklists" in sql:
                    return []
                if "FROM checklist_items" in sql:
                    return []
                if "FROM material_inspection_journal" in sql:
                    return [(7, "Лицей", None, 1, 12)]
                if "FROM cable_journal" in sql:
                    return []
                if "FROM material_aliases" in sql:
                    return [(8, "", None, None, None)]
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=True)
        updates = [item for item in cursor.updates if item[0].startswith("UPDATE")]
        self.assertEqual(plan["applied"], len(updates))
        self.assertIn(
            ("UPDATE material_inspection_journal SET owner_scope=%s WHERE id=%s AND owner_scope IS NULL AND company_id=%s AND project_id IS NOT DISTINCT FROM %s",
             ("project", 7, 1, 12)),
            updates,
        )
        self.assertTrue(any(sql.startswith("UPDATE contracts") and params[1] == 1 for sql, params in updates))
        self.assertFalse(any(sql.startswith("UPDATE material_aliases") for sql, _params in updates))
        self.assertFalse(any(params[1] == 4 for _sql, params in updates))


if __name__ == "__main__":
    unittest.main()
