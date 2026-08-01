import unittest

from .report import build_report_from_rows


class MaterialTraceabilityReportTest(unittest.TestCase):
    def test_classifies_linked_unlinked_and_broken_transfers_without_writes(self):
        report = build_report_from_rows({
            "warehouse_invoices": [
                {"id": 10, "company_id": 1, "items": '[{"name":"Кабель"}]'},
            ],
            "material_transfers": [
                {"id": 1, "company_id": 1, "invoice_id": 10, "invoice_line_index": 0},
                {"id": 2, "company_id": 1, "invoice_id": None, "invoice_line_index": None},
                {"id": 3, "company_id": 1, "invoice_id": 10, "invoice_line_index": 3},
            ],
            "warehouse_movements": [{"id": 4, "company_id": 1}],
            "warehouse_history": [
                {"id": 5, "company_id": 1},
                {"id": 6, "company_id": 1, "source_invoice_id": 10, "source_invoice_line_index": 0},
            ],
        })
        self.assertEqual(report["summary"], {"totalRows": 6, "linked": 2, "unlinked": 3, "broken": 1})
        self.assertFalse(report["readyForStockCorrection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["blockers"][0]["reason"], "receipt_not_selected")


if __name__ == "__main__":
    unittest.main()
