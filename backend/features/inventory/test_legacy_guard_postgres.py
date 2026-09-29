"""Legacy inventory integrity through authenticated HTTP and disposable PG.

With reconciliation enabled the legacy write API is read-only. Historical
fixtures are created with the flag off, then unsafe writes must fail atomically.
"""
import os
import unittest
from unittest.mock import patch

from backend.features.material_traceability import test_transfer_workflow_postgres as shared


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class LegacyInventoryGuardPostgresTests(unittest.TestCase):
    sql = shared.TransferWorkflowPostgresTests.sql
    api = shared.TransferWorkflowPostgresTests.api

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from backend.features.inventory_ownership.migration import _ensure_schema
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)
        cls.addClassCleanup(cls.client.close)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                # Production already has this separate owner migration. The
                # shared blank-database bootstrap intentionally does not run it.
                _ensure_schema(cur)
        finally:
            conn.close()

    def setUp(self):
        flag = patch.dict(os.environ, {"INVENTORY_RECONCILIATION_ENABLED": "1"})
        flag.start()
        self.addCleanup(flag.stop)
        self.f = self.fixture
        for table in ("inventory_items", "inventory", "materials"):
            self.sql("DELETE FROM " + table)
        for company, amount in ((2, 10), (3, 99)):
            self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
                VALUES(%s,%s,%s,%s,%s,'Основная')""",
                (company, self.f["materialName"], self.f["unit"], amount, self.f["project"]))
        self.stock_id = self.sql("SELECT id FROM materials WHERE company_id=2")[0][0]
        self.inventory_payload = {"project": self.f["project"], "date": "2026-09-19",
                                  "createdBy": self.f["users"]["foreman"]["name"], "notes": "Synthetic count"}
        with patch.dict(os.environ, {"INVENTORY_RECONCILIATION_ENABLED": "0"}):
            self.inventory_id = self.api("foreman", "POST", "/inventory", self.inventory_payload)["id"]
        self.path = f"/inventory/{self.inventory_id}"

    def request(self, method, path, payload=None, actor="foreman"):
        token = self.main.create_auth_token(self.f["users"][actor], two_factor_passed=True)
        return self.client.request(method, path, json=payload,
            headers={"Authorization": "Bearer " + token, "X-Company-Mode": "company", "X-Company-Id": "2"})

    def snapshot(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
                     for table in ("inventory", "inventory_items", "materials", "warehouse_history",
                                   "warehouse_main", "warehouse_movements"))

    def item_payload(self, **changes):
        return {"inventoryId": self.inventory_id, "materialName": self.f["materialName"],
                "unit": self.f["unit"], "expected": 10, "actual": 8, "difference": -2, **changes}

    def add_item(self):
        with patch.dict(os.environ, {"INVENTORY_RECONCILIATION_ENABLED": "0"}):
            return self.api("foreman", "POST", self.path + "/items", self.item_payload())

    def assert_conflict_unchanged(self, method, path, payload=None):
        before = self.snapshot()
        response = self.request(method, path, payload)
        state = self.sql("SELECT id,status FROM inventory WHERE id=%s", (self.inventory_id,))
        item_count = self.sql("SELECT COUNT(*) FROM inventory_items WHERE inventory_id=%s", (self.inventory_id,))[0][0]
        self.assertEqual(response.status_code, 409,
                         f"{method} {path}: {response.text}; persisted inventory={state!r}, items={item_count}")
        self.assertEqual(self.snapshot(), before)

    def finish_existing_inventory(self):
        self.add_item()
        # A synthetic historical completed record. The old API has no status
        # enum or completion command; this does not invent a new closing API.
        self.sql("UPDATE inventory SET status='Завершена' WHERE id=%s", (self.inventory_id,))

    def test_created_by_cannot_impersonate_another_person(self):
        self.assert_conflict_unchanged("POST", "/inventory",
            {**self.inventory_payload, "createdBy": "Поддельная подпись директора"})

    def test_expected_quantity_cannot_be_forged_on_either_legacy_item_route(self):
        for path in (self.path + "/items", "/inventory-items"):
            with self.subTest(path=path):
                self.assert_conflict_unchanged("POST", path, self.item_payload(expected=999, difference=0))

    def test_difference_cannot_hide_a_shortage_when_actual_is_below_expected(self):
        self.assert_conflict_unchanged("POST", self.path + "/items", self.item_payload(difference=0))

    def test_repeated_same_post_does_not_duplicate_a_counted_material(self):
        first = self.add_item()
        before = self.snapshot()
        response = self.request("POST", self.path + "/items", self.item_payload())
        self.assertEqual(response.status_code, 409, response.text)
        rows = self.sql("SELECT id,expected,actual,difference FROM inventory_items WHERE inventory_id=%s",
                        (self.inventory_id,))
        self.assertEqual(rows, [(first["id"], 10, 8, -2)],
                         "A retried count must not become a second material line or a second shortage")
        self.assertEqual(self.snapshot(), before)

    def test_reentering_actual_through_other_legacy_route_does_not_append_another_line(self):
        self.add_item()
        before = self.snapshot()
        response = self.request("POST", "/inventory-items", self.item_payload(actual=7, difference=-3))
        self.assertEqual(response.status_code, 409, response.text)
        rows = self.sql("SELECT actual FROM inventory_items WHERE inventory_id=%s", (self.inventory_id,))
        self.assertEqual(len(rows), 1, f"Repeated field input must update or reject, not append: {rows!r}")
        self.assertEqual(rows, [(8,)])
        self.assertEqual(self.snapshot(), before)

    def test_completed_inventory_cannot_receive_more_items(self):
        self.finish_existing_inventory()
        for path in (self.path + "/items", "/inventory-items"):
            with self.subTest(path=path):
                self.assert_conflict_unchanged("POST", path, self.item_payload(actual=7, difference=-3))

    def test_completed_inventory_cannot_be_reopened_by_raw_status_update(self):
        self.finish_existing_inventory()
        self.assert_conflict_unchanged("PUT", self.path, {"status": "Открыта"})

    def test_completed_inventory_and_its_count_lines_cannot_be_deleted(self):
        self.finish_existing_inventory()
        self.assert_conflict_unchanged("DELETE", self.path)

    def test_arbitrary_status_cannot_be_persisted(self):
        before = self.snapshot()
        response = self.request("PUT", self.path, {"status": "Любой клиентский текст вместо состояния"})
        stored = self.sql("SELECT status FROM inventory WHERE id=%s", (self.inventory_id,))
        self.assertEqual(response.status_code, 409, f"{response.text}; persisted status={stored!r}")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
