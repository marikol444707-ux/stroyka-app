"""V2 factual material consumption through authenticated HTTP and real PG.

Only the explicit disposable Unix-socket fixture is allowed. Actual company,
executor, contract, source-stock and journal handlers run without domain mocks.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.material_traceability import test_work_consumption_postgres as support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class WorkMaterialAccountingPostgresTests(unittest.TestCase):
    sql = support.WorkConsumptionPostgresTests.sql
    api = support.WorkConsumptionPostgresTests.api
    payload = support.WorkConsumptionPostgresTests.payload
    balance = support.WorkConsumptionPostgresTests.balance
    work_payload = support.WorkConsumptionPostgresTests.work_payload
    request = support.WorkConsumptionPostgresTests.request

    @classmethod
    def setUpClass(cls):
        support.WorkConsumptionPostgresTests.setUpClass.__func__(cls)
        flags = patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": "1"})
        flags.start()
        cls.addClassCleanup(flags.stop)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                before = {row[0] for row in cur.fetchall()}
                for filename in ("0024_company_material_aliases.py", "0027_work_material_accounting.py"):
                    path = Path(__file__).resolve().parents[3] / "migrations/versions" / filename
                    spec = importlib.util.spec_from_file_location("work_material_accounting_test_migration", path)
                    migration = importlib.util.module_from_spec(spec)
                    alembic = ModuleType("alembic")
                    alembic.op = None
                    with patch.dict(sys.modules, {"alembic": alembic}):
                        spec.loader.exec_module(migration)
                    with patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                        migration.upgrade()
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                cls.new_tables = sorted({row[0] for row in cur.fetchall()} - before)
        finally:
            conn.close()

    def setUp(self):
        # Reset only the new migration's test-owned tables before the shared
        # fixture resets legacy journals and issues/signs two personal units.
        if self.new_tables:
            from psycopg2 import sql
            statement = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(map(sql.Identifier, self.new_tables)))
            self.sql(statement)
        support.WorkConsumptionPostgresTests.setUp(self)
        self.sql("UPDATE materials SET quantity=2 WHERE company_id=2")
        self.stock_id = self.sql("SELECT id FROM materials WHERE company_id=2")[0][0]
        self.foreign_stock_id = self.sql("SELECT id FROM materials WHERE company_id=3")[0][0]

    def consumption_payload(self, personal=0, warehouse=0, **overrides):
        payload = self.work_payload(personal + warehouse)
        payload.update(materialAccountingVersion=2, requestId=str(uuid4()))
        material = payload["materialsUsed"][0]
        material.update(personalQuantity=personal, warehouseQuantity=warehouse)
        if warehouse:
            material["warehouseMaterialId"] = self.stock_id
        payload.update(overrides)
        return payload

    def stock_quantity(self):
        return self.sql("SELECT quantity FROM materials WHERE id=%s", (self.stock_id,))[0][0]

    def test_worker_v2_stock_quantity_is_visible_only_in_assigned_scope_while_prices_stay_hidden(self):
        self.sql("UPDATE materials SET price=125,min_quantity=9 WHERE id=%s", (self.stock_id,))
        other_project = "Synthetic unassigned stock " + uuid4().hex
        self.sql("INSERT INTO projects(name,company_id) VALUES(%s,2)", (other_project,))
        for project, package in ((self.f["project"], "Other package"), (other_project, self.f["workPackage"])):
            self.sql("""INSERT INTO materials(company_id,name,unit,quantity,price,min_quantity,project,work_package)
                VALUES(2,%s,%s,23,321,8,%s,%s)""",
                (self.f["materialName"], self.f["unit"], project, package))
        self.assertEqual(self.sql("SELECT company_id,quantity FROM materials WHERE id=%s",
                                  (self.foreign_stock_id,)), [(3, 7)])
        before = self.snapshot()
        for enabled, expected_quantity in (("1", 2), ("0", 0)):
            with self.subTest(accounting_flag=enabled), patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": enabled}):
                rows = self.api("worker", "GET", "/materials", **{"X-Company-Id": "2", "X-Company-Mode": "company"})
                self.assertEqual([row["id"] for row in rows], [self.stock_id])
                self.assertEqual(rows[0]["companyId"], 2)
                self.assertEqual(rows[0]["workPackage"], self.f["workPackage"])
                self.assertEqual(rows[0]["quantity"], expected_quantity)
                self.assertEqual(rows[0]["price"], 0)
                self.assertEqual(rows[0]["minQuantity"], 0)
        self.assertEqual(self.snapshot(), before)

    def seed_aliased_warehouse_unit_mismatch(self):
        flag = patch.dict(os.environ, {"COMPANY_MATERIAL_ALIASES_ENABLED": "1"})
        flag.start()
        self.addCleanup(flag.stop)
        alias_name = "TONNE-label " + self.f["materialName"]
        self.api("director", "POST", "/company-material-aliases", {
            "companyId": 2, "projectId": self.f["projectId"],
            "aliasName": alias_name, "canonicalName": self.f["materialName"],
            "canonicalUnit": "кг", "expectedAliasId": None,
        }, expected=201)
        self.sql("UPDATE materials SET unit='кг' WHERE id=%s", (self.stock_id,))
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                # The alias is a name mapping, never evidence that one tonne
                # and one kilogram are interchangeable quantities.
                typed_key = self.main._material_control_key_resolved(
                    cur, self.f["project"], alias_name, "т", company_id=2)
                stock_key = self.main._material_control_key_resolved(
                    cur, self.f["project"], self.f["materialName"], "кг", company_id=2)
                self.assertEqual(typed_key, stock_key)
        finally:
            conn.close()
        return alias_name

    def consume_personal_stock_with_owned_alias(self):
        flag = patch.dict(os.environ, {"COMPANY_MATERIAL_ALIASES_ENABLED": "1"})
        flag.start()
        self.addCleanup(flag.stop)
        alias = self.api("director", "POST", "/company-material-aliases", {
            "companyId": 2, "projectId": self.f["projectId"],
            "aliasName": "Brand " + self.f["materialName"],
            "canonicalName": self.f["materialName"], "canonicalUnit": self.f["unit"],
            "expectedAliasId": None,
        }, expected=201)
        payload = self.consumption_payload(personal=1, warehouse=0)
        payload["materialsUsed"][0]["name"] = alias["aliasName"]
        self.api("worker", "POST", "/work-journal", payload)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=0, available=1))
        return alias

    def snapshot(self):
        tables = ("materials", "material_transfers", "warehouse_history", "work_journal",
                  "room_works", "brigade_contract_items", *self.new_tables)
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
                     for table in tables)

    def assert_rejected_unchanged(self, payload, status=400):
        before = self.snapshot()
        response = self.request("POST", "/work-journal", payload)
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.balance(), dict(issued=2, used=0, returned=0, available=2))

    def create_consumption(self, personal, warehouse, **overrides):
        payload = self.consumption_payload(personal, warehouse, **overrides)
        result = self.api("worker", "POST", "/work-journal", payload)
        self.assertEqual(self.sql("SELECT material_accounting_version FROM work_journal WHERE id=%s",
                                  (result["id"],)), [(2,)])
        self.assertEqual(self.stock_quantity(), 2 - warehouse)
        self.assertEqual(self.balance(), dict(issued=2, used=personal, returned=0, available=2-personal))
        expected_sources = [(source, amount) for source, amount in
                            (("personal", personal), ("warehouse", warehouse)) if amount]
        self.assertEqual(self.sql("""SELECT source,SUM(quantity) FROM work_material_entries
            WHERE company_id=2 AND journal_id=%s GROUP BY source ORDER BY source""", (result["id"],)),
                         expected_sources)
        stored = self.sql("SELECT materials_used FROM work_journal WHERE id=%s", (result["id"],))[0][0]
        material = (json.loads(stored) if isinstance(stored, str) else stored)[0]
        self.assertEqual(material["quantity"], personal + warehouse)
        self.assertEqual(material["personalQuantity"], personal)
        self.assertEqual(material["warehouseQuantity"], warehouse)
        if warehouse:
            self.assertEqual(material["warehouseMaterialId"], self.stock_id)
        return result, payload

    def test_signed_personal_consumption_does_not_debit_warehouse_again(self):
        self.create_consumption(personal=2, warehouse=0)

    def test_warehouse_only_consumption_preserves_personal_balance(self):
        self.create_consumption(personal=0, warehouse=2)

    def test_mixed_consumption_debits_exactly_the_explicit_sources(self):
        self.create_consumption(personal=1, warehouse=2)

    def test_insufficient_warehouse_rolls_back_personal_usage_and_journal(self):
        self.assert_rejected_unchanged(self.consumption_payload(personal=1, warehouse=3))

    def test_insufficient_personal_rolls_back_warehouse_usage_and_journal(self):
        self.assert_rejected_unchanged(self.consumption_payload(personal=3, warehouse=1))

    def test_request_replay_returns_same_journal_without_second_expense(self):
        journal, payload = self.create_consumption(personal=1, warehouse=1)
        before = self.snapshot()
        replay = self.api("worker", "POST", "/work-journal", payload)
        self.assertEqual(replay["id"], journal["id"])
        self.assertEqual(self.snapshot(), before)

    def test_reusing_request_id_with_different_body_is_conflict(self):
        _, payload = self.create_consumption(personal=1, warehouse=1)
        before = self.snapshot()
        payload["comment"] = "Different factual submission"
        self.api("worker", "POST", "/work-journal", payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_foreign_company_warehouse_id_is_not_a_source(self):
        payload = self.consumption_payload(personal=0, warehouse=1)
        payload["materialsUsed"][0]["warehouseMaterialId"] = self.foreign_stock_id
        self.assert_rejected_unchanged(payload, status=404)

    def test_missing_warehouse_id_cannot_choose_source_implicitly(self):
        payload = self.consumption_payload(personal=0, warehouse=1)
        del payload["materialsUsed"][0]["warehouseMaterialId"]
        self.assert_rejected_unchanged(payload)

    def test_source_quantities_must_add_up_to_factual_total(self):
        payload = self.consumption_payload(personal=1, warehouse=1)
        payload["materialsUsed"][0]["quantity"] = 1
        self.assert_rejected_unchanged(payload)

    def test_source_quantity_must_not_be_silently_rounded(self):
        payload = self.consumption_payload(personal=0, warehouse=1)
        payload["materialsUsed"][0].update(quantity=0.0000001, warehouseQuantity=0.0000001)
        self.assert_rejected_unchanged(payload)

    def test_alias_deactivation_cannot_restore_personal_stock_for_another_work(self):
        alias = self.consume_personal_stock_with_owned_alias()
        self.api("director", "DELETE", "/company-material-aliases/"+alias["id"]+"?companyId=2")
        before = self.snapshot()
        payload = self.consumption_payload(personal=2, warehouse=0, roomName="Another room")
        self.api("worker", "POST", "/work-journal", payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_alias_replacement_cannot_restore_returnable_stock_when_accounting_is_disabled(self):
        alias = self.consume_personal_stock_with_owned_alias()
        self.api("director", "POST", "/company-material-aliases", {
            "companyId": 2, "projectId": self.f["projectId"],
            "aliasName": alias["aliasName"], "canonicalName": "Different material",
            "canonicalUnit": self.f["unit"], "expectedAliasId": alias["id"],
        }, expected=201)
        before = self.snapshot()
        with patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": "0"}):
            self.api("worker", "POST", "/material-transfers/return", self.payload(2), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_changing_issued_source_alias_cannot_hide_consumption_under_unchanged_brand(self):
        alias = self.consume_personal_stock_with_owned_alias()
        self.api("director", "POST", "/company-material-aliases", {
            "companyId": 2, "projectId": self.f["projectId"],
            "aliasName": self.f["materialName"], "canonicalName": "Different issued material",
            "canonicalUnit": self.f["unit"], "expectedAliasId": None,
        }, expected=201)
        brand = self.sql("""SELECT canonical_name,active FROM company_material_aliases
            WHERE company_id=2 AND alias_name=%s""", (alias["aliasName"],))
        self.assertEqual(brand, [(self.f["materialName"], True)],
                         "The journal's Brand alias stays unchanged; only the issued source identity moved")
        before = self.snapshot()
        self.api("worker", "POST", "/material-transfers/return", self.payload(2), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_contract_item_with_factual_material_usage_cannot_be_deleted(self):
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        before = self.snapshot()
        self.api("director", "DELETE", "/brigade-contract-items/"+str(self.contract_item), expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("""SELECT i.id FROM work_journal w
            JOIN brigade_contract_items i ON i.id=w.contract_item_id WHERE w.id=%s""", (journal["id"],)),
                         [(self.contract_item,)])

    def test_owned_alias_cannot_hide_warehouse_and_requested_unit_mismatch(self):
        alias_name = self.seed_aliased_warehouse_unit_mismatch()
        payload = self.consumption_payload(personal=0, warehouse=1)
        payload["materialsUsed"][0].update(name=alias_name, unit="т")
        self.assert_rejected_unchanged(payload, status=409)

    def test_malformed_v2_material_edit_releases_transaction_and_stock_locks(self):
        journal, payload = self.create_consumption(personal=1, warehouse=1)
        before = self.snapshot()
        baseline_pids = [row[0] for row in self.sql("""SELECT pid FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()""")]

        def close_leaked_test_connections():
            self.sql("""SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                  AND NOT (pid=ANY(%s::int[]))""", (baseline_pids,))

        self.addCleanup(close_leaked_test_connections)
        material = {**payload["materialsUsed"][0], "name": 123}
        path = "/work-journal/" + str(journal["id"])
        response = self.request("PUT", path, {"materialsUsed": [material]})
        self.assertIn(response.status_code, (400, 409, 500), response.text)
        # The original failure happened in .strip() before the inner try/finally.
        # Query activity before touching business tables so RED cannot deadlock.
        self.assertEqual(self.sql("""SELECT count(*) FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()
              AND NOT (pid=ANY(%s::int[]))""", (baseline_pids,)), [(0,)],
                         "Rejected material edits must not leave an open transaction")
        probe = self.main.get_db()
        probe.autocommit = False
        try:
            with probe.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE")
        finally:
            probe.rollback()
            probe.close()
        self.assertEqual(self.snapshot(), before)
        self.api("worker", "POST", "/material-transfers/return", self.payload(1))
        self.api("worker", "PUT", path, {"comment": "Valid correction after rejected edit"})
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=1, available=0))
        self.assertEqual(self.stock_quantity(), 2)

    def test_rejecting_work_preserves_factual_consumption(self):
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        history = self.sql("SELECT * FROM warehouse_history ORDER BY id")
        self.api("director", "PUT", "/work-journal/"+str(journal["id"]), {"status": "Отклонено"})
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=0, available=1))
        self.assertEqual(self.sql("SELECT * FROM warehouse_history ORDER BY id"), history)
        self.api("worker", "POST", "/material-transfers/return", self.payload(2), expected=400)

    def test_deleting_work_preserves_factual_consumption(self):
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        history = self.sql("SELECT * FROM warehouse_history ORDER BY id")
        self.api("director", "DELETE", "/work-journal/"+str(journal["id"]))
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=0, available=1))
        self.assertEqual(self.sql("SELECT * FROM warehouse_history ORDER BY id"), history)
        self.api("worker", "POST", "/material-transfers/return", self.payload(2), expected=400)

    def test_partial_acceptance_does_not_scale_or_restore_consumed_materials(self):
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        before = self.sql("SELECT materials_used FROM work_journal WHERE id=%s", (journal["id"],))
        history = self.sql("SELECT * FROM warehouse_history ORDER BY id")
        self.api("director", "PUT", "/work-journal/"+str(journal["id"]),
                 {"status": "Подтверждено", "quantity": 0.5})
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=0, available=1))
        self.assertEqual(self.sql("SELECT materials_used FROM work_journal WHERE id=%s", (journal["id"],)), before)
        self.assertEqual(self.sql("SELECT * FROM warehouse_history ORDER BY id"), history)


if __name__ == "__main__":
    unittest.main()
