import unittest
from unittest.mock import patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


class MessengerAccountOwnershipReportTests(unittest.TestCase):
    def base_rows(self):
        return {
            "messenger_accounts": [],
            "users": [],
            "user_company_roles": [],
            "staff": [],
        }

    def test_user_account_uses_active_company_membership(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {
                "id": 10,
                "provider": "max",
                "user_id": 7,
                "external_user_id": "max-7",
                "enabled": True,
            },
        ]
        rows["users"] = [{"id": 7, "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForRuntime"])
        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["verifiedByCompany"], {"3": 1})

    def test_user_account_may_be_shared_across_active_companies(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {
                "id": 10,
                "provider": "max",
                "user_id": 7,
                "external_user_id": "max-7",
                "enabled": True,
            },
        ]
        rows["users"] = [{"id": 7, "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
            {"user_id": 7, "company_id": 8, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForRuntime"])
        self.assertEqual(report["summary"]["sharedAccounts"], 1)
        self.assertEqual(report["verifiedByCompany"], {"3": 1, "8": 1})

    def test_staff_account_uses_stored_staff_company(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {
                "id": 11,
                "provider": "max",
                "staff_id": 5,
                "external_user_id": "max-staff-5",
                "enabled": True,
            },
        ]
        rows["staff"] = [{"id": 5, "company_id": 4}]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForRuntime"])
        self.assertEqual(report["verifiedByCompany"], {"4": 1})

    def test_dual_target_requires_review(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {"id": 12, "provider": "max", "user_id": 7, "staff_id": 5},
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForRuntime"])
        self.assertEqual(report["needsReview"][0]["reason"], "multiple_employee_targets")

    def test_missing_target_requires_review(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [{"id": 13, "provider": "max"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "employee_target_missing")

    def test_missing_user_requires_review(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {"id": 14, "provider": "max", "user_id": 404, "external_user_id": "max-404"},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "user_not_found")

    def test_inactive_membership_is_not_ownership(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {"id": 15, "provider": "max", "user_id": 7, "external_user_id": "max-7"},
        ]
        rows["users"] = [{"id": 7, "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": False},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "active_user_company_missing")

    def test_duplicate_external_identity_is_ambiguous_without_exposing_value(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {
                "id": 16,
                "provider": "max",
                "user_id": 7,
                "external_user_id": "secret-max-id",
            },
            {
                "id": 17,
                "provider": "max",
                "user_id": 8,
                "external_user_id": "secret-max-id",
            },
        ]
        rows["users"] = [{"id": 7, "active": True}, {"id": 8, "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
            {"user_id": 8, "company_id": 4, "active": True},
        ]

        report = build_report_from_rows(rows)
        serialized = str(report)

        self.assertEqual(report["summary"]["ambiguous"], 2)
        self.assertEqual(report["needsReview"][0]["reason"], "duplicate_external_identity")
        self.assertNotIn("secret-max-id", serialized)

    def test_duplicate_chat_identity_is_ambiguous(self):
        rows = self.base_rows()
        rows["messenger_accounts"] = [
            {"id": 18, "provider": "max", "user_id": 7, "chat_id": "shared-chat"},
            {"id": 19, "provider": "max", "user_id": 8, "chat_id": "shared-chat"},
        ]
        rows["users"] = [{"id": 7, "active": True}, {"id": 8, "active": True}]
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 3, "active": True},
            {"user_id": 8, "company_id": 4, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["ambiguous"], 2)
        self.assertEqual(report["needsReview"][0]["reason"], "duplicate_chat_identity")

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

    def test_loader_does_not_read_profile_or_phone_hash_columns(self):
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

        self.assertEqual(rows["messenger_accounts"], [])
        self.assertNotIn("display_name", sql)
        self.assertNotIn("phone_hash", sql)
        self.assertNotIn("password", sql)


if __name__ == "__main__":
    unittest.main()
