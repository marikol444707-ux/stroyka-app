"""Offline regression tests for QA read-only session lookup."""
import unittest

from backend.features.company_context.qa_readonly import (
    QAReadOnlyAuthRejected,
    resolve_qa_identity_read_only,
)


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, sql, parameters):
        self.queries.append((sql, parameters))

    def fetchall(self):
        return self.rows


def row():
    return {
        "user_id": 9, "user_name": "QA", "user_email": "qa@example.test",
        "company_id": 5, "membership_id": 12, "role": "прораб",
    }


class ReadOnlyAuthTest(unittest.TestCase):
    def test_single_company_uses_select_only(self):
        cursor = Cursor([row()])
        result = resolve_qa_identity_read_only(
            cursor,
            {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
        )
        self.assertEqual(result["user"]["companyId"], 5)
        self.assertEqual(len(cursor.queries), 1)
        sql = cursor.queries[0][0].upper()
        self.assertTrue(sql.strip().startswith("SELECT "))
        for forbidden in ("UPDATE ", "INSERT ", "DELETE ", "FOR UPDATE", "LAST_SEEN_AT"):
            self.assertNotIn(forbidden, sql)

    def test_platform_and_unknown_roles_are_rejected(self):
        for role in ("platform_admin", "account_owner", "unexpected"):
            with self.subTest(role=role):
                candidate = dict(row(), role=role)
                cursor = Cursor([candidate])
                with self.assertRaises(QAReadOnlyAuthRejected):
                    resolve_qa_identity_read_only(
                        cursor,
                        {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
                    )
                self.assertEqual(len(cursor.queries), 1)

    def test_invalid_session_claims_do_not_query_database(self):
        for claims in (None, {}, {"authenticationKind": "bearer", "sessionHash": "a" * 64},
                       {"authenticationKind": "cookie_session", "sessionHash": "wrong"}):
            with self.subTest(claims=claims):
                cursor = Cursor([row()])
                with self.assertRaises(QAReadOnlyAuthRejected):
                    resolve_qa_identity_read_only(cursor, claims)
                self.assertEqual(cursor.queries, [])

    def test_ambiguous_memberships_are_rejected(self):
        cursor = Cursor([row(), row()])
        with self.assertRaises(QAReadOnlyAuthRejected):
            resolve_qa_identity_read_only(
                cursor,
                {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
            )


if __name__ == "__main__":
    unittest.main()
