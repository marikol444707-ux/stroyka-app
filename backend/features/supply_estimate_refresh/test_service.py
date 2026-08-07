import json
import unittest

from .service import refresh_open_supply_request_controls


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self.rows


class SupplyEstimateRefreshTests(unittest.TestCase):
    def test_refreshes_each_open_request_without_changing_business_fields(self):
        cursor = FakeCursor([
            {
                "id": 17,
                "items_json": json.dumps([{
                    "materialName": "Доска",
                    "quantity": 5,
                    "unit": "м3",
                }]),
            },
        ])

        def attach_control(
            _cursor,
            project,
            items,
            exclude_request_id=None,
            company_id=None,
            project_id=None,
        ):
            self.assertEqual(project, "Лицей")
            self.assertEqual(exclude_request_id, 17)
            self.assertEqual(company_id, 3)
            self.assertEqual(project_id, 8)
            items[0]["estimateControl"] = {"plannedQty": 0, "calculatedAt": "now"}
            return items

        result = refresh_open_supply_request_controls(
            cursor,
            project_name="Лицей",
            company_id=3,
            project_id=8,
            attach_control=attach_control,
        )

        self.assertEqual(result, {"scanned": 1, "updated": 1})
        select_sql, select_params = cursor.calls[0]
        self.assertIn("company_id=%s", select_sql)
        self.assertIn("project=%s", select_sql)
        self.assertEqual(select_params[:2], (3, "Лицей"))
        self.assertIn("Новая", select_params[2])
        self.assertNotIn("Отменена", select_params[2])
        update_sql, update_params = cursor.calls[1]
        self.assertEqual(update_sql, "UPDATE supply_requests SET items_json=%s WHERE id=%s")
        saved_items = json.loads(update_params[0])
        self.assertEqual(saved_items[0]["quantity"], 5)
        self.assertEqual(saved_items[0]["estimateControl"]["plannedQty"], 0)
        self.assertEqual(update_params[1], 17)

    def test_does_nothing_without_project_or_company(self):
        cursor = FakeCursor([])

        result = refresh_open_supply_request_controls(
            cursor,
            project_name="",
            company_id=None,
            attach_control=lambda *_args, **_kwargs: [],
        )

        self.assertEqual(result, {"scanned": 0, "updated": 0})
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
