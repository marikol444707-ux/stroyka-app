import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from backend.features.company_messages.migration import (
    _apply_ready_rows,
    _load_legacy_rows,
    classify_legacy_message,
    main,
    plan_legacy_message_migration,
    run_migration,
)


class FakeCursor:
    def __init__(self, rows=(), rowcount=0, schema_exists=True):
        self.rows = list(rows)
        self.rowcount = rowcount
        self.schema_exists = schema_exists
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return {"exists": self.schema_exists}

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False
        self.session_calls = []

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class ApplyConflictCursor(FakeCursor):
    def execute(self, sql, params=()):
        super().execute(sql, params)
        if "UPDATE messages AS m" in sql:
            self.rowcount = 0


class CompanyMessageMigrationTests(unittest.TestCase):
    def test_maps_author_with_one_company(self):
        result = classify_legacy_message({
            "message_id": 11,
            "author_id": 7,
            "user_id": 7,
            "user_company_id": 4,
            "membership_company_ids": [4],
        })

        self.assertEqual(result, {
            "messageId": 11,
            "authorId": 7,
            "status": "ready",
            "companyId": 4,
            "reason": "single_company",
        })

    def test_maps_legacy_user_without_membership_from_stored_company(self):
        result = classify_legacy_message({
            "message_id": 12,
            "author_id": 8,
            "user_id": 8,
            "user_company_id": 4,
            "membership_company_ids": [],
        })

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["companyId"], 4)

    def test_rejects_author_with_multiple_company_links(self):
        result = classify_legacy_message({
            "message_id": 13,
            "author_id": 9,
            "user_id": 9,
            "user_company_id": 5,
            "membership_company_ids": [4, 5],
        })

        self.assertEqual(result["status"], "needs_review")
        self.assertIsNone(result["companyId"])
        self.assertEqual(result["reason"], "multiple_company_links")

    def test_rejects_missing_or_unassigned_author(self):
        fixtures = (
            ({"message_id": None, "author_id": 9, "user_id": 9, "user_company_id": 4}, "message_missing"),
            ({"message_id": 14, "author_id": None}, "author_missing"),
            ({"message_id": 15, "author_id": 10, "user_id": None}, "author_not_found"),
            ({"message_id": 16, "author_id": 11, "user_id": 11, "user_company_id": None}, "author_company_missing"),
        )

        for row, reason in fixtures:
            with self.subTest(reason=reason):
                result = classify_legacy_message(row)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["reason"], reason)

    def test_plan_groups_only_ready_rows_and_keeps_review_ids(self):
        plan = plan_legacy_message_migration((
            {"message_id": 21, "author_id": 1, "user_id": 1, "user_company_id": 4, "membership_company_ids": [4]},
            {"message_id": 22, "author_id": 2, "user_id": 2, "user_company_id": 4, "membership_company_ids": []},
            {"message_id": 23, "author_id": 3, "user_id": 3, "user_company_id": 5, "membership_company_ids": [4, 5]},
        ))

        self.assertEqual(plan["readyByCompany"], {4: [21, 22]})
        self.assertEqual(plan["readyCount"], 2)
        self.assertEqual(plan["reviewCount"], 1)
        self.assertEqual(plan["needsReview"][0]["messageId"], 23)

    def test_legacy_query_only_reads_general_company_chat(self):
        cursor = FakeCursor()

        _load_legacy_rows(cursor, has_company_id=True)

        sql, params = cursor.calls[0]
        self.assertIn("m.chat_type='company'", sql)
        self.assertIn("m.company_id IS NULL", sql)
        self.assertNotIn("membership.active", sql)
        self.assertEqual(params, ())

    def test_apply_rechecks_author_company_and_conflicting_memberships(self):
        cursor = FakeCursor(rowcount=2)

        updated = _apply_ready_rows(cursor, {4: [11, 12]})

        sql, params = cursor.calls[0]
        self.assertIn("UPDATE messages AS m", sql)
        self.assertIn("m.chat_type='company'", sql)
        self.assertIn("u.id=m.author_id", sql)
        self.assertIn("u.company_id=%s", sql)
        self.assertIn("FROM user_company_roles membership", sql)
        self.assertIn("membership.company_id<>%s", sql)
        self.assertNotIn("membership.active", sql)
        self.assertEqual(params, (4, [11, 12], 4, 4))
        self.assertEqual(updated, 2)

    def test_apply_rolls_back_when_recheck_skips_a_ready_row(self):
        cursor = ApplyConflictCursor(rows=(
            {
                "message_id": 31,
                "author_id": 7,
                "user_id": 7,
                "user_company_id": 4,
                "membership_company_ids": [4],
            },
        ))
        connection = FakeConnection(cursor)

        result = run_migration(connection, apply=True, expected_ready_count=1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["readyCount"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["writeConflicts"], 1)
        self.assertFalse(result["complete"])
        self.assertTrue(result["rolledBack"])
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_apply_commits_only_when_every_expected_row_is_revalidated(self):
        cursor = FakeCursor(rows=(
            {
                "message_id": 32,
                "author_id": 7,
                "user_id": 7,
                "user_company_id": 4,
                "membership_company_ids": [4],
            },
        ), rowcount=1)
        connection = FakeConnection(cursor)

        result = run_migration(connection, apply=True, expected_ready_count=1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["writeConflicts"], 0)
        self.assertTrue(result["complete"])
        self.assertFalse(result["rolledBack"])
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)

    def test_apply_stops_before_update_when_expected_count_changed(self):
        cursor = FakeCursor(rows=(
            {
                "message_id": 33,
                "author_id": 7,
                "user_id": 7,
                "user_company_id": 4,
                "membership_company_ids": [4],
            },
        ))
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "Expected 2 ready rows, found 1"):
            run_migration(connection, apply=True, expected_ready_count=2)

        self.assertFalse(any("UPDATE messages" in sql for sql, _params in cursor.calls))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_apply_requires_existing_m6_4a_schema(self):
        cursor = FakeCursor(schema_exists=False)
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "messages.company_id is missing"):
            run_migration(connection, apply=True, expected_ready_count=0)

        sql_calls = [sql for sql, _params in cursor.calls]
        self.assertFalse(any("ALTER TABLE" in sql for sql in sql_calls))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_apply_refuses_review_rows_before_any_update(self):
        cursor = FakeCursor(rows=(
            {
                "message_id": 34,
                "author_id": 7,
                "user_id": 7,
                "user_company_id": 4,
                "membership_company_ids": [4, 5],
            },
        ))
        connection = FakeConnection(cursor)

        result = run_migration(connection, apply=True, expected_ready_count=0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["failureReason"], "needs_review")
        self.assertEqual(result["reviewCount"], 1)
        self.assertFalse(any("UPDATE messages" in sql for sql, _params in cursor.calls))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_dry_run_is_not_complete_while_ready_rows_still_exist(self):
        cursor = ApplyConflictCursor(rows=(
            {
                "message_id": 41,
                "author_id": 8,
                "user_id": 8,
                "user_company_id": 4,
                "membership_company_ids": [4],
            },
        ))
        connection = FakeConnection(cursor)

        result = run_migration(connection, apply=False)

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["readyCount"], 1)
        self.assertFalse(result["complete"])
        self.assertTrue(connection.rolled_back)
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])

    def test_apply_cli_requires_expected_ready_count_before_connecting(self):
        with patch("backend.features.company_messages.migration.psycopg2.connect") as connect:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--apply", "--confirm", "APPLY_COMPANY_MESSAGES"])

        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
