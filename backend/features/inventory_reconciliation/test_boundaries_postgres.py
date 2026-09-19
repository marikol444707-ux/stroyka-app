"""Concurrent approvals, authorization pinning and immutable inventory evidence."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest
from uuid import uuid4

from .test_support import InventoryReconciliationPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class InventoryReconciliationBoundaryPostgresTests(InventoryReconciliationPostgresSupport, unittest.TestCase):
    def prepare_approval(self):
        self.create_inventory()
        self.count_and_submit("1")
        return self.command_payload("approve", reason="Verified by director")

    def wait_for_lock(self, prefix, future):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            waiting = self.sql("""SELECT COUNT(*) FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                AND wait_event_type='Lock' AND query LIKE %s""", (prefix + "%",))[0][0]
            if waiting or future.done():
                return waiting
            time.sleep(0.02)
        return 0

    def test_two_concurrent_approvals_create_only_one_adjustment_and_one_decision(self):
        first_payload = self.prepare_approval()
        second_payload = {**first_payload, "requestId": str(uuid4())}
        history_before = self.sql("SELECT COUNT(*) FROM warehouse_history")[0][0]
        self.sql("""CREATE FUNCTION pause_inventory_approval() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.action='approve' THEN PERFORM pg_advisory_xact_lock(914251,1); END IF;
            RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER pause_inventory_approval BEFORE INSERT ON inventory_reconciliation_events
            FOR EACH ROW EXECUTE FUNCTION pause_inventory_approval()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914251,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", self.path, first_payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("INSERT INTO inventory_reconciliation_events", first), 1,
                                     "First approval must pause inside its real decision transaction")
                    second = pool.submit(self.request, "POST", self.path, second_payload, "director")
                    self.assertEqual(self.wait_for_lock("LOCK TABLE materials, warehouse_main, projects", second), 1,
                                     "Second approval must wait on the shared stock lock")
                finally:
                    blocker.rollback()
                first_response, second_response = first.result(timeout=20), second.result(timeout=20)
        finally:
            blocker.close()
            self.sql("DROP TRIGGER pause_inventory_approval ON inventory_reconciliation_events")
            self.sql("DROP FUNCTION pause_inventory_approval()")
        self.assertEqual(first_response.status_code, 200, first_response.text)
        self.assertEqual(second_response.status_code, 409, second_response.text)
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM inventory_stock_adjustments"), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM inventory_reconciliation_events WHERE action='approve'"), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_history"), [(history_before + 1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM warehouse_movements"), [(1,)])
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.path, first_payload), first_response.json())
        self.assertEqual(self.snapshot(), before)

    def test_membership_revocation_winning_the_pin_rejects_pending_approval(self):
        payload = self.prepare_approval()
        director_id = self.f["users"]["director"]["id"]
        restore = "UPDATE user_company_roles SET active=TRUE WHERE company_id=2 AND user_id=%s"
        self.addCleanup(self.sql, restore, (director_id,))
        before = self.snapshot()
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s", (director_id,))
                cur.execute("LOCK TABLE materials IN ACCESS EXCLUSIVE MODE")
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.request, "POST", self.path, payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("SELECT role,assigned_projects,assigned_packages FROM user_company_roles", pending),
                                     1, "Actor must be revalidated before reaching the stock lock")
                    blocker.commit()
                finally:
                    blocker.rollback()
                response = pending.result(timeout=20)
        finally:
            blocker.close()
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("SELECT state FROM inventory_reconciliations"), [("submitted",)])
        self.sql(restore, (director_id,))
        self.api("director", "POST", self.path, payload)
        self.assertEqual(self.stock_quantity(), 1)

    def test_membership_is_pinned_until_an_approval_waiting_for_stock_has_finished(self):
        payload = self.prepare_approval()
        director_id = self.f["users"]["director"]["id"]
        restore = "UPDATE user_company_roles SET active=TRUE WHERE company_id=2 AND user_id=%s"
        self.addCleanup(self.sql, restore, (director_id,))
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("LOCK TABLE materials IN ACCESS EXCLUSIVE MODE")
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(self.request, "POST", self.path, payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("LOCK TABLE materials, warehouse_main, projects", pending), 1)
                    revocation = pool.submit(self.sql,
                        "UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s", (director_id,))
                    self.assertEqual(self.wait_for_lock("UPDATE user_company_roles SET active=FALSE", revocation), 1,
                                     "A committed revocation cannot overtake an already pinned stock operation")
                finally:
                    blocker.rollback()
                response = pending.result(timeout=20)
                revocation.result(timeout=20)
        finally:
            blocker.close()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.stock_quantity(), 1)
        self.assertEqual(self.sql("SELECT state FROM inventory_reconciliations"), [("approved",)])
        self.assertEqual(self.sql("SELECT active FROM user_company_roles WHERE company_id=2 AND user_id=%s", (director_id,)), [(False,)])
        before = self.snapshot()
        denied = self.request("POST", self.path, payload, actor="director")
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertEqual(self.snapshot(), before)

    def assert_database_rejects_change(self, statement, params):
        import psycopg2
        before = self.snapshot()
        with self.assertRaises(psycopg2.Error) as caught:
            self.sql(statement, params)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(caught.exception.pgcode, "P0001",
            "The immutable guard must reject this, not an unrelated SQL error: " + str(caught.exception))

    def test_approved_session_events_and_adjustments_are_database_immutable(self):
        payload = self.prepare_approval()
        result = self.api("director", "POST", self.path, payload)
        adjustment_id = self.sql("SELECT id FROM inventory_stock_adjustments")[0][0]
        commands = [
            ("UPDATE inventory_reconciliation_events SET reason='Rewritten evidence' WHERE id=%s", result["eventId"]),
            ("DELETE FROM inventory_reconciliation_events WHERE id=%s", result["eventId"]),
            ("UPDATE inventory_stock_adjustments SET after_quantity=0 WHERE id=%s", adjustment_id),
            ("DELETE FROM inventory_stock_adjustments WHERE id=%s", adjustment_id),
            ("UPDATE inventory_reconciliations SET counts='{}'::jsonb,version=version+1 WHERE inventory_id=%s", self.inventory_id),
            ("UPDATE inventory_reconciliations SET state='draft',version=version+1 WHERE inventory_id=%s", self.inventory_id),
            ("DELETE FROM inventory_reconciliations WHERE inventory_id=%s", self.inventory_id),
        ]
        for statement, key in commands:
            with self.subTest(statement=statement):
                self.assert_database_rejects_change(statement, (key,))

    def test_adjustment_linked_stock_history_and_movement_cannot_be_rewritten_or_deleted(self):
        payload = self.prepare_approval()
        self.api("director", "POST", self.path, payload)
        history_id, movement_id = self.sql("SELECT history_id,movement_id FROM inventory_stock_adjustments")[0]
        for table, key in (("warehouse_history", history_id), ("warehouse_movements", movement_id)):
            for statement in (f"UPDATE {table} SET quantity=999 WHERE id=%s", f"DELETE FROM {table} WHERE id=%s"):
                with self.subTest(statement=statement):
                    self.assert_database_rejects_change(statement, (key,))
        before = self.snapshot()
        self.api("director", "DELETE", f"/warehouse-history/{history_id}", expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_stale_actor_or_company_pin_rejects_create_and_approval_without_operations(self):
        payload = self.prepare_approval()
        for context in ({"expectedCompanyId": 3}, {"expectedActorId": self.f["users"]["foreman"]["id"]}):
            with self.subTest(context=context):
                self.unchanged_command({**payload, **context})
                before = self.snapshot()
                self.api("director", "POST", "/inventory/reconciliation", {
                    "requestId": str(uuid4()), "projectId": self.f["projectId"], **context}, expected=409)
                self.assertEqual(self.snapshot(), before)
        valid = {**payload, "expectedCompanyId": 2, "expectedActorId": self.f["users"]["director"]["id"]}
        self.api("director", "POST", self.path, valid)
        self.assertEqual(self.stock_quantity(), 1)


if __name__ == "__main__":
    unittest.main()
