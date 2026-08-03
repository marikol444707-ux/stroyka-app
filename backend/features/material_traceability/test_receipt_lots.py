import unittest

from .receipt_lots import (
    consume_receipt_lot,
    create_receipt_lot,
    ensure_receipt_lot_schema,
    lock_receipt_lot_for_movement,
    restore_receipt_lot,
)


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = list(rows or [])
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return self.row


class ReceiptLotTests(unittest.TestCase):
    def test_schema_has_one_source_lot_per_company_invoice_line(self):
        cur = FakeCursor()

        ensure_receipt_lot_schema(cur)

        sql = "\n".join(statement for statement, _ in cur.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS warehouse_receipt_lots", sql)
        self.assertIn("UNIQUE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_source", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS warehouse_lot_movements", sql)

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

    def test_historic_invoice_source_remains_unlinked_when_no_lot_exists(self):
        cur = FakeCursor()

        lot = lock_receipt_lot_for_movement(
            cur, company_id=1, warehouse_invoice_id=20, invoice_line_index=0,
            warehouse_location="Основной склад", material_name="Кабель ВВГ", unit="м",
            requested_quantity=10,
        )

        self.assertIsNone(lot)
        self.assertIn("FOR UPDATE", cur.statements[0][0])

    def test_exact_lot_rejects_quantity_above_available_balance(self):
        cur = FakeCursor({
            "id": 7, "company_id": 1, "warehouse_location": "Основной склад",
            "material_name": "Кабель ВВГ", "unit": "м", "available_quantity": 12,
            "status": "active",
        })

        with self.assertRaisesRegex(ValueError, "доступно 12 м"):
            lock_receipt_lot_for_movement(
                cur, company_id=1, warehouse_invoice_id=20, invoice_line_index=0,
                warehouse_location="Основной склад", material_name="Кабель ВВГ", unit="м",
                requested_quantity=12.1,
            )

    def test_consuming_lot_reduces_balance_and_creates_immutable_event(self):
        cur = FakeCursor(rows=[{"available_quantity": 75}])
        remaining = consume_receipt_lot(
            cur,
            lot={"id": 7, "company_id": 1, "unit": "м"},
            warehouse_movement_id=55,
            quantity=25,
            from_location="Основной склад",
            to_location="Объект",
            created_by="Директор",
        )

        self.assertEqual(remaining, 75)
        self.assertIn("UPDATE warehouse_receipt_lots", cur.statements[0][0])
        self.assertIn("INSERT INTO warehouse_lot_movements", cur.statements[1][0])
        self.assertEqual(cur.statements[1][1][:5], (7, 1, 55, 25, "м"))

    def test_restoring_lot_appends_compensating_event(self):
        cur = FakeCursor(rows=[{"available_quantity": 100}])

        remaining = restore_receipt_lot(
            cur, lot_id=7, company_id=1, warehouse_movement_id=56,
            original_lot_movement_id=99, quantity=25, unit="м",
            from_location="Объект", to_location="Основной склад", created_by="Директор",
        )

        self.assertEqual(remaining, 100)
        self.assertIn("available_quantity=available_quantity+%s", cur.statements[0][0])
        self.assertIn("warehouse_movement_reversal", cur.statements[1][0])
        self.assertEqual(cur.statements[1][1][-1], 99)
