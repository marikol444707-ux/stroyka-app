import unittest

from .service import is_resource_adjustment, material_plan_contribution


class EstimateMaterialPlanContributionTests(unittest.TestCase):
    def test_negative_resource_adjustment_reduces_material_plan(self):
        material = {
            "itemType": "material",
            "name": "Доски необрезные хвойных пород 32-40 мм, III сорта",
            "quantity": 41.4,
            "unit": "м3",
            "isImported": True,
            "sourceCode": "102-0053",
            "totalMaterial": 1000,
        }
        correction = {
            "itemType": "adjustment",
            "name": material["name"],
            "quantity": -41.4,
            "unit": "м3",
            "isImported": True,
            "sourceCode": "102-0053",
            "lineTotal": -1000,
        }

        self.assertTrue(is_resource_adjustment(
            correction,
            imported_quantity=correction["quantity"],
            line_total=correction["lineTotal"],
        ))
        self.assertEqual(
            material_plan_contribution(
                is_material=True,
                is_adjustment=False,
                imported_quantity=material["quantity"],
                material_sum=material["totalMaterial"],
                item_sum=material["totalMaterial"],
            ),
            (41.4, 1000.0, False),
        )
        self.assertEqual(
            material_plan_contribution(
                is_material=False,
                is_adjustment=True,
                imported_quantity=correction["quantity"],
                material_sum=0,
                item_sum=correction["lineTotal"],
            ),
            (-41.4, -1000.0, True),
        )

    def test_negative_work_row_is_not_treated_as_material_correction(self):
        work = {
            "itemType": "adjustment",
            "name": "Корректировка монтажа оборудования",
            "quantity": -1,
            "unit": "шт",
            "sourceCode": "ГЭСНм08-01-001-01",
            "lineTotal": -1000,
        }

        self.assertFalse(is_resource_adjustment(
            work,
            imported_quantity=work["quantity"],
            line_total=work["lineTotal"],
        ))


if __name__ == "__main__":
    unittest.main()
