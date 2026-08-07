import json
import unittest
from decimal import Decimal

from backend.features.project_budget_adjustments.preview import (
    BudgetAdjustmentPreviewError,
    calculate_sections_total,
)


class EstimateSectionsTotalTests(unittest.TestCase):
    def test_calculates_exact_work_and_material_total(self):
        sections = [{
            "name": "Работы",
            "items": [{
                "quantity": "2.5",
                "priceWork": "100.10",
                "priceMaterial": "20.20",
            }],
        }]

        total = calculate_sections_total(json.dumps(sections))

        self.assertEqual(total, Decimal("300.75"))

    def test_matches_imported_total_precedence(self):
        sections = [{
            "items": [
                {
                    "isImported": True,
                    "quantity": 999,
                    "priceWork": 999,
                    "totalWork": "100.10",
                    "totalMaterial": "20.20",
                    "lineTotal": "9999.00",
                },
                {
                    "isImported": True,
                    "lineTotal": "7.25",
                    "total": "8.00",
                },
            ],
        }]

        total = calculate_sections_total(sections)

        self.assertEqual(total, Decimal("127.55"))

    def test_accepts_legacy_decimal_strings_with_spaces_and_comma(self):
        sections = [{
            "items": [{
                "quantity": "1 000,5",
                "priceWork": "2,00",
                "priceMaterial": "0",
            }],
        }]

        total = calculate_sections_total(sections)

        self.assertEqual(total, Decimal("2001.00"))

    def test_rounds_only_the_final_total_to_money_scale(self):
        sections = [{
            "items": [
                {"quantity": "1", "priceWork": "0.005", "priceMaterial": 0},
                {"quantity": "1", "priceWork": "0.005", "priceMaterial": 0},
            ],
        }]

        total = calculate_sections_total(sections)

        self.assertEqual(total, Decimal("0.01"))

    def test_rejects_invalid_shape_or_non_finite_number(self):
        invalid = (
            {},
            [{"items": {}}],
            [{"items": [{"quantity": "NaN", "priceWork": 1}]}],
            [{"items": [True]}],
        )

        for sections in invalid:
            with self.subTest(sections=sections):
                with self.assertRaises(BudgetAdjustmentPreviewError) as raised:
                    calculate_sections_total(sections)
                self.assertEqual(
                    raised.exception.code,
                    "budget_adjustment_estimate_content_invalid",
                )

    def test_rejects_oversized_payload_and_item_count(self):
        with self.assertRaises(BudgetAdjustmentPreviewError) as payload_error:
            calculate_sections_total("[" + (" " * 101) + "]", max_bytes=100)
        self.assertEqual(
            payload_error.exception.code,
            "budget_adjustment_estimate_content_too_large",
        )

        with self.assertRaises(BudgetAdjustmentPreviewError) as row_error:
            calculate_sections_total(
                [{"items": [{"quantity": 1}, {"quantity": 1}]}],
                max_items=1,
            )
        self.assertEqual(
            row_error.exception.code,
            "budget_adjustment_estimate_content_too_large",
        )


if __name__ == "__main__":
    unittest.main()
