import unittest
from pathlib import Path


ROUTES_PATH = Path(__file__).with_name("routes.py")


class ShipmentPaymentPolicyTest(unittest.TestCase):
    def test_free_text_payment_terms_do_not_block_shipment(self):
        source = ROUTES_PATH.read_text(encoding="utf-8")

        self.assertNotIn("need_payment =", source)
        self.assertNotIn("Сначала поставщик должен выставить счёт", source)
        self.assertIn("scheduled_advance = advance_amount", source)
        self.assertIn("paid < scheduled_advance", source)


if __name__ == "__main__":
    unittest.main()
