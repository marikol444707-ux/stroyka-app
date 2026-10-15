"""Offline regression tests for QA read-only session lookup."""
import unittest
from collections import UserDict

from backend.features.company_context.qa_readonly import (
    QAReadOnlyAuthRejected,
    resolve_qa_identity_read_only,
)


class Cursor:
    def __init__(self, rows, read_only="on"):
        self.rows = rows
        self.read_only = read_only
        self.queries = []

    def execute(self, sql, parameters=None):
        self.queries.append((sql, parameters))

    def fetchone(self):
        return {"transaction_read_only": self.read_only}

    def fetchall(self):
        return self.rows


def row():
    return {
        "user_id": 9, "user_name": "QA", "user_email": "qa@example.test",
        "company_id": 5, "membership_id": 12, "role": "прораб", "global_role": "прораб",
        "user_account_id": 3, "company_account_id": 3,
    }


class ReadOnlyAuthTest(unittest.TestCase):
    def test_single_company_uses_select_only(self):
        cursor = Cursor([row()])
        result = resolve_qa_identity_read_only(
            cursor,
            {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
        )
        self.assertEqual(result["user"]["companyId"], 5)
        self.assertEqual(len(cursor.queries), 2)
        self.assertEqual(cursor.queries[0][0], "SHOW transaction_read_only")
        sql = cursor.queries[1][0].upper()
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
                self.assertEqual(len(cursor.queries), 2)

    def test_global_platform_or_account_role_cannot_use_company_membership(self):
        for global_role in ("platform_support", "platform_admin", "system_owner",
                            "billing_admin", "account_owner", "account_admin", "поставщик", "unknown", None):
            with self.subTest(global_role=global_role):
                cursor = Cursor([dict(row(), global_role=global_role)])
                with self.assertRaises(QAReadOnlyAuthRejected):
                    resolve_qa_identity_read_only(cursor, {
                        "authenticationKind": "cookie_session", "sessionHash": "a" * 64,
                    })

    def test_distinct_valid_company_roles_keep_the_server_membership_role(self):
        cursor = Cursor([dict(row(), global_role="главный_инженер")])
        result = resolve_qa_identity_read_only(cursor, {
            "authenticationKind": "cookie_session", "sessionHash": "a" * 64,
        })
        self.assertEqual(result["user"]["role"], "прораб")
        self.assertNotIn("global_role", repr(result))

    def test_known_user_account_must_match_membership_company_account(self):
        for user_account_id in (4, 0, -1, True, "3"):
            with self.subTest(user_account_id=user_account_id):
                cursor = Cursor([dict(row(), user_account_id=user_account_id, company_account_id=3)])
                with self.assertRaises(QAReadOnlyAuthRejected):
                    resolve_qa_identity_read_only(cursor, {
                        "authenticationKind": "cookie_session", "sessionHash": "a" * 64,
                    })

    def test_legacy_null_user_account_keeps_exact_server_membership(self):
        cursor = Cursor([dict(row(), user_account_id=None)])
        result = resolve_qa_identity_read_only(cursor, {
            "authenticationKind": "cookie_session", "sessionHash": "a" * 64,
        })
        self.assertEqual(result["user"]["companyId"], 5)
        self.assertNotIn("account_id", repr(result))

    def test_invalid_session_claims_do_not_query_database(self):
        for claims in (None, {}, {"authenticationKind": "bearer", "sessionHash": "a" * 64},
                       {"authenticationKind": "cookie_session", "sessionHash": "wrong"}):
            with self.subTest(claims=claims):
                cursor = Cursor([row()])
                with self.assertRaises(QAReadOnlyAuthRejected):
                    resolve_qa_identity_read_only(cursor, claims)
                self.assertEqual(cursor.queries, [])

    def test_write_enabled_transaction_is_rejected_before_session_query(self):
        cursor = Cursor([row()], read_only="off")
        with self.assertRaises(QAReadOnlyAuthRejected):
            resolve_qa_identity_read_only(
                cursor,
                {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
            )
        self.assertEqual(cursor.queries, [("SHOW transaction_read_only", None)])

    def test_psycopg_mapping_rows_are_accepted(self):
        cursor = Cursor([UserDict(row())])
        cursor.fetchone = lambda: UserDict({"transaction_read_only": "on"})
        result = resolve_qa_identity_read_only(
            cursor,
            {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
        )
        self.assertEqual(result["defaultCompanyId"], 5)

    def test_ambiguous_memberships_are_rejected(self):
        cursor = Cursor([row(), row()])
        with self.assertRaises(QAReadOnlyAuthRejected):
            resolve_qa_identity_read_only(
                cursor,
                {"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
            )


if __name__ == "__main__":
    unittest.main()
