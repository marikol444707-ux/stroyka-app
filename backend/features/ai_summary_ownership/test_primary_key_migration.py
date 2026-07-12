import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.ai_summary_ownership.primary_key_migration import (
    APPLY_CONFIRMATION,
    _plan_sha256,
    build_cutover_report,
    main,
    run_migration,
)


def stored_owner():
    return {
        "projectName": "Объект A",
        "storedCompanyId": 4,
        "storedProjectId": 10,
        "proposedCompanyId": 4,
        "proposedProjectId": 10,
        "status": "stored",
        "reason": "stored_owner_verified",
    }


def report(*, legacy=True, complete=False, plan_sha=None):
    return {
        "ok": True,
        "table": "project_ai_summary",
        "columns": {"companyId": True, "projectId": True},
        "totalRows": 1,
        "storedRows": 1,
        "legacyRows": 0,
        "ownershipReady": True,
        "primaryKey": {
            "constraintName": "project_ai_summary_pkey",
            "columns": ["project_name"] if legacy else ["company_id", "project_id"],
        },
        "duplicateOwnerGroups": 0,
        "legacyPrimaryKey": legacy,
        "tenantPrimaryKey": not legacy,
        "readyForCutover": legacy,
        "complete": complete,
        "planSha256": plan_sha or _plan_sha256([stored_owner()]),
    }


class FakeCursor:
    def __init__(self, primary_columns=None):
        self.primary_columns = primary_columns or ["project_name"]
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if "information_schema.table_constraints" in compact:
            self.current = [
                {
                    "constraint_name": "project_ai_summary_pkey",
                    "column_name": column,
                    "ordinal_position": index,
                }
                for index, column in enumerate(self.primary_columns, start=1)
            ]
        elif "duplicate_groups" in compact:
            self.current = {"duplicate_groups": 0}
        else:
            self.current = None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session_calls = []
        self.committed = False
        self.rolled_back = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class AiSummaryPrimaryKeyMigrationTests(unittest.TestCase):
    def test_report_is_ready_only_with_stored_owner_and_legacy_key(self):
        cursor = FakeCursor()
        with patch(
            "backend.features.ai_summary_ownership.primary_key_migration.collect_ownership",
            return_value=({"company_id", "project_id"}, [stored_owner()]),
        ):
            result = build_cutover_report(cursor)
        self.assertTrue(result["readyForCutover"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["primaryKey"]["columns"], ["project_name"])

    def test_dry_run_is_read_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch(
            "backend.features.ai_summary_ownership.primary_key_migration.build_cutover_report",
            return_value=report(),
        ):
            result = run_migration(connection, apply=False)
        self.assertTrue(result["readyForCutover"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)
        self.assertEqual(cursor.calls, [])

    def test_apply_replaces_primary_key_and_commits_after_postcheck(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = report()
        after = report(legacy=False, complete=True)
        with patch(
            "backend.features.ai_summary_ownership.primary_key_migration.build_cutover_report",
            side_effect=[before, after],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_row_count=1,
                expected_plan_sha256=before["planSha256"],
            )
        self.assertTrue(result["complete"])
        self.assertEqual(result["schemaWritesAttempted"], 1)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in cursor.calls)
        self.assertIn("DROP CONSTRAINT project_ai_summary_pkey", sql)
        self.assertIn("PRIMARY KEY (company_id,project_id)", sql)

    def test_apply_rejects_plan_drift_before_alter(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = report(plan_sha="a" * 64)
        with patch(
            "backend.features.ai_summary_ownership.primary_key_migration.build_cutover_report",
            return_value=before,
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(
                    connection,
                    apply=True,
                    expected_row_count=1,
                    expected_plan_sha256="b" * 64,
                )
        self.assertFalse(any("DROP CONSTRAINT" in sql for sql, _params in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_not_ready_report_rolls_back_without_schema_cutover(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        blocked = {**report(), "readyForCutover": False, "ownershipReady": False}
        with patch(
            "backend.features.ai_summary_ownership.primary_key_migration.build_cutover_report",
            return_value=blocked,
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_row_count=1,
                expected_plan_sha256=blocked["planSha256"],
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "not_ready")
        self.assertTrue(connection.rolled_back)

    def test_cli_requires_confirmation_count_and_sha(self):
        with patch("backend.features.ai_summary_ownership.primary_key_migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", APPLY_CONFIRMATION, "--expected-row-count", "1"])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
