import unittest
from unittest.mock import patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


class ApiErrorOwnershipReportTests(unittest.TestCase):
    def base_rows(self):
        return {
            "api_errors": [],
            "users": [],
            "user_company_roles": [],
        }

    def test_unique_active_membership_resolves_company_owner(self):
        rows = self.base_rows()
        rows["api_errors"] = [
            {"id": 10, "user_id": 7, "method": "GET", "status_code": 500},
        ]
        rows["users"] = [{"id": 7, "role": "директор", "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["verifiedByCompany"], {"3": 1})

    def test_multiple_active_memberships_are_ambiguous(self):
        rows = self.base_rows()
        rows["api_errors"] = [{"id": 11, "user_id": 7, "method": "POST"}]
        rows["users"] = [{"id": 7, "role": "директор", "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
            {"user_id": 7, "company_id": 4, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "actor_company_ambiguous")

    def test_platform_staff_role_resolves_platform_owner(self):
        rows = self.base_rows()
        rows["api_errors"] = [
            {
                "id": 12,
                "user_id": 8,
                "user_role": "platform_support",
                "method": "GET",
            }
        ]
        rows["users"] = [{"id": 8, "role": "platform_support", "active": True}]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["summary"]["platformRows"], 1)

    def test_role_scope_change_is_mismatched_instead_of_reassigned(self):
        rows = self.base_rows()
        rows["api_errors"] = [
            {
                "id": 18,
                "user_id": 8,
                "user_role": "директор",
                "method": "GET",
            }
        ]
        rows["users"] = [{"id": 8, "role": "system_owner", "active": True}]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "actor_role_scope_mismatch")

    def test_client_account_role_is_not_promoted_to_global_platform(self):
        rows = self.base_rows()
        rows["api_errors"] = [{"id": 13, "user_id": 9, "method": "GET"}]
        rows["users"] = [
            {"id": 9, "role": "account_owner", "active": True, "platform_account_id": 4},
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "account_scope_not_supported")

    def test_anonymous_error_requires_explicit_legacy_decision(self):
        rows = self.base_rows()
        rows["api_errors"] = [{"id": 14, "user_id": None, "method": "CLIENT"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "actor_missing")

    def test_missing_or_inactive_user_is_not_ownership(self):
        rows = self.base_rows()
        rows["api_errors"] = [
            {"id": 15, "user_id": 404, "method": "GET"},
            {"id": 16, "user_id": 10, "method": "GET"},
        ]
        rows["users"] = [{"id": 10, "role": "директор", "active": False}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 2)
        self.assertEqual(
            [item["reason"] for item in report["needsReview"]],
            ["actor_not_found", "actor_inactive"],
        )

    def test_report_does_not_expose_path_message_or_identity(self):
        rows = self.base_rows()
        rows["api_errors"] = [
            {
                "id": 17,
                "user_id": None,
                "method": "GET",
                "path": "/secret/customer/42",
                "error_message": "private payload",
                "user_name": "Secret Person",
            }
        ]

        serialized = str(build_report_from_rows(rows))

        self.assertNotIn("/secret/customer/42", serialized)
        self.assertNotIn("private payload", serialized)
        self.assertNotIn("Secret Person", serialized)

    def test_loader_avoids_error_text_and_user_identity_columns(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql):
                self.calls.append(" ".join(sql.split()).lower())

            def fetchall(self):
                return []

        cursor = Cursor()

        rows = load_ownership_rows(cursor)
        sql = " ".join(cursor.calls)

        self.assertEqual(rows["api_errors"], [])
        self.assertNotIn("error_message", sql)
        self.assertNotIn("path", sql)
        self.assertNotIn("user_name", sql)

    def test_database_runner_forces_readonly_session(self):
        class Cursor:
            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.session = None
                self.closed = False

            def set_session(self, **kwargs):
                self.session = kwargs

            def cursor(self, **_kwargs):
                return Cursor()

            def close(self):
                self.closed = True

        connection = Connection()
        with patch.object(
            ownership_report_module,
            "load_ownership_rows",
            return_value=self.base_rows(),
        ):
            report = run_ownership_report(lambda: connection)

        self.assertEqual(connection.session, {"readonly": True, "autocommit": False})
        self.assertTrue(connection.closed)
        self.assertEqual(report["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
