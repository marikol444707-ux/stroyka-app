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


def projects():
    return [
        {"id": 10, "company_id": 2, "name": "Объект"},
        {"id": 11, "company_id": 4, "name": "Объект"},
        {"id": 12, "company_id": 2, "name": "Склад"},
        {"id": 13, "company_id": None, "name": "Пустой"},
        {"id": 14, "company_id": 4, "name": "Цех"},
    ]


def creators():
    return [
        {"name": "Анна", "company_id": 2},
        {"name": "Борис", "company_id": 2},
        {"name": "Борис", "company_id": 4},
        {"name": "Вера", "company_id": 4},
    ]


def tool(row_id, project="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "project": project, "company_id": company_id,
        "project_id": project_id, "owner_scope": owner_scope,
    }


def history(row_id, tool_id, project="", created_by="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "tool_id": tool_id, "project": project, "created_by": created_by,
        "company_id": company_id, "project_id": project_id, "owner_scope": owner_scope,
    }


def inventory(row_id, project="", created_by="", company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "project": project, "created_by": created_by,
        "company_id": company_id, "project_id": project_id, "owner_scope": owner_scope,
    }


def item(row_id, inventory_id, company_id=None, project_id=None, owner_scope=None):
    return {
        "id": row_id, "inventory_id": inventory_id, "company_id": company_id,
        "project_id": project_id, "owner_scope": owner_scope,
    }


def empty_tables():
    return {"tools": [], "tool_history": [], "inventory": [], "inventory_items": []}


class ToolInventoryBackfillTest(unittest.TestCase):
    def test_same_project_name_in_two_companies_stays_unowned(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, "Объект"), tool(2, "Склад"), tool(3, "Нет такого"), tool(4, "   ")]
        tables["inventory"] = [inventory(5, "Склад", "Анна"), inventory(6, "Объект", "Анна")]
        plan = plan_backfill(projects(), creators(), tables)
        assigned = {(row["table"], row["id"]): (row["company_id"], row["project_id"]) for row in plan["assignments"]}
        self.assertNotIn(("tools", 1), assigned)
        self.assertEqual(assigned[("tools", 2)], (2, 12))
        self.assertNotIn(("tools", 3), assigned)
        self.assertNotIn(("tools", 4), assigned)
        self.assertEqual(plan["counts"]["tools"]["ambiguous"], 1)
        self.assertEqual(plan["counts"]["tools"]["unknown"], 2)
        self.assertEqual(assigned[("inventory", 5)], (2, 12))
        self.assertNotIn(("inventory", 6), assigned)
        self.assertEqual(plan["counts"]["inventory"]["conflict"], 0)
        self.assertEqual(plan["counts"]["inventory"]["ambiguous"], 1)
        self.assertIn("Объект", plan["ambiguousNames"])

    def test_creator_in_another_company_blocks_a_unique_project(self):
        tables = empty_tables()
        tables["inventory"] = [inventory(1, "Склад", "Вера"), inventory(2, "Склад", "Неизвестный")]
        plan = plan_backfill(projects(), creators(), tables)
        assigned = {row["id"]: row for row in plan["assignments"]}
        self.assertNotIn(1, assigned)
        self.assertEqual(plan["counts"]["inventory"]["conflict"], 1)
        self.assertEqual((assigned[2]["company_id"], assigned[2]["project_id"]), (2, 12))

    def test_blank_project_uses_a_creator_from_exactly_one_company(self):
        tables = empty_tables()
        tables["inventory"] = [
            inventory(1, "", "Анна"),
            inventory(2, "   ", "Борис"),
            inventory(3, "", "Никто"),
        ]
        tables["tool_history"] = [history(8, None, "", "Анна")]
        plan = plan_backfill(projects(), creators(), tables)
        assigned = {(row["table"], row["id"]): row for row in plan["assignments"]}
        inventory_owner = assigned[("inventory", 1)]
        self.assertEqual((inventory_owner["owner_scope"], inventory_owner["company_id"], inventory_owner["project_id"]), ("company", 2, None))
        self.assertNotIn(("inventory", 2), assigned)
        self.assertNotIn(("inventory", 3), assigned)
        history_owner = assigned[("tool_history", 8)]
        self.assertEqual((history_owner["owner_scope"], history_owner["company_id"]), ("company", 2))

    def test_history_and_items_follow_the_owner_their_parent_will_receive(self):
        tables = empty_tables()
        tables["tools"] = [tool(1, "Склад"), tool(2, "Объект")]
        tables["tool_history"] = [
            history(3, 1, "Склад"),
            history(4, 1, "Цех"),
            history(5, 2, "Объект", "Анна"),
        ]
        tables["inventory"] = [inventory(6, "Склад", "Анна")]
        tables["inventory_items"] = [item(7, 6), item(8, 99)]
        plan = plan_backfill(projects(), creators(), tables)
        assigned = {(row["table"], row["id"]): (row["owner_scope"], row["company_id"], row["project_id"]) for row in plan["assignments"]}
        self.assertEqual(assigned[("tools", 1)], ("project", 2, 12))
        self.assertEqual(assigned[("tool_history", 3)], ("project", 2, 12))
        self.assertNotIn(("tool_history", 4), assigned)
        self.assertEqual(plan["counts"]["tool_history"]["conflict"], 1)
        self.assertNotIn(("tools", 2), assigned)
        self.assertNotIn(("tool_history", 5), assigned)
        self.assertEqual(plan["counts"]["tool_history"]["parentUnowned"], 1)
        self.assertEqual(assigned[("inventory_items", 7)], ("project", 2, 12))
        self.assertNotIn(("inventory_items", 8), assigned)

    def test_existing_and_partial_owners_are_not_replaced(self):
        tables = empty_tables()
        tables["tools"] = [
            tool(1, "Склад", company_id=4, project_id=14, owner_scope="project"),
            tool(2, "Склад", company_id=2),
        ]
        tables["inventory"] = [inventory(3, "", "Анна", company_id=4, owner_scope="company")]
        plan = plan_backfill(projects(), creators(), tables)
        self.assertEqual(plan["assignments"], [])
        self.assertEqual(plan["counts"]["tools"]["alreadyOwned"], 1)
        self.assertEqual(plan["counts"]["tools"]["partial"], 1)
        self.assertEqual(plan["counts"]["inventory"]["alreadyOwned"], 1)

    def test_apply_updates_only_unowned_rows(self):
        class Cursor:
            def __init__(self):
                self.updates = []
                self.last = ""

            def execute(self, sql, params=()):
                self.last = " ".join(sql.split())
                self.updates.append((self.last, tuple(params)))

            def fetchall(self):
                sql = self.last
                if "FROM projects" in sql:
                    return [(12, 2, "Склад"), (10, 2, "Объект"), (11, 4, "Объект")]
                if "FROM users" in sql:
                    return [("Анна", 2)]
                if "FROM tools" in sql:
                    return [
                        (1, "Склад", None, None, None),
                        (2, "Объект", None, None, None),
                        (3, "Склад", "project", 2, 12),
                    ]
                if "FROM tool_history" in sql:
                    return [(4, 1, "Склад", "", None, None, None)]
                if "FROM inventory " in sql or sql.rstrip().endswith("FROM inventory"):
                    return [(5, "", "Анна", None, None, None)]
                if "FROM inventory_items" in sql:
                    return [(6, 5, None, None, None)]
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=True)
        updates = [item for item in cursor.updates if item[0].startswith("UPDATE")]
        self.assertEqual(updates, [
            (
                "UPDATE tools SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("project", 2, 12, 1),
            ),
            (
                "UPDATE tool_history SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("project", 2, 12, 4),
            ),
            (
                "UPDATE inventory SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("company", 2, None, 5),
            ),
            (
                "UPDATE inventory_items SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                ("company", 2, None, 6),
            ),
        ])
        self.assertEqual(plan["applied"], 4)
        self.assertIn("Объект", plan["ambiguousNames"])

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
