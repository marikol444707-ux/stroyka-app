import ast
import importlib.util
import unittest
from pathlib import Path

from backend.features.inventory_ownership.company_backfill import (
    ADD_COLUMNS_SQL,
    CONSTRAINTS_SQL,
    TABLES,
    apply_backfill,
    plan_backfill,
)


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "0121_tool_inventory_owners.py"
BACKFILL = ROOT / "backend" / "features" / "inventory_ownership" / "company_backfill.py"


def tool(row_id, project="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "project": project, "company_id": company_id,
        "project_id": project_id, "owner_scope": owner_scope,
    }


def history(row_id, tool_id, project="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "tool_id": tool_id, "project": project,
        "company_id": company_id, "project_id": project_id, "owner_scope": owner_scope,
    }


def inventory(row_id, project="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "project": project, "company_id": company_id,
        "project_id": project_id, "owner_scope": owner_scope,
    }


def item(row_id, inventory_id, company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "inventory_id": inventory_id, "company_id": company_id,
        "project_id": project_id, "owner_scope": owner_scope,
    }


def empty_tables():
    return {"tools": [], "tool_history": [], "inventory": [], "inventory_items": []}


def only_company(company_id=1):
    return [{"id": company_id}]


def projects_for(*rows):
    return [{"id": project_id, "company_id": company_id, "name": name} for project_id, company_id, name in rows]


class ToolInventoryBackfillTest(unittest.TestCase):
    def test_single_company_keeps_every_legacy_row_and_a_second_company_does_not_receive_it(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, "Склад"), tool(2, ""), tool(3, "Объект")]
        tables["tool_history"] = [history(4, 1, "Склад"), history(5, 2, "")]
        tables["inventory"] = [inventory(6, "Склад"), inventory(7, "")]
        tables["inventory_items"] = [item(8, 6), item(9, 7)]
        plan = plan_backfill(only_company(1), projects_for((12, 1, "Склад"), (13, 1, "Объект")), tables)
        assigned = {(row["table"], row["id"]): (row["company_id"], row["project_id"], row["owner_scope"]) for row in plan["assignments"]}
        self.assertEqual(plan["legacyCompanyId"], 1)
        self.assertEqual(assigned[("tools", 1)], (1, 12, "project"))
        self.assertEqual(assigned[("tools", 2)], (1, None, "company"))
        self.assertEqual(assigned[("tools", 3)], (1, 13, "project"))
        self.assertTrue(all(owner[0] == 1 for owner in assigned.values()))
        self.assertNotIn(2, {owner[0] for owner in assigned.values()})
        self.assertEqual(assigned[("inventory", 6)][0], 1)
        self.assertEqual(assigned[("inventory_items", 8)][0], 1)
        self.assertEqual(assigned[("tool_history", 4)][0], 1)

    def test_newer_company_with_its_own_project_does_not_receive_the_original_blank_rows(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, ""), tool(2, "Склад"), tool(3, "Цех"), tool(4, "Объект")]
        tables["inventory"] = [inventory(5, "Склад")]
        companies = [{"id": 1}, {"id": 5}]
        projects = projects_for((12, 1, "Склад"), (13, 1, "Объект"), (90, 5, "Цех"), (91, 5, "Объект"))
        plan = plan_backfill(companies, projects, tables)
        assigned = {row["id"]: row for row in plan["assignments"] if row["table"] == "tools"}
        self.assertIsNone(plan["legacyCompanyId"])
        self.assertNotIn(1, assigned)
        self.assertEqual((assigned[2]["company_id"], assigned[2]["project_id"]), (1, 12))
        self.assertEqual((assigned[3]["company_id"], assigned[3]["project_id"]), (5, 90))
        self.assertNotIn(4, assigned)
        self.assertIn("Объект", plan["ambiguousNames"])
        inventory_owner = next(row for row in plan["assignments"] if row["table"] == "inventory")
        self.assertEqual(inventory_owner["company_id"], 1)
        self.assertNotEqual(inventory_owner["company_id"], 5)

    def test_empty_extra_company_does_not_take_the_original_warehouse(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, ""), tool(2, "Склад")]
        tables["tool_history"] = [history(3, 1, "")]
        tables["inventory"] = [inventory(4, "")]
        tables["inventory_items"] = [item(5, 4)]
        plan = plan_backfill([{"id": 1}, {"id": 5}], projects_for((12, 1, "Склад")), tables)
        self.assertEqual(plan["legacyCompanyId"], 1)
        self.assertTrue(all(row["company_id"] == 1 for row in plan["assignments"]))
        self.assertFalse(any(row["company_id"] == 5 for row in plan["assignments"]))

    def test_creator_name_is_not_a_source_of_ownership(self):
        source = BACKFILL.read_text(encoding="utf-8")
        self.assertNotIn("created_by", source)
        self.assertNotIn("FROM users", source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)

    def test_children_copy_only_an_owner_the_parent_already_stores(self):
        tables = empty_tables()
        tables["tools"] = [
            tool(1, "Склад", company_id=2, project_id=12, owner_scope="project"),
            tool(2, "Объект"),
        ]
        tables["tool_history"] = [
            history(3, 1, "Склад"),
            history(4, 1, ""),
            history(5, 1, "Цех"),
            history(6, 2, "Объект"),
        ]
        tables["inventory"] = [
            inventory(7, "Склад", company_id=2, project_id=12, owner_scope="project"),
            inventory(8, "Склад"),
        ]
        tables["inventory_items"] = [item(9, 7), item(10, 8), item(11, 99)]
        plan = plan_backfill([{"id": 2}, {"id": 4}], [], tables)
        assigned = {(row["table"], row["id"]): (row["owner_scope"], row["company_id"], row["project_id"]) for row in plan["assignments"]}
        self.assertEqual(assigned[("tool_history", 3)], ("project", 2, 12))
        self.assertEqual(assigned[("tool_history", 4)], ("project", 2, 12))
        self.assertNotIn(("tool_history", 5), assigned)
        self.assertEqual(plan["counts"]["tool_history"]["conflict"], 1)
        self.assertNotIn(("tools", 2), assigned)
        self.assertNotIn(("tool_history", 6), assigned)
        self.assertEqual(plan["counts"]["tool_history"]["parentUnowned"], 1)
        self.assertEqual(assigned[("inventory_items", 9)], ("project", 2, 12))
        self.assertNotIn(("inventory_items", 10), assigned)
        self.assertEqual(plan["counts"]["inventory_items"]["parentUnowned"], 1)
        self.assertNotIn(("inventory_items", 11), assigned)
        self.assertEqual(plan["counts"]["tools"]["alreadyOwned"], 1)
        self.assertEqual(plan["counts"]["tools"]["unknown"], 1)

    def test_partial_owner_is_not_replaced_or_copied(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, "Склад", company_id=2)]
        tables["tool_history"] = [history(2, 1, "Склад")]
        tables["inventory"] = [inventory(3, "Склад", company_id=4, project_id=14, owner_scope="project")]
        plan = plan_backfill([{"id": 2}, {"id": 4}], [], tables)
        self.assertEqual(plan["assignments"], [])
        self.assertEqual(plan["counts"]["tools"]["partial"], 1)
        self.assertEqual(plan["counts"]["tool_history"]["parentUnowned"], 1)
        self.assertEqual(plan["counts"]["inventory"]["alreadyOwned"], 1)

    def test_apply_updates_only_child_rows_of_a_stored_owner(self):
        class Cursor:
            def __init__(self):
                self.updates = []
                self.last = ""

            def execute(self, sql, params=()):
                self.last = " ".join(sql.split())
                self.updates.append((self.last, tuple(params)))

            def fetchall(self):
                sql = self.last
                if "FROM tools" in sql:
                    return [
                        (1, "Склад", "project", 2, 12),
                        (2, "Склад", None, None, None),
                    ]
                if "FROM tool_history" in sql:
                    return [
                        (4, 1, "Склад", None, None, None),
                        (5, 2, "Склад", None, None, None),
                    ]
                if sql.rstrip().endswith("FROM inventory"):
                    return [(6, "Склад", "company", 2, None)]
                if "FROM inventory_items" in sql:
                    return [(7, 6, None, None, None)]
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=True)
        updates = [item for item in cursor.updates if item[0].startswith("UPDATE")]
        self.assertEqual(updates, [
            (
                "UPDATE tool_history SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("project", 2, 12, 4),
            ),
            (
                "UPDATE inventory_items SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("company", 2, None, 7),
            ),
        ])
        self.assertEqual(plan["applied"], 2)
        self.assertFalse(any("UPDATE tools" in sql for sql, _params in updates))
        self.assertFalse(any(sql.startswith("UPDATE inventory ") for sql, _params in updates))

    def test_preview_does_not_write(self):
        class Cursor:
            def __init__(self):
                self.statements = []

            def execute(self, sql, params=()):
                self.statements.append(sql)

            def fetchall(self):
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=False)
        self.assertEqual(plan["applied"], 0)
        self.assertFalse(any(sql.strip().upper().startswith("UPDATE") for sql in cursor.statements))

    def test_migration_is_the_single_next_head_and_does_not_guess_company_one(self):
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('revision = "0121_tool_inventory_owners"', source)
        self.assertIn('down_revision = "0120_crm_lead_utm"', source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", source)
        self.assertNotIn("created_by", source)
        self.assertNotIn("DEFAULT 1", ADD_COLUMNS_SQL)
        for table in TABLES:
            self.assertIn(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER", ADD_COLUMNS_SQL)
            self.assertIn(f"ck_{table}_owner", CONSTRAINTS_SQL)
            self.assertIn(f"idx_{table}_owner", CONSTRAINTS_SQL)
        tree = ast.parse(source)
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        self.assertIsInstance(downgrade.body[0], ast.Raise)
        spec = importlib.util.spec_from_file_location("tool_inventory_owners", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0121_tool_inventory_owners")
        self.assertEqual(module.down_revision, "0120_crm_lead_utm")
        self.assertLessEqual(len(module.revision), 32)

        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        graph = ScriptDirectory.from_config(config)
        self.assertEqual(graph.get_heads(), ["0121_tool_inventory_owners"])


if __name__ == "__main__":
    unittest.main()
