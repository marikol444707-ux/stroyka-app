import unittest

from .receipt_lots import create_receipt_lot, ensure_receipt_lot_schema


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return self.row


class ReceiptLotTests(unittest.TestCase):
    def test_schema_has_one_source_lot_per_company_invoice_line(self):
        cur = FakeCursor()

        ensure_receipt_lot_schema(cur)

        sql = "\n".join(statement for statement, _ in cur.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS warehouse_receipt_lots", sql)
        self.assertIn("UNIQUE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_source", sql)

    def test_new_receipt_lot_preserves_document_and_normalized_quantities(self):
        cur = FakeCursor({"id": 41})

        lot_id = create_receipt_lot(
            cur, company_id=1, project_id=None, project_name="", warehouse_location="Основной склад",
            warehouse_target="main", warehouse_invoice_id=20, invoice_line_index=0,
            material_name="Кабель ВВГ", document_quantity=2, document_unit="бухта",
            received_quantity=200, unit="м", created_by="Директор",
        )

        self.assertEqual(lot_id, 41)
        params = cur.statements[0][1]
        self.assertEqual(params[8:12], (2, "бухта", 200, "м"))
        self.assertEqual(params[12], 200)
        self.assertIn("ON CONFLICT", cur.statements[0][0])

    def test_rejects_incomplete_lot_source(self):
        with self.assertRaisesRegex(ValueError, "компания и накладная"):
            create_receipt_lot(
                FakeCursor(), company_id=None, project_id=None, project_name="", warehouse_location="",
                warehouse_target="main", warehouse_invoice_id=None, invoice_line_index=0,
                material_name="Кабель", document_quantity=1, document_unit="бухта",
                received_quantity=100, unit="м", created_by="",
            )
