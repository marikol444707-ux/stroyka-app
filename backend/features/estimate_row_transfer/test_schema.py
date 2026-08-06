import unittest
import json
from pathlib import Path

from backend.features.estimate_row_transfer.schema import (
    PLAN_SHA256_RE,
    SchemaMigrationError,
    build_schema_plan,
    run_schema_migration,
    schema_plan_sha256,
)


class FakeCursor:
    def __init__(self, catalog_rows):
        self.catalog_rows = list(catalog_rows)
        self.calls = []
        self.current = None
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if sql.lstrip().startswith("SELECT") and "pg_advisory_xact_lock" not in sql:
            self.current = self.catalog_rows.pop(0)

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, catalog_rows):
        self.cursor_value = FakeCursor(catalog_rows)
        self.session = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def empty_catalog_row():
    return {
        "plans_table": False,
        "entries_table": False,
        "assignment_transfers_table": False,
        "plan_columns": [],
        "entry_columns": [],
        "assignment_transfer_columns": [],
        "constraints": [],
        "indexes": [],
        "functions": [],
        "triggers": [],
        "constraint_definitions": {},
        "index_definitions": {},
        "function_definitions": {},
        "trigger_definitions": {},
    }


def ready_catalog_row():
    plan = build_schema_plan(empty_catalog_row())
    catalog = empty_catalog_row()
    catalog.update({
        "plans_table": True,
        "entries_table": True,
        "assignment_transfers_table": True,
        "plan_columns": sorted(plan["expected"]["planColumns"]),
        "entry_columns": sorted(plan["expected"]["entryColumns"]),
        "assignment_transfer_columns": sorted(
            plan["expected"]["assignmentTransferColumns"]
        ),
        "constraints": sorted(plan["expected"]["constraints"]),
        "indexes": sorted(plan["expected"]["indexes"]),
        "functions": sorted(plan["expected"]["functions"]),
        "triggers": sorted(plan["expected"]["triggers"]),
        "constraint_definitions": plan["expected"]["constraintDefinitions"],
        "index_definitions": plan["expected"]["indexDefinitions"],
        "function_definitions": plan["expected"]["functionDefinitions"],
        "trigger_definitions": plan["expected"]["triggerDefinitions"],
    })
    return catalog


class EstimateRowTransferSchemaPlanTests(unittest.TestCase):
    def test_fresh_plan_is_deterministic_and_contains_only_schema_changes(self):
        first = build_schema_plan(empty_catalog_row())
        second = build_schema_plan(empty_catalog_row())

        self.assertTrue(first["readyForApply"])
        self.assertEqual(first["changes"], second["changes"])
        self.assertEqual(schema_plan_sha256(first["changes"]), schema_plan_sha256(second["changes"]))
        self.assertRegex(schema_plan_sha256(first["changes"]), PLAN_SHA256_RE)
        sql = "\n".join(item["sql"] for item in first["changes"])
        self.assertIn("CREATE TABLE public.estimate_row_transfer_plans", sql)
        self.assertIn("CREATE TABLE public.estimate_row_transfer_entries", sql)
        self.assertIn("source_available_quantity", sql)
        self.assertIn("base_snapshot_row_count", sql)
        self.assertIn("target_snapshot_row_count", sql)
        self.assertIn("quantity<=source_available_quantity", "".join(sql.split()))
        self.assertIn("estimate_row_transfer_entry_immutable", sql)
        self.assertIn("estimate_row_transfer_plan_guard", sql)
        self.assertIn("CREATE TABLE public.estimate_row_assignment_transfers", sql)
        self.assertIn("uq_etre_id_plan_owner", sql)
        self.assertIn("guard_estimate_row_assignment_transfer", sql)
        self.assertIn("estimate_row_assignment_transfer_guard", sql)
        self.assertIn("source_quantity_before", sql)
        self.assertIn("source_quantity_after", sql)
        self.assertIn("confirmed_quantity", sql)
        self.assertIn(
            "source_done_quantity<=source_quantity_after",
            "".join(sql.split()),
        )
        self.assertIn("contract_total_before", sql)
        self.assertIn("contract_total_after", sql)
        self.assertIn("e.source_total_quantity=NEW.source_quantity_before", sql)
        self.assertIn("e.source_protected_quantity=NEW.confirmed_quantity", sql)
        self.assertIn("source_item.status=NEW.source_status", sql)
        self.assertNotIn("UPDATE brigade_contract_items", sql)
        self.assertNotIn("UPDATE supply_requests", sql)

    def test_existing_partial_table_fails_closed_instead_of_silent_repair(self):
        catalog = ready_catalog_row()
        catalog["plan_columns"].remove("plan_sha256")

        plan = build_schema_plan(catalog)

        self.assertFalse(plan["readyForApply"])
        self.assertEqual(plan["blockers"], ["plan_columns_invalid"])

    def test_ready_catalog_has_no_changes(self):
        plan = build_schema_plan(ready_catalog_row())

        self.assertTrue(plan["schemaReady"])
        self.assertTrue(plan["readyForApply"])
        self.assertEqual(plan["changes"], [])

    def test_same_name_wrong_function_fails_closed(self):
        catalog = ready_catalog_row()
        catalog["function_definitions"]["guard_estimate_row_transfer_plan_mutation"] = (
            "CREATE FUNCTION guard_estimate_row_transfer_plan_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"
        )

        plan = build_schema_plan(catalog)

        self.assertFalse(plan["readyForApply"])
        self.assertIn(
            "invalidFunction:guard_estimate_row_transfer_plan_mutation",
            plan["blockers"],
        )

    def test_operator_commands_exist_but_deploy_has_no_auto_migration(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deploy = (root / "deploy.sh").read_text(encoding="utf-8")

        self.assertEqual(
            package["scripts"]["audit:estimate-row-transfer-schema"],
            "python3 -m backend.features.estimate_row_transfer.schema",
        )
        self.assertEqual(
            package["scripts"]["migrate:estimate-row-transfer-schema"],
            "python3 -m backend.features.estimate_row_transfer.schema --apply",
        )
        self.assertNotIn("estimate_row_transfer.schema", deploy)


class EstimateRowTransferSchemaRunnerTests(unittest.TestCase):
    def test_dry_run_is_rolled_back_and_attempts_no_writes(self):
        connection = FakeConnection([empty_catalog_row()])

        report = run_schema_migration(lambda: connection)

        self.assertTrue(report["dryRun"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertGreater(report["changeCount"], 0)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_apply_requires_exact_count_and_hash_before_ddl(self):
        connection = FakeConnection([empty_catalog_row()])

        with self.assertRaisesRegex(SchemaMigrationError, "schema_apply_guard_mismatch"):
            run_schema_migration(
                lambda: connection,
                apply=True,
                expected_change_count=999,
                expected_plan_sha256="0" * 64,
            )

        self.assertFalse(any(call[0].startswith("CREATE") for call in connection.cursor_value.calls))
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
