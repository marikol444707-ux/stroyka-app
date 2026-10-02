"""Authenticated two-company transfer lifecycle on the guarded disposable PG fixture."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.material_traceability import test_transfer_workflow_postgres as support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class IntercompanyWarehouseTransferPostgresTests(unittest.TestCase):
    sql = support.TransferWorkflowPostgresTests.sql
    api = support.TransferWorkflowPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.TransferWorkflowPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {"INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED": "1"})
        flag.start()
        cls.addClassCleanup(flag.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0082_intercompany_warehouse_transfers.py"
        spec = importlib.util.spec_from_file_location("intercompany_transfer_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType("alembic")
        alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur, patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                migration.upgrade()
        finally:
            conn.close()

    def setUp(self):
        support.TransferWorkflowPostgresTests.setUp(self)
        self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
            VALUES(%s,3,1,'директор',TRUE,FALSE) ON CONFLICT DO NOTHING""",
            (self.f["users"]["director"]["id"],))
        self.source_stock_id = self.sql("""INSERT INTO warehouse_main
            (company_id,name,unit,quantity,price,min_quantity,category)
            VALUES(2,%s,'шт',10,125,0,'Кабель') RETURNING id""", ("INTERCOMPANY " + uuid4().hex,))[0][0]

    def headers(self, company_id):
        return {"X-Company-Id": str(company_id), "X-Company-Mode": "company"}

    def payload(self, **changes):
        return {"requestId": str(uuid4()), "destinationCompanyId": 3,
                "sourceStockId": self.source_stock_id, "quantity": "4",
                "reason": "Передача между собственными компаниями", **changes}

    def create(self, payload=None):
        return self.api("director", "POST", "/intercompany-warehouse-transfers",
                        payload or self.payload(), **self.headers(2))

    def balances(self, material):
        return self.sql("""SELECT company_id,quantity FROM warehouse_main
            WHERE name=%s ORDER BY company_id""", (material,))

    def test_acceptance_changes_both_stocks_once_and_creates_paired_evidence(self):
        material = self.sql("SELECT name FROM warehouse_main WHERE id=%s", (self.source_stock_id,))[0][0]
        payload = self.payload()
        created = self.create(payload)
        self.assertEqual((created["side"], created["status"], created["document"]["kind"]),
                         ("source", "pending", "intercompany_dispatch"))
        self.assertEqual(self.balances(material), [(2, 10)])
        replay = self.create(payload)
        self.assertEqual(replay["id"], created["id"])
        self.api("director", "POST", "/intercompany-warehouse-transfers",
                 {**payload, "quantity": "3"}, expected=409, **self.headers(2))
        incoming = self.api("stranger", "GET", "/intercompany-warehouse-transfers", **self.headers(3))
        received = next(item for item in incoming["items"] if item["id"] == created["id"])
        self.assertEqual((received["side"], received["document"]["kind"]),
                         ("destination", "intercompany_receipt"))
        accepted = self.api("stranger", "POST",
            f"/intercompany-warehouse-transfers/{created['id']}/accept", {}, **self.headers(3))
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(self.balances(material), [(2, 6), (3, 4)])
        self.api("stranger", "POST", f"/intercompany-warehouse-transfers/{created['id']}/accept",
                 {}, **self.headers(3))
        self.assertEqual(self.balances(material), [(2, 6), (3, 4)])
        movement_ids = self.sql("""SELECT source_movement_id,destination_movement_id
            FROM intercompany_warehouse_transfers WHERE id=%s""", (created["id"],))[0]
        self.assertEqual(self.sql("""SELECT company_id,count(*) FROM warehouse_movements
            WHERE id IN (%s,%s) GROUP BY company_id ORDER BY company_id""", movement_ids), [(2, 1), (3, 1)])
        self.assertEqual(self.sql("""SELECT company_id,type FROM warehouse_history
            WHERE source_type='intercompany_warehouse_transfer' AND source_id=%s ORDER BY company_id""",
            (created["id"],)), [(2, "межфирменная передача: списание"),
                                (3, "межфирменная передача: приход")])

    def test_rejection_and_cancel_leave_both_stocks_unchanged(self):
        material = self.sql("SELECT name FROM warehouse_main WHERE id=%s", (self.source_stock_id,))[0][0]
        rejected = self.create()
        self.api("stranger", "POST", f"/intercompany-warehouse-transfers/{rejected['id']}/reject",
                 {"reason": "Не ожидаем материал"}, **self.headers(3))
        cancelled = self.create()
        self.api("director", "POST", f"/intercompany-warehouse-transfers/{cancelled['id']}/cancel",
                 {"reason": "Передача больше не нужна"}, **self.headers(2))
        self.assertEqual(self.balances(material), [(2, 10)])

    def test_wrong_company_cannot_decide_and_accept_rechecks_source_balance(self):
        transfer = self.create()
        self.api("director", "POST", f"/intercompany-warehouse-transfers/{transfer['id']}/accept",
                 {}, expected=403, **self.headers(2))
        self.sql("UPDATE warehouse_main SET quantity=1 WHERE id=%s", (self.source_stock_id,))
        self.api("stranger", "POST", f"/intercompany-warehouse-transfers/{transfer['id']}/accept",
                 {}, expected=409, **self.headers(3))
        self.assertEqual(self.sql("SELECT status FROM intercompany_warehouse_transfers WHERE id=%s",
                                  (transfer["id"],)), [("pending",)])
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_history WHERE source_type='intercompany_warehouse_transfer' AND source_id=%s",
                                  (transfer["id"],)), [(0,)])

    def test_source_cannot_target_a_company_outside_its_cabinet(self):
        self.sql("""INSERT INTO companies(id,name,short_name,plan,active,payment_status,platform_account_id)
            VALUES(4,'FOREIGN company','FOREIGN','pro',TRUE,'active',2)""")
        self.addCleanup(self.sql, "DELETE FROM companies WHERE id=4")
        self.api("director", "POST", "/intercompany-warehouse-transfers",
                 self.payload(destinationCompanyId=4), expected=403, **self.headers(2))
        self.assertEqual(self.sql("SELECT count(*) FROM intercompany_warehouse_transfers WHERE destination_company_id=4"),
                         [(0,)])

    def test_concurrent_destination_acceptance_posts_stock_only_once(self):
        from fastapi.testclient import TestClient
        transfer = self.create()
        token = self.main.create_auth_token(self.f["users"]["stranger"], two_factor_passed=True)

        def accept():
            with TestClient(self.main.app) as client:
                return client.post(f"/intercompany-warehouse-transfers/{transfer['id']}/accept", json={},
                    headers={"Authorization": "Bearer " + token, **self.headers(3)})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [future.result(timeout=20) for future in (pool.submit(accept), pool.submit(accept))]
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(self.sql("SELECT quantity FROM warehouse_main WHERE id=%s", (self.source_stock_id,)), [(6,)])
        self.assertEqual(self.sql("""SELECT count(*) FROM warehouse_history
            WHERE source_type='intercompany_warehouse_transfer' AND source_id=%s""", (transfer["id"],)), [(2,)])


if __name__ == "__main__":
    unittest.main()
