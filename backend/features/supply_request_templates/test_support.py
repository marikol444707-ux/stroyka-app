"""Supply-template integration fixture: real auth and disposable socket-only PG."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from backend.features.work_material_accounting import test_postgres as materials


class SupplyTemplatesPostgresSupport:
    sql = materials.WorkMaterialAccountingPostgresTests.sql
    api = materials.WorkMaterialAccountingPostgresTests.api
    payload = materials.WorkMaterialAccountingPostgresTests.payload
    balance = materials.WorkMaterialAccountingPostgresTests.balance
    request = materials.WorkMaterialAccountingPostgresTests.request

    @classmethod
    def setUpClass(cls):
        materials.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {"SUPPLY_TEMPLATES_ENABLED": "1"})
        flag.start()
        cls.addClassCleanup(flag.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0032_supply_templates.py"
        # The first RED must run against the actual old schema/routes. Once
        # present, apply the complete real migration through the SQL adapter.
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location("supply_templates_test_migration", path)
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
        self.sql("TRUNCATE TABLE supply_request_templates RESTART IDENTITY CASCADE")
        self.legacy_id = self.sql("""INSERT INTO supply_request_templates(name,category,items_json,created_by)
            VALUES('Synthetic unowned template','Legacy private category',%s,'Unverified legacy author') RETURNING id""",
            (json.dumps([self.item(materialName="Private legacy material")]),))[0][0]
        business = self.business_snapshot()
        self.addCleanup(lambda: self.assertEqual(self.business_snapshot(), business,
            "Template commands must not submit requests or change stock/financial records"))

    def business_snapshot(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("materials", "warehouse_main", "warehouse_history", "warehouse_movements", "material_transfers",
                          "warehouse_invoices", "supplier_invoices", "project_payments", "brigade_payments",
                          "supply_requests", "supply_history", "work_journal", "warehouses"))

    def snapshot(self):
        return self.business_snapshot() + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("supply_request_templates", *self.new_tables))

    def item(self, **changes):
        return {"materialName": "Synthetic request material", "quantity": "1.25", "unit": "шт",
                "workPackage": "Основная", **changes}

    def template_payload(self, actor="director", **changes):
        return {"name": "Synthetic reusable request", "category": "Synthetic category", "items": [self.item()],
                "requestId": str(uuid4()), "expectedCompanyId": 3 if actor == "stranger" else 2,
                "expectedActorId": self.f["users"][actor]["id"], **changes}

    def own_headers(self):
        return {"X-Company-Id": "2", "X-Company-Mode": "company"}

    def create_template(self, actor="director", **changes):
        payload = self.template_payload(actor=actor, **changes)
        result = self.api(actor, "POST", "/supply-request-templates", payload)
        self.assertTrue(result["ok"])
        self.assertTrue(result["eventId"])
        self.template_id = result["id"]
        self.path = f"/supply-request-templates/{self.template_id}/archive"
        return result, payload

    def catalog(self, actor="director", **headers):
        return self.api(actor, "GET", "/supply-request-templates/catalog", **headers)

    def archive_payload(self, actor="director", **changes):
        return {"requestId": str(uuid4()), "expectedCompanyId": 3 if actor == "stranger" else 2,
                "expectedActorId": self.f["users"][actor]["id"], "expectedVersion": 1, **changes}

    def assert_denied_unchanged(self, method, path, data=None, expected=400, actor="director", **headers):
        before = self.snapshot()
        self.api(actor, method, path, data, expected=expected, **headers)
        self.assertEqual(self.snapshot(), before)
