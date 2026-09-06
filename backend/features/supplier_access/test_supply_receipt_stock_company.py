"""Run the real stock helper without importing main or opening a database."""

import ast
from pathlib import Path
import re
import unittest


MAIN_PATH = Path(__file__).resolve().parents[3] / "backend/main.py"


class _StockCursor:
    def __init__(self, materials=(), tuple_result=False):
        self.materials = [dict(row) for row in materials]
        self.history = []
        self.calls = []
        self.result = None
        self.tuple_result = tuple_result

    def execute(self, sql, params):
        sql = " ".join(sql.split())
        self.calls.append((sql, params))
        company_filter = re.search(r"\bcompany_id\s*=\s*%s", sql)
        company_id = params[sql[:company_filter.start()].count("%s")] if company_filter else None
        if sql.startswith("SELECT id FROM materials"):
            name, project, package, unit = params[:4]
            rows = [
                row for row in self.materials
                if (row["name"], row["project"], row.get("work_package") or "", row["unit"])
                == (name, project, package, unit)
                and (not company_filter or row.get("company_id") == company_id)
            ]
            self.result = rows[0] if rows else None
        elif sql.startswith("UPDATE materials"):
            quantity, unit, price, material_id = params[:4]
            for row in self.materials:
                if row["id"] == material_id and (not company_filter or row.get("company_id") == company_id):
                    row.update(quantity=(row.get("quantity") or 0) + quantity, unit=unit, price=price)
        elif sql.startswith("INSERT INTO"):
            columns = [column.strip() for column in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
            row = dict(zip(columns, params))
            if sql.startswith("INSERT INTO materials"):
                # Match the real schema's DEFAULT 1 when the insert omits ownership.
                row.setdefault("company_id", 1)
                row["id"] = max((material["id"] for material in self.materials), default=0) + 1
                self.materials.append(row)
            elif sql.startswith("INSERT INTO warehouse_history"):
                self.history.append(row)
            else:
                raise AssertionError(f"Unexpected insert: {sql}")
        else:
            raise AssertionError(f"Unexpected query: {sql}")

    def fetchone(self):
        if self.result and self.tuple_result:
            return (self.result["id"],)
        return self.result


def _material(material_id, company_id, quantity=10):
    return {
        "id": material_id, "company_id": company_id, "name": "Кабель",
        "project": "Объект", "work_package": "Основная", "unit": "м",
        "quantity": quantity, "price": 20,
    }


class SupplyReceiptStockCompanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "_add_project_material")
        namespace = {"_norm_base_unit": lambda value: value, "_sql_norm_unit": lambda column: column}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(MAIN_PATH), "exec"), namespace)
        cls.add_material = staticmethod(namespace["_add_project_material"])

    def receive(self, cursor, **overrides):
        values = dict(name="Кабель", unit="м", qty=2, price=30, project="Объект",
                      work_package=" Основная ", company_id=2, source_type="supply_delivery",
                      source_id=42, source_invoice_id=84)
        values.update(overrides)
        self.add_material(cursor, **values)

    def test_company_two_receipt_creates_stock_and_history_in_company_two(self):
        cursor = _StockCursor()
        self.receive(cursor)

        self.assertEqual(2, cursor.materials[0]["company_id"])
        self.assertEqual(2, cursor.materials[0]["quantity"])
        self.assertEqual(30, cursor.materials[0]["price"])
        self.assertEqual("Основная", cursor.materials[0]["work_package"])
        self.assertEqual(2, cursor.history[0]["company_id"])
        self.assertEqual(("supply_delivery", 42, 84), tuple(
            cursor.history[0][key] for key in ("source_type", "source_id", "source_invoice_id")))

    def test_identical_stock_in_other_company_is_not_updated(self):
        cursor = _StockCursor([_material(1, 1), _material(2, 2)])
        self.receive(cursor)

        self.assertEqual([10, 12], [row["quantity"] for row in cursor.materials])
        self.assertEqual([20, 30], [row["price"] for row in cursor.materials])
        self.assertEqual([2], [row["company_id"] for row in cursor.history])

    def test_other_company_or_unowned_stock_does_not_absorb_new_receipt(self):
        for other_company in (1, None):
            with self.subTest(other_company=other_company):
                cursor = _StockCursor([_material(1, other_company)])
                self.receive(cursor)

                self.assertEqual(2, len(cursor.materials))
                self.assertEqual(10, cursor.materials[0]["quantity"])
                self.assertEqual(2, cursor.materials[1]["company_id"])
                self.assertEqual(2, cursor.materials[1]["quantity"])

    def test_stock_update_is_guarded_by_company_as_well_as_id(self):
        cursor = _StockCursor([_material(2, 2)], tuple_result=True)
        self.receive(cursor)

        self.assertEqual(12, cursor.materials[0]["quantity"])
        update_sql, update_params = next(call for call in cursor.calls if call[0].startswith("UPDATE"))
        self.assertRegex(update_sql, r"WHERE id=%s AND company_id=%s")
        self.assertEqual((2, 2), update_params[-2:])

    def test_default_company_remains_one_for_stock_and_history(self):
        cursor = _StockCursor()
        self.add_material(cursor, "Кабель", "м", 2, 30, "Объект")

        self.assertEqual([1], [row["company_id"] for row in cursor.materials])
        self.assertEqual([1], [row["company_id"] for row in cursor.history])

    def test_invalid_or_empty_receipt_remains_a_no_op(self):
        for values in ({"name": ""}, {"project": ""}, {"qty": 0}, {"qty": -1}):
            with self.subTest(values=values):
                cursor = _StockCursor()
                self.receive(cursor, **values)
                self.assertEqual([], cursor.calls)


if __name__ == "__main__":
    unittest.main()
