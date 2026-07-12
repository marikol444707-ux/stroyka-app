import unittest
from unittest.mock import patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


class MessengerOwnershipReportTests(unittest.TestCase):
    def base_rows(self):
        return {
            "projects": [
                {"id": 10, "company_id": 1, "name": "Объект A"},
                {"id": 20, "company_id": 2, "name": "Объект B"},
            ],
            "user_company_roles": [],
            "staff": [],
            "messenger_accounts": [],
            "messenger_channels": [],
            "entity_owners": [],
            "messenger_files": [],
            "messenger_outbox": [],
        }

    def test_file_uses_unique_project_owner(self):
        rows = self.base_rows()
        rows["messenger_files"] = [{"id": 1, "project_name": "Объект A"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["readyByCompany"], {"1": 1})
        self.assertEqual(report["needsReview"], [])

    def test_channel_uses_unique_project_owner(self):
        rows = self.base_rows()
        rows["messenger_channels"] = [
            {"id": 3, "channel_type": "object", "project_name": "Объект A", "enabled": True},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["byTable"]["messenger_channels"]["verified"], 1)
        self.assertEqual(report["readyByCompany"], {"1": 1})

    def test_company_level_channel_without_owner_requires_review(self):
        rows = self.base_rows()
        rows["messenger_channels"] = [
            {"id": 4, "channel_type": "internal", "project_name": "", "enabled": True},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "channel_owner_missing")
        self.assertEqual(report["needsReview"][0]["channelType"], "internal")
        self.assertEqual(report["needsReview"][0]["rowStatus"], "enabled")

    def test_recipient_company_disambiguates_duplicate_project_name(self):
        rows = self.base_rows()
        rows["projects"].append({"id": 30, "company_id": 2, "name": "Объект A"})
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 1, "active": True}]
        rows["messenger_files"] = [{"id": 2, "user_id": 7, "project_name": "Объект A"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["readyByCompany"], {"1": 1})

    def test_multi_company_recipient_without_parent_is_ambiguous(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [
            {"user_id": 7, "company_id": 1, "active": True},
            {"user_id": 7, "company_id": 2, "active": True},
        ]
        rows["messenger_outbox"] = [{"id": 3, "user_id": 7, "entity_type": "", "entity_id": None}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "recipient_company_ambiguous")

    def test_entity_owner_conflicting_with_recipient_is_mismatched(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 2, "active": True}]
        rows["entity_owners"] = [
            {"entity_type": "supply_request", "entity_id": 9, "company_id": 1, "project_id": 10},
        ]
        rows["messenger_outbox"] = [
            {"id": 4, "user_id": 7, "entity_type": "supply_request", "entity_id": 9},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "recipient_owner_mismatch")

    def test_unsupported_entity_parent_is_not_hidden_by_recipient(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 1, "active": True}]
        rows["messenger_outbox"] = [
            {"id": 5, "user_id": 7, "entity_type": "unknown_document", "entity_id": 99},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "entity_parent_unsupported")
        self.assertEqual(report["needsReview"][0]["entityType"], "unknown_document")
        self.assertEqual(report["byEntityType"], {"messenger_outbox:unknown_document": 1})

    def test_supported_but_deleted_parent_is_reported_as_not_found(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 1, "active": True}]
        rows["messenger_outbox"] = [
            {
                "id": 12,
                "user_id": 7,
                "entity_type": "supply_request",
                "entity_id": 404,
                "status": "queued",
                "created_at": "2026-07-01",
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "entity_parent_not_found")
        self.assertEqual(report["needsReview"][0]["recipientCompanyIds"], [1])
        self.assertEqual(report["needsReview"][0]["entityId"], 404)
        self.assertEqual(report["needsReview"][0]["rowStatus"], "queued")
        self.assertEqual(report["byStatus"], {"messenger_outbox:queued": 1})

    def test_known_entity_without_owner_is_not_hidden_by_recipient(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 1, "active": True}]
        rows["entity_owners"] = [
            {"entity_type": "messenger_channel", "entity_id": 4, "project_name": ""},
        ]
        rows["messenger_outbox"] = [
            {"id": 11, "user_id": 7, "entity_type": "messenger_channel", "entity_id": 4},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "entity_owner_missing")

    def test_entity_project_company_conflict_is_mismatched(self):
        rows = self.base_rows()
        rows["entity_owners"] = [
            {"entity_type": "ai_task", "entity_id": 8, "company_id": 2, "project_id": 10},
        ]
        rows["messenger_outbox"] = [{"id": 6, "entity_type": "ai_task", "entity_id": 8}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "entity_project_company_mismatch")

    def test_account_link_and_entity_parent_produce_exact_owner(self):
        rows = self.base_rows()
        rows["user_company_roles"] = [{"user_id": 7, "company_id": 1, "active": True}]
        rows["messenger_accounts"] = [{"id": 5, "user_id": 7, "staff_id": None}]
        rows["entity_owners"] = [
            {"entity_type": "warehouse_invoice", "entity_id": 11, "company_id": 1, "project_id": 10},
        ]
        rows["messenger_outbox"] = [
            {"id": 9, "messenger_account_id": 5, "entity_type": "warehouse_invoice", "entity_id": 11},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["summary"]["verified"], 1)

    def test_exact_project_is_preferred_over_compatible_company_parent(self):
        rows = self.base_rows()
        rows["entity_owners"] = [
            {"entity_type": "warehouse_invoice", "entity_id": 11, "company_id": 1, "project_id": None},
        ]
        rows["messenger_files"] = [
            {"id": 8, "project_name": "Объект A", "entity_type": "warehouse_invoice", "entity_id": 11},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["readyByCompany"], {"1": 1})

    def test_entity_company_and_project_name_resolve_exact_project(self):
        rows = self.base_rows()
        rows["entity_owners"] = [
            {
                "entity_type": "supply_request",
                "entity_id": 12,
                "company_id": 1,
                "project_id": None,
                "project_name": "Объект A",
            },
        ]
        rows["messenger_outbox"] = [
            {"id": 10, "entity_type": "supply_request", "entity_id": 12},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["verified"], 1)
        self.assertEqual(report["readyByCompany"], {"1": 1})

    def test_row_without_owner_evidence_requires_review(self):
        rows = self.base_rows()
        rows["messenger_files"] = [{"id": 7, "project_name": ""}]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "owner_evidence_missing")

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
        with patch.object(ownership_report_module, "load_ownership_rows", return_value=self.base_rows()):
            report = run_ownership_report(lambda: connection)

        self.assertEqual(connection.session, {"readonly": True, "autocommit": False})
        self.assertTrue(connection.closed)
        self.assertEqual(report["writesAttempted"], 0)

    def test_loader_reads_only_identity_columns(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql):
                self.calls.append(sql)

            def fetchall(self):
                return []

        cursor = Cursor()
        rows = load_ownership_rows(cursor)
        sql = "\n".join(cursor.calls).lower()

        self.assertEqual(set(rows), set(self.base_rows()))
        for forbidden in ("title", "body", "payload_json", "metadata_json", "url", "storage_key"):
            self.assertNotIn(forbidden, sql)
        for statement in cursor.calls:
            self.assertTrue(statement.lstrip().upper().startswith("SELECT"))


if __name__ == "__main__":
    unittest.main()
