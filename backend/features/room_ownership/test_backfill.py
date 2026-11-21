import ast
import unittest
from pathlib import Path

import importlib.util

from backend.features.room_ownership.backfill import (
    ADD_COLUMNS_SQL,
    CONSTRAINTS_SQL,
    TABLE_NAMES,
    apply_backfill,
    plan_backfill,
)


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "0119_room_measurement_owners.py"


def projects():
    return [
        {"id": 10, "company_id": 2, "name": "Объект"},
        {"id": 11, "company_id": 3, "name": "Объект"},
        {"id": 12, "company_id": 2, "name": "Склад"},
        {"id": 13, "company_id": None, "name": "Пустой"},
        {"id": 14, "company_id": 3, "name": "Цех"},
    ]


def row(row_id, name=None, company_id=None, project_id=None, parent_id=None):
    return {
        "id": row_id,
        "name": name,
        "company_id": company_id,
        "project_id": project_id,
        "parent_id": parent_id,
    }


class RoomOwnershipBackfillTest(unittest.TestCase):
    def test_same_name_in_two_companies_stays_unowned(self):
        tables = {
            "rooms": [row(1, "Объект"), row(2, "Склад"), row(3, "Нет такого"), row(4, "   ")],
            "project_measurements": [row(5, "Склад")],
            "room_works": [
                row(6, "Склад", parent_id=1),
                row(7, "Склад", parent_id=2),
                row(8, "Цех", parent_id=2),
            ],
            "measurement_room_drafts": [row(9, "Склад", parent_id=5)],
            "room_windows": [row(10, parent_id=1), row(11, parent_id=2), row(12, parent_id=99)],
            "room_doors": [row(13, parent_id=2)],
        }
        plan = plan_backfill(projects(), tables)
        assigned = {(item["table"], item["id"]): (item["company_id"], item["project_id"]) for item in plan["assignments"]}
        self.assertNotIn(("rooms", 1), assigned)
        self.assertEqual(plan["counts"]["rooms"]["ambiguous"], 1)
        self.assertEqual(plan["counts"]["rooms"]["unknown"], 2)
        self.assertEqual(assigned[("rooms", 2)], (2, 12))
        self.assertEqual(assigned[("project_measurements", 5)], (2, 12))
        self.assertEqual(assigned[("room_works", 6)], (2, 12))
        self.assertEqual(assigned[("room_works", 7)], (2, 12))
        self.assertNotIn(("room_works", 8), assigned)
        self.assertEqual(plan["counts"]["room_works"]["parentConflict"], 1)
        self.assertEqual(assigned[("measurement_room_drafts", 9)], (2, 12))
        self.assertNotIn(("room_windows", 10), assigned)
        self.assertEqual(assigned[("room_windows", 11)], (2, 12))
        self.assertEqual(plan["counts"]["room_windows"]["unknown"], 1)
        self.assertEqual(assigned[("room_doors", 13)], (2, 12))
        self.assertIn("Объект", plan["ambiguousNames"])

    def test_existing_and_partial_owners_are_not_replaced(self):
        tables = {
            "rooms": [row(1, "Склад", company_id=3, project_id=11), row(2, "Склад", company_id=2)],
            "room_windows": [row(3, company_id=2, project_id=12, parent_id=1)],
        }
        plan = plan_backfill(projects(), tables)
        self.assertEqual(plan["assignments"], [])
        self.assertEqual(plan["counts"]["rooms"]["alreadyOwned"], 1)
        self.assertEqual(plan["counts"]["rooms"]["partial"], 1)
        self.assertEqual(plan["counts"]["room_windows"]["alreadyOwned"], 1)

    def test_child_follows_the_owner_its_parent_will_receive(self):
        tables = {
            "rooms": [row(1, "Склад")],
            "room_doors": [row(2, parent_id=1)],
            "room_works": [row(3, "Склад", parent_id=1)],
        }
        plan = plan_backfill(projects(), tables)
        owners = {(item["table"], item["id"]): (item["company_id"], item["project_id"]) for item in plan["assignments"]}
        self.assertEqual(owners[("rooms", 1)], owners[("room_doors", 2)])
        self.assertEqual(owners[("rooms", 1)], owners[("room_works", 3)])

    def test_apply_updates_only_unowned_rows(self):
        class Cursor:
            def __init__(self):
                self.updates = []
                self.queries = 0

            def execute(self, sql, params=()):
                self.updates.append((" ".join(sql.split()), tuple(params)))
                self.queries += 1

            def fetchall(self):
                if self.queries == 1:
                    return [(12, 2, "Склад"), (10, 2, "Объект"), (11, 3, "Объект")]
                if self.updates[-1][0].rstrip().endswith("FROM rooms"):
                    return [(1, "Склад", None, None, None), (2, "Объект", None, None, None)]
                return []

        cursor = Cursor()
        plan = apply_backfill(cursor, write=True)
        updates = [item for item in cursor.updates if item[0].startswith("UPDATE")]
        self.assertEqual(updates, [(
            "UPDATE rooms SET company_id=%s, project_id=%s WHERE id=%s AND company_id IS NULL AND project_id IS NULL",
            (2, 12, 1),
        )])
        self.assertEqual(plan["applied"], 1)
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

    def test_migration_is_the_next_head_and_does_not_guess_company_one(self):
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn('revision = "0119_room_measurement_owners"', source)
        self.assertIn('down_revision = "0118_main_server_heads"', source)
        self.assertNotIn("company_id=1", source)
        self.assertNotIn("DEFAULT 1", ADD_COLUMNS_SQL)
        self.assertIn("quality_projects_id_company_idx", CONSTRAINTS_SQL)
        for table in TABLE_NAMES:
            self.assertIn(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER", ADD_COLUMNS_SQL)
            self.assertIn(f"{table}_owner_pair", CONSTRAINTS_SQL)
            self.assertIn(f"{table}_project_owner_fk", CONSTRAINTS_SQL)
        tree = ast.parse(source)
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        self.assertIsInstance(downgrade.body[0], ast.Raise)
        spec = importlib.util.spec_from_file_location("room_measurement_owners", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0119_room_measurement_owners")
        self.assertEqual(module.down_revision, "0118_main_server_heads")


if __name__ == "__main__":
    unittest.main()
