import unittest

from backend.features.warehouse_movement_documents.storage import freeze_warehouse_movement


class Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row


class WarehouseMovementSnapshotTest(unittest.TestCase):
    def test_freezes_company_route_actor_material_and_source(self):
        row = {
            "id": 9, "company_id": 2, "company_name": "Компания", "full_name": "ООО Компания",
            "short_name": "", "inn": "2611008712", "kpp": "", "ogrn": "",
            "legal_address": "Ставрополь", "actual_address": "", "phone": "", "email": "",
            "from_location": "Основной склад", "to_location": "Лицей", "from_project_id": None,
            "to_project_id": 17, "date": "2026-10-02", "notes": "На объект", "work_package": "Отделка",
            "material_name": "Краска", "quantity": 5, "unit": "кг", "source_invoice_id": 4,
            "source_invoice_line_index": 0, "document_snapshot_json": None, "document_snapshot_hash": None,
        }
        cursor = Cursor(row)
        snapshot = freeze_warehouse_movement(cursor, 9, {"id": 7, "name": "Кладовщик", "role": "кладовщик"})
        self.assertEqual(snapshot["company"]["fullName"], "ООО Компания")
        self.assertEqual(snapshot["route"]["to"], {"name": "Лицей", "projectId": 17})
        self.assertEqual(snapshot["actor"]["userId"], 7)
        self.assertEqual(snapshot["material"]["quantity"], "5")
        self.assertTrue(any("document_snapshot_json=%s::jsonb" in sql for sql, _ in cursor.calls))


if __name__ == "__main__":
    unittest.main()
