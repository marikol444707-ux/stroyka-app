import json
import unittest
from unittest.mock import Mock, patch

from . import ownership_report as ownership_report_module
from .ownership_report import build_report_from_rows, load_ownership_rows, run_ownership_report


def base_rows():
    return {
        "companies": [{"id": 3}, {"id": 4}],
        "projects": [
            {"id": 11, "company_id": 3, "name": "Object A"},
            {"id": 12, "company_id": 4, "name": "Object B"},
        ],
        "supply_requests": [],
        "supply_request_recipients": [],
        "supplier_offers": [],
    }


class SupplyOwnershipReportTests(unittest.TestCase):
    def test_exact_request_recipient_and_offer_chain_is_verified(self):
        rows = base_rows()
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ]
        rows["supply_request_recipients"] = [
            {"id": 31, "company_id": 3, "request_id": 21},
        ]
        rows["supplier_offers"] = [
            {"id": 41, "company_id": 3, "request_id": 21},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 3,
            "verified": 3,
            "unresolved": 0,
            "ambiguous": 0,
            "mismatched": 0,
        })
        self.assertEqual(report["readyByCompany"], {"3": 3})
        self.assertEqual(report["needsReview"], [])

    def test_request_project_must_belong_to_stored_company(self):
        rows = base_rows()
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object B"},
        ]

        report = build_report_from_rows(rows)

        self.assertFalse(report["readyForStrictRuntime"])
        self.assertEqual(report["needsReview"][0]["reason"], "project_company_mismatch")
        self.assertEqual(report["summary"]["mismatched"], 1)

    def test_duplicate_project_name_inside_company_is_ambiguous(self):
        rows = base_rows()
        rows["projects"].append({"id": 13, "company_id": 3, "name": "Object A"})
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_ambiguous")
        self.assertEqual(report["summary"]["ambiguous"], 1)

    def test_same_project_name_in_another_company_is_disambiguated_by_owner(self):
        rows = base_rows()
        rows["projects"].append({"id": 13, "company_id": 4, "name": "Object A"})
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["projectId"], 11)

    def test_report_does_not_expose_project_names(self):
        rows = base_rows()
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ]

        report = build_report_from_rows(rows)

        self.assertNotIn("Object A", json.dumps(report))
        self.assertNotIn("Object B", json.dumps(report))

    def test_child_company_must_match_exact_request_parent(self):
        rows = base_rows()
        rows["supply_requests"] = [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ]
        rows["supply_request_recipients"] = [
            {"id": 31, "company_id": 4, "request_id": 21},
        ]
        rows["supplier_offers"] = [
            {"id": 41, "company_id": 4, "request_id": 21},
        ]

        report = build_report_from_rows(rows)

        reasons = {item["table"]: item["reason"] for item in report["needsReview"]}
        self.assertEqual(reasons["supply_request_recipients"], "request_company_mismatch")
        self.assertEqual(reasons["supplier_offers"], "request_company_mismatch")
        self.assertEqual(report["summary"]["mismatched"], 2)

    def test_missing_request_parent_is_unresolved_for_both_children(self):
        rows = base_rows()
        rows["supply_request_recipients"] = [
            {"id": 31, "company_id": 3, "request_id": 404},
        ]
        rows["supplier_offers"] = [
            {"id": 41, "company_id": 3, "request_id": 404},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(
            {item["reason"] for item in report["needsReview"]},
            {"request_parent_not_found"},
        )
        self.assertEqual(report["summary"]["unresolved"], 2)

    def test_unresolved_request_keeps_children_unresolved(self):
        rows = base_rows()
        rows["supply_requests"] = [
            {"id": 21, "company_id": None, "project": "Object A"},
        ]
        rows["supplier_offers"] = [
            {"id": 41, "company_id": 3, "request_id": 21},
        ]

        report = build_report_from_rows(rows)

        reasons = {item["table"]: item["reason"] for item in report["needsReview"]}
        self.assertEqual(reasons["supply_requests"], "company_owner_missing")
        self.assertEqual(reasons["supplier_offers"], "request_parent_unresolved")

    def test_loader_reads_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 3}],
            [{"id": 11, "company_id": 3, "name": "Object A"}],
            [{"id": 21, "company_id": 3, "project": "Object A"}],
            [{"id": 31, "company_id": 3, "request_id": 21}],
            [{"id": 41, "company_id": 3, "request_id": 21}],
        ]

        rows = load_ownership_rows(cur)

        self.assertEqual(rows["supplier_offers"][0]["request_id"], 21)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "material_name", "quantity", "unit", "notes", "items_json",
            "selected_suppliers", "supplier_id", "price_per_unit", "total_price",
            "delivery_days", "supplier_message", "payment_terms",
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
