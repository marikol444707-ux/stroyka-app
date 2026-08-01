import unittest

from .service import resolve_invoice_line_source


class InvoiceLineSourceTest(unittest.TestCase):
    def test_allows_a_transfer_without_an_invoice_source(self):
        self.assertIsNone(resolve_invoice_line_source(None, None, None))

    def test_canonicalizes_selected_invoice_line_on_the_server(self):
        source = resolve_invoice_line_source(
            12,
            "1",
            {"number": "UPD-12", "items": '[{"name":"Кабель"},{"name":"Муфта"}]'},
        )
        self.assertEqual(source, {
            "invoiceId": 12,
            "invoiceLineIndex": 1,
            "invoiceLineKey": "warehouse_invoice:12:item:1",
            "invoiceNumber": "UPD-12",
        })

    def test_accepts_the_first_invoice_line(self):
        source = resolve_invoice_line_source(12, 0, {"number": "UPD-12", "items": '[{"name":"Кабель"}]'})
        self.assertEqual(source["invoiceLineIndex"], 0)

    def test_rejects_partial_or_out_of_range_source(self):
        with self.assertRaisesRegex(ValueError, "укажите накладную и строку"):
            resolve_invoice_line_source(12, None, None)
        with self.assertRaisesRegex(ValueError, "Строка материала"):
            resolve_invoice_line_source(12, 1, {"items": "[]"})


if __name__ == "__main__":
    unittest.main()
