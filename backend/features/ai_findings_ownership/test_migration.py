import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.ai_findings_ownership.migration import (
    APPLY_CONFIRMATION,
    _plan_sha256,
    build_report,
    classify_stored_finding,
    main,
    run_migration,
)


def finding(status="ready", finding_id=20, company_id=4, project_id=10):
    return {
        "findingId": finding_id,
        "storedCompanyId": company_id if status == "stored" else None,
        "storedProjectId": project_id if status == "stored" else None,
        "proposedCompanyId": company_id,
        "proposedProjectId": project_id,
        "status": status,
        "reason": "stored_owner_verified" if status == "stored" else "verified_project_owner",
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
        if compact.startswith("UPDATE ai_findings"):
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


class AiFindingsOwnershipMigrationTests(unittest.TestCase):
    def test_project_only_finding_is_ready(self):
        result = classify_stored_finding(
            {"id": 20, "project_name": "Объект A", "linked_entity_type": "", "linked_entity_id": ""},
            {"Объект A": [{"id": 10, "company_id": 4}]},
            {},
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual((result["proposedCompanyId"], result["proposedProjectId"]), (4, 10))

    def test_linked_entity_owner_mismatch_fails_closed(self):
        result = classify_stored_finding(
            {"id": 20, "project_name": "Объект A", "linked_entity_type": "room", "linked_entity_id": "30"},
            {
                "Объект A": [{"id": 10, "company_id": 4}],
                "Объект B": [{"id": 11, "company_id": 8}],
            },
            {("room", "30"): [{"project_name": "Объект B"}]},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "linked_entity_owner_mismatch"))

    def test_stored_owner_mismatch_fails_closed(self):
        result = classify_stored_finding(
            {
                "id": 20,
                "project_name": "Объект A",
                "linked_entity_type": "",
                "linked_entity_id": "",
                "stored_company_id": 8,
                "stored_project_id": 11,
            },
            {"Объект A": [{"id": 10, "company_id": 4}]},
            {},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "stored_owner_mismatch"))

    def test_report_hides_business_content(self):
        report = build_report(set(), [finding()])
        self.assertTrue(report["readyForMigration"])
        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["readyByCompany"], {"4": 1})
        self.assertNotIn("projectName", str(report))

    def test_dry_run_is_read_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        before = [finding()]
        with patch(
            "backend.features.ai_findings_ownership.migration.collect_ownership",
            return_value=(set(), before),
        ):
            result = run_migration(connection, apply=False)
        self.assertEqual(result["readyCount"], 1)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any("ALTER TABLE" in sql for sql, _params in cursor.calls))

    def test_apply_bulk_backfills_and_commits_after_postcheck(self):
        cursor = FakeCursor(update_rowcount=2)
        connection = FakeConnection(cursor)
        before = [finding(finding_id=20), finding(finding_id=21)]
        after = [finding("stored", 20), finding("stored", 21)]
        with patch(
            "backend.features.ai_findings_ownership.migration.collect_ownership",
            side_effect=[({"company_id", "project_id"}, before), ({"company_id", "project_id"}, after)],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=2,
                expected_plan_sha256=_plan_sha256(before),
            )
        self.assertTrue(result["complete"])
        self.assertEqual(result["updated"], 2)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in cursor.calls)
        self.assertIn("LOCK TABLE ai_findings IN ACCESS EXCLUSIVE MODE", sql)
        self.assertIn("FROM UNNEST", sql)
        self.assertIn("idx_ai_findings_owner_status", sql)

    def test_apply_rejects_plan_drift_before_update(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        audited = [finding(company_id=4, project_id=10)]
        changed = [finding(company_id=8, project_id=11)]
        with patch(
            "backend.features.ai_findings_ownership.migration.collect_ownership",
            return_value=({"company_id", "project_id"}, changed),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan SHA-256"):
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=1,
                    expected_plan_sha256=_plan_sha256(audited),
                )
        self.assertFalse(any(sql.startswith("UPDATE ai_findings") for sql, _params in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_cli_requires_confirmation_count_and_sha(self):
        with patch("backend.features.ai_findings_ownership.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", APPLY_CONFIRMATION, "--expected-ready-count", "1342"])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
