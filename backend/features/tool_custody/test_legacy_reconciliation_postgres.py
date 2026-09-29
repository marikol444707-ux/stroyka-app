"""Explicit, attributable reconciliation of unresolved legacy tool custody."""
import os
import unittest
from uuid import uuid4

from backend.features.tool_custody.test_support import ToolCustodyPostgresSupport


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class ToolLegacyReconciliationPostgresTests(ToolCustodyPostgresSupport, unittest.TestCase):
    def legacy_tool(self, status="На объекте", holder_name="Прежний получатель: требуется сверка"):
        # Synthetic examples of old rows: text exists, exact ownership does not.
        self.sql("""UPDATE tools SET status=%s,location='Прежнее место хранения',project='Прежний объект',
            master_id=NULL,master_name=%s,project_id=NULL,owner_scope='company',custody_contract_id=NULL
            WHERE id=%s""", (status, holder_name, self.tool_id))

    def reconcile_payload(self, status="На складе", **changes):
        target = {} if status != "У мастера" else {
            "recipientId": self.f["users"]["worker"]["id"], "projectId": self.f["projectId"], "contractId": None,
        }
        return self.tool_command_payload("reconcile", reconciledStatus=status,
            reason="Фактическое наличие и назначение проверены директором", **{**target, **changes})

    def reconcile(self, status="На складе", **changes):
        payload = self.reconcile_payload(status, **changes)
        result = self.api("director", "POST", self.custody_path, payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["toolId"], self.tool_id)
        self.assertTrue(result["eventId"])
        return result, payload

    def test_legacy_object_reconciles_to_warehouse_with_original_text_preserved(self):
        self.legacy_tool()
        before_tool = self.custody_view()["tool"]
        result, payload = self.reconcile()
        view = self.custody_view()
        self.assertEqual(view["tool"]["status"], "На складе")
        self.assertIsNone(view["tool"]["masterId"])
        self.assertFalse(view["tool"]["masterName"])
        self.assertIsNone(view["tool"]["projectId"])
        self.assertEqual(view["tool"]["companyId"], 2)
        self.assertEqual(len(view["history"]), 1)
        event = view["history"][0]
        self.assertEqual(event["id"], result["eventId"])
        self.assertEqual(event["action"], "reconcile")
        self.assertEqual(event["reason"], payload["reason"])
        self.assertEqual(event["before"], before_tool)
        self.assertEqual(event["after"], view["tool"])
        self.assertEqual(view["incidents"], [])

    def test_legacy_holder_reconciles_to_exact_recipient_then_normal_return_works(self):
        self.legacy_tool(status="У мастера")
        result, _ = self.reconcile("У мастера")
        tool = self.custody_view()["tool"]
        self.assertEqual(tool["masterId"], self.f["users"]["worker"]["id"])
        self.assertEqual(tool["masterName"], self.f["users"]["worker"]["name"])
        self.assertEqual(tool["projectId"], self.f["projectId"])
        self.assertIsNone(tool["contractId"])
        self.assertEqual(self.sql("SELECT custody_version FROM tools WHERE id=%s", (self.tool_id,)), [(1,)])
        self.tool_command("return", condition="good")
        view = self.custody_view()
        self.assertEqual(view["tool"]["status"], "На складе")
        self.assertIsNone(view["tool"]["masterId"])
        original = next(event for event in view["history"] if event["id"] == result["eventId"])
        self.assertEqual(original["before"]["masterName"], "Прежний получатель: требуется сверка")
        self.assertIsNone(original["before"]["masterId"])
        self.assertEqual(len(view["history"]), 2)

    def test_reconciliation_is_director_only_and_requires_reason(self):
        self.legacy_tool()
        payload = self.reconcile_payload()
        for actor in ("foreman", "worker"):
            with self.subTest(actor=actor):
                self.assert_rejected_unchanged(actor, "POST", self.custody_path, payload, expected=403)
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                      {**payload, "reason": "   "}, expected=400)

    def test_matching_legacy_name_does_not_replace_explicit_recipient_choice(self):
        self.legacy_tool(status="У мастера", holder_name=self.f["users"]["worker"]["name"])
        payload = self.reconcile_payload("У мастера", contractId=self.contract_id)
        del payload["recipientId"]
        self.assert_rejected_unchanged("director", "POST", self.custody_path, payload, expected=400)

    def test_held_reconciliation_validates_active_recipient_assignment_and_exact_contract(self):
        self.legacy_tool(status="У мастера")
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
            self.reconcile_payload("У мастера", recipientId=self.f["users"]["other_worker"]["id"],
                                   contractId=self.contract_id), expected=409)
        worker_id = self.f["users"]["worker"]["id"]
        self.sql("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2", (worker_id,))
        try:
            self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                          self.reconcile_payload("У мастера"), expected=404)
        finally:
            self.sql("UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2", (worker_id,))
        project_id = self.sql("INSERT INTO projects(name,company_id) VALUES('Synthetic unassigned reconciliation object',2) RETURNING id")[0][0]
        self.assert_rejected_unchanged("director", "POST", self.custody_path,
                                      self.reconcile_payload("У мастера", projectId=project_id), expected=409)
        self.reconcile("У мастера", contractId=self.contract_id)
        self.assertEqual(self.custody_view()["tool"]["contractId"], self.contract_id)

    def test_same_uuid_replays_once_and_stale_or_changed_reconciliation_conflicts(self):
        self.legacy_tool()
        result, payload = self.reconcile()
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.custody_path, payload), result)
        self.assertEqual(self.snapshot(), before)
        for changes in ({"reason": "Другое основание"}, {"requestId": str(uuid4())}):
            with self.subTest(changes=changes):
                self.assert_rejected_unchanged("director", "POST", self.custody_path, {**payload, **changes}, expected=409)

    def test_tool_with_prior_custody_event_cannot_be_reconciled_again(self):
        self.issue_tool()
        self.tool_command("return", condition="good")
        # Even if a historical-shaped row is restored independently, its real
        # existing event history must prevent a second initial attribution.
        self.legacy_tool()
        self.assert_rejected_unchanged("director", "POST", self.custody_path, self.reconcile_payload(), expected=409)

    def test_warehouse_and_previously_purchased_tools_are_not_legacy_reconciliation_candidates(self):
        self.assert_rejected_unchanged("director", "POST", self.custody_path, self.reconcile_payload(), expected=409)
        self.legacy_tool(status="У мастера (куплен)")
        self.assert_rejected_unchanged("director", "POST", self.custody_path, self.reconcile_payload(), expected=409)

    def test_foreign_company_cannot_reconcile_legacy_tool(self):
        self.legacy_tool()
        self.assert_rejected_unchanged("stranger", "POST", self.custody_path, self.reconcile_payload(), expected=404)


if __name__ == "__main__":
    unittest.main()
