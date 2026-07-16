import json
import unittest
from unittest.mock import Mock, patch

from . import orphan_report as orphan_report_module
from .orphan_report import build_report_from_rows, load_orphan_rows, run_orphan_report


EXPECTED_SHA = "99f5b9b8a3e7d45bbea2042e12dfbadf727447e58996975243f36f5cf0f001e8"


def base_rows():
    return {
        "orphan_recipients": [],
        "orphan_offers": [],
        "supplier_offer_events": [],
        "supplier_invoices": [],
        "supply_deliveries": [],
        "supply_claims": [],
        "supply_history": [],
        "warehouse_invoices": [],
        "messenger_outbox": [],
    }


class SupplyOrphanReportTests(unittest.TestCase):
    def test_unreferenced_orphan_is_a_residue_candidate(self):
        rows = base_rows()
        rows["orphan_recipients"] = [
            {"id": 31, "company_id": 3, "request_id": 404, "max_outbox_id": None},
        ]

        report = build_report_from_rows(rows)

        self.assertEqual(report["summary"]["orphanRows"], 1)
        self.assertEqual(report["summary"]["residueCandidates"], 1)
        self.assertEqual(report["summary"]["withDownstreamReferences"], 0)
        self.assertEqual(report["orphanRows"][0]["classification"], "residue_candidate")
        self.assertEqual(report["orphanRows"][0]["references"], [])

    def test_offer_references_are_reported_without_business_content(self):
        rows = base_rows()
        rows["orphan_offers"] = [
            {"id": 41, "company_id": 3, "request_id": 404},
        ]
        rows["supplier_offer_events"] = [
            {"id": 51, "offer_id": 41},
            {"id": 52, "offer_id": 41},
        ]
        rows["supplier_invoices"] = [
            {"id": 61, "company_id": 3, "request_id": 404, "offer_id": 41},
        ]
        rows["supply_deliveries"] = [
            {"id": 71, "company_id": 3, "request_id": 404, "offer_id": 41},
        ]

        report = build_report_from_rows(rows)

        item = report["orphanRows"][0]
        self.assertEqual(item["classification"], "has_downstream_references")
        self.assertEqual(
            {ref["table"]: ref["recordIds"] for ref in item["references"]},
            {
                "supplier_invoices": [61],
                "supplier_offer_events": [51, 52],
                "supply_deliveries": [71],
            },
        )
        serialized = json.dumps(report)
        for forbidden in ("price_per_unit", "material_name", "notes", "payload_json"):
            self.assertNotIn(forbidden, serialized.lower())

    def test_source_snapshot_mismatch_fails_closed(self):
        rows = base_rows()
        rows["orphan_offers"] = [
            {"id": 41, "company_id": 3, "request_id": 404},
        ]

        report = build_report_from_rows(
            rows,
            expected_source_count=25,
            expected_source_sha256=EXPECTED_SHA,
        )

        self.assertFalse(report["sourceSetMatchesExpected"])
        self.assertFalse(report["readyForRemediationPlanning"])
        self.assertEqual(report["expectedSourceCount"], 25)

    def test_empty_snapshot_reports_completed_cleanup(self):
        report = build_report_from_rows(
            base_rows(),
            expected_source_count=25,
            expected_source_sha256=EXPECTED_SHA,
        )

        self.assertFalse(report["sourceSetMatchesExpected"])
        self.assertFalse(report["readyForRemediationPlanning"])
        self.assertTrue(report["cleanupComplete"])
        self.assertEqual(report["summary"]["orphanRows"], 0)
        self.assertTrue(orphan_report_module._report_exit_ok(report))

    def test_loader_reads_only_ids_and_relation_columns(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [{"id": 31, "company_id": 3, "request_id": 404, "max_outbox_id": None}],
            [{"id": 41, "company_id": 3, "request_id": 404}],
            [], [], [], [], [], [], [],
        ]

        rows = load_orphan_rows(cur)

        self.assertEqual(rows["orphan_recipients"][0]["request_id"], 404)
        sql = " ".join(call.args[0] for call in cur.execute.call_args_list).lower()
        for forbidden in (
            "price_per_unit", "total_price", "material_name", "supplier_name",
            "notes", "message", "payload_json", "body", "title",
        ):
            self.assertNotIn(forbidden, sql)

    def test_runner_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        get_db = Mock(return_value=conn)

        with patch.object(orphan_report_module, "load_orphan_rows", return_value=base_rows()):
            result = run_orphan_report(get_db)

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        conn.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
