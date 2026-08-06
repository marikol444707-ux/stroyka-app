import unittest

from backend.features.brigade_lineage.writer_service import insert_pricelist_contract_item


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))


class PricelistContractItemWriterTests(unittest.TestCase):
    def test_pricelist_item_has_explicit_source_and_no_estimate_coordinates(self):
        cursor = FakeCursor()

        result = insert_pricelist_contract_item(
            cursor,
            contract_id=7,
            work_package="Отделка",
            name="Штукатурка",
            unit="м2",
            price=1000,
            category="Стены",
            coefficient=0.65,
        )

        sql, params = cursor.calls[0]
        self.assertIn("source_type", sql)
        self.assertEqual(params[:5], (7, "Стены", "Штукатурка", "Отделка", ""))
        self.assertEqual(params[6], 0)
        self.assertEqual(params[7:10], (1000.0, 650.0, 0))
        self.assertEqual(params[10:], ("pricelist", None, None, None, None))
        self.assertEqual(result, {"priceSmeta": 1000.0, "priceBrigade": 650.0})

    def test_non_finite_values_cannot_reach_contract_item_storage(self):
        for field, value in (("price", float("nan")), ("coefficient", float("inf"))):
            with self.subTest(field=field):
                cursor = FakeCursor()
                kwargs = {
                    "contract_id": 7,
                    "work_package": "Основная",
                    "name": "Работа",
                    "unit": "шт",
                    "price": 100,
                    "category": "",
                    "coefficient": 1,
                }
                kwargs[field] = value
                with self.assertRaises(ValueError):
                    insert_pricelist_contract_item(cursor, **kwargs)
                self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
