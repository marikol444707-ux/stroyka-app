import unittest

from .annulled_link_cleanup import build_report, classify_rows


def row(**changes):
    value = {
        "warehouse_invoice_id": 166,
        "warehouse_company_id": 1,
        "warehouse_status": "Принята",
        "supplier_invoice_id": 144,
        "supplier_company_id": 1,
        "supplier_status": "Аннулирован",
        "warehouse_payment_registered": False,
    }
    value.update(changes)
    return value


class AnnulledWarehouseLinkCleanupTests(unittest.TestCase):
    def test_live_warehouse_link_to_annulled_invoice_is_ready(self):
        report = build_report([row()])

        self.assertEqual(report["readyCount"], 1)
        self.assertEqual(report["reviewCount"], 0)
        self.assertEqual(report["cleanupPreview"][0], {
            "warehouseInvoiceId": 166,
            "supplierInvoiceId": 144,
            "companyId": 1,
            "status": "ready",
            "reason": "annulled_supplier_reverse_link",
        })
        self.assertFalse(report["readyForStrictRuntime"])

    def test_active_and_fully_inactive_pairs_are_not_changed(self):
        classified = classify_rows([
            row(supplier_status="Утверждён"),
            row(warehouse_invoice_id=167, warehouse_status="Аннулирована"),
        ])

        self.assertEqual([item["status"] for item in classified], ["verified", "verified"])

    def test_cross_company_or_payment_registered_link_requires_review(self):
        report = build_report([
            row(supplier_company_id=2),
            row(warehouse_invoice_id=167, warehouse_payment_registered=True),
        ])

        self.assertEqual(report["readyCount"], 0)
        self.assertEqual(report["reviewCount"], 2)
        self.assertEqual(
            {item["reason"] for item in report["needsReview"]},
            {"company_mismatch", "warehouse_payment_document_registered"},
        )

    def test_plan_hash_is_deterministic_and_identifier_only(self):
        first = build_report([row(), row(warehouse_invoice_id=167, supplier_invoice_id=145)])
        second = build_report([row(warehouse_invoice_id=167, supplier_invoice_id=145), row()])

        self.assertEqual(first["planSha256"], second["planSha256"])
        self.assertEqual(len(first["planSha256"]), 64)


if __name__ == "__main__":
    unittest.main()
