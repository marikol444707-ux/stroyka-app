import unittest

from .estimate_control import build_movement_estimate_control


class WarehouseMovementEstimateControlTests(unittest.TestCase):
    def test_matched_material_does_not_require_review(self):
        result = build_movement_estimate_control([{
            "materialName": "Кабель ВВГ",
            "quantity": 20,
            "unit": "м",
            "workPackage": "Электрика",
            "estimateControl": {
                "status": "shortage_open",
                "plannedQty": 100,
                "remainingQty": 80,
                "remainingAfterRequest": 60,
                "canonicalName": "Кабель ВВГ",
            },
        }])

        self.assertEqual(result["status"], "matched")
        self.assertFalse(result["needsReview"])
        self.assertEqual(result["items"][0]["checkStatus"], "shortage_open")

    def test_material_outside_estimate_is_recorded_as_review_not_blocker(self):
        result = build_movement_estimate_control([{
            "materialName": "Дополнительная грунтовка",
            "quantity": 5,
            "unit": "кг",
            "workPackage": "Отделка",
            "estimateControl": {
                "status": "no_estimate_material",
                "controlLabel": "Материал вне сметы",
                "controlMessage": "Материал нужно разобрать и при необходимости добавить в смету.",
                "plannedQty": 0,
                "remainingQty": 0,
                "remainingAfterRequest": -5,
            },
        }])

        self.assertEqual(result["status"], "review_required")
        self.assertTrue(result["needsReview"])
        self.assertEqual(result["issues"], ["no_estimate_material"])

    def test_over_estimate_quantity_is_recorded_as_review(self):
        result = build_movement_estimate_control([{
            "materialName": "Кирпич",
            "quantity": 50,
            "unit": "шт",
            "estimateControl": {
                "status": "over_estimate_need",
                "plannedQty": 100,
                "remainingQty": 10,
                "remainingAfterRequest": -40,
            },
        }])

        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["issues"], ["over_estimate_need"])
        self.assertEqual(result["items"][0]["remainingAfterMovement"], -40)

    def test_empty_control_is_not_applicable_for_move_to_main_warehouse(self):
        result = build_movement_estimate_control([])

        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(result["needsReview"])
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
