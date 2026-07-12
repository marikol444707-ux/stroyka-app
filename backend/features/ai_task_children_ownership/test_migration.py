import unittest
from unittest.mock import patch

from backend.features.ai_task_children_ownership.migration import (
    _plan_sha256,
    build_report,
    classify_attachment,
    classify_report,
    run_migration,
)


def task(task_id=10, scope="company", company_id=4, project_id=20):
    return {
        "taskId": task_id,
        "scope": scope,
        "companyId": company_id if scope == "company" else None,
        "projectId": project_id if scope == "company" else None,
        "status": "verified",
    }


def report(status="ready", report_id=30, task_id=10, scope="company", company_id=4, project_id=20):
    return {
        "table": "ai_task_reports", "recordId": report_id, "taskId": task_id,
        "proposedScope": scope,
        "proposedCompanyId": company_id if scope == "company" else None,
        "proposedProjectId": project_id if scope == "company" else None,
        "status": status, "reason": "verified_task_parent",
    }


def attachment(status="ready", attachment_id=40, task_id=10, report_id=30, scope="company", company_id=4, project_id=20):
    return {
        "table": "ai_task_attachments", "recordId": attachment_id,
        "taskId": task_id, "reportId": report_id,
        "proposedScope": scope,
        "proposedCompanyId": company_id if scope == "company" else None,
        "proposedProjectId": project_id if scope == "company" else None,
        "status": status, "reason": "verified_report_and_task_parents",
    }


class FakeCursor:
    def __init__(self, report_updates=0, attachment_updates=0):
        self.calls = []
        self.rowcount = 0
        self.report_updates = report_updates
        self.attachment_updates = attachment_updates
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if compact.startswith("UPDATE ai_task_reports r SET owner_scope"):
            self.rowcount = self.report_updates
        elif compact.startswith("UPDATE ai_task_attachments a SET owner_scope"):
            self.rowcount = self.attachment_updates

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


class AiTaskChildrenOwnershipMigrationTests(unittest.TestCase):
    def test_report_inherits_company_task_owner(self):
        result = classify_report({"id": 30, "task_id": 10}, {10: task()})
        self.assertEqual(result["status"], "ready")
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (4, 20))

    def test_report_inherits_platform_task_owner(self):
        result = classify_report({"id": 30, "task_id": 10}, {10: task(scope="platform")})
        self.assertEqual((result["status"], result["proposedScope"]), ("ready", "platform"))

    def test_attachment_requires_same_report_and_task(self):
        reports = {30: report()}
        result = classify_attachment(
            {"id": 40, "report_id": 30, "task_id": 11}, reports, {10: task(), 11: task(task_id=11)},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "report_task_mismatch"))

    def test_attachment_inherits_verified_parent_owner(self):
        result = classify_attachment(
            {"id": 40, "report_id": 30, "task_id": 10}, {30: report()}, {10: task()},
        )
        self.assertEqual((result["status"], result["proposedCompanyId"]), ("ready", 4))

    def test_stored_owner_mismatch_is_blocked(self):
        result = classify_report(
            {"id": 30, "task_id": 10, "stored_scope": "company", "stored_company_id": 8, "stored_project_id": 20},
            {10: task()},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "stored_owner_mismatch"))

    def test_report_counts_both_tables(self):
        result = build_report(set(), set(), [report(), report(scope="platform", report_id=31), attachment()])
        self.assertEqual(result["summary"]["ready"], 3)
        self.assertEqual(result["readyByTable"], {"ai_task_attachments": 1, "ai_task_reports": 2})

    def test_empty_tables_without_owner_columns_are_not_strict_ready(self):
        result = build_report(set(), set(), [])
        self.assertTrue(result["readyForMigration"])
        self.assertFalse(result["readyForStrictRuntime"])

        complete = build_report(
            {"owner_scope", "company_id", "project_id"},
            {"owner_scope", "company_id", "project_id"},
            [],
        )
        self.assertTrue(complete["readyForStrictRuntime"])

    def test_dry_run_is_read_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        classified = [report()]
        with patch(
            "backend.features.ai_task_children_ownership.migration.collect_ownership",
            return_value=(set(), set(), classified),
        ):
            result = run_migration(connection, apply=False)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)

    def test_apply_updates_parent_before_child_and_commits(self):
        cursor = FakeCursor(report_updates=1, attachment_updates=1)
        connection = FakeConnection(cursor)
        before = [report(), attachment()]
        after = [report("stored"), attachment("stored")]
        with patch(
            "backend.features.ai_task_children_ownership.migration.collect_ownership",
            side_effect=[(set(), set(), before), ({"owner_scope", "company_id", "project_id"}, {"owner_scope", "company_id", "project_id"}, after)],
        ):
            result = run_migration(connection, True, 2, _plan_sha256(before))
        self.assertTrue(result["complete"])
        self.assertEqual((result["updatedReports"], result["updatedAttachments"]), (1, 1))
        updates = [sql for sql, _params in cursor.calls if sql.startswith("UPDATE ai_task_")]
        self.assertTrue(updates[0].startswith("UPDATE ai_task_reports"))
        self.assertTrue(updates[1].startswith("UPDATE ai_task_attachments"))
        self.assertTrue(connection.committed)

    def test_apply_schema_rejects_partial_legacy_owner(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch(
            "backend.features.ai_task_children_ownership.migration.collect_ownership",
            side_effect=[
                (set(), set(), []),
                (
                    {"owner_scope", "company_id", "project_id"},
                    {"owner_scope", "company_id", "project_id"},
                    [],
                ),
            ],
        ):
            run_migration(connection, True, 0, _plan_sha256([]))

        constraint_sql = "\n".join(sql for sql, _params in cursor.calls if "ADD CONSTRAINT" in sql)
        self.assertIn(
            "owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
            constraint_sql,
        )

    def test_apply_rejects_plan_drift(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch(
            "backend.features.ai_task_children_ownership.migration.collect_ownership",
            return_value=(set(), set(), [report(company_id=8)]),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(connection, True, 1, _plan_sha256([report()]))
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
