import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("smoke-receipt-lot-movement.py")
SPEC = importlib.util.spec_from_file_location("smoke_receipt_lot_movement", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReceiptLotMovementSmokeTests(unittest.TestCase):
    def test_seed_estimate_contains_exact_material_line(self):
        sections = MODULE.estimate_sections()

        self.assertEqual(sections[0]["items"][0]["name"], MODULE.MATERIAL_NAME)
        self.assertEqual(sections[0]["items"][0]["unit"], "шт")
        self.assertEqual(sections[0]["items"][0]["type"], "material")

    def test_invoice_items_accept_text_and_jsonb_values(self):
        self.assertEqual(MODULE.invoice_items_as_list('[{"name":"Кабель"}]'), [{"name": "Кабель"}])
        self.assertEqual(MODULE.invoice_items_as_list([{"name": "Кабель"}]), [{"name": "Кабель"}])

    def test_temporary_project_uses_postgres_text_array_for_tasks(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("ARRAY[]::TEXT[]", source)

    def test_smoke_uses_saved_invoice_line_before_moving_it(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("SELECT items FROM warehouse_invoices", source)
        self.assertIn("source_line_index", source)
        self.assertIn("source_material_name", source)
        self.assertIn('item.get("materialName")', source)
        self.assertIn("storedItems", source)
        self.assertIn("invoice_items_as_list", source)

    def test_backend_rechecks_invoice_items_before_receipt_lot_creation(self):
        backend_source = (SCRIPT_PATH.parents[1] / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn("Не удалось сохранить строки накладной", backend_source)
        self.assertIn("UPDATE warehouse_invoices SET items=%s", backend_source)


if __name__ == "__main__":
    unittest.main()
