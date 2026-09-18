"""Full authenticated transfer HTTP lifecycle against an explicit empty UTF8 DB.
SUPPLY_CHAIN_RUN_POSTGRES=1 + explicit SUPPLY_CHAIN_TEST_DB_* Unix-socket settings.
build_fixture leaves schema: EVERY run needs a fresh empty UTF8 DB.
No auth/stock/balance/estimate mocks. Only postcommit external AI is disabled.
Migration 0012 enables real common locks; distribution races are not covered here.
"""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import time
from threading import Barrier
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires an explicitly provisioned empty PostgreSQL database")
class TransferWorkflowPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)
        ai = patch.object(cls.main, "_run_project_ai_control_safely", return_value=None)
        ai.start()
        cls.addClassCleanup(ai.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0025_warehouse_distribution.py"
        spec = importlib.util.spec_from_file_location("transfer_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        # No Alembic installed: execute WHOLE migration with a SQL executor adapter.
        alembic = ModuleType("alembic")
        alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("SHOW server_encoding")
                if cur.fetchone()[0] != "UTF8":
                    raise RuntimeError("Transfer test requires an empty UTF8 database")
                with patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                    migration.upgrade()
        finally:
            conn.close()

    def sql(self, statement, params=()):
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        from psycopg2.extras import Json
        self.f = self.fixture
        for table in ("warehouse_history", "material_transfers", "materials", "work_journal",
                      "supply_deliveries", "supply_requests"):
            self.sql("DELETE FROM " + table)
        self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
                    VALUES(2,%s,%s,2,%s,%s)""",
                 (self.f["materialName"], self.f["unit"], self.f["project"], self.f["workPackage"]))
        self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
                    VALUES(3,%s,%s,7,%s,%s)""",
                 (self.f["materialName"], self.f["unit"], self.f["project"], self.f["workPackage"]))
        sentinel = self.sql("SELECT * FROM materials WHERE company_id=3")
        self.addCleanup(lambda: self.assertEqual(
            self.sql("SELECT * FROM materials WHERE company_id=3"), sentinel))
        for key, packages in (("worker", [self.f["workPackage"]]),
                              ("other_worker", [self.f["workPackage"]]),
                              ("wrong_package", ["Other package"])):
            if key in self.f["users"]:
                continue
            uid = self.sql("""INSERT INTO users(name,email,password,role,active,company_id,
                           assigned_projects,assigned_packages)
                           VALUES(%s,%s,%s,'мастер',TRUE,2,%s,%s) RETURNING id""",
                           ("TRANSFER " + key, key + "@supply-chain.invalid",
                            self.f["users"]["foreman"]["password"],
                            Json([self.f["project"]]), Json(packages)))[0][0]
            self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
                        role,assigned_projects,assigned_packages,active,is_default)
                        VALUES(%s,2,1,'мастер',%s,%s,TRUE,TRUE)""",
                     (uid, Json([self.f["project"]]), Json(packages)))
            conn = self.main.get_db()
            try:
                from psycopg2.extras import RealDictCursor
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
                    self.f["users"][key] = dict(cur.fetchone())
            finally:
                conn.close()

    def api(self, actor, method, path, payload=None, expected=200, **headers):
        token = self.main.create_auth_token(self.f["users"][actor], two_factor_passed=True)
        response = self.client.request(method, path, json=payload, headers={
            "Authorization": "Bearer " + token, **headers})
        self.assertEqual(response.status_code, expected, (method, path, actor, response.text))
        return response.json()

    def payload(self, quantity=2, **overrides):
        worker = self.f["users"]["worker"]
        return {"companyId": 2, "projectId": self.f["projectId"],
                "projectName": self.f["project"], "fromLocation": self.f["project"],
                "workPackage": self.f["workPackage"], "materialName": self.f["materialName"],
                "unit": self.f["unit"], "quantity": quantity, "toUserId": worker["id"],
                "toPerson": worker["name"], "toPersonRole": "мастер", **overrides}

    def issue(self):
        return self.api("foreman", "POST", "/material-transfers", self.payload())["id"]

    def balance(self, actor="worker"):
        from psycopg2.extras import RealDictCursor
        worker = self.f["users"][actor]
        conn = self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return self.main._personal_material_balance(
                    cur, self.f["project"], worker["id"], worker["name"],
                    self.f["materialName"], self.f["workPackage"], self.f["unit"], company_id=2)
        finally:
            conn.close()

    def snapshot(self):
        return tuple(self.sql("SELECT * FROM " + table + " ORDER BY id")
                     for table in ("materials", "material_transfers", "warehouse_history"))

    def assert_state(self, stock, issued, returned):
        self.assertEqual(self.sql("SELECT company_id,quantity FROM materials WHERE company_id=2"), [(2, stock)])
        self.assertEqual(self.balance(), {"issued": issued, "used": 0,
                                         "returned": returned, "available": issued - returned})

    def denied_unchanged(self, actor, method, path, payload=None, expected=403, **headers):
        before, balance = self.snapshot(), self.balance()
        self.api(actor, method, path, payload, expected, **headers)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.balance(), balance)

    def test_full_cycle_sign_partial_return_and_overreturn_denied(self):
        self.assert_state(2, 0, 0)
        for quantity in ("NaN", "badquantity"):
            for actor, path in (("foreman", "/material-transfers"),
                                ("worker", "/material-transfers/return")):
                with self.subTest(quantity=quantity, path=path):
                    self.denied_unchanged(actor, "POST", path, self.payload(quantity), 400)
        tid = self.issue()
        self.assert_state(0, 0, 0)
        self.assertEqual(self.sql("""SELECT company_id,project_id,to_user_id,quantity,signed
                                     FROM material_transfers WHERE id=%s""", (tid,)),
                         [(2, self.f["projectId"], self.f["users"]["worker"]["id"], 2, False)])
        self.assertEqual(self.sql("SELECT type,quantity,source_type,source_id FROM warehouse_history"),
                         [("расход", 2, "material_transfer", tid)])
        self.denied_unchanged("worker", "POST", "/material-transfers/return", self.payload(1), 400)
        self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
        self.assert_state(0, 2, 0)
        before = self.snapshot()
        self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
        self.assertEqual(self.snapshot(), before)
        self.api("worker", "POST", "/material-transfers/return", self.payload(1))
        self.assert_state(1, 2, 1)
        self.assertEqual(self.sql("""SELECT type,quantity,issued_by FROM warehouse_history
                                     WHERE type='возврат от мастера'"""),
                         [("возврат от мастера", 1, self.f["users"]["worker"]["name"])])
        self.denied_unchanged("worker", "POST", "/material-transfers/return", self.payload(2), 400)
        self.api("worker", "POST", "/material-transfers/return", self.payload(1))
        self.assert_state(2, 2, 2)

    def test_foreign_same_name_aggregate_rows_do_not_change_control(self):
        def projection(exclude_request_id=None):
            conn = self.main.get_db()
            try:
                with conn.cursor() as cur:
                    control = self.main._supply_material_estimate_control(cur,
                        {"id": self.f["projectId"], "name": self.f["project"], "companyId": 2},
                        self.f["materialName"], self.f["unit"], self.f["workPackage"],
                        exclude_request_id=exclude_request_id)
                return [control[k] for k in ("stockQty", "returnedQty", "writtenOffQty", "requestedQty")]
            finally:
                conn.close()
        identity = (self.f["project"], self.f["workPackage"], self.f["materialName"], self.f["unit"])
        request_sql = """INSERT INTO supply_requests(company_id,project,work_package,material_name,unit,quantity)
                         VALUES(%s,%s,%s,%s,%s,%s) RETURNING id"""
        own_request = self.sql(request_sql, (2, *identity, 1))[0][0]
        baseline = projection()
        self.assertEqual(baseline, [2, 0, 0, 1])
        self.sql("""INSERT INTO warehouse_history(company_id,project,work_package,material,unit,type,quantity)
                    VALUES(3,%s,%s,%s,%s,'возврат от мастера',11)""", identity)
        self.sql("""INSERT INTO work_journal(company_id,project,work_package,materials_used)
                    VALUES(3,%s,%s,%s)""", (self.f["project"], self.f["workPackage"],
                    self.main.json.dumps([{"name": self.f["materialName"], "unit": self.f["unit"], "quantity": 13}])))
        self.sql(request_sql, (3, *identity, 17))
        self.sql("""INSERT INTO supply_deliveries(company_id,request_id,project,work_package,
                    material_name,unit,received_quantity) VALUES(3,%s,%s,%s,%s,%s,1)""", (own_request, *identity))
        foreign = tuple(self.sql("SELECT * FROM " + t + " WHERE company_id=3 ORDER BY id")
                        for t in ("materials", "warehouse_history", "work_journal", "supply_requests", "supply_deliveries"))
        self.assertEqual(projection(), baseline)
        self.sql("""INSERT INTO supply_deliveries(company_id,request_id,project,work_package,
                    material_name,unit,received_quantity) VALUES(2,%s,%s,%s,%s,%s,0.5)""", (own_request, *identity))
        self.assertEqual(projection(), [2, 0, 0, 0.5])
        self.assertEqual(projection(exclude_request_id=own_request), [2, 0, 0, 0])
        self.assertEqual(tuple(self.sql("SELECT * FROM " + t + " WHERE company_id=3 ORDER BY id")
                               for t in ("materials", "warehouse_history", "work_journal", "supply_requests", "supply_deliveries")), foreign)

    def test_unsigned_cancel_restores_exactly_once(self):
        tid = self.issue()
        self.api("foreman", "DELETE", f"/material-transfers/{tid}")
        self.assert_state(2, 0, 0)
        self.assertEqual(self.sql("SELECT status,signed,cancelled_at IS NOT NULL FROM material_transfers"),
                         [("Аннулирована", False, True)])
        before = self.snapshot()
        self.api("foreman", "DELETE", f"/material-transfers/{tid}")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("SELECT type,quantity FROM warehouse_history ORDER BY id"),
                         [("расход", 2), ("отмена передачи", 2)])
        self.denied_unchanged("worker", "PUT", f"/material-transfers/{tid}/sign", expected=400)

    def test_signed_cancel_denied(self):
        tid = self.issue()
        self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
        self.denied_unchanged("foreman", "DELETE", f"/material-transfers/{tid}", expected=400)
        self.assert_state(0, 2, 0)

    def test_concurrent_full_returns_credit_stock_only_once(self):
        from fastapi.testclient import TestClient
        tid = self.issue()
        self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
        self.assert_state(0, 2, 0)
        transfer_before = self.sql("SELECT * FROM material_transfers ORDER BY id")
        token = self.main.create_auth_token(self.f["users"]["worker"], two_factor_passed=True)
        start = Barrier(2, timeout=5)

        def return_all():
            client = TestClient(self.main.app)
            try:
                start.wait()
                return client.post("/material-transfers/return", json=self.payload(2),
                                   headers={"Authorization": "Bearer " + token})
            finally:
                client.close()

        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("LOCK TABLE materials IN SHARE ROW EXCLUSIVE MODE")
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(return_all) for _ in range(2)]
                try:
                    # Prove BOTH real handlers overlap at the common PG lock.
                    deadline = time.monotonic() + 3
                    waiting = 0
                    while waiting < 2 and time.monotonic() < deadline:
                        waiting = self.sql("""SELECT count(*) FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                              AND query LIKE 'LOCK TABLE materials, warehouse_main, projects%%'""")[0][0]
                        if waiting < 2:
                            time.sleep(0.02)
                    self.assertEqual(waiting, 2, "Both return handlers must reach the real stock lock")
                finally:
                    blocker.rollback()
                responses = [future.result(timeout=20) for future in futures]
        finally:
            blocker.close()
        self.assertEqual(sorted(r.status_code for r in responses), [200, 400],
                         [(r.status_code, r.text) for r in responses])
        self.assert_state(2, 2, 2)
        self.assertEqual(self.sql("SELECT * FROM material_transfers ORDER BY id"), transfer_before)
        self.assertEqual(self.sql("SELECT company_id,type,quantity FROM warehouse_history ORDER BY id"),
                         [(2, "расход", 2), (2, "возврат от мастера", 2)])

    def test_company_role_package_and_other_receiver_denials(self):
        self.denied_unchanged("worker", "POST", "/material-transfers", self.payload())
        self.denied_unchanged("foreman", "POST", "/material-transfers", self.payload(),
                              **{"X-Company-Id": "3"})
        wrong = self.f["users"]["wrong_package"]
        self.denied_unchanged("foreman", "POST", "/material-transfers",
                              self.payload(toUserId=wrong["id"], toPerson=wrong["name"]))
        tid = self.issue()
        for actor, status in (("stranger", 404), ("other_worker", 403),
                              ("wrong_package", 403), ("foreman", 403)):
            with self.subTest(actor=actor):
                self.denied_unchanged(actor, "PUT", f"/material-transfers/{tid}/sign", expected=status)
        self.denied_unchanged("stranger", "DELETE", f"/material-transfers/{tid}", expected=404)
        self.denied_unchanged("worker", "DELETE", f"/material-transfers/{tid}")
        self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
        self.denied_unchanged("wrong_package", "POST", "/material-transfers/return", self.payload(1))
        self.denied_unchanged("other_worker", "POST", "/material-transfers/return",
                              self.payload(1, fromPersonId=self.f["users"]["worker"]["id"],
                                           fromPerson=self.f["users"]["worker"]["name"]), 400)

    def test_history_failure_rolls_back_create_return_and_cancel(self):
        self.sql("""CREATE FUNCTION transfer_test_fail_history() RETURNS trigger LANGUAGE plpgsql
                    AS $$ BEGIN RAISE EXCEPTION 'injected transfer history failure'; END $$""")
        self.addCleanup(self.sql, "DROP FUNCTION transfer_test_fail_history()")
        for operation in ("create", "return", "cancel"):
            with self.subTest(operation=operation):
                tid = self.issue() if operation != "create" else None
                if operation == "return":
                    self.api("worker", "PUT", f"/material-transfers/{tid}/sign")
                self.sql("""CREATE TRIGGER transfer_test_fail_history BEFORE INSERT ON warehouse_history
                            FOR EACH ROW EXECUTE FUNCTION transfer_test_fail_history()""")
                try:
                    if operation == "create":
                        self.denied_unchanged("foreman", "POST", "/material-transfers", self.payload(), 500)
                    elif operation == "return":
                        self.denied_unchanged("worker", "POST", "/material-transfers/return", self.payload(1), 500)
                    else:
                        self.denied_unchanged("foreman", "DELETE", f"/material-transfers/{tid}", expected=500)
                finally:
                    self.sql("DROP TRIGGER transfer_test_fail_history ON warehouse_history")
                if operation == "return":
                    self.api("worker", "POST", "/material-transfers/return", self.payload(2))
                for table in ("warehouse_history", "material_transfers"):
                    self.sql("DELETE FROM " + table)
                self.sql("UPDATE materials SET quantity=2 WHERE company_id=2")


if __name__ == "__main__":
    unittest.main()
