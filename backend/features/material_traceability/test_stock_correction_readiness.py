import unittest

from .stock_correction_readiness import build_readiness_report


class StockCorrectionReadinessTests(unittest.TestCase):
    def test_missing_lot_schema_blocks_even_a_fully_linked_chain(self):
        report = build_readiness_report({
            "warehouse_invoices": [{"id": 10, "company_id": 1, "items": '[{"name":"Кабель"}]'}],
            "material_transfers": [],
            "warehouse_movements": [{"id": 1, "company_id": 1, "source_invoice_id": 10, "source_invoice_line_index": 0}],
            "warehouse_history": [{"id": 2, "company_id": 1, "source_invoice_id": 10, "source_invoice_line_index": 0}],
        }, receipt_lot_schema_exists=False)

        self.assertTrue(report["reportConsistent"])
        self.assertFalse(report["readyForReceiptLots"])
        self.assertFalse(report["readyForStockCorrection"])
        self.assertEqual(report["summary"]["linked"], 2)
        self.assertEqual(report["schemaBlockers"][0]["reason"], "receipt_lot_schema_missing")

    def test_lot_schema_and_clean_traceability_are_required_for_future_apply(self):
        report = build_readiness_report({
            "warehouse_invoices": [{"id": 10, "company_id": 1, "items": '[{"name":"Кабель"}]'}],
            "material_transfers": [],
            "warehouse_movements": [{"id": 1, "company_id": 1, "source_invoice_id": 10, "source_invoice_line_index": 0}],
            "warehouse_history": [],
        }, receipt_lot_schema_exists=True)

        self.assertTrue(report["readyForReceiptLots"])
        self.assertTrue(report["readyForStockCorrection"])
        self.assertEqual(report["summary"]["traceabilityBlockers"], 0)

    def test_unlinked_history_remains_a_traceability_blocker(self):
        report = build_readiness_report({
            "warehouse_invoices": [],
            "material_transfers": [],
            "warehouse_movements": [],
            "warehouse_history": [{"id": 3, "company_id": 1}],
        }, receipt_lot_schema_exists=True)

        self.assertFalse(report["readyForStockCorrection"])
        self.assertEqual(report["traceabilityBlockers"][0]["reason"], "receipt_reference_not_stored")


if __name__ == "__main__":
    unittest.main()
