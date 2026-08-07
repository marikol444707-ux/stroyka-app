import json
import unittest
from pathlib import Path

from backend.features.project_budget_adjustments.schema import (
    PLAN_SHA256_RE,
    SchemaMigrationError,
    build_schema_plan,
    run_schema_migration,
    schema_plan_sha256,
)


def empty_catalog():
    return {
        "budget_type": "double precision",
        "budget_udt": "float8",
        "budget_precision": 53,
        "budget_scale": None,
        "receipt_table": False,
        "receipt_columns": [],
        "receipt_column_definitions": {},
        "constraints": [],
        "constraint_definitions": {},
        "indexes": [],
        "index_definitions": {},
        "functions": [],
        "function_definitions": {},
        "triggers": [],
        "trigger_definitions": {},
    }


def safe_conversion():
    return {
        "rows_total": 4,
        "null_budget": 0,
        "non_finite_budget": 0,
        "negative_budget": 0,
        "out_of_range_budget": 0,
        "precision_loss_budget": 0,
    }


def ready_catalog():
    initial = build_schema_plan(empty_catalog(), safe_conversion())
    expected = initial["expected"]
    catalog = empty_catalog()
    catalog.update({
        "budget_type": "numeric",
        "budget_udt": "numeric",
        "budget_precision": 14,
        "budget_scale": 2,
        "receipt_table": True,
        "receipt_columns": sorted(expected["receiptColumns"]),
        "receipt_column_definitions": expected["receiptColumnDefinitions"],
        "constraints": sorted(expected["constraints"]),
        "constraint_definitions": expected["constraintDefinitions"],
        "indexes": sorted(expected["indexes"]),
        "index_definitions": expected["indexDefinitions"],
        "functions": sorted(expected["functions"]),
        "function_definitions": expected["functionDefinitions"],
        "triggers": sorted(expected["triggers"]),
        "trigger_definitions": expected["triggerDefinitions"],
    })
    return catalog


class FakeCursor:
    def __init__(self, result_rows):
        self.result_rows = list(result_rows)
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        if compact.upper().startswith("SELECT ") and "pg_advisory_xact_lock" not in compact:
            self.current = self.result_rows.pop(0)

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, result_rows):
        self.cursor_value = FakeCursor(result_rows)
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


class BudgetAdjustmentSchemaPlanTests(unittest.TestCase):
    def test_fresh_safe_plan_is_deterministic_and_guarded(self):
        first = build_schema_plan(empty_catalog(), safe_conversion())
        second = build_schema_plan(empty_catalog(), safe_conversion())

        self.assertTrue(first["readyForApply"])
        self.assertEqual(first["changes"], second["changes"])
        plan_hash = schema_plan_sha256(first["changes"])
        self.assertRegex(plan_hash, PLAN_SHA256_RE)
        sql = "\n".join(change["sql"] for change in first["changes"])
        compact = "".join(sql.split())
        self.assertIn("ALTER TABLE public.projects", sql)
        self.assertIn("TYPE NUMERIC(14,2)", sql)
        self.assertIn("CREATE TABLE public.project_budget_adjustments", sql)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertIn("approved_by_role", sql)
        self.assertIn("'директор','зам_директора'", compact)
        self.assertIn("project_budget_after=project_budget_before+adjustment_amount", compact)
        self.assertIn("estimate_next_total-estimate_base_total", compact)
        self.assertIn("guard_project_budget_adjustment_insert", sql)
        self.assertIn("reject_project_budget_adjustment_mutation", sql)
        self.assertNotIn("UPDATE public.projects SET budget", sql)

    def test_lossy_budget_data_blocks_schema_apply_plan(self):
        unsafe = {**safe_conversion(), "precision_loss_budget": 1}

        plan = build_schema_plan(empty_catalog(), unsafe)

        self.assertFalse(plan["readyForApply"])
        self.assertFalse(plan["conversionReady"])
        self.assertEqual(plan["blockers"], ["project_budget_conversion_unsafe"])

    def test_partial_receipt_table_fails_closed(self):
        catalog = ready_catalog()
        catalog["receipt_columns"].remove("plan_sha256")

        plan = build_schema_plan(catalog, safe_conversion())

        self.assertFalse(plan["readyForApply"])
        self.assertIn("receipt_columns_invalid", plan["blockers"])

    def test_same_name_wrong_immutability_function_fails_closed(self):
        catalog = ready_catalog()
        catalog["function_definitions"]["reject_project_budget_adjustment_mutation"] = (
            "CREATE FUNCTION reject_project_budget_adjustment_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN OLD; END $$"
        )

        plan = build_schema_plan(catalog, safe_conversion())

        self.assertFalse(plan["readyForApply"])
        self.assertIn(
            "invalidFunction:reject_project_budget_adjustment_mutation",
            plan["blockers"],
        )

    def test_postgres_normalized_trigger_event_order_is_accepted(self):
        catalog = ready_catalog()
        catalog["trigger_definitions"]["project_budget_adjustment_immutable"] = (
            "CREATE TRIGGER project_budget_adjustment_immutable "
            "BEFORE DELETE OR UPDATE ON project_budget_adjustments FOR EACH ROW "
            "EXECUTE FUNCTION reject_project_budget_adjustment_mutation()"
        )

        plan = build_schema_plan(catalog, safe_conversion())

        self.assertTrue(plan["schemaReady"], plan["blockers"])

    def test_ready_catalog_is_repeatably_zero_change(self):
        plan = build_schema_plan(ready_catalog(), safe_conversion())

        self.assertTrue(plan["schemaReady"])
        self.assertTrue(plan["readyForApply"])
        self.assertEqual(plan["changes"], [])

    def test_operator_commands_exist_but_deploy_does_not_run_migration(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deploy = (root / "deploy.sh").read_text(encoding="utf-8")

        self.assertEqual(
            package["scripts"]["audit:project-budget-adjustment-schema"],
            "python3 -m backend.features.project_budget_adjustments.schema",
        )
        self.assertEqual(
            package["scripts"]["migrate:project-budget-adjustment-schema"],
            "python3 -m backend.features.project_budget_adjustments.schema --apply",
        )
        self.assertNotIn("project_budget_adjustments.schema", deploy)


class BudgetAdjustmentSchemaRunnerTests(unittest.TestCase):
    def test_dry_run_rolls_back_and_attempts_no_writes(self):
        connection = FakeConnection((empty_catalog(), safe_conversion()))

        report = run_schema_migration(lambda: connection)

        self.assertTrue(report["ok"])
        self.assertTrue(report["dryRun"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertGreater(report["changeCount"], 0)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_unsafe_dry_run_reports_fixed_blocker_without_ddl(self):
        unsafe = {**safe_conversion(), "non_finite_budget": 1}
        connection = FakeConnection((empty_catalog(), unsafe))

        report = run_schema_migration(lambda: connection)

        self.assertFalse(report["ok"])
        self.assertFalse(report["readyForApply"])
        self.assertEqual(report["blockers"], ["project_budget_conversion_unsafe"])
        self.assertFalse(any(call[0].startswith("ALTER TABLE") for call in connection.cursor_value.calls))
        self.assertFalse(any(call[0].startswith("CREATE TABLE") for call in connection.cursor_value.calls))

    def test_apply_requires_exact_count_and_hash_before_ddl(self):
        connection = FakeConnection((empty_catalog(), safe_conversion()))

        with self.assertRaisesRegex(SchemaMigrationError, "schema_apply_guard_mismatch"):
            run_schema_migration(
                lambda: connection,
                apply=True,
                expected_change_count=999,
                expected_plan_sha256="0" * 64,
            )

        self.assertFalse(any(call[0].startswith("ALTER TABLE") for call in connection.cursor_value.calls))
        self.assertFalse(any(call[0].startswith("CREATE TABLE") for call in connection.cursor_value.calls))
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_exact_apply_postchecks_commits_and_repeat_is_zero_change(self):
        before = build_schema_plan(empty_catalog(), safe_conversion())
        connection = FakeConnection((
            empty_catalog(), safe_conversion(),
            empty_catalog(), safe_conversion(),
            ready_catalog(),
        ))

        report = run_schema_migration(
            lambda: connection,
            apply=True,
            expected_change_count=len(before["changes"]),
            expected_plan_sha256=schema_plan_sha256(before["changes"]),
        )

        self.assertTrue(report["committed"])
        self.assertTrue(report["schemaReady"])
        self.assertEqual(report["writesAttempted"], len(before["changes"]))
        self.assertEqual(report["conversionAudit"]["rows_total"], 4)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        calls = [call[0] for call in connection.cursor_value.calls]
        lock_index = calls.index(
            "LOCK TABLE public.projects IN ACCESS EXCLUSIVE MODE"
        )
        first_ddl_index = next(
            index for index, call in enumerate(calls)
            if call.startswith("ALTER TABLE public.projects")
        )
        self.assertLess(lock_index, first_ddl_index)

        repeat_connection = FakeConnection((ready_catalog(),))
        repeat = run_schema_migration(lambda: repeat_connection)
        self.assertTrue(repeat["schemaReady"])
        self.assertEqual(repeat["changeCount"], 0)
        self.assertEqual(repeat["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
