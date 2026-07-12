import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.ai_summary_ownership.migration import (
    APPLY_CONFIRMATION,
    _plan_sha256,
    build_report,
    classify_summary,
    main,
    run_migration,
)


def ownership(status="ready", company_id=4, project_id=10, project_name="Объект A "):
    return {
        "summaryKey": "project:test",
        "projectName": project_name,
        "storedCompanyId": company_id if status == "stored" else None,
        "storedProjectId": project_id if status == "stored" else None,
        "proposedCompanyId": company_id,
        "proposedProjectId": project_id,
        "status": status,
        "reason": "stored_owner_verified" if status == "stored" else "unique_project_name",
    }


class FakeCursor:
    def __init__(self, update_rowcounts=None):
        self.calls = []
        self.rowcount = 0
        self.update_rowcounts = list(update_rowcounts or [])
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if compact.startswith("UPDATE project_ai_summary"):
            self.rowcount = self.update_rowcounts.pop(0) if self.update_rowcounts else 0

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


class AiSummaryOwnershipMigrationTests(unittest.TestCase):
    def test_exact_legacy_name_maps_to_one_project(self):
        result = classify_summary(
            {"project_name": "Объект A ", "stored_company_id": None, "stored_project_id": None},
            {"Объект A ": [{"id": 10, "company_id": 4}]},
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (4, 10))

    def test_near_match_is_not_used_as_owner(self):
        result = classify_summary(
            {"project_name": "Объект A", "stored_company_id": None, "stored_project_id": None},
            {"Объект A ": [{"id": 10, "company_id": 4}]},
        )
        self.assertEqual((result["status"], result["reason"]), ("unresolved", "project_not_found"))

    def test_ambiguous_and_stored_mismatch_fail_closed(self):
        ambiguous = classify_summary(
            {"project_name": "Объект A", "stored_company_id": None, "stored_project_id": None},
            {"Объект A": [{"id": 10, "company_id": 4}, {"id": 11, "company_id": 8}]},
        )
        mismatch = classify_summary(
            {"project_name": "Объект B", "stored_company_id": 8, "stored_project_id": 11},
            {"Объект B": [{"id": 10, "company_id": 4}]},
        )
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual((mismatch["status"], mismatch["reason"]), ("mismatched", "stored_owner_mismatch"))

    def test_report_hides_project_name_and_requires_backfill(self):
        report = build_report(set(), [ownership()])
        self.assertTrue(report["readyForMigration"])
        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"]["ready"], 1)
        self.assertNotIn("projectName", str(report))

    def test_dry_run_is_read_only_and_never_changes_schema(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [ownership()]
        with patch(
            "backend.features.ai_summary_ownership.migration.collect_ownership",
            return_value=(set(), before),
        ):
            result = run_migration(connection, apply=False)
        self.assertEqual(result["readyCount"], 1)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(result["planSha256"], _plan_sha256(before))
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any("ALTER TABLE" in sql for sql, _params in cursor.calls))

    def test_apply_adds_schema_backfills_and_commits_after_postcheck(self):
        cursor = FakeCursor(update_rowcounts=[1])
        connection = FakeConnection(cursor)
        before = [ownership()]
        after = [ownership(status="stored")]
        with patch(
            "backend.features.ai_summary_ownership.migration.collect_ownership",
            side_effect=[({"company_id", "project_id"}, before), ({"company_id", "project_id"}, after)],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256=_plan_sha256(before),
            )
        self.assertTrue(result["complete"])
        self.assertEqual(result["updated"], 1)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in cursor.calls)
        self.assertIn("LOCK TABLE project_ai_summary IN ACCESS EXCLUSIVE MODE", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS company_id", sql)
        self.assertIn("uq_project_ai_summary_company_project", sql)

    def test_apply_rejects_plan_drift_before_update(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        audited = [ownership(company_id=4, project_id=10)]
        changed = [ownership(company_id=8, project_id=20)]
        with patch(
            "backend.features.ai_summary_ownership.migration.collect_ownership",
            return_value=({"company_id", "project_id"}, changed),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=1,
                    expected_plan_sha256=_plan_sha256(audited),
                )
        self.assertFalse(any(sql.startswith("UPDATE project_ai_summary") for sql, _params in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_cli_requires_confirmation_count_and_sha_before_connecting(self):
        with patch("backend.features.ai_summary_ownership.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", APPLY_CONFIRMATION, "--expected-ready-count", "1"])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
