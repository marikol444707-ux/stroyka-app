import unittest

from backend.features.supplier_access.service import (
    supplier_invoice_visibility_filter,
    supplier_offer_visibility_filter,
    supplier_recipient_identity_filter,
)


class SupplierOfferVisibilityFilterTests(unittest.TestCase):
    def test_builds_recipient_identity_filter_for_user_and_duplicate_group(self):
        sql, params = supplier_recipient_identity_filter([7, "3", 7], 42)

        self.assertIn("recipient.supplier_user_id=%s", sql)
        self.assertIn("recipient.supplier_group_ids", sql)
        self.assertEqual(params, [42, [3, 7], [3, 7], [3, 7]])

    def test_denies_missing_supplier_identity(self):
        self.assertEqual(supplier_offer_visibility_filter([], None), (" AND FALSE", []))

    def test_supplier_invoice_filter_keeps_company_and_offer_chain_aligned(self):
        sql, params = supplier_invoice_visibility_filter([7, "3", 7], 42)

        self.assertTrue(sql.startswith(" AND "))
        self.assertIn("si.company_id > 0", sql)
        self.assertIn("supplier_offers.company_id=si.company_id", sql)
        self.assertIn("si.offer_id IS NULL", sql)
        self.assertEqual(params[:2], [[3, 7], [3, 7]])
        self.assertIn(42, params)
        self.assertEqual(sql.count("%s"), len(params))

    def test_supplier_invoice_filter_denies_missing_identity(self):
        self.assertEqual(supplier_invoice_visibility_filter([], None), (" AND FALSE", []))
        self.assertEqual(supplier_invoice_visibility_filter([], 42), (" AND FALSE", []))

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
