import unittest
from unittest.mock import patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


class AuditOwnershipReportTests(unittest.TestCase):
    def base_rows(self):
        return {
            "audit_log": [],
            "projects": [],
            "user_company_roles": [],
            "entity_owners": [],
        }

    def test_unique_project_resolves_exact_tenant_owner(self):
        rows = self.base_rows()
        rows["projects"] = [{"id": 11, "name": "Лицей", "company_id": 3}]
        rows["audit_log"] = [
            {
                "id": 7,
                "user_id": 5,
                "action": "create",
                "entity_type": "supply_request",
                "entity_id": 18,
                "project_name": "Лицей",
            }
        ]
        rows["user_company_roles"] = [
            {"user_id": 5, "company_id": 3, "active": True}
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["readyByCompany"], {"3": 1})
        self.assertEqual(report["summary"]["verified"], 1)

    def test_duplicate_project_name_is_ambiguous_without_exact_parent(self):
        rows = self.base_rows()
        rows["projects"] = [
            {"id": 11, "name": "Школа", "company_id": 3},
            {"id": 12, "name": "Школа", "company_id": 4},
        ]
        rows["audit_log"] = [
            {
                "id": 8,
                "action": "update",
                "entity_type": "unknown_parent",
                "entity_id": 19,
                "project_name": "Школа",
            }
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_name_ambiguous")

    def test_exact_entity_parent_disambiguates_duplicate_project_name(self):
        rows = self.base_rows()
        rows["projects"] = [
            {"id": 11, "name": "Школа", "company_id": 3},
            {"id": 12, "name": "Школа", "company_id": 4},
        ]
        rows["entity_owners"] = [
            {
                "entity_type": "supply_request",
                "entity_id": 19,
                "company_id": 4,
                "project_id": 12,
                "project_name": "Школа",
            }
        ]
        rows["audit_log"] = [
            {
                "id": 9,
                "action": "update",
                "entity_type": "supply_request",
                "entity_id": 19,
                "project_name": "Школа",
            }
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["readyByCompany"], {"4": 1})

    def test_conflicting_project_and_entity_owner_is_mismatched(self):
        rows = self.base_rows()
        rows["projects"] = [
            {"id": 11, "name": "Лицей", "company_id": 3},
            {"id": 12, "name": "Склад", "company_id": 4},
        ]
        rows["entity_owners"] = [
            {
                "entity_type": "work_journal",
                "entity_id": 25,
                "company_id": 4,
                "project_id": 12,
                "project_name": "Склад",
            }
        ]
        rows["audit_log"] = [
            {
                "id": 10,
                "action": "update",
                "entity_type": "work_journal",
                "entity_id": 25,
                "project_name": "Лицей",
            }
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_entity_owner_mismatch")

    def test_unique_actor_membership_is_fallback_for_company_action(self):
        rows = self.base_rows()
        rows["audit_log"] = [
            {
                "id": 11,
                "user_id": 5,
                "action": "director_agent_ask",
                "entity_type": "director_agent",
            }
        ]
        rows["user_company_roles"] = [
            {"user_id": 5, "company_id": 8, "active": True}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["readyByCompany"], {"8": 1})
        self.assertEqual(report["summary"]["verified"], 1)

    def test_multiple_actor_memberships_are_not_guessed(self):
        rows = self.base_rows()
        rows["audit_log"] = [
            {
                "id": 12,
                "user_id": 5,
                "action": "director_agent_ask",
                "entity_type": "director_agent",
            }
        ]
        rows["user_company_roles"] = [
            {"user_id": 5, "company_id": 8, "active": True},
            {"user_id": 5, "company_id": 9, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "actor_company_ambiguous")

    def test_review_summary_and_plan_hash_cover_all_review_rows(self):
        rows = self.base_rows()
        rows["audit_log"] = [
            {"id": 20, "entity_type": "crm_lead", "entity_id": 404},
            {"id": 21, "entity_type": "invite_code", "entity_id": 405},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["reviewCount"], 2)
        self.assertEqual(
            report["reviewByReason"],
            {"entity_parent_not_found": 2},
        )
        self.assertEqual(report["reviewByEntityType"], {"crm_lead": 1, "invite_code": 1})
        self.assertEqual(report["reviewIdRange"], {"first": 20, "last": 21})
        self.assertEqual(len(report["reviewPlanSha256"]), 64)

    def test_login_and_2fa_actions_are_platform_scope(self):
        rows = self.base_rows()
        rows["audit_log"] = [
            {"id": 13, "user_id": 5, "action": "login", "entity_type": "user"},
            {"id": 14, "user_id": 5, "action": "2fa_setup", "entity_type": "user"},
        ]
        rows["user_company_roles"] = [
            {"user_id": 5, "company_id": 8, "active": True},
            {"user_id": 5, "company_id": 9, "active": True},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["summary"]["platformRows"], 2)

    def test_actor_conflict_with_exact_parent_is_mismatched(self):
        rows = self.base_rows()
        rows["projects"] = [{"id": 11, "name": "Лицей", "company_id": 3}]
        rows["audit_log"] = [
            {
                "id": 15,
                "user_id": 5,
                "action": "update",
                "entity_type": "project",
                "entity_id": 11,
                "project_name": "Лицей",
            }
        ]
        rows["user_company_roles"] = [
            {"user_id": 5, "company_id": 4, "active": True}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "actor_parent_company_mismatch")

    def test_report_does_not_expose_audit_text_or_identity(self):
        rows = self.base_rows()
        rows["audit_log"] = [
            {
                "id": 16,
                "user_name": "Секретное имя",
                "description": "Секретное описание",
                "ip": "10.0.0.1",
                "action": "unknown",
            }
        ]

        serialized = str(build_report_from_rows(rows))

        self.assertNotIn("Секретное", serialized)
        self.assertNotIn("10.0.0.1", serialized)

    def test_loader_does_not_read_audit_text_ip_or_user_profile(self):
        class Cursor:
            def __init__(self):
                self.calls = []
                self.last_sql = ""

            def execute(self, sql, _params=None):
                self.last_sql = " ".join(sql.split()).lower()
                self.calls.append(self.last_sql)

            def fetchall(self):
                if "information_schema.columns" in self.last_sql:
                    return []
                return []

        cursor = Cursor()

        rows = load_ownership_rows(cursor)
        sql = " ".join(cursor.calls)

        self.assertEqual(rows["audit_log"], [])
        self.assertNotIn("description", sql)
        self.assertNotIn("user_name", sql)
        self.assertNotIn("user_role", sql)
        self.assertNotIn(" ip", sql)
        self.assertNotIn("email", sql)
        self.assertNotIn("password", sql)

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
