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


if __name__ == "__main__":
    unittest.main()
