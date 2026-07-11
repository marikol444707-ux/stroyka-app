import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from backend.features.estimate_changes.migration import (
    APPLY_CONFIRMATION,
    _apply_ready_rows,
    _plan_sha256,
    main,
    run_migration,
)


def ownership(change_id, status="ready", company_id=1, project_id=1, reason="unique_project_name"):
    return {
        "changeId": change_id,
        "estimateId": None,
        "includedEstimateId": None,
        "storedProjectId": project_id if status == "stored" else None,
        "storedCompanyId": company_id if status == "stored" else None,
        "proposedProjectId": project_id,
        "proposedCompanyId": company_id,
        "source": "stored" if status == "stored" else "unique_project_name",
        "status": status,
        "reason": "stored_owner" if status == "stored" else reason,
    }


class FakeCursor:
    def __init__(self, update_rowcounts=None):
        self.update_rowcounts = list(update_rowcounts or [])
        self.rowcount = 0
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if normalized.startswith("UPDATE unexpected_works"):
            self.rowcount = self.update_rowcounts.pop(0) if self.update_rowcounts else 0

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session_calls = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class EstimateChangeMigrationTests(unittest.TestCase):
    def test_script_entrypoint_can_import_backend_from_repo_root(self):
        root = Path(__file__).resolve().parents[3]

        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "migrate-estimate-changes.py"), "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--expected-ready-count", result.stdout)
        self.assertIn("--expected-plan-sha256", result.stdout)
        self.assertIn(APPLY_CONFIRMATION, result.stdout)

    def test_dry_run_is_read_only_and_never_changes_schema(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [ownership(change_id) for change_id in range(1, 5)]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            return_value=({"company_id", "project_id"}, before),
        ):
            result = run_migration(connection, apply=False)

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["readyCount"], 4)
        self.assertEqual(result["planSha256"], _plan_sha256(before))
        self.assertEqual(result["writesAttempted"], 0)
        self.assertTrue(result["rolledBack"])
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertFalse(any("ALTER TABLE" in sql or "UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertFalse(connection.committed)

    def test_dry_run_rolls_back_when_report_fails(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                run_migration(connection, apply=False)

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_commits_only_after_every_row_becomes_stored(self):
        cursor = FakeCursor(update_rowcounts=[1, 1, 1, 1])
        connection = FakeConnection(cursor)
        before = [ownership(change_id) for change_id in range(1, 5)]
        after = [ownership(change_id, status="stored") for change_id in range(1, 5)]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            side_effect=[({"company_id", "project_id"}, before), ({"company_id", "project_id"}, after)],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=4,
                expected_plan_sha256=_plan_sha256(before),
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["updated"], 4)
        self.assertEqual(result["postSummary"]["storedRows"], 4)
        self.assertEqual(result["postSummary"]["legacyRows"], 0)
        self.assertTrue(result["complete"])
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        sql_calls = [sql for sql, _params in cursor.calls]
        self.assertTrue(any("LOCK TABLE projects IN SHARE MODE" in sql for sql in sql_calls))
        self.assertTrue(any("LOCK TABLE estimates IN SHARE MODE" in sql for sql in sql_calls))
        self.assertTrue(any("LOCK TABLE unexpected_works IN ACCESS EXCLUSIVE MODE" in sql for sql in sql_calls))
        self.assertTrue(any("ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS project_id" in sql for sql in sql_calls))
        self.assertTrue(any("CREATE INDEX IF NOT EXISTS idx_unexpected_works_company_id" in sql for sql in sql_calls))

    def test_apply_stops_before_updates_when_expected_count_changed(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [ownership(change_id) for change_id in range(1, 5)]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            return_value=({"company_id", "project_id"}, before),
        ):
            with self.assertRaisesRegex(RuntimeError, "Expected 3 ready rows, found 4"):
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=3,
                    expected_plan_sha256=_plan_sha256(before),
                )

        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_apply_refuses_review_rows_before_updates(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [ownership(1), ownership(2, status="ambiguous", reason="project_name_ambiguous")]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            return_value=({"company_id", "project_id"}, before),
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256=_plan_sha256(before),
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "needs_review")
        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertTrue(result["rolledBack"])
        self.assertFalse(connection.committed)

    def test_apply_rolls_back_when_one_ready_row_was_not_updated(self):
        cursor = FakeCursor(update_rowcounts=[1, 0])
        connection = FakeConnection(cursor)
        before = [ownership(1), ownership(2)]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            return_value=({"company_id", "project_id"}, before),
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=2,
                expected_plan_sha256=_plan_sha256(before),
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "write_conflict")
        self.assertEqual(result["attemptedUpdated"], 1)
        self.assertEqual(result["writeConflicts"], 1)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_rolls_back_when_postcheck_is_not_fully_stored(self):
        cursor = FakeCursor(update_rowcounts=[1])
        connection = FakeConnection(cursor)
        before = [ownership(1)]
        after = [ownership(1, status="mismatched", reason="stored_project_company_mismatch")]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            side_effect=[({"company_id", "project_id"}, before), ({"company_id", "project_id"}, after)],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256=_plan_sha256(before),
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "postcheck_failed")
        self.assertTrue(result["rolledBack"])
        self.assertFalse(connection.committed)

    def test_apply_is_idempotent_when_expected_ready_count_is_zero(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        stored = [ownership(1, status="stored")]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            side_effect=[({"company_id", "project_id"}, stored), ({"company_id", "project_id"}, stored)],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=0,
                expected_plan_sha256=_plan_sha256(stored),
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["updated"], 0)
        self.assertTrue(result["complete"])
        self.assertTrue(connection.committed)

    def test_apply_stops_when_plan_mapping_changed_without_count_drift(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        audited = [ownership(1, company_id=1, project_id=10)]
        changed = [ownership(1, company_id=2, project_id=20)]

        with patch(
            "backend.features.estimate_changes.migration.collect_estimate_change_ownership",
            return_value=({"company_id", "project_id"}, changed),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=1,
                    expected_plan_sha256=_plan_sha256(audited),
                )

        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_apply_cli_requires_confirmation_count_and_plan_before_connecting(self):
        with patch("backend.features.estimate_changes.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--apply",
                    "--confirm",
                    APPLY_CONFIRMATION,
                    "--expected-ready-count",
                    "4",
                ])

        connect.assert_not_called()

    def test_apply_ready_rows_updates_only_null_owner_columns(self):
        cursor = FakeCursor(update_rowcounts=[1])

        updated = _apply_ready_rows(cursor, [ownership(7, company_id=3, project_id=9)])

        self.assertEqual(updated, 1)
        sql, params = cursor.calls[0]
        self.assertIn("project_id IS NULL", sql)
        self.assertIn("company_id IS NULL", sql)
        self.assertEqual(params, (9, 3, 7))


if __name__ == "__main__":
    unittest.main()
