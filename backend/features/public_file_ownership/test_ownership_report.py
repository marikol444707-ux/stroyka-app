import unittest
from unittest.mock import Mock, patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


def base_rows():
    return {
        "companies": [{"id": 3}, {"id": 4}],
        "projects": [{"id": 11, "company_id": 3}],
        "crm_leads": [{"id": 21, "company_id": 3}],
        "file_ownership": [],
        "public_lead_uploads": [],
    }


class PublicFileOwnershipReportTests(unittest.TestCase):
    def test_company_file_and_pending_public_upload_are_verified(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 3, "project_id": None}]
        rows["public_lead_uploads"] = [
            {"file_ownership_id": 31, "company_id": 3, "lead_id": None}
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 2,
            "verified": 2,
            "unresolved": 0,
            "mismatched": 0,
        })
        self.assertEqual(report["needsReview"], [])

    def test_attached_upload_requires_exact_file_and_lead_company(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 3, "project_id": None}]
        rows["public_lead_uploads"] = [
            {"file_ownership_id": 31, "company_id": 3, "lead_id": 21}
        ]

        report = build_report_from_rows(rows)

        upload = next(item for item in report["verifiedPreview"] if item["table"] == "public_lead_uploads")
        self.assertEqual(upload["reason"], "verified_file_and_lead_parents")
        self.assertEqual(upload["companyId"], 3)

    def test_upload_cannot_claim_another_company_than_file(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 3, "project_id": None}]
        rows["public_lead_uploads"] = [
            {"file_ownership_id": 31, "company_id": 4, "lead_id": None}
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["needsReview"][0]["reason"], "file_company_mismatch")
        self.assertEqual(report["summary"]["mismatched"], 1)

    def test_attached_upload_with_missing_lead_is_unresolved(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 3, "project_id": None}]
        rows["public_lead_uploads"] = [
            {"file_ownership_id": 31, "company_id": 3, "lead_id": 404}
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "lead_parent_not_found")
        self.assertEqual(report["summary"]["unresolved"], 1)

    def test_missing_file_parent_is_reported_without_breaking_plan_hash(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 3, "project_id": None}]
        rows["public_lead_uploads"] = [
            {"file_ownership_id": 31, "company_id": 3, "lead_id": None},
            {"file_ownership_id": None, "company_id": 3, "lead_id": None},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "file_parent_missing")
        self.assertEqual(len(report["planSha256"]), 64)

    def test_file_project_must_belong_to_file_company(self):
        rows = base_rows()
        rows["file_ownership"] = [{"id": 31, "company_id": 4, "project_id": 11}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "project_company_mismatch")
        self.assertEqual(report["summary"]["mismatched"], 1)

    def test_loader_reads_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 3}],
            [{"id": 11, "company_id": 3}],
            [{"id": 21, "company_id": 3}],
            [{"id": 31, "company_id": 3, "project_id": None}],
            [{"file_ownership_id": 31, "company_id": 3, "lead_id": 21}],
        ]

        rows = load_ownership_rows(cur)

        self.assertEqual(rows["public_lead_uploads"][0]["file_ownership_id"], 31)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "token", "file_url", "storage_key", "original_name", "content_type",
            "client_ip", "name", "phone", "email", "notes",
        ):
            self.assertNotIn(forbidden, sql)

    def test_runner_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        get_db = Mock(return_value=conn)

        with patch.object(
            ownership_report_module,
            "load_ownership_rows",
            return_value=base_rows(),
        ):
            result = run_ownership_report(get_db)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
