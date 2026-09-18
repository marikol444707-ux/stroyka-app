"""The estimate submission path must post and replay the same v2 ledger.

Real authenticated HTTP, real company memberships and stock transactions, and
the complete 0027 migration in a fresh guarded Unix-socket PostgreSQL database.
"""
import json
import os
import unittest
from uuid import uuid4

from backend.features.material_traceability import test_estimate_consumption_postgres as estimate_support
from backend.features.work_material_accounting import test_postgres as accounting_support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class EstimateMaterialAccountingPostgresTests(unittest.TestCase):
    sql = accounting_support.WorkMaterialAccountingPostgresTests.sql
    api = accounting_support.WorkMaterialAccountingPostgresTests.api
    payload = accounting_support.WorkMaterialAccountingPostgresTests.payload
    balance = accounting_support.WorkMaterialAccountingPostgresTests.balance
    request = accounting_support.WorkMaterialAccountingPostgresTests.request
    stock_quantity = accounting_support.WorkMaterialAccountingPostgresTests.stock_quantity
    seed_aliased_warehouse_unit_mismatch = accounting_support.WorkMaterialAccountingPostgresTests.seed_aliased_warehouse_unit_mismatch
    estimate_payload = estimate_support.EstimateConsumptionPostgresTests.estimate_payload
    race_work_with_return = estimate_support.EstimateConsumptionPostgresTests.race_work_with_return

    @classmethod
    def setUpClass(cls):
        accounting_support.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        from psycopg2 import sql
        if self.new_tables:
            self.sql(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(map(sql.Identifier, self.new_tables))))
        estimate_support.EstimateConsumptionPostgresTests.setUp(self)
        self.sql("UPDATE materials SET quantity=2 WHERE company_id=2")
        self.stock_id = self.sql("SELECT id FROM materials WHERE company_id=2")[0][0]

    def v2_payload(self, personal=1, warehouse=1):
        payload = self.estimate_payload(personal + warehouse)
        payload.update(materialAccountingVersion=2, requestId=str(uuid4()))
        material = payload["_workJournalMaterials"][self.work_key][0]
        material.update(personalQuantity=personal, warehouseQuantity=warehouse)
        if warehouse:
            material["warehouseMaterialId"] = self.stock_id
        return payload

    def snapshot(self):
        tables = ("estimates", "estimate_versions", "materials", "material_transfers",
                  "warehouse_history", "work_journal", "room_works", "brigade_contract_items",
                  *self.new_tables)
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
                     for table in tables)

    def assert_consumption(self, personal, warehouse):
        self.assertEqual(self.sql("""SELECT company_id,estimate_id,master_id,material_accounting_version
            FROM work_journal"""), [(2, self.f["estimateId"], self.f["users"]["worker"]["id"], 2)])
        self.assertEqual(self.stock_quantity(), 2 - warehouse)
        self.assertEqual(self.balance(), dict(issued=2, used=personal, returned=0, available=2-personal))
        self.assertEqual(self.sql("SELECT source,SUM(quantity) FROM work_material_entries GROUP BY source ORDER BY source"),
                         [(source, quantity) for source, quantity in
                          (("personal", personal), ("warehouse", warehouse)) if quantity])
        stored = self.sql("SELECT materials_used FROM work_journal")[0][0]
        materials = json.loads(stored) if isinstance(stored, str) else stored
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["quantity"], personal + warehouse)
        self.assertEqual(materials[0]["personalQuantity"], personal)
        self.assertEqual(materials[0]["warehouseQuantity"], warehouse)
        if warehouse:
            self.assertEqual(materials[0]["warehouseMaterialId"], self.stock_id)

    def test_mixed_estimate_work_posts_exact_sources_and_v2_journal(self):
        result = self.api("worker", "PUT", self.path, self.v2_payload(1, 2))
        self.assertEqual(result["journalEntries"], 1)
        self.assert_consumption(personal=1, warehouse=2)

    def test_estimate_request_replay_returns_original_result_without_more_entries(self):
        payload = self.v2_payload()
        original = self.api("worker", "PUT", self.path, payload)
        before = self.snapshot()
        replay = self.api("worker", "PUT", self.path, payload)
        self.assertEqual(replay, original)
        self.assertEqual(self.snapshot(), before)
        self.assert_consumption(personal=1, warehouse=1)

    def test_estimate_request_id_with_changed_body_is_conflict(self):
        payload = self.v2_payload()
        self.api("worker", "PUT", self.path, payload)
        before = self.snapshot()
        payload["_workJournalParams"][self.work_key]["comment"] = "Different factual submission"
        self.api("worker", "PUT", self.path, payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_source_rows_within_balance_are_aggregated(self):
        payload = self.v2_payload(0.5, 0.5)
        payload["_workJournalMaterials"][self.work_key] *= 2
        self.api("worker", "PUT", self.path, payload)
        self.assert_consumption(personal=1, warehouse=1)

    def test_duplicate_source_rows_cannot_exceed_either_available_source(self):
        for personal, warehouse in ((1, 0.5), (0.5, 1)):
            with self.subTest(personal=personal, warehouse=warehouse):
                payload = self.v2_payload(personal, warehouse)
                payload["_workJournalMaterials"][self.work_key] *= 3
                before = self.snapshot()
                self.api("worker", "PUT", self.path, payload, expected=400)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.balance(), dict(issued=2, used=0, returned=0, available=2))

    def test_selected_material_value_must_be_a_list_not_silently_discarded(self):
        payload = self.v2_payload()
        payload["_workJournalMaterials"][self.work_key] = payload["_workJournalMaterials"][self.work_key][0]
        before = self.snapshot()
        self.api("worker", "PUT", self.path, payload, expected=400)
        self.assertEqual(self.snapshot(), before)

    def test_blank_material_name_cannot_create_work_without_its_requested_expense(self):
        payload = self.v2_payload()
        payload["_workJournalMaterials"][self.work_key][0]["name"] = "   "
        before = self.snapshot()
        self.api("worker", "PUT", self.path, payload, expected=400)
        self.assertEqual(self.snapshot(), before)

    def test_owned_alias_cannot_hide_estimate_material_unit_mismatch(self):
        alias_name = self.seed_aliased_warehouse_unit_mismatch()
        payload = self.v2_payload(personal=0, warehouse=1)
        payload["_workJournalMaterials"][self.work_key][0].update(name=alias_name, unit="т")
        before = self.snapshot()
        self.api("worker", "PUT", self.path, payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_mixed_estimate_work_and_personal_return_cannot_spend_same_material(self):
        # The real BEFORE INSERT history trigger pauses the first personal
        # expense after warehouse UPDATE. The competing return must wait on
        # the shared stock lock, then observe the committed personal expense.
        self.race_work_with_return("PUT", self.path, self.v2_payload(2, 2))
        self.assert_consumption(personal=2, warehouse=2)

    def test_revoked_membership_cannot_replay_a_previously_valid_estimate_submission(self):
        payload = self.v2_payload()
        self.api("worker", "PUT", self.path, payload)
        worker_id = self.f["users"]["worker"]["id"]
        self.sql("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (worker_id,))
        self.addCleanup(self.sql,
                        "UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2", (worker_id,))
        before = self.snapshot()
        self.api("worker", "PUT", self.path, payload, expected=403)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
