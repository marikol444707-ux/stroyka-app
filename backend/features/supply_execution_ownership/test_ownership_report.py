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
        "supply_requests": [
            {"id": 21, "company_id": 3, "project": "Object A"},
        ],
        "supplier_offers": [
            {"id": 31, "company_id": 3, "request_id": 21},
        ],
        "supplier_invoices": [],
        "supply_deliveries": [],
    }


class SupplyExecutionOwnershipReportTests(unittest.TestCase):
    def test_exact_invoice_and_delivery_chain_is_verified(self):
        rows = base_rows()
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": 21,
                "offer_id": 31,
            },
        ]
        rows["supply_deliveries"] = [
            {
                "id": 51,
                "company_id": 3,
                "project": "Object A",
                "request_id": 21,
                "offer_id": 31,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["summary"], {
            "totalRows": 2,
            "verified": 2,
            "unresolved": 0,
            "ambiguous": 0,
            "mismatched": 0,
        })
        self.assertEqual(report["readyByCompany"], {"3": 2})
        self.assertEqual(report["needsReview"], [])

    def test_direct_invoice_without_request_or_offer_uses_exact_project_owner(self):
        rows = base_rows()
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": None,
                "offer_id": None,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["reason"], "verified_company_and_project")

    def test_invoice_offer_and_request_must_describe_one_chain(self):
        rows = base_rows()
        rows["supply_requests"].append(
            {"id": 22, "company_id": 3, "project": "Object A"}
        )
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": 22,
                "offer_id": 31,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "offer_request_mismatch")

    def test_invoice_with_only_offer_inherits_its_verified_request(self):
        rows = base_rows()
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": None,
                "offer_id": 31,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["requestId"], 21)
        self.assertEqual(
            report["verifiedPreview"][0]["reason"],
            "verified_request_and_offer_chain",
        )

    def test_delivery_requires_request_and_offer_parents(self):
        rows = base_rows()
        rows["supply_deliveries"] = [
            {
                "id": 51,
                "company_id": 3,
                "project": "Object A",
                "request_id": None,
                "offer_id": None,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "request_parent_missing")

    def test_delivery_with_request_but_without_offer_is_unresolved(self):
        rows = base_rows()
        rows["supply_deliveries"] = [
            {
                "id": 51,
                "company_id": 3,
                "project": "Object A",
                "request_id": 21,
                "offer_id": None,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "offer_parent_missing")

    def test_delivery_company_must_match_request_and_offer(self):
        rows = base_rows()
        rows["supply_deliveries"] = [
            {
                "id": 51,
                "company_id": 4,
                "project": "Object B",
                "request_id": 21,
                "offer_id": 31,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "request_company_mismatch")

    def test_project_owner_must_match_stored_company(self):
        rows = base_rows()
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object B",
                "request_id": None,
                "offer_id": None,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_company_mismatch")

    def test_duplicate_project_name_inside_company_is_ambiguous(self):
        rows = base_rows()
        rows["projects"].append({"id": 13, "company_id": 3, "name": "Object A"})
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": None,
                "offer_id": None,
            },
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_ambiguous")

    def test_report_does_not_expose_project_names(self):
        rows = base_rows()
        rows["supplier_invoices"] = [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": 21,
                "offer_id": 31,
            },
        ]

        report = build_report_from_rows(rows)

        encoded = json.dumps(report)
        self.assertNotIn("Object A", encoded)
        self.assertNotIn("Object B", encoded)

    def test_loader_reads_only_ids_and_owner_relations(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 3}],
            [{"id": 11, "company_id": 3, "name": "Object A"}],
            [{"id": 21, "company_id": 3, "project": "Object A"}],
            [{"id": 31, "company_id": 3, "request_id": 21}],
            [{
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": 21,
                "offer_id": 31,
            }],
            [{
                "id": 51,
                "company_id": 3,
                "project": "Object A",
                "request_id": 21,
                "offer_id": 31,
            }],
        ]

        rows = load_ownership_rows(cur)

        self.assertEqual(rows["supplier_invoices"][0]["offer_id"], 31)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "supplier_id", "supplier_name", "invoice_number", "amount",
            "material_name", "quantity", "unit", "notes", "description",
            "file_url", "photo_url", "price_per_unit", "total_price",
            "payment_terms", "waybill_number", "driver_name",
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
