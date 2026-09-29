"""Real tool lifecycle, history atomicity and access on disposable PostgreSQL."""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.tool_custody.test_support import ToolCustodyPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class ToolCustodyPostgresTests(ToolCustodyPostgresSupport, unittest.TestCase):
    def issue_payload(self, **changes):
        return self.tool_command_payload("issue", **{
            "recipientId": self.f["users"]["worker"]["id"], "projectId": self.f["projectId"],
            "contractId": self.contract_id, **changes,
        })

    def assert_holder(self, status, recipient_id=None):
        row = self.sql("SELECT status,master_id,master_name FROM tools WHERE id=%s", (self.tool_id,))[0]
        self.assertEqual(row[0], status)
        self.assertEqual(row[1], recipient_id)
        if recipient_id is None:
            self.assertFalse(row[2])

    def test_issue_updates_exact_holder_and_history_in_one_operation(self):
        result = self.issue_tool(actor="foreman")
        self.assert_holder("У мастера", self.f["users"]["worker"]["id"])
        view = self.custody_view()
        self.assertEqual(view["tool"]["companyId"], 2)
        self.assertEqual(view["tool"]["projectId"], self.f["projectId"])
        self.assertEqual(view["tool"]["contractId"], self.contract_id)
        self.assertEqual(len(view["history"]), 1)
        self.assertEqual(view["history"][0]["id"], result["eventId"])
        self.assertEqual(view["incidents"], [])

    def test_physical_issue_without_contract_is_allowed_without_financial_attribution(self):
        self.issue_tool(contractId=None)
        self.assert_holder("У мастера", self.f["users"]["worker"]["id"])
        self.assertIsNone(self.custody_view()["tool"]["contractId"])

    def test_employment_contract_cannot_be_used_as_contractor_responsibility_basis(self):
        self.sql("UPDATE brigade_contracts SET contractor_type='Трудовой договор' WHERE id=%s", (self.contract_id,))
        self.assert_rejected_unchanged("director", "POST", self.custody_path, self.issue_payload(), expected=409)
        self.issue_tool(contractId=None)
        self.assert_holder("У мастера", self.f["users"]["worker"]["id"])

    def test_issue_rolls_back_holder_when_history_write_fails_and_next_issue_succeeds(self):
        payload = self.issue_payload()
        self.sql("""CREATE FUNCTION reject_synthetic_custody_event() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic history write failure'; END $$""")
        self.sql("""CREATE TRIGGER reject_synthetic_custody_event BEFORE INSERT ON tool_custody_events
            FOR EACH ROW EXECUTE FUNCTION reject_synthetic_custody_event()""")
        try:
            before = self.snapshot()
            response = self.request("POST", self.custody_path, payload, actor="director")
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(self.snapshot(), before)
            self.assert_holder("На складе")
        finally:
            self.sql("DROP TRIGGER reject_synthetic_custody_event ON tool_custody_events")
            self.sql("DROP FUNCTION reject_synthetic_custody_event()")
        self.api("director", "POST", self.custody_path, payload)
        self.assert_holder("У мастера", self.f["users"]["worker"]["id"])

    def test_good_return_clears_exact_holder_and_keeps_both_events(self):
        self.issue_tool()
        result = self.tool_command("return", condition="good")
        self.assert_holder("На складе")
        self.assertFalse(result.get("incidentId"))
        view = self.custody_view()
        self.assertEqual(len(view["history"]), 2)
        self.assertEqual(view["incidents"], [])

    def test_lost_return_is_lost_not_repair_and_has_no_automatic_penalty(self):
        self.issue_tool()
        result = self.tool_command("return", condition="lost", reason="Утерян при перевозке")
        self.assert_holder("Утерян")
        self.assertTrue(result["incidentId"])
        incident = self.custody_view()["incidents"][0]
        self.assertEqual(incident["id"], result["incidentId"])
        self.assertEqual(incident["status"], "pending")
        self.assertEqual(float(incident.get("amount") or 0), 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tool_incident_decisions"), [(0,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tool_fine_allocations"), [(0,)])

    def test_damaged_return_and_completed_repair_are_separate_events(self):
        self.issue_tool()
        self.tool_command("return", condition="damaged", reason="Повреждён редуктор")
        self.assert_holder("На ремонте")
        self.tool_command("repair", reason="Редуктор заменён, инструмент проверен")
        self.assert_holder("На складе")
        self.assertEqual(len(self.custody_view()["history"]), 3)

    def test_lost_tool_can_only_reenter_stock_through_recovery(self):
        self.issue_tool()
        self.tool_command("return", condition="lost", reason="Не найден при возврате")
        self.assert_rejected_unchanged("director", "POST", self.custody_path, self.issue_payload())
        self.tool_command("recover", condition="good", reason="Обнаружен на объекте")
        self.assert_holder("На складе")
        self.assertEqual(len(self.custody_view()["history"]), 3)

    def test_same_uuid_replays_once_and_changed_body_or_old_state_conflicts(self):
        payload = self.issue_payload()
        result = self.api("director", "POST", self.custody_path, payload)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.custody_path, payload), result)
        self.assertEqual(self.snapshot(), before)
        for changed in ({**payload, "recipientId": self.f["users"]["other_worker"]["id"]},
                        {**payload, "requestId": str(uuid4())}):
            self.assert_rejected_unchanged("director", "POST", self.custody_path, changed)

    def test_damaged_or_lost_return_requires_reason_without_changing_custody(self):
        self.issue_tool()
        for condition in ("damaged", "lost"):
            with self.subTest(condition=condition):
                self.assert_rejected_unchanged("director", "POST", self.custody_path,
                    self.tool_command_payload("return", condition=condition, reason=""), expected=400)

    def test_foreign_company_cannot_read_or_move_tool_and_worker_cannot_issue(self):
        payload = self.issue_payload()
        self.assert_rejected_unchanged("stranger", "GET", self.custody_path, expected=404)
        self.assert_rejected_unchanged("stranger", "POST", self.custody_path, payload, expected=404)
        self.assert_rejected_unchanged("worker", "POST", self.custody_path, payload, expected=403)
        self.assert_rejected_unchanged("accountant", "POST", self.custody_path, payload, expected=403)

    def test_recipient_must_be_the_exact_contract_party_not_a_namesake(self):
        worker = self.f["users"]["worker"]
        other = self.f["users"]["other_worker"]
        self.sql("UPDATE users SET name=%s WHERE id=%s", (worker["name"], other["id"]))
        self.addCleanup(self.sql, "UPDATE users SET name=%s WHERE id=%s", (other["name"], other["id"]))
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                      self.issue_payload(recipientId=other["id"]), expected=409)
        self.issue_tool()
        self.assert_holder("У мастера", worker["id"])
        self.assert_rejected_unchanged("other_worker", "GET", self.custody_path, expected=404)
        self.assertEqual(self.api("other_worker", "GET", "/tool-history"), [])

    def test_recipient_foreign_company_and_wrong_contract_project_are_rejected(self):
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
            self.issue_payload(recipientId=self.f["users"]["stranger"]["id"]), expected=404)
        project_id = self.sql("INSERT INTO projects(name,company_id) VALUES('Synthetic other tool object',2) RETURNING id")[0][0]
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                      self.issue_payload(projectId=project_id), expected=409)

    def test_inactive_recipient_membership_prevents_issue(self):
        worker_id = self.f["users"]["worker"]["id"]
        self.sql("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (worker_id,))
        self.addCleanup(self.sql, "UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2", (worker_id,))
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                      self.issue_payload(), expected=404)

    def test_managed_tool_cannot_bypass_movement_or_history_when_flag_is_off(self):
        self.issue_tool()
        forged_history = {"toolId": self.tool_id, "toolName": self.tool_card["name"], "action": "Возврат",
                          "masterName": self.f["users"]["worker"]["name"], "project": self.f["project"]}
        for flag in ("1", "0"):
            with patch.dict(os.environ, {"TOOL_CUSTODY_ENABLED": flag}):
                for method, path, payload in (("PUT", self.tool_path, self.tool_card),
                                              ("DELETE", self.tool_path, None),
                                              ("POST", "/tool-history", forged_history)):
                    with self.subTest(flag=flag, method=method):
                        self.assert_rejected_unchanged("director", method, path, payload)

    def test_legacy_name_only_holder_is_not_claimed_by_matching_worker(self):
        self.sql("UPDATE tools SET status='У мастера',master_id=NULL,master_name=%s WHERE id=%s",
                 (self.f["users"]["worker"]["name"], self.tool_id))
        self.assert_rejected_unchanged("worker", "GET", self.custody_path, expected=404)
        self.assertEqual(self.api("worker", "GET", "/tools"), [])
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
            self.tool_command_payload("return", condition="good"), expected=409)


if __name__ == "__main__":
    unittest.main()
