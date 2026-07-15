import unittest
from unittest.mock import Mock, patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


def base_rows():
    return {
        "companies": [{"id": 3}],
        "projects": [{"id": 11, "company_id": 3}],
        "crm_leads": [],
        "crm_lead_documents": [],
        "crm_lead_tasks": [],
    }


class CrmOwnershipReportTests(unittest.TestCase):
    def test_exact_project_owner_is_inherited_by_lead_and_children(self):
        rows = base_rows()
        rows["crm_leads"] = [{"id": 21, "project_id": 11}]
        rows["crm_lead_documents"] = [{"id": 31, "lead_id": 21}]
        rows["crm_lead_tasks"] = [{"id": 41, "lead_id": 21}]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForMigration"])
        self.assertEqual(report["summary"]["verified"], 3)
        self.assertEqual(report["readyByCompany"], {"3": 3})
        self.assertEqual(report["needsReview"], [])

    def test_lead_without_project_and_its_children_require_review(self):
        rows = base_rows()
        rows["crm_leads"] = [{"id": 22, "project_id": None}]
        rows["crm_lead_documents"] = [{"id": 32, "lead_id": 22}]
        rows["crm_lead_tasks"] = [{"id": 42, "lead_id": 22}]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForMigration"])
        reasons = {
            (item["table"], item["recordId"]): item["reason"]
            for item in report["needsReview"]
        }
        self.assertEqual(reasons[("crm_leads", 22)], "project_owner_missing")
        self.assertEqual(reasons[("crm_lead_documents", 32)], "lead_parent_unresolved")
        self.assertEqual(reasons[("crm_lead_tasks", 42)], "lead_parent_unresolved")

    def test_dangling_project_and_dangling_lead_are_not_guessed(self):
        rows = base_rows()
        rows["crm_leads"] = [{"id": 23, "project_id": 404}]
        rows["crm_lead_documents"] = [{"id": 33, "lead_id": 404}]

        report = build_report_from_rows(rows)

        reasons = {item["recordId"]: item["reason"] for item in report["needsReview"]}
        self.assertEqual(reasons[23], "project_not_found")
        self.assertEqual(reasons[33], "lead_parent_not_found")

    def test_project_with_missing_company_is_not_verified(self):
        rows = base_rows()
        rows["projects"] = [{"id": 11, "company_id": 404}]
        rows["crm_leads"] = [{"id": 24, "project_id": 11}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "company_not_found")

    def test_loader_selects_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 3}],
            [{"id": 11, "company_id": 3}],
            [{"id": 21, "project_id": 11}],
            [{"id": 31, "lead_id": 21}],
            [{"id": 41, "lead_id": 21}],
        ]

        rows = load_ownership_rows(cur)

        self.assertEqual(rows["crm_leads"], [{"id": 21, "project_id": 11}])
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in ("name", "phone", "email", "notes", "source", "title"):
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
