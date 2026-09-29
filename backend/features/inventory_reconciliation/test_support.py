"""Real authenticated inventory fixture on the guarded disposable PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from backend.features.tool_custody.test_support import ToolCustodyPostgresSupport


class InventoryReconciliationPostgresSupport(ToolCustodyPostgresSupport):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flags = patch.dict(os.environ, {"INVENTORY_RECONCILIATION_ENABLED": "1"})
        flags.start()
        cls.addClassCleanup(flags.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0030_inventory_reconciliation.py"
        spec = importlib.util.spec_from_file_location("inventory_reconciliation_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType("alembic")
        alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                before = {row[0] for row in cur.fetchall()}
                with patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                    migration.upgrade()
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                cls.new_tables = sorted(set(cls.new_tables) | ({row[0] for row in cur.fetchall()} - before))
        finally:
            conn.close()

    def setUp(self):
        super().setUp()
        # The inherited reset truncates the new immutable ledgers first. All
        # remaining rows here belong to this isolated synthetic test fixture.
        for table in ("inventory_items", "inventory", "warehouse_lot_movements",
                      "warehouse_receipt_lots", "warehouse_movements", "warehouse_main", "warehouse_invoices"):
            self.sql("DELETE FROM " + table)
        self.main_stock_id = self.sql("""INSERT INTO warehouse_main(company_id,name,unit,quantity,price)
            VALUES(2,%s,%s,5,15) RETURNING id""", (self.f["materialName"], self.f["unit"]))[0][0]
        self.sql("""INSERT INTO warehouse_main(company_id,name,unit,quantity,price)
            VALUES(3,%s,%s,99,125)""", (self.f["materialName"], self.f["unit"]))

    def snapshot(self):
        tables = ("inventory", "inventory_items", "warehouse_main", "warehouse_movements",
                  "warehouse_receipt_lots", "warehouse_lot_movements", "warehouse_invoices", "supplier_invoices")
        return super().snapshot() + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1")) for table in tables)

    def create_inventory(self, *, main=False, actor="foreman", **changes):
        payload = {"requestId": str(uuid4()), "projectId": None if main else self.f["projectId"],
                   "notes": "Synthetic factual stocktake", **changes}
        result = self.api(actor, "POST", "/inventory/reconciliation", payload)
        self.assertTrue(result["ok"])
        self.inventory_id = result["inventoryId"]
        self.path = f"/inventory/{self.inventory_id}/reconciliation"
        self.counter_actor = actor
        return result, payload

    def detail(self, actor="director"):
        return self.api(actor, "GET", self.path)

    def material_row(self, detail=None):
        matches = [row for row in (detail or self.detail())["rows"]
                   if row["kind"] == "material" and row["name"] == self.f["materialName"]]
        self.assertEqual(len(matches), 1, matches)
        return matches[0]

    def command_payload(self, action, **changes):
        return {"requestId": str(uuid4()), "action": action,
                "expectedState": self.detail()["expectedState"], **changes}

    def command(self, action, actor=None, **changes):
        payload = self.command_payload(action, **changes)
        result = self.api(actor or self.counter_actor, "POST", self.path, payload)
        self.assertTrue(result["ok"])
        return result, payload

    def count_and_submit(self, actual, reason="Synthetic observed discrepancy"):
        counts = [{"key": row["key"], **(
            {"actual": actual if row["name"] == self.f["materialName"] else row["expected"], "reason": reason}
            if row["kind"] == "material" else {"condition": "as_recorded"})}
            for row in self.detail()["rows"]]
        self.command("save", counts=counts)
        self.command("submit")

    def seed_receipt_lot(self, available=3):
        from psycopg2.extras import Json
        invoice = self.sql("""INSERT INTO warehouse_invoices(company_id,number,location,items,
            total_base,total_with_vat,status) VALUES(2,'SYNTHETIC-INVENTORY-LOT','Основной склад',
            %s,45,45,'Принята') RETURNING id""", (Json([
                {"name": self.f["materialName"], "unit": self.f["unit"], "quantity": available, "price": 15}]),))[0][0]
        lot = self.sql("""INSERT INTO warehouse_receipt_lots(company_id,warehouse_location,warehouse_target,
            warehouse_invoice_id,invoice_line_index,material_name,received_quantity,available_quantity,unit,
            document_quantity,document_unit)
            VALUES(2,'Основной склад','main',%s,0,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (invoice, self.f["materialName"], available, available, self.f["unit"], available, self.f["unit"]))[0][0]
        return invoice, lot

    def unchanged_command(self, payload, actor="director", expected=409, **headers):
        before = self.snapshot()
        self.api(actor, "POST", self.path, payload, expected=expected, **headers)
        self.assertEqual(self.snapshot(), before)
