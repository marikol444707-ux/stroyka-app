import unittest

from .routes import build_packaging_correction_preview, normalize_invoice_packaging_items


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchall(self):
        return self.rows


class MaterialPackagingRulesTest(unittest.TestCase):
    def test_confirmed_cable_rule_converts_to_base_meters(self):
        cursor = FakeCursor([{
            "id": 7, "company_id": 1, "supplier_id": 3,
            "material_key": "кабель tokov ввг пнг a ls 3x2 5", "material_name": "Кабель TOKOV ВВГ-Пнг(A)-LS 3x2.5",
            "document_unit": "уп", "base_unit": "м", "content_quantity": 100,
            "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
        }])
        rows = normalize_invoice_packaging_items(cursor, [{
            "name": "Кабель TOKOV ВВГ-Пнг(A)-LS 3x2.5", "quantity": 25, "unit": "уп", "price": 1200, "total": 30000,
        }], company_id=1, supplier_id=3)
        item = rows[0]
        self.assertEqual(item["documentQuantity"], 25)
        self.assertEqual(item["documentUnit"], "уп")
        self.assertEqual(item["quantity"], 2500)
        self.assertEqual(item["unit"], "м")
        self.assertEqual(item["price"], 12)
        self.assertEqual(item["total"], 30000)
        self.assertEqual(item["conversionStatus"], "confirmed")

    def test_unknown_packaging_stays_in_document_unit_and_requires_review(self):
        cursor = FakeCursor([])
        source = {"name": "Арматура A500C", "quantity": 4, "unit": "пач", "price": 50000}
        item = normalize_invoice_packaging_items(cursor, [source], company_id=1)[0]
        self.assertEqual(item["quantity"], 4)
        self.assertEqual(item["unit"], "пач")
        self.assertEqual(item["conversionStatus"], "needs_review")
        self.assertEqual(item["conversionReviewReason"], "Не найдено подтвержденное правило содержимого упаковки")

    def test_direct_non_packaged_item_does_not_enter_packaging_review(self):
        cursor = FakeCursor([])
        source = {"name": "Муфта противопожарная", "quantity": 10, "unit": "шт", "price": 500}
        self.assertEqual(normalize_invoice_packaging_items(cursor, [source], company_id=1), [source])

    def test_historical_correction_preview_never_changes_stock_automatically(self):
        preview = build_packaging_correction_preview(
            {"name": "Кабель", "quantity": 25, "unit": "уп"},
            {"id": 12, "contentQuantity": 100, "baseUnit": "м"},
        )
        self.assertEqual(preview["stored"], {"quantity": 25.0, "unit": "уп"})
        self.assertEqual(preview["proposed"], {"quantity": 2500.0, "unit": "м"})
        self.assertFalse(preview["canApply"])
        self.assertEqual(preview["status"], "preview_only")

    def test_packaging_label_with_its_content_uses_packaging_rule(self):
        cursor = FakeCursor([{
            "id": 9, "company_id": 1, "supplier_id": None,
            "material_key": "кабель ввг 3x1 5", "material_name": "Кабель ВВГ 3x1.5",
            "document_unit": "уп", "base_unit": "м", "content_quantity": 100,
            "status": "confirmed", "note": "", "created_by": "", "created_at": None, "updated_at": None,
        }])
        item = normalize_invoice_packaging_items(cursor, [{
            "name": "Кабель ВВГ 3x1.5", "quantity": 10, "unit": "уп. 100 м",
        }], company_id=1)[0]
        self.assertEqual(item["documentUnit"], "уп. 100 м")
        self.assertEqual(item["quantity"], 1000)
        self.assertEqual(item["unit"], "м")


if __name__ == "__main__":
    unittest.main()
