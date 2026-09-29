"""Independent request identity, concurrency and membership boundary regressions."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest
from uuid import uuid4

from .test_support import CompanyWarehousesPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class CompanyWarehouseReviewPostgresTests(CompanyWarehousesPostgresSupport, unittest.TestCase):
    def wait_for_lock(self, prefix, futures, count=1):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            waiting = self.sql("""SELECT count(*) FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                AND wait_event_type='Lock' AND query LIKE %s""", (prefix + "%",))[0][0]
            if waiting >= count or any(future.done() for future in futures):
                return waiting
            time.sleep(0.02)
        return 0

    def test_invalid_card_ids_never_create_or_expose_directory_rows(self):
        before = self.snapshot()
        for warehouse_id in (0, -1, 2147483648):
            for method in ("GET", "POST"):
                with self.subTest(warehouse_id=warehouse_id, method=method):
                    payload = {"action": "create", "requestId": str(uuid4()), **self.warehouse_payload()} if method == "POST" else None
                    self.api("director", method, f"/warehouses/{warehouse_id}/directory", payload, expected=400)
                    self.assertEqual(self.snapshot(), before)

    def test_two_concurrent_updates_cannot_overwrite_the_same_version(self):
        self.create_card()
        first_payload = self.update_payload(notes="First committed edit")
        second_payload = self.update_payload(notes="Competing stale edit")
        self.sql("""CREATE FUNCTION company_directory_review_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(913153,1); RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER company_directory_review_pause BEFORE INSERT ON warehouse_directory_events
            FOR EACH ROW EXECUTE FUNCTION company_directory_review_pause()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(913153,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", self.path, first_payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("INSERT INTO warehouse_directory_events", [first]), 1)
                    second = pool.submit(self.request, "POST", self.path, second_payload, "director")
                    self.assertEqual(self.wait_for_lock("SELECT pg_advisory_xact_lock(178991,", [second]), 1)
                finally:
                    blocker.rollback()
                first_result, second_result = first.result(timeout=20), second.result(timeout=20)
        finally:
            blocker.close()
            self.sql("DROP TRIGGER company_directory_review_pause ON warehouse_directory_events")
            self.sql("DROP FUNCTION company_directory_review_pause()")
        self.assertEqual(first_result.status_code, 200, first_result.text)
        self.assertEqual(second_result.status_code, 409, second_result.text)
        card = self.detail()["warehouse"]
        self.assertEqual((card["version"], card["notes"]), (2, "First committed edit"))
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_directory_events WHERE warehouse_id=%s",
                                  (self.warehouse_id,)), [(2,)])

    def test_concurrent_same_uuid_create_returns_one_card_and_event(self):
        payload = {"action": "create", "requestId": str(uuid4()), **self.warehouse_payload()}
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(178991,2)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = [pool.submit(self.request, "POST", "/warehouses/directory", payload, "director") for _ in range(2)]
                try:
                    self.assertEqual(self.wait_for_lock("SELECT pg_advisory_xact_lock(178991,", pending, count=2), 2)
                finally:
                    blocker.rollback()
                responses = [future.result(timeout=20) for future in pending]
        finally:
            blocker.close()
        for response in responses:
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(self.sql("SELECT count(*) FROM warehouses WHERE company_id=2"), [(1,)])
        self.assertEqual(self.sql("SELECT count(*) FROM warehouse_directory_events"), [(1,)])
        self.assertEqual(self.sql("SELECT count(*) FROM work_material_operations WHERE kind='company-warehouse'"), [(1,)])

    def test_membership_revoked_while_read_or_update_waits_blocks_access_without_mutation(self):
        self.create_card()
        director_id = self.f["users"]["director"]["id"]
        restore = "UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2"
        self.addCleanup(self.sql, restore, (director_id,))
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                payload = self.update_payload(notes="Protected edit") if method == "POST" else None
                before = self.snapshot()
                blocker = self.main.get_db()
                blocker.autocommit = False
                try:
                    with blocker.cursor() as cur:
                        cur.execute("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (director_id,))
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(self.request, method, self.path, payload, "director")
                        try:
                            self.assertEqual(self.wait_for_lock("SELECT role,assigned_projects,assigned_packages FROM user_company_roles", [pending]), 1)
                            blocker.commit()
                        finally:
                            blocker.rollback()
                        response = pending.result(timeout=20)
                finally:
                    blocker.close()
                self.assertEqual(response.status_code, 403, response.text)
                self.assertEqual(self.snapshot(), before)
                self.sql(restore, (director_id,))
                self.api("director", method, self.path, payload)

    def test_revoked_membership_cannot_replay_a_successful_create(self):
        _, payload = self.create_card()
        director_id = self.f["users"]["director"]["id"]
        self.addCleanup(self.sql, "UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2", (director_id,))
        before = self.snapshot()
        self.sql("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (director_id,))
        self.api("director", "POST", "/warehouses/directory", payload, expected=403)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
