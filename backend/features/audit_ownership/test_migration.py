import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from . import migration as migration_module
from .migration import (
    APPLY_CONFIRMATION,
    _plan_sha256,
    build_migration_report,
    classify_migration_row,
    collect_ownership,
    main,
    run_migration,
)


def evidence(record_id=1, status="verified", scope="company", company_id=4, project_id=10):
    return {
        "recordId": record_id,
        "entityType": "project",
        "scope": scope if status == "verified" else None,
        "companyId": company_id if status == "verified" else None,
        "projectId": project_id if status == "verified" else None,
        "status": status,
        "reason": "verified_entity_parent" if status == "verified" else "project_not_found",
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
        if compact.startswith("UPDATE audit_log"):
            self.rowcount = self.update_rowcounts.pop(0) if self.update_rowcounts else 0

    def fetchall(self):
        return []

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


class AuditOwnershipMigrationTests(unittest.TestCase):
    def test_verified_company_and_platform_rows_are_ready(self):
        company = classify_migration_row(evidence())
        platform = classify_migration_row(
            evidence(2, scope="platform", company_id=None, project_id=None)
        )

        self.assertEqual(
            (company["status"], company["proposedScope"], company["proposedCompanyId"]),
            ("ready", "company", 4),
        )
        self.assertEqual(
            (platform["status"], platform["proposedScope"]), ("ready", "platform")
        )

    def test_unresolved_row_requires_explicit_review_set_before_legacy(self):
        unresolved = evidence(status="unresolved")

        blocked = classify_migration_row(unresolved, allow_legacy=False)
        accepted = classify_migration_row(unresolved, allow_legacy=True)

        self.assertEqual((blocked["status"], blocked["reason"]), ("unresolved", "project_not_found"))
        self.assertEqual(
            (accepted["status"], accepted["proposedScope"], accepted["reason"]),
            ("ready", "legacy", "explicit_review_set_as_legacy"),
        )

    def test_ambiguous_or_mismatched_rows_cannot_be_hidden_as_legacy(self):
        ambiguous = classify_migration_row(evidence(status="ambiguous"), allow_legacy=True)
        mismatched = classify_migration_row(evidence(status="mismatched"), allow_legacy=True)

        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(mismatched["status"], "mismatched")

    def test_stored_owner_mismatch_fails_closed(self):
        result = classify_migration_row(
            evidence(),
            {"owner_scope": "company", "company_id": 5, "project_id": 10},
        )
        self.assertEqual((result["status"], result["reason"]), ("mismatched", "stored_company_owner_mismatch"))

    def test_report_is_strict_only_after_columns_and_all_rows_are_stored(self):
        ready = classify_migration_row(evidence())
        stored = classify_migration_row(
            evidence(),
            {"owner_scope": "company", "company_id": 4, "project_id": 10},
        )

        before = build_migration_report(set(), [ready], "a" * 64)
        after = build_migration_report({"owner_scope", "company_id", "project_id"}, [stored], "b" * 64)

        self.assertTrue(before["readyForMigration"])
        self.assertFalse(before["readyForStrictRuntime"])
        self.assertTrue(after["readyForStrictRuntime"])

    def test_collect_rejects_changed_review_sha(self):
        rows = {
            "audit_log": [{"id": 9, "entity_type": "project", "entity_id": 404}],
            "projects": [],
            "user_company_roles": [],
            "entity_owners": [],
        }
        with patch.object(migration_module, "load_ownership_rows", return_value=rows):
            with self.assertRaisesRegex(RuntimeError, "review set changed"):
                collect_ownership(FakeCursor(), "f" * 64)

    def test_dry_run_is_read_only_and_never_changes_schema(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        classified = [classify_migration_row(evidence())]
        with patch.object(
            migration_module, "collect_ownership", return_value=(set(), classified, "a" * 64)
        ):
            result = run_migration(connection)

        self.assertEqual(result["readyCount"], 1)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any("ALTER TABLE" in sql for sql, _params in cursor.calls))

    def test_apply_adds_schema_and_commits_only_after_strict_postcheck(self):
        cursor = FakeCursor(update_rowcounts=[1])
        connection = FakeConnection(cursor)
        ready = [classify_migration_row(evidence())]
        stored = [
            classify_migration_row(
                evidence(),
                {"owner_scope": "company", "company_id": 4, "project_id": 10},
            )
        ]
        with patch.object(
            migration_module,
            "collect_ownership",
            side_effect=[
                ({"owner_scope", "company_id", "project_id"}, ready, "a" * 64),
                ({"owner_scope", "company_id", "project_id"}, stored, "b" * 64),
            ],
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256=_plan_sha256(ready),
            )

        self.assertTrue(result["complete"])
        self.assertEqual(result["updated"], 1)
        self.assertTrue(connection.committed)
        sql = " ".join(call[0] for call in cursor.calls)
        self.assertIn("LOCK TABLE audit_log IN ACCESS EXCLUSIVE MODE", sql)
        self.assertIn("ck_audit_log_owner_scope", sql)

    def test_apply_rejects_plan_drift_before_update(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        audited = [classify_migration_row(evidence())]
        changed = [classify_migration_row(evidence(company_id=8, project_id=20))]
        with patch.object(
            migration_module,
            "collect_ownership",
            return_value=({"owner_scope", "company_id", "project_id"}, changed, "a" * 64),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan changed"):
                run_migration(
                    connection,
                    apply=True,
                    expected_ready_count=1,
                    expected_plan_sha256=_plan_sha256(audited),
                )

        self.assertFalse(any(sql.startswith("UPDATE audit_log") for sql, _params in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_apply_rolls_back_when_an_ownerless_row_changed_before_update(self):
        cursor = FakeCursor(update_rowcounts=[0])
        connection = FakeConnection(cursor)
        ready = [classify_migration_row(evidence())]
        with patch.object(
            migration_module,
            "collect_ownership",
            return_value=({"owner_scope", "company_id", "project_id"}, ready, "a" * 64),
        ):
            result = run_migration(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256=_plan_sha256(ready),
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "write_conflict")
        self.assertTrue(result["rolledBack"])
        self.assertFalse(connection.committed)

    def test_cli_requires_confirmation_count_and_plan_before_connecting(self):
        with patch.object(migration_module.psycopg2, "connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", APPLY_CONFIRMATION, "--expected-ready-count", "1"])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
