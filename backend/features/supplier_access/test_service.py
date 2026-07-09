import unittest

from backend.features.supplier_access.service import supplier_offer_visibility_filter


class SupplierOfferVisibilityFilterTests(unittest.TestCase):
    def test_denies_missing_supplier_identity(self):
        self.assertEqual(supplier_offer_visibility_filter([], None), (" AND FALSE", []))

    def test_builds_explicit_recipient_and_company_chain_filter(self):
        sql, params = supplier_offer_visibility_filter([7, "3", 7, 0, "bad"], 42)

        self.assertIn("scoped_request.company_id=supplier_offers.company_id", sql)
        self.assertIn("mixed_recipient.company_id IS DISTINCT FROM supplier_offers.company_id", sql)
        self.assertIn("recipient.target_supplier_id=supplier_offers.supplier_id", sql)
        self.assertIn("supplier_offers.supplier_id = ANY(COALESCE(recipient.supplier_group_ids", sql)
        self.assertIn("recipient.supplier_user_id=%s", sql)
        self.assertIn("recipient.supplier_group_ids", sql)
        self.assertEqual(params, [42, [3, 7], [3, 7], [3, 7], [3, 7], [3, 7]])

    def test_keeps_legacy_fallback_only_when_recipient_rows_are_absent(self):
        sql, _ = supplier_offer_visibility_filter([7], None)

        self.assertIn("NOT EXISTS", sql)
        self.assertIn("any_recipient.request_id=supplier_offers.request_id", sql)
        self.assertIn("legacy_request.selected_suppliers", sql)


if __name__ == "__main__":
    unittest.main()
