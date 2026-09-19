"""Concurrent custody, membership, request-context and former-holder boundaries."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest
from uuid import uuid4

from backend.features.tool_custody.test_support import ToolCustodyPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class ToolCustodyBoundaryPostgresTests(ToolCustodyPostgresSupport, unittest.TestCase):
    def issue_payload(self, **changes):
        return self.tool_command_payload("issue", **{
            "recipientId": self.f["users"]["worker"]["id"], "projectId": self.f["projectId"],
            "contractId": self.contract_id, **changes,
        })

    def wait_for_lock(self, prefix, future, event="Lock"):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            waiting = self.sql("""SELECT count(*) FROM pg_stat_activity
                WHERE datname=current_database() AND pid<>pg_backend_pid()
                AND wait_event_type=%s AND query LIKE %s""", (event, prefix + "%"))[0][0]
            if waiting or future.done():
                return waiting
            time.sleep(0.02)
        return 0

    def test_concurrent_issues_allocate_one_holder_and_one_immutable_event(self):
        first_payload = self.issue_payload()
        second_payload = {**first_payload, "requestId": str(uuid4()),
                          "recipientId": self.f["users"]["other_worker"]["id"], "contractId": None}
        self.sql("""CREATE FUNCTION pause_synthetic_tool_issue() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914241,1); RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER pause_synthetic_tool_issue BEFORE INSERT ON tool_custody_events
            FOR EACH ROW EXECUTE FUNCTION pause_synthetic_tool_issue()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914241,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", self.custody_path, first_payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("INSERT INTO tool_custody_events", first), 1,
                                     "First issuance must pause after physical state update")
                    second = pool.submit(self.request, "POST", self.custody_path, second_payload, "director")
                    self.assertEqual(self.wait_for_lock("LOCK TABLE materials, warehouse_main, projects", second), 1,
                                     "Second issuance must wait for the first transaction")
                finally:
                    blocker.rollback()
                first_response, second_response = first.result(timeout=20), second.result(timeout=20)
        finally:
            blocker.close()
            self.sql("DROP TRIGGER pause_synthetic_tool_issue ON tool_custody_events")
            self.sql("DROP FUNCTION pause_synthetic_tool_issue()")
        self.assertEqual(first_response.status_code, 200, first_response.text)
        self.assertEqual(second_response.status_code, 409, second_response.text)
        self.assertEqual(self.sql("SELECT status,master_id,custody_version FROM tools WHERE id=%s", (self.tool_id,)),
                         [("У мастера", self.f["users"]["worker"]["id"], 1)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tool_custody_events WHERE tool_id=%s", (self.tool_id,)), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tool_history WHERE tool_id=%s", (self.tool_id,)), [(1,)])

    def test_recipient_revocation_committed_while_issue_waits_prevents_custody(self):
        payload = self.issue_payload()
        worker_id = self.f["users"]["worker"]["id"]
        restore = "UPDATE user_company_roles SET active=TRUE WHERE company_id=2 AND user_id=%s"
        self.addCleanup(self.sql, restore, (worker_id,))
        before = self.snapshot()
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s", (worker_id,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.request, "POST", self.custody_path, payload, "director")
                try:
                    self.assertEqual(self.wait_for_lock("SELECT role,assigned_projects,assigned_packages FROM user_company_roles", pending),
                                     1, "Issue must pin and revalidate the current recipient membership")
                    blocker.commit()
                finally:
                    blocker.rollback()
                response = pending.result(timeout=20)
        finally:
            blocker.close()
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.snapshot(), before)
        self.sql(restore, (worker_id,))
        self.api("director", "POST", self.custody_path, payload)

    def test_custody_command_rejects_stale_expected_company_or_actor_without_mutation(self):
        payload = self.issue_payload()
        for scope in ({"expectedCompanyId": 3}, {"expectedActorId": self.f["users"]["other_worker"]["id"]}):
            with self.subTest(scope=scope):
                self.assert_rejected_unchanged("director", "POST", self.custody_path, {**payload, **scope}, expected=409)

    def test_financial_decision_rejects_stale_expected_company_or_actor_without_mutation(self):
        self.issue_tool()
        incident = self.tool_command("return", condition="damaged", reason="Редуктор повреждён")
        path = f"{self.tool_path}/incidents/{incident['incidentId']}/decisions"
        payload = {"requestId": str(uuid4()), "decision": "confirmed", "reason": "Акт повреждения",
                   "amount": "125.00", "priceEvidence": "Счёт сервиса № TEST-1",
                   "contractEvidence": "Договор подряда, пункт об инструменте"}
        for scope in ({"expectedCompanyId": 3}, {"expectedActorId": self.f["users"]["other_worker"]["id"]}):
            with self.subTest(scope=scope):
                self.assert_rejected_unchanged("director", "POST", path, {**payload, **scope}, expected=409)

    def test_catalog_does_not_reveal_next_holder_to_former_holder_with_an_incident(self):
        self.issue_tool()
        self.tool_command("return", condition="damaged", reason="Редуктор повреждён")
        self.tool_command("repair", reason="После ремонта проверен")
        other = self.f["users"]["other_worker"]
        self.issue_tool(recipientId=other["id"], contractId=None)
        own_view = self.custody_view(actor="worker")
        self.assertNotIn("masterId", own_view["tool"])
        self.assertEqual(len(own_view["incidents"]), 1)
        rows = self.api("worker", "GET", "/tools")
        former_rows = [row for row in rows if row["id"] == self.tool_id]
        for row in former_rows:
            self.assertNotEqual(row.get("masterId"), other["id"], row)
        self.assertNotIn(other["name"], json.dumps(former_rows, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
