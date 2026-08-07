import unittest

from backend.features.material_control_ownership.readiness_report import (
    collect_owner_readiness,
    run_readiness_report,
)


REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in {
        "projects": ("id", "company_id", "name", "archived"),
        "estimates": (
            "id",
            "company_id",
            "project_id",
            "project_name",
            "status",
            "is_template",
            "smeta_type",
            "work_package",
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
        raise AssertionError("readiness audit must not commit")

    def close(self):
        self.closed = True


class MaterialControlReadinessCollectionTests(unittest.TestCase):
    def test_collection_is_bounded_and_selects_no_business_payload(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            ({
                "project_id": 1,
                "company_id": 10,
                "project_name": "Школа",
                "archived": False,
            },),
            ({
                "estimate_id": 101,
                "company_id": 10,
                "project_id": 1,
                "project_name": "Школа",
                "estimate_kind": "Заказчик",
                "work_package": "Основная",
            },),
        ))

        report = collect_owner_readiness(cursor)

        self.assertTrue(report["dataReady"])
        self.assertTrue(report["schemaReady"])
        self.assertEqual(len(cursor.calls), 3)
        for index, (sql, params) in enumerate(cursor.calls):
            self.assertTrue(sql.upper().startswith("SELECT "))
            if index == 0:
                self.assertIn("information_schema.columns", sql)
            else:
                self.assertIn("LIMIT %s", sql)
            self.assertEqual(len(params), 1)
            for forbidden in ("sections_json", "total", "price", "client", "budget"):
                self.assertNotIn(forbidden, sql.lower())

    def test_project_scan_limit_fails_closed_before_estimate_query(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (
                {"project_id": 1},
                {"project_id": 2},
                {"project_id": 3},
            ),
        ))

        report = collect_owner_readiness(
            cursor,
            max_project_rows=2,
            max_estimate_rows=2,
        )

        self.assertFalse(report["dataReady"])
        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "active_project_scan_limit_exceeded",
        }])
        self.assertEqual(len(cursor.calls), 2)

    def test_estimate_scan_limit_fails_closed(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            ({"project_id": 1, "company_id": 10},),
            (
                {"estimate_id": 1},
                {"estimate_id": 2},
                {"estimate_id": 3},
            ),
        ))

        report = collect_owner_readiness(
            cursor,
            max_project_rows=2,
            max_estimate_rows=2,
        )

        self.assertFalse(report["dataReady"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "active_estimate_scan_limit_exceeded",
        }])
        self.assertEqual(len(cursor.calls), 3)

    def test_missing_owner_column_returns_fixed_schema_blocker_without_data_scan(self):
        schema_rows = tuple(
            row for row in REQUIRED_SCHEMA_ROWS
            if not (
                row["table_name"] == "projects"
                and row["column_name"] == "company_id"
            )
        )
        cursor = FakeCursor((schema_rows,))

        report = collect_owner_readiness(cursor)

        self.assertFalse(report["schemaReady"])
        self.assertFalse(report["dataReady"])
        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "material_control_owner_schema_not_ready",
        }])
        self.assertEqual(report["missingColumns"], ["projects.company_id"])
        self.assertEqual(len(cursor.calls), 1)


class MaterialControlReadinessRunnerTests(unittest.TestCase):
    def test_runner_is_repeatable_read_read_only_and_always_rolls_back(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)
        data = {"ok": True, "dataReady": True}
        inventory = {"ok": True, "runtimeInventoryReady": False}

        report = run_readiness_report(
            lambda: connection,
            collect_data=lambda _cur: data,
            collect_inventory=lambda: inventory,
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
        self.assertTrue(report["dataReady"])
        self.assertFalse(report["runtimeInventoryReady"])
        self.assertFalse(report["readyForCutover"])
        self.assertTrue(report["readOnlyTransaction"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["rolledBack"])

    def test_runner_rolls_back_and_closes_when_collection_raises(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            run_readiness_report(
                lambda: connection,
                collect_data=lambda _cur: (_ for _ in ()).throw(RuntimeError("boom")),
                collect_inventory=lambda: {},
            )

        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
