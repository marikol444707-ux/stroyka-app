import json
import unittest
from decimal import Decimal
from pathlib import Path

from backend.features.project_budget_adjustments.readiness_report import (
    collect_baseline_readiness,
    run_readiness_report,
)


REQUIRED_SCHEMA_ROWS = tuple(
    {
        "table_name": table,
        "column_name": column,
        "data_type": (
            "double precision"
            if (table, column) == ("projects", "budget")
            else "integer"
        ),
        "udt_name": "float8" if (table, column) == ("projects", "budget") else "int4",
        "numeric_precision": None,
        "numeric_scale": None,
    }
    for table, columns in {
        "projects": ("id", "company_id", "budget"),
        "estimates": (
            "id", "company_id", "project_id", "status", "smeta_type",
            "work_package",
        ),
        "estimate_reconciliations": (
            "id", "base_estimate_id", "next_estimate_id", "status",
            "smeta_type", "work_package", "base_total", "next_total",
        ),
    }.items()
    for column in columns
)


class FakeCursor:
    def __init__(self, result_sets):
        self.result_sets = [list(rows) for rows in result_sets]
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.result_sets.pop(0) if self.result_sets else []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1
        raise AssertionError("E6.1 readiness audit must not commit")

    def close(self):
        self.closed = True


class BudgetAdjustmentCollectionTests(unittest.TestCase):
    def test_collection_reports_float_catalog_and_safe_data_without_payloads(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            ({"project_id": 20, "company_id": 10,
              "project_budget": Decimal("1000.00")},),
            ({
                "reconciliation_id": 7,
                "company_id": 10,
                "project_id": 20,
                "status": "Утверждена",
                "smeta_type": "Заказчик",
                "work_package": "Основная",
                "base_estimate_id": 100,
                "next_estimate_id": 101,
                "base_total": Decimal("100.00"),
                "next_total": Decimal("125.00"),
                "base_company_id": 10,
                "base_project_id": 20,
                "base_smeta_type": "Заказчик",
                "base_work_package": "Основная",
                "next_company_id": 10,
                "next_project_id": 20,
                "next_smeta_type": "Заказчик",
                "next_work_package": "Основная",
                "next_status": "Активная",
            },),
        ))

        report = collect_baseline_readiness(cursor)

        self.assertTrue(report["schemaReady"])
        self.assertFalse(report["budgetColumnExact"])
        self.assertTrue(report["dataReady"])
        self.assertTrue(report["readyForSchemaPlan"])
        self.assertEqual(report["budgetColumn"], {
            "dataType": "double precision",
            "udtName": "float8",
            "numericPrecision": None,
            "numericScale": None,
        })
        self.assertEqual(len(cursor.calls), 3)
        for index, (sql, params) in enumerate(cursor.calls):
            self.assertTrue(sql.upper().startswith("SELECT "))
            if index:
                self.assertIn("LIMIT %s", sql)
                self.assertEqual(len(params), 1)
            for forbidden in (
                "sections_json", "project_name", "base_estimate_name",
                "next_estimate_name", "notes", "client", "created_by",
            ):
                self.assertNotIn(forbidden, sql.lower())

    def test_numeric_budget_catalog_is_already_exact(self):
        schema_rows = tuple(
            {
                **row,
                "data_type": "numeric",
                "udt_name": "numeric",
                "numeric_precision": 14,
                "numeric_scale": 2,
            }
            if (row["table_name"], row["column_name"]) == ("projects", "budget")
            else row
            for row in REQUIRED_SCHEMA_ROWS
        )
        cursor = FakeCursor((schema_rows, (), ()))

        report = collect_baseline_readiness(cursor)

        self.assertTrue(report["budgetColumnExact"])
        self.assertTrue(report["readyForSchemaPlan"])

    def test_missing_required_column_fails_closed_before_data_queries(self):
        schema_rows = tuple(
            row for row in REQUIRED_SCHEMA_ROWS
            if not (
                row["table_name"] == "projects"
                and row["column_name"] == "company_id"
            )
        )
        cursor = FakeCursor((schema_rows,))

        report = collect_baseline_readiness(cursor)

        self.assertFalse(report["schemaReady"])
        self.assertFalse(report["dataReady"])
        self.assertFalse(report["scanComplete"])
        self.assertFalse(report["readyForSchemaPlan"])
        self.assertEqual(report["missingColumns"], ["projects.company_id"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "project_budget_adjustment_schema_not_ready",
        }])
        self.assertEqual(len(cursor.calls), 1)

    def test_project_scan_limit_fails_closed_before_reconciliation_query(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            ({"project_id": 1}, {"project_id": 2}, {"project_id": 3}),
        ))

        report = collect_baseline_readiness(
            cursor,
            max_project_rows=2,
            max_reconciliation_rows=2,
        )

        self.assertFalse(report["scanComplete"])
        self.assertFalse(report["dataReady"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "project_budget_scan_limit_exceeded",
        }])
        self.assertEqual(len(cursor.calls), 2)

    def test_reconciliation_scan_limit_fails_closed(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            ({"project_id": 1, "company_id": 10, "project_budget": 0},),
            ({"reconciliation_id": 1}, {"reconciliation_id": 2},
             {"reconciliation_id": 3}),
        ))

        report = collect_baseline_readiness(
            cursor,
            max_project_rows=2,
            max_reconciliation_rows=2,
        )

        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "budget_adjustment_reconciliation_scan_limit_exceeded",
        }])


class BudgetAdjustmentReadinessRunnerTests(unittest.TestCase):
    def test_runner_is_repeatable_read_read_only_and_always_rolls_back(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        report = run_readiness_report(
            lambda: connection,
            collect_schema=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
            },
            collect_data=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
                "dataReady": True,
                "readyForSchemaPlan": True,
            },
            collect_ledger=lambda _cur: {
                "ok": True,
                "ledgerReady": True,
            },
            collect_inventory=lambda: {
                "ok": True,
                "writerInventoryReady": True,
            },
            collect_cutover=lambda: {
                "ok": True,
                "routeInventoryReady": True,
                "integrationInventoryReady": True,
            },
        )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(report["ok"])
        self.assertTrue(report["writerInventoryReady"])
        self.assertTrue(report["readyForSchemaPlan"])
        self.assertTrue(report["ledgerReady"])
        self.assertTrue(report["routeInventoryReady"])
        self.assertTrue(report["integrationInventoryReady"])
        self.assertTrue(report["readyForCutover"])
        self.assertTrue(report["readOnlyTransaction"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["rolledBack"])

    def test_runner_rolls_back_and_closes_when_collection_raises(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            run_readiness_report(
                lambda: connection,
                collect_schema=lambda _cur: {
                    "ok": True,
                    "schemaReady": True,
                    "budgetColumnExact": True,
                },
                collect_data=lambda _cur: (_ for _ in ()).throw(
                    RuntimeError("boom")
                ),
                collect_ledger=lambda _cur: {},
                collect_inventory=lambda: {},
                collect_cutover=lambda: {},
            )

        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_writer_drift_blocks_schema_plan_without_changing_audit_ok(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        report = run_readiness_report(
            lambda: connection,
            collect_schema=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
            },
            collect_data=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
                "dataReady": True,
                "readyForSchemaPlan": True,
            },
            collect_ledger=lambda _cur: {
                "ok": True,
                "ledgerReady": True,
            },
            collect_inventory=lambda: {
                "ok": False,
                "writerInventoryReady": False,
                "violations": [{"reasonCode": "writer_drift"}],
            },
            collect_cutover=lambda: {
                "ok": True,
                "routeInventoryReady": True,
                "integrationInventoryReady": True,
            },
        )

        self.assertFalse(report["ok"])
        self.assertFalse(report["writerInventoryReady"])
        self.assertFalse(report["readyForSchemaPlan"])
        self.assertFalse(report["readyForCutover"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_schema_gap_skips_ledger_and_fails_cutover(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)
        ledger_calls = []

        report = run_readiness_report(
            lambda: connection,
            collect_schema=lambda _cur: {
                "ok": True,
                "schemaReady": False,
                "budgetColumnExact": False,
            },
            collect_data=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": False,
                "dataReady": True,
                "readyForSchemaPlan": True,
            },
            collect_ledger=lambda _cur: ledger_calls.append(True),
            collect_inventory=lambda: {
                "ok": True,
                "writerInventoryReady": True,
            },
            collect_cutover=lambda: {
                "ok": True,
                "routeInventoryReady": True,
                "integrationInventoryReady": True,
            },
        )

        self.assertEqual(ledger_calls, [])
        self.assertFalse(report["schemaReady"])
        self.assertFalse(report["ledgerReady"])
        self.assertEqual(report["ledgerAudit"]["issues"], [{
            "reasonCode": "budget_adjustment_schema_not_ready",
        }])
        self.assertFalse(report["readyForCutover"])
        self.assertEqual(connection.rollbacks, 1)

    def test_ledger_or_route_test_drift_blocks_cutover(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        report = run_readiness_report(
            lambda: connection,
            collect_schema=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
            },
            collect_data=lambda _cur: {
                "ok": True,
                "schemaReady": True,
                "budgetColumnExact": True,
                "dataReady": True,
                "readyForSchemaPlan": True,
            },
            collect_ledger=lambda _cur: {
                "ok": True,
                "ledgerReady": False,
                "issues": [{"reasonCode": "receipt_drift"}],
            },
            collect_inventory=lambda: {
                "ok": True,
                "writerInventoryReady": True,
            },
            collect_cutover=lambda: {
                "ok": False,
                "routeInventoryReady": False,
                "integrationInventoryReady": True,
            },
        )

        self.assertFalse(report["ok"])
        self.assertFalse(report["ledgerReady"])
        self.assertFalse(report["routeInventoryReady"])
        self.assertTrue(report["integrationInventoryReady"])
        self.assertFalse(report["readyForCutover"])
        self.assertEqual(connection.rollbacks, 1)

    def test_package_exposes_read_only_audit_command(self):
        package = json.loads(Path("package.json").read_text(encoding="utf-8"))

        self.assertEqual(
            package["scripts"]["audit:project-budget-adjustments"],
            "python3 -m backend.features.project_budget_adjustments.readiness_report",
        )


if __name__ == "__main__":
    unittest.main()
