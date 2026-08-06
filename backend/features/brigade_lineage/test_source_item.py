import unittest

from backend.features.brigade_lineage.source_item import (
    estimate_item_unit_price,
    is_estimate_work_item,
    number,
)


class EstimateSourceItemPolicyTests(unittest.TestCase):
    def test_work_total_fallback_is_shared_by_all_assignment_routes(self):
        self.assertEqual(
            estimate_item_unit_price({"quantity": 4, "workTotal": 1200}),
            300,
        )

    def test_material_only_and_non_work_rows_are_not_assignable(self):
        self.assertFalse(is_estimate_work_item({"type": "material", "priceMaterial": 100}))
        self.assertFalse(is_estimate_work_item({"type": "work", "priceMaterial": 100, "priceWork": 0}))
        self.assertTrue(is_estimate_work_item({"type": "work", "priceWork": 100}))

    def test_non_finite_numbers_fail_closed_to_zero(self):
        self.assertEqual(number(float("nan")), 0)
        self.assertEqual(number(float("inf")), 0)


if __name__ == "__main__":
    unittest.main()
