"""Company warehouse HTTP fixtures in the guarded disposable PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from backend.features.work_material_accounting import test_postgres as materials


class CompanyWarehousesPostgresSupport:
    sql = materials.WorkMaterialAccountingPostgresTests.sql
    api = materials.WorkMaterialAccountingPostgresTests.api
    payload = materials.WorkMaterialAccountingPostgresTests.payload
    balance = materials.WorkMaterialAccountingPostgresTests.balance
    request = materials.WorkMaterialAccountingPostgresTests.request

    @classmethod
    def setUpClass(cls):
        materials.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {"WAREHOUSE_DIRECTORY_ENABLED": "1"})
        flag.start()
        cls.addClassCleanup(flag.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0031_company_warehouses.py"
        spec = importlib.util.spec_from_file_location("company_warehouses_test_migration", path)
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
        materials.WorkMaterialAccountingPostgresTests.setUp(self)
        # Test-only TRUNCATE: production forbids deleting catalog evidence.
        self.sql("TRUNCATE TABLE warehouses RESTART IDENTITY CASCADE")
        self.legacy_id = self.sql("""INSERT INTO warehouses(name,city,address,notes)
            VALUES('Synthetic unowned warehouse','Legacy city','Private legacy address',
                   'Unattributed historical record') RETURNING id""")[0][0]
        business = self.business_snapshot()
        self.addCleanup(lambda: self.assertEqual(self.business_snapshot(), business,
            "Directory metadata commands must not change stock, receipts, payments, tools or inventories"))

    def business_snapshot(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("materials", "warehouse_main", "warehouse_history", "warehouse_movements", "material_transfers",
                          "warehouse_invoices", "supplier_invoices", "project_payments", "brigade_payments",
                          "inventory", "inventory_items", "tools", "tool_history"))

    def snapshot(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("warehouses", "materials", "warehouse_main", "warehouse_history", "warehouse_movements",
                          "material_transfers", *self.new_tables))

    def warehouse_payload(self, **changes):
        return {"name": "Synthetic warehouse", "city": "Synthetic city", "address": "Synthetic address",
                "notes": "Private company warehouse notes", **changes}

    def own_headers(self):
        return {"X-Company-Id": "2", "X-Company-Mode": "company"}

    def create_card(self, actor="director", **changes):
        payload = {"action": "create", "requestId": str(uuid4()), **self.warehouse_payload(**changes)}
        result = self.api(actor, "POST", "/warehouses/directory", payload)
        self.assertTrue(result["ok"])
        self.warehouse_id = result["warehouseId"]
        self.path = f"/warehouses/{self.warehouse_id}/directory"
        return result, payload

    def detail(self, actor="director"):
        return self.api(actor, "GET", self.path)

    def command_payload(self, action, **changes):
        return {"action": action, "requestId": str(uuid4()), "expectedVersion": self.detail()["warehouse"]["version"], **changes}

    def update_payload(self, **changes):
        card = self.detail()["warehouse"]
        return self.command_payload("update", **{**{key: card[key] for key in ("name", "city", "address", "notes")}, **changes})

    def assert_denied_unchanged(self, method, path, data=None, expected=409):
        before = self.snapshot()
        self.api("director", method, path, data, expected=expected, **self.own_headers())
        self.assertEqual(self.snapshot(), before)
