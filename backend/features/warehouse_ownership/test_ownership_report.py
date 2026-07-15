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
        "supplier_invoices": [
            {
                "id": 41,
                "company_id": 3,
                "project_name": "Object A",
                "request_id": 21,
                "offer_id": 31,
                "warehouse_invoice_id": 61,
            },
        ],
        "supply_deliveries": [
            {
                "id": 51,
                "company_id": 3,
                "project": "Object A",
                "request_id": 21,
                "offer_id": 31,
            },
        ],
        "warehouse_invoices": [],
        "warehouse_history": [],
    }


class WarehouseOwnershipReportTests(unittest.TestCase):
    def test_exact_object_invoice_and_history_are_verified(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": 51,
            "supply_request_id": 21,
            "supplier_invoice_id": 41,
        }]
        rows["warehouse_history"] = [{
            "id": 71,
            "company_id": 3,
            "project": "Object A",
        }]

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
        invoice = next(item for item in report["verifiedPreview"] if item["table"] == "warehouse_invoices")
        self.assertEqual(invoice["reason"], "verified_document_chain")

    def test_direct_main_warehouse_invoice_and_history_are_company_scoped(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "",
            "location": "Основной склад",
            "warehouse_target": "main",
            "supply_delivery_id": None,
            "supply_request_id": None,
            "supplier_invoice_id": None,
        }]
        rows["warehouse_history"] = [{
            "id": 71,
            "company_id": 3,
            "project": "Основной склад",
        }]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(
            {item["reason"] for item in report["verifiedPreview"]},
            {"verified_company_main_warehouse"},
        )

    def test_reciprocal_main_warehouse_invoice_resolves_projectless_supplier_invoice(self):
        rows = base_rows()
        rows["supplier_invoices"] = [{
            "id": 15,
            "company_id": 3,
            "project_name": "",
            "request_id": None,
            "offer_id": None,
            "warehouse_invoice_id": 37,
        }]
        rows["warehouse_invoices"] = [{
            "id": 37,
            "company_id": 3,
            "project": "",
            "location": "Основной склад",
            "warehouse_target": "main",
            "supply_delivery_id": None,
            "supply_request_id": None,
            "supplier_invoice_id": 15,
        }]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["reason"], "verified_document_chain")

    def test_object_invoice_requires_exact_project(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "",
            "location": "",
            "warehouse_target": "object",
            "supply_delivery_id": None,
            "supply_request_id": None,
            "supplier_invoice_id": None,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_missing")

    def test_main_target_cannot_hide_object_project(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "main",
            "supply_delivery_id": None,
            "supply_request_id": None,
            "supplier_invoice_id": None,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "warehouse_target_project_mismatch")

    def test_duplicate_project_name_inside_company_is_ambiguous(self):
        rows = base_rows()
        rows["projects"].append({"id": 13, "company_id": 3, "name": "Object A"})
        rows["warehouse_history"] = [{"id": 71, "company_id": 3, "project": "Object A"}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "project_owner_ambiguous")

    def test_missing_delivery_parent_is_unresolved(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": 999,
            "supply_request_id": 21,
            "supplier_invoice_id": 41,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "delivery_parent_not_found")

    def test_unresolved_delivery_chain_is_not_accepted(self):
        rows = base_rows()
        rows["supply_deliveries"][0]["offer_id"] = 999
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": 51,
            "supply_request_id": 21,
            "supplier_invoice_id": None,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "delivery_parent_unresolved")

    def test_parent_company_must_match_warehouse_company(self):
        rows = base_rows()
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 4,
            "project": "Object B",
            "location": "Object B",
            "warehouse_target": "object",
            "supply_delivery_id": 51,
            "supply_request_id": 21,
            "supplier_invoice_id": 41,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "request_company_mismatch")

    def test_supplier_invoice_reverse_link_must_not_point_elsewhere(self):
        rows = base_rows()
        rows["supplier_invoices"][0]["warehouse_invoice_id"] = 999
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": 51,
            "supply_request_id": 21,
            "supplier_invoice_id": 41,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "supplier_invoice_reverse_link_mismatch")

    def test_delivery_and_supplier_invoice_must_reference_one_request(self):
        rows = base_rows()
        rows["supply_requests"].append({"id": 22, "company_id": 3, "project": "Object A"})
        rows["supplier_offers"].append({"id": 32, "company_id": 3, "request_id": 22})
        rows["supplier_invoices"][0].update({"request_id": 22, "offer_id": 32})
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": 51,
            "supply_request_id": None,
            "supplier_invoice_id": 41,
        }]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["mismatched"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "document_request_mismatch")

    def test_direct_supplier_invoice_does_not_conflict_with_warehouse_request(self):
        rows = base_rows()
        rows["supplier_invoices"][0].update({"request_id": None, "offer_id": None})
        rows["warehouse_invoices"] = [{
            "id": 61,
            "company_id": 3,
            "project": "Object A",
            "location": "Object A",
            "warehouse_target": "object",
            "supply_delivery_id": None,
            "supply_request_id": 21,
            "supplier_invoice_id": 41,
        }]

        report = build_report_from_rows(rows)

        self.assertTrue(report["readyForStrictRuntime"])
        self.assertEqual(report["verifiedPreview"][0]["reason"], "verified_document_chain")

    def test_history_without_project_or_main_scope_is_unresolved(self):
        rows = base_rows()
        rows["warehouse_history"] = [{"id": 71, "company_id": 3, "project": ""}]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["unresolved"], 1)
        self.assertEqual(report["needsReview"][0]["reason"], "warehouse_scope_missing")

    def test_report_and_loader_exclude_commercial_and_personal_fields(self):
        rows = base_rows()
        rows["warehouse_history"] = [{"id": 71, "company_id": 3, "project": "Object A"}]
        report = build_report_from_rows(rows)
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Object A", encoded)

        cur = Mock()
        cur.fetchall.side_effect = [[], [], [], [], [], [], [], []]
        load_ownership_rows(cur)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "material", "quantity", "unit", "supplier_name", "number", "amount",
            "total_base", "total_vat", "total_with_vat", "items", "photo_url",
            "accepted_by", "issued_to", "issued_by", "paid_amount", "driver_name",
        ):
            self.assertNotIn(forbidden, sql)

    def test_runner_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        get_db = Mock(return_value=conn)

        with patch.object(ownership_report_module, "load_ownership_rows", return_value=base_rows()):
            result = run_ownership_report(get_db)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
