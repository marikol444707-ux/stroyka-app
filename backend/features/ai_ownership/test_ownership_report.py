import unittest

from backend.features.ai_ownership.ownership_report import (
    build_ai_ownership_report,
    build_report_from_rows,
    run_ai_ownership_report,
)


def complete_rows():
    return {
        "projects": [{"id": 10, "name": "Объект A", "company_id": 4}],
        "project_ai_summary": [{"project_name": "Объект A"}],
        "ai_findings": [{
            "id": 20,
            "project_name": "Объект A",
            "linked_entity_type": "room",
            "linked_entity_id": "30",
        }],
        "ai_tasks": [
            {"id": 40, "finding_id": 20, "project_name": "Объект A"},
            {"id": 41, "finding_id": None, "project_name": "Система"},
        ],
        "ai_task_reports": [
            {"id": 50, "task_id": 40},
            {"id": 51, "task_id": 41},
        ],
        "ai_task_attachments": [
            {"id": 60, "report_id": 50, "task_id": 40},
            {"id": 61, "report_id": 51, "task_id": 41},
        ],
        "linked_entities": [{"entity_type": "room", "entity_id": "30", "project_name": "Объект A"}],
    }


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.current = []
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if " FROM projects " in " " + compact + " ":
            key = "projects"
        elif " FROM project_ai_summary " in " " + compact + " ":
            key = "project_ai_summary"
        elif " FROM ai_findings " in " " + compact + " ":
            key = "ai_findings"
        elif " FROM ai_tasks " in " " + compact + " ":
            key = "ai_tasks"
        elif " FROM ai_task_reports " in " " + compact + " ":
            key = "ai_task_reports"
        elif " FROM ai_task_attachments " in " " + compact + " ":
            key = "ai_task_attachments"
        else:
            key = "linked_entities"
        self.current = self.rows.get(key, [])

    def fetchall(self):
        return list(self.current)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.session_calls = []
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def close(self):
        self.closed = True


class AiOwnershipReportTests(unittest.TestCase):
    def test_verified_chain_covers_all_five_tables_and_system_scope(self):
        report = build_report_from_rows(complete_rows())
        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 8,
            "verified": 8,
            "systemRows": 3,
            "unresolved": 0,
            "mismatched": 0,
        })
        self.assertEqual(report["readyByCompany"], {"4": 5})
        self.assertEqual(set(report["byTable"]), {
            "project_ai_summary",
            "ai_findings",
            "ai_tasks",
            "ai_task_reports",
            "ai_task_attachments",
        })

    def test_ambiguous_project_name_fails_closed(self):
        rows = complete_rows()
        rows["projects"].append({"id": 11, "name": "Объект A", "company_id": 8})
        report = build_report_from_rows(rows)
        self.assertFalse(report["readyForStrictRuntime"])
        self.assertGreater(report["summary"]["unresolved"], 0)
        self.assertIn("project_name_ambiguous", {item["reason"] for item in report["needsReview"]})

    def test_linked_entity_from_other_project_is_mismatched(self):
        rows = complete_rows()
        rows["projects"].append({"id": 11, "name": "Объект B", "company_id": 8})
        rows["linked_entities"][0]["project_name"] = "Объект B"
        report = build_report_from_rows(rows)
        finding = next(item for item in report["needsReview"] if item["table"] == "ai_findings")
        self.assertEqual((finding["status"], finding["reason"]), ("mismatched", "linked_entity_owner_mismatch"))

    def test_unsupported_polymorphic_entity_requires_review(self):
        rows = complete_rows()
        rows["ai_findings"][0].update({"linked_entity_type": "unknown", "linked_entity_id": "30"})
        report = build_report_from_rows(rows)
        finding = next(item for item in report["needsReview"] if item["table"] == "ai_findings")
        self.assertEqual(finding["reason"], "linked_entity_type_unsupported")

    def test_work_journal_is_a_supported_finding_parent(self):
        rows = complete_rows()
        rows["ai_findings"][0].update({"linked_entity_type": "work_journal", "linked_entity_id": "70"})
        rows["linked_entities"] = [{
            "entity_type": "work_journal",
            "entity_id": "70",
            "project_name": "Объект A",
        }]
        report = build_report_from_rows(rows)
        self.assertTrue(report["readyForStrictRuntime"])

    def test_task_finding_owner_conflict_is_mismatched(self):
        rows = complete_rows()
        rows["projects"].append({"id": 11, "name": "Объект B", "company_id": 8})
        rows["ai_tasks"][0]["project_name"] = "Объект B"
        report = build_report_from_rows(rows)
        task = next(item for item in report["needsReview"] if item["table"] == "ai_tasks")
        self.assertEqual((task["status"], task["reason"]), ("mismatched", "finding_owner_mismatch"))

    def test_orphan_report_and_cross_task_attachment_fail_closed(self):
        rows = complete_rows()
        rows["ai_task_reports"].append({"id": 52, "task_id": 999})
        rows["ai_task_attachments"][0]["task_id"] = 41
        report = build_report_from_rows(rows)
        reasons = {(item["table"], item["reason"]) for item in report["needsReview"]}
        self.assertIn(("ai_task_reports", "task_not_found"), reasons)
        self.assertIn(("ai_task_attachments", "report_task_mismatch"), reasons)

    def test_database_report_uses_selects_and_excludes_business_payload(self):
        cursor = FakeCursor(complete_rows())
        report = build_ai_ownership_report(cursor)
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(len(cursor.calls), 7)
        self.assertTrue(all(sql.startswith("SELECT") for sql, _params in cursor.calls))
        sql = " ".join(call[0].lower() for call in cursor.calls)
        for business_column in (" title", " description", " report_text", " file_url", "payload_hash"):
            self.assertNotIn(business_column, sql)

    def test_runner_enforces_read_only_transaction(self):
        cursor = FakeCursor(complete_rows())
        connection = FakeConnection(cursor)
        report = run_ai_ownership_report(lambda: connection)
        self.assertTrue(report["ok"])
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
