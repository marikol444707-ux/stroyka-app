"""Estimate-submitted work must conserve the same stock as direct journal work.

Uses authenticated HTTP and the guarded, disposable socket-only PostgreSQL
fixture. No authorization, estimate, stock, or personal-balance mocks.
"""
import json
import os
import unittest

from backend.features.material_traceability import test_work_consumption_postgres as support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class EstimateConsumptionPostgresTests(unittest.TestCase):
    sql = support.WorkConsumptionPostgresTests.sql
    api = support.WorkConsumptionPostgresTests.api
    payload = support.WorkConsumptionPostgresTests.payload
    balance = support.WorkConsumptionPostgresTests.balance
    request = support.WorkConsumptionPostgresTests.request
    race_work_with_return = support.WorkConsumptionPostgresTests.race_work_with_return

    @classmethod
    def setUpClass(cls):
        support.WorkConsumptionPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        # Restore the material-only plan before the shared fixture issues stock.
        # Every case then adds the same precisely assigned work line to that plan.
        f = self.fixture
        sections = [{"name": f["workPackage"], "items": [{
            "id": "chain-material-1", "name": f["materialName"],
            "type": "material", "itemType": "material", "unit": f["unit"],
            "quantity": 20, "price": 100, "priceMaterial": 100,
            "lineTotal": 2000, "workPackage": f["workPackage"],
        }]}]
        self.sql("UPDATE estimates SET sections_json=%s WHERE id=%s",
                 (json.dumps(sections), f["estimateId"]))
        support.WorkConsumptionPostgresTests.setUp(self)
        self.work_key = str(f["estimateId"]) + ":0:1"
        self.work_item = {
            "id": "chain-work-1", "estimateItemKey": self.work_key,
            "name": "Synthetic work", "type": "work", "itemType": "work",
            "unit": "шт", "quantity": 20, "priceWork": 10,
            "doneQuantity": 0, "workPackage": f["workPackage"],
        }
        sections[0]["items"].append(self.work_item)
        self.sql("UPDATE estimates SET sections_json=%s WHERE id=%s",
                 (json.dumps(sections), f["estimateId"]))
        self.sql("""UPDATE brigade_contract_items
                    SET estimate_section=%s,estimate_item_key=%s WHERE id=%s""",
                 (f["workPackage"], self.work_key, self.contract_item))
        self.path = "/estimates/" + str(f["estimateId"])

    def estimate_payload(self, quantity=2):
        return {
            "sections": [{"name": self.f["workPackage"], "items": [
                {**self.work_item, "doneQuantity": 1},
            ]}],
            "_workJournalParams": {self.work_key: {
                "contractItemId": self.contract_item,
                "estimateItemKey": self.work_key,
                "workPackage": self.f["workPackage"],
                "date": "2026-09-18", "roomName": "Synthetic room",
            }},
            "_workJournalMaterials": {self.work_key: [{
                "name": self.f["materialName"], "unit": self.f["unit"],
                "quantity": quantity,
            }]},
        }

    def assert_rejected_without_writes(self, payload):
        before = tuple(self.sql("SELECT * FROM " + table + " ORDER BY id")
                       for table in ("estimates", "estimate_versions", "work_journal",
                                     "warehouse_history", "materials", "material_transfers"))
        response = self.request("PUT", self.path, payload)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(tuple(self.sql("SELECT * FROM " + table + " ORDER BY id")
                               for table in ("estimates", "estimate_versions", "work_journal",
                                             "warehouse_history", "materials", "material_transfers")),
                         before)
        self.assertEqual(self.balance(), dict(issued=2, used=0, returned=0, available=2))

    def test_valid_estimate_work_consumes_signed_personal_stock_once(self):
        response = self.api("worker", "PUT", self.path, self.estimate_payload())
        self.assertEqual(response["journalEntries"], 1)
        self.assertEqual(self.balance(), dict(issued=2, used=2, returned=0, available=0))
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE company_id=2"), [(0,)])
        self.assertEqual(self.sql("SELECT company_id,estimate_id,master_id,status FROM work_journal"),
                         [(2, self.f["estimateId"], self.f["users"]["worker"]["id"], "На проверке")])
        response = self.api("worker", "PUT", self.path, self.estimate_payload())
        self.assertEqual(response["journalEntries"], 0)
        self.assertEqual(self.sql("SELECT count(*) FROM work_journal"), [(1,)])
        self.assertEqual(self.balance(), dict(issued=2, used=2, returned=0, available=0))

    def test_repeated_material_rows_cannot_overconsume_within_one_estimate_work(self):
        payload = self.estimate_payload()
        payload["_workJournalMaterials"][self.work_key] *= 2
        self.assert_rejected_without_writes(payload)

    def test_estimate_work_and_return_cannot_spend_the_same_personal_stock(self):
        self.race_work_with_return("PUT", self.path, self.estimate_payload())

    def test_nonfinite_estimate_work_material_is_rejected_without_silent_omission(self):
        self.assert_rejected_without_writes(self.estimate_payload("NaN"))

    def test_pre_journal_failure_rolls_back_and_releases_stock_for_next_operation(self):
        tables = ("estimates", "estimate_versions", "work_journal", "warehouse_history",
                  "materials", "material_transfers", "room_works", "brigade_contract_items")
        before = tuple(self.sql("SELECT * FROM " + table + " ORDER BY id") for table in tables)
        baseline_pids = [row[0] for row in self.sql("""SELECT pid FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()""")]

        def close_leaked_test_connections():
            # Keep a failing regression bounded: this fixture owns the entire
            # disposable database, and leaked transactions must not hang setUp.
            self.sql("""SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                  AND NOT (pid=ANY(%s::int[]))""", (baseline_pids,))

        self.addCleanup(close_leaked_test_connections)
        payload = self.estimate_payload()
        # A malformed comment currently fails with HTTP 500 at .strip(), after
        # estimate writes and the stock lock, before the inner journal try.
        payload["_workJournalParams"][self.work_key]["comment"] = {"invalid": "comment"}
        response = self.request("PUT", self.path, payload)
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(self.sql("""SELECT count(*) FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()
              AND NOT (pid=ANY(%s::int[]))""", (baseline_pids,)), [(0,)],
                         "A failed estimate must close its connection and release its transaction")

        # Bound the independent lock probe even if a future regression stops
        # reporting the leaked connection as idle in pg_stat_activity.
        probe = self.main.get_db()
        probe.autocommit = False
        try:
            with probe.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE")
        finally:
            probe.rollback()
            probe.close()
        self.assertEqual(tuple(self.sql("SELECT * FROM " + table + " ORDER BY id")
                               for table in tables), before)
        self.assertEqual(self.balance(), dict(issued=2, used=0, returned=0, available=2))

        self.api("worker", "POST", "/material-transfers/return", self.payload(1))
        completed = self.api("worker", "PUT", self.path, self.estimate_payload(1))
        self.assertEqual(completed["journalEntries"], 1)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=1, available=0))
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE company_id=2"), [(1,)])


if __name__ == "__main__":
    unittest.main()
