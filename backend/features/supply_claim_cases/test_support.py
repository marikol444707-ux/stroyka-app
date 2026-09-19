"""Supply-claim fixture using real authentication, addressing and disposable PG."""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from backend.features.work_material_accounting import test_postgres as materials


class SupplyClaimCasesPostgresSupport:
    sql = materials.WorkMaterialAccountingPostgresTests.sql
    api = materials.WorkMaterialAccountingPostgresTests.api
    payload = materials.WorkMaterialAccountingPostgresTests.payload
    balance = materials.WorkMaterialAccountingPostgresTests.balance
    request = materials.WorkMaterialAccountingPostgresTests.request

    @classmethod
    def setUpClass(cls):
        materials.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {"SUPPLY_CLAIMS_ENABLED": "1"})
        flag.start()
        cls.addClassCleanup(flag.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0033_supply_claim_cases.py"
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location("supply_claim_cases_test_migration", path)
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
        self.sql("""TRUNCATE TABLE supply_claims,supply_deliveries,supply_request_recipients,supplier_offers
            RESTART IDENTITY CASCADE""")
        materials.WorkMaterialAccountingPostgresTests.setUp(self)
        worker = self.f["users"]["worker"]
        self.request_id = self.sql("""INSERT INTO supply_requests(company_id,project,material_name,quantity,unit,work_package,
            status,prorab_confirmed_at,director_approved_at,requested_by_id,created_by)
            VALUES(2,%s,%s,2,%s,%s,'КП запрошены',NOW(),NOW(),%s,%s) RETURNING id""",
            (self.f["project"], self.f["materialName"], self.f["unit"], self.f["workPackage"], worker["id"], worker["name"]))[0][0]
        self.offer_id = self.sql("""INSERT INTO supplier_offers(company_id,request_id,supplier_id,status)
            VALUES(2,%s,%s,'Утверждено') RETURNING id""", (self.request_id, self.f["supplierId"]))[0][0]
        self.recipient_id = self.sql("""INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
            supplier_user_id,supplier_group_ids,visible_to_supplier) VALUES(2,%s,%s,%s,%s,%s,TRUE) RETURNING id""",
            (self.request_id, self.f["supplierId"], self.f["supplierId"], self.f["users"]["supplier"]["id"], [self.f["supplierId"]]))[0][0]
        self.delivery_id = self.sql("""INSERT INTO supply_deliveries(company_id,request_id,offer_id,supplier_id,project,
            material_name,planned_quantity,shipped_quantity,received_quantity,shortage_quantity,unit,work_package,status)
            VALUES(2,%s,%s,%s,%s,%s,2,2,1,1,%s,%s,'Принято с замечаниями') RETURNING id""",
            (self.request_id, self.offer_id, self.f["supplierId"], self.f["project"], self.f["materialName"],
             self.f["unit"], self.f["workPackage"]))[0][0]
        status = getattr(getattr(self, self._testMethodName), "initial_status", "Открыта")
        self.claim_id = self.sql("""INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,material_name,
            work_package,claim_type,description,expected_quantity,received_quantity,shortage_quantity,status,resolution,resolved_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'Недостача','One item missing',2,1,1,%s,%s,%s) RETURNING id""",
            (self.delivery_id, self.request_id, self.offer_id, self.f["supplierId"], self.f["project"], self.f["materialName"],
             self.f["workPackage"], status, "Director original decision" if status in ("Решена", "Закрыта") else "",
             "2026-09-19 12:00:00" if status in ("Решена", "Закрыта") else None))[0][0]
        self.legacy_path = f"/supply-claims/{self.claim_id}"
        self.path = self.legacy_path + "/case"

    def snapshot(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("supply_claims", "supply_deliveries", "supplier_offers", "supply_requests", "supply_request_recipients",
                          "materials", "warehouse_main", "warehouse_history", "warehouse_movements", "material_transfers",
                          "warehouse_invoices", "supplier_invoices", "project_payments", "brigade_payments", *self.new_tables))

    def assert_denied_unchanged(self, method, path, data=None, expected=409, actor="director", **headers):
        before = self.snapshot()
        response = self.request(method, path, data, actor=actor) if not headers else None
        if response is not None:
            actual = self.sql("SELECT status,resolution,resolved_at FROM supply_claims WHERE id=%s", (self.claim_id,))
            self.assertEqual(response.status_code, expected, f"{response.text}; persisted claim={actual!r}")
        else:
            self.api(actor, method, path, data, expected=expected, **headers)
        self.assertEqual(self.snapshot(), before)
