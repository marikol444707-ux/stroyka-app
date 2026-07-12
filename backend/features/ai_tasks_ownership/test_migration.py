import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.ai_tasks_ownership.migration import (
    APPLY_CONFIRMATION,
    _plan_sha256,
    build_report,
    classify_stored_task,
    main,
    run_migration,
)


def task(status="ready", task_id=20, scope="company", company_id=4, project_id=10):
    return {
        "taskId": task_id,
        "storedScope": scope if status == "stored" else None,
        "storedCompanyId": company_id if status == "stored" and scope == "company" else None,
        "storedProjectId": project_id if status == "stored" and scope == "company" else None,
        "proposedScope": scope,
        "proposedCompanyId": company_id if scope == "company" else None,
        "proposedProjectId": project_id if scope == "company" else None,
        "status": status,
        "reason": "stored_owner_verified" if status == "stored" else "verified_project_task",
    }


class FakeCursor:
    def __init__(self, update_rowcount=0):
        self.calls = []
        self.rowcount = 0
        self.update_rowcount = update_rowcount
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if compact.startswith("UPDATE ai_tasks t SET owner_scope"):
            self.rowcount = self.update_rowcount

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


class AiTasksOwnershipMigrationTests(unittest.TestCase):
    def test_project_task_is_ready_for_company_scope(self):
        result = classify_stored_task(
            {"id": 20, "project_name": "Объект A", "finding_id": None},
            {"Объект A": [{"id": 10, "company_id": 4}]},
            {},
        )
        self.assertEqual((result["status"], result["proposedScope"]), ("ready", "company"))
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (4, 10))

    def test_system_task_is_ready_for_platform_scope(self):
        result = classify_stored_task(
            {"id": 20, "project_name": "Система", "finding_id": None}, {}, {}
        )
        self.assertEqual((result["status"], result["proposedScope"]), ("ready", "platform"))
        self.assertIsNone(result["proposedCompanyId"])

    def test_system_task_cannot_store_company_ids(self):
        result = classify_stored_task(
            {
                "id": 20, "project_name": "Система", "finding_id": None,
                "stored_scope": "platform", "stored_company_id": 4, "stored_project_id": 10,
            }, {}, {},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "platform_owner_contains_tenant_ids"))

    def test_finding_parent_owner_mismatch_fails_closed(self):
        result = classify_stored_task(
            {"id": 20, "project_name": "Объект A", "finding_id": 30},
            {"Объект A": [{"id": 10, "company_id": 4}]},
            {30: {"status": "verified", "scope": "tenant", "companyId": 8, "projectId": 11}},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "finding_owner_mismatch"))

    def test_report_counts_company_and_platform_ready_rows(self):
        report = build_report(set(), [task(), task(task_id=21, scope="platform")])
        self.assertEqual(report["readyByScope"], {"company": 1, "platform": 1})
        self.assertTrue(report["readyForMigration"])
        self.assertFalse(report["readyForStrictRuntime"])

    def test_dry_run_is_read_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [task()]
        with patch("backend.features.ai_tasks_ownership.migration.collect_ownership", return_value=(set(), before)):
            result = run_migration(connection, apply=False)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any("ALTER TABLE" in sql for sql, _ in cursor.calls))

    def test_apply_updates_both_scopes_and_commits_after_postcheck(self):
        cursor = FakeCursor(update_rowcount=2)
        connection = FakeConnection(cursor)
        before = [task(), task(task_id=21, scope="platform")]
        after = [task("stored"), task("stored", task_id=21, scope="platform")]
        with patch(
            "backend.features.ai_tasks_ownership.migration.collect_ownership",
            side_effect=[({"owner_scope", "company_id", "project_id"}, before), ({"owner_scope", "company_id", "project_id"}, after)],
        ):
            result = run_migration(connection, True, 2, _plan_sha256(before))
        self.assertTrue(result["complete"])
        self.assertEqual(result["updated"], 2)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in cursor.calls)
        self.assertIn("LOCK TABLE ai_tasks IN ACCESS EXCLUSIVE MODE", sql)
        self.assertIn("FROM UNNEST", sql)

    def test_apply_rejects_plan_drift_before_update(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        audited = [task()]
        changed = [task(company_id=8, project_id=11)]
        with patch(
            "backend.features.ai_tasks_ownership.migration.collect_ownership",
            return_value=({"owner_scope", "company_id", "project_id"}, changed),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(connection, True, 1, _plan_sha256(audited))
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any(sql.startswith("UPDATE ai_tasks") for sql, _ in cursor.calls))

    def test_cli_requires_confirmation_count_and_sha(self):
        with patch("backend.features.ai_tasks_ownership.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", APPLY_CONFIRMATION, "--expected-ready-count", "2039"])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
