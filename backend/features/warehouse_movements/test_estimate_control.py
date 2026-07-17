import unittest

from .estimate_control import (
    build_movement_estimate_control,
    build_movement_review_task,
)


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

    def test_review_task_links_the_movement_and_explains_outside_estimate(self):
        task = build_movement_review_task(
            movement_id=41,
            project_name="Школа",
            actor_name="Кладовщик",
            estimate_control={
                "status": "review_required",
                "needsReview": True,
                "issues": ["no_estimate_material"],
                "items": [{
                    "materialName": "Грунтовка",
                    "quantity": 5,
                    "unit": "кг",
                    "workPackage": "Отделка",
                    "plannedQuantity": 0,
                    "remainingBeforeMovement": 0,
                    "remainingAfterMovement": -5,
                }],
            },
        )

        self.assertEqual(task["dedupeKey"], "WAREHOUSE_MOVEMENT_ESTIMATE:41")
        self.assertEqual(task["assignedRole"], "сметчик")
        self.assertEqual(task["actionPayload"]["movementId"], 41)
        self.assertIn("добавить материал", task["description"].lower())

    def test_matched_movement_does_not_create_review_task(self):
        task = build_movement_review_task(
            movement_id=42,
            project_name="Школа",
            actor_name="Кладовщик",
            estimate_control={"status": "matched", "needsReview": False, "items": []},
        )

        self.assertIsNone(task)


if __name__ == "__main__":
    unittest.main()
