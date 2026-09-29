"""Tool responsibility shares immutable contract acts with material penalties.

All business commands use authenticated HTTP against a disposable socket-only
PostgreSQL fixture. SQL only arranges existing contracts and checks conservation.
"""
from decimal import Decimal
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.tool_custody.test_support import ToolCustodyPostgresSupport
from backend.features.work_material_accounting import test_settlement_postgres as material


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class ToolSettlementPostgresTests(ToolCustodyPostgresSupport, unittest.TestCase):
    # Reuse financial helpers without collecting the material tests a second time.
    confirm_work = material.MaterialSettlementPostgresTests.confirm_work
    confirm_defect = material.MaterialSettlementPostgresTests.confirm_defect
    defect_payload = material.MaterialSettlementPostgresTests.defect_payload
    create_defect = material.MaterialSettlementPostgresTests.create_defect
    decision_payload = material.MaterialSettlementPostgresTests.decision_payload
    expense_state = material.MaterialSettlementPostgresTests.expense_state
    registered_signature_file = material.MaterialSettlementPostgresTests.registered_signature_file
    preview = material.MaterialSettlementPostgresTests.preview
    act_payload = material.MaterialSettlementPostgresTests.act_payload
    create_act = material.MaterialSettlementPostgresTests.create_act
    sign_act = material.MaterialSettlementPostgresTests.sign_act
    payment_payload = material.MaterialSettlementPostgresTests.payment_payload
    assert_amounts = material.MaterialSettlementPostgresTests.assert_amounts
    race_settlement_requests = material.MaterialSettlementPostgresTests.race_settlement_requests

    def setUp(self):
        super().setUp()
        for table in ("brigade_payments", "project_payments", "interim_acts", "piecework", "file_ownership"):
            self.sql("DELETE FROM " + table)
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        self.journal_id = journal["id"]
        self.path = "/work-journal/" + str(self.journal_id)
        self.contract_path = "/brigade-contracts/" + str(self.contract_id)
        self.entry_ids = dict(self.sql("SELECT source,id FROM work_material_entries WHERE journal_id=%s",
                                       (self.journal_id,)))
        # Existing, confirmed work is fixture input to the new financial flow.
        with patch.dict(os.environ, {"WORK_ACCEPTANCE_ENABLED": "0"}):
            self.confirm_work(self.journal_id, "Synthetic tool settlement room 1")

    def snapshot(self):
        return super().snapshot() + (("file_ownership", self.sql(
            "SELECT row_to_json(t)::text FROM file_ownership t ORDER BY 1")),)

    def incident_path(self, incident_id):
        return self.tool_path + "/incidents/" + str(incident_id) + "/decisions"

    def create_incident(self, condition="damaged"):
        self.issue_tool()
        result = self.tool_command("return", condition=condition,
                                   reason="Инструмент повреждён либо утрачен при выполнении работ")
        self.assertTrue(result["incidentId"])
        incidents = self.custody_view()["incidents"]
        incident = next(row for row in incidents if row["id"] == result["incidentId"])
        self.assertEqual(incident["status"], "pending")
        self.assertEqual(incident["contractId"], self.contract_id)
        return incident

    def tool_decision_payload(self, **changes):
        return {"requestId": str(uuid4()), "decision": "confirmed", "amount": "3.00",
                "reason": "Директор подтвердил документированный ущерб",
                "priceEvidence": "Счёт за ремонт SYNTHETIC-TOOL-1",
                "contractEvidence": "Подписанный договор SYNTHETIC-1, пункт об инструменте",
                **changes}

    def confirm_tool_fine(self, amount="3.00", condition="damaged"):
        incident = self.create_incident(condition)
        payload = self.tool_decision_payload(amount=amount)
        decision = self.api("director", "POST", self.incident_path(incident["id"]), payload)
        self.assertEqual(decision["status"], "confirmed")
        self.assertEqual(Decimal(str(decision["amount"])), Decimal(amount))
        return incident, decision, payload

    def second_confirmed_work(self):
        payload = self.consumption_payload(personal=1, warehouse=1,
                                           roomName="Synthetic tool settlement room 2")
        result = self.api("worker", "POST", "/work-journal", payload)
        with patch.dict(os.environ, {"WORK_ACCEPTANCE_ENABLED": "0"}):
            self.confirm_work(result["id"], "Synthetic tool settlement room 2")
        return result["id"]

    def test_pending_loss_does_not_automatically_charge_tool_value(self):
        incident = self.create_incident("lost")
        before = self.snapshot()
        self.assert_amounts(self.preview(), gross=10, fine=0, net=10, carry=0)
        self.assertEqual(self.preview()["fineAllocations"], [])
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", self.incident_path(incident["id"]), self.tool_decision_payload())
        self.assert_amounts(self.preview(), gross=10, fine=3, net=7, carry=0)

    def test_confirmation_requires_director_amount_and_both_documentary_grounds(self):
        incident = self.create_incident()
        for changes in ({"amount": "0"}, {"amount": "-1"}, {"amount": "NaN"},
                        {"reason": ""}, {"priceEvidence": ""}, {"contractEvidence": ""}):
            with self.subTest(changes=changes):
                before = self.snapshot()
                self.api("director", "POST", self.incident_path(incident["id"]),
                         self.tool_decision_payload(**changes), expected=400)
                self.assertEqual(self.snapshot(), before)
        for actor in ("worker", "foreman"):
            with self.subTest(actor=actor):
                before = self.snapshot()
                self.api(actor, "POST", self.incident_path(incident["id"]),
                         self.tool_decision_payload(), expected=403)
                self.assertEqual(self.snapshot(), before)

    def test_confirmation_rechecks_signed_contractor_status_and_forbids_employee_fine(self):
        incident = self.create_incident()
        for contract_type, status in (("Субподрядчик", "Черновик"), ("Сотрудник", "Подписан")):
            with self.subTest(contract_type=contract_type, status=status):
                # Simulate a historical contract correction after the issue.
                # No act has allocated this incident or its decision yet.
                self.sql("UPDATE brigade_contracts SET contractor_type=%s,status=%s WHERE id=%s",
                         (contract_type, status, self.contract_id))
                before = self.snapshot()
                self.api("director", "POST", self.incident_path(incident["id"]),
                         self.tool_decision_payload(), expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_uncontracted_employee_custody_cannot_generate_a_contract_fine(self):
        self.sql("UPDATE brigade_contracts SET contractor_type='Сотрудник' WHERE id=%s", (self.contract_id,))
        self.issue_tool(contractId=None)
        returned = self.tool_command("return", condition="lost", reason="Инструмент утрачен сотрудником")
        incident = next(row for row in self.custody_view()["incidents"] if row["id"] == returned["incidentId"])
        self.assertEqual(incident["status"], "pending")
        self.assertIsNone(incident["contractId"])
        before = self.snapshot()
        self.api("director", "POST", self.incident_path(incident["id"]),
                 self.tool_decision_payload(), expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assert_amounts(self.preview(), gross=10, fine=0, net=10, carry=0)

    def test_foreign_company_cannot_confirm_or_dispute_an_owned_incident(self):
        incident = self.create_incident()
        for decision in ("confirmed", "disputed"):
            with self.subTest(decision=decision):
                before = self.snapshot()
                response = self.request("POST", self.incident_path(incident["id"]),
                                        self.tool_decision_payload(decision=decision), actor="stranger")
                self.assertIn(response.status_code, (403, 404), response.text)
                self.assertEqual(self.snapshot(), before)

    def test_foreman_cannot_remove_another_holders_confirmed_fine_by_disputing(self):
        incident, _, _ = self.confirm_tool_fine()
        before = self.snapshot()
        self.api("foreman", "POST", self.incident_path(incident["id"]), {
            "requestId": str(uuid4()), "decision": "disputed", "reason": "Менеджер не является получателем",
        }, expected=403)
        self.assertEqual(self.snapshot(), before)
        self.assert_amounts(self.preview(), gross=10, fine=3, net=7, carry=0)

    def test_warehouse_tool_does_not_expose_another_projects_incident_or_history(self):
        self.confirm_tool_fine()
        foreman_id = self.f["users"]["foreman"]["id"]
        original = self.sql("SELECT assigned_projects::text FROM user_company_roles WHERE user_id=%s AND company_id=2",
                            (foreman_id,))[0][0]
        self.addCleanup(self.sql, "UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2",
                        (original, foreman_id))
        other_name = "Synthetic other foreman project " + uuid4().hex
        other_id = self.sql("INSERT INTO projects(name,company_id,archived) VALUES(%s,2,FALSE) RETURNING id",
                            (other_name,))[0][0]
        self.addCleanup(self.sql, "DELETE FROM projects WHERE id=%s", (other_id,))
        # A nonempty distinct assignment suppresses the legacy primary-project
        # fallback, so this actually tests an inaccessible incident project.
        self.sql("UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2",
                 (json.dumps([other_name]), foreman_id))
        before = self.snapshot()
        view = self.custody_view(actor="foreman")
        self.assertEqual(view["tool"]["id"], self.tool_id)
        self.assertIsNone(view["tool"]["projectId"])
        self.assertEqual([row["id"] for row in view["choices"]["projects"]], [other_id])
        self.assertEqual(view["incidents"], [])
        self.assertEqual(view["history"], [])
        self.assertEqual(self.snapshot(), before)
        director = self.custody_view()
        self.assertEqual(len(director["incidents"]), 1)
        self.assertEqual(len(director["history"]), 2)

    def test_decision_request_replays_once_and_changed_amount_is_a_conflict(self):
        incident, decision, payload = self.confirm_tool_fine()
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.incident_path(incident["id"]), payload), decision)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", self.incident_path(incident["id"]),
                 {**payload, "amount": "4.00"}, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assert_amounts(self.preview(), gross=10, fine=3, net=7, carry=0)

    def test_reconciliation_keeps_foreign_legacy_snapshot_private_for_new_holder_and_foreman(self):
        old_name = "Synthetic inaccessible legacy object " + uuid4().hex
        old_project = self.sql("INSERT INTO projects(name,company_id,archived) VALUES(%s,2,FALSE) RETURNING id",
                               (old_name,))[0][0]
        old_holder = self.f["users"]["other_worker"]
        # Legacy status is unresolved even when its old attribution has IDs.
        # The new event belongs to a different, explicitly chosen recipient.
        self.sql("""UPDATE tools SET status='На объекте',project=%s,project_id=%s,
            master_id=%s,master_name=%s,owner_scope='project' WHERE id=%s""",
                 (old_name, old_project, old_holder["id"], old_holder["name"], self.tool_id))
        before_tool = self.custody_view()["tool"]
        result = self.tool_command("reconcile", reconciledStatus="У мастера",
            recipientId=self.f["users"]["worker"]["id"], projectId=self.f["projectId"],
            contractId=None, reason="Директор установил фактического получателя")
        before_read = self.snapshot()
        for actor in ("worker", "foreman"):
            with self.subTest(actor=actor):
                view = self.custody_view(actor=actor)
                if actor == "foreman":
                    self.assertNotIn(old_project, [row["id"] for row in view["choices"]["projects"]])
                event = next(row for row in view["history"] if row["id"] == result["eventId"])
                self.assertEqual(event["before"], {key: before_tool[key]
                    for key in ("name", "inventoryNumber", "status")})
                self.assertEqual(event["after"]["projectId"], self.f["projectId"])
                self.assertEqual(event["after"]["masterId"], self.f["users"]["worker"]["id"])
        director_event = next(row for row in self.custody_view()["history"] if row["id"] == result["eventId"])
        self.assertEqual(director_event["before"], before_tool)
        self.assertEqual(self.snapshot(), before_read)

    def test_material_and_tool_ids_do_not_collide_and_share_one_gross_capacity(self):
        defect, _ = self.confirm_defect()
        incident, _, _ = self.confirm_tool_fine()
        # Independent sequences deliberately produce the same numeric ID.
        self.assertEqual(defect["id"], incident["id"])
        expense = self.expense_state()
        preview = self.preview()
        self.assert_amounts(preview, gross=10, fine=7, net=3, carry=0)
        self.assertEqual(len(preview["fineAllocations"]), 2)
        material_fine, tool_fine = preview["fineAllocations"]
        self.assertNotIn("source", material_fine, "Existing material payload shape must remain valid")
        self.assertEqual(material_fine["defectId"], defect["id"])
        self.assertEqual((tool_fine["source"], tool_fine["incidentId"]), ("tool", incident["id"]))
        self.assertTrue(tool_fine["decisionId"])
        self.assertEqual(Decimal(str(tool_fine["amount"])), Decimal(3))
        act, payload = self.create_act(preview)
        self.assert_amounts(act, gross=10, fine=7, net=3)
        self.assertEqual(act["snapshot"]["fines"], preview["fineAllocations"])
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.contract_path + "/acts", payload), act)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("SELECT amount FROM tool_fine_allocations WHERE incident_id=%s",
                                  (incident["id"],)), [(Decimal(3),)])
        self.assertEqual(self.sql("SELECT amount FROM work_contract_fine_allocations WHERE defect_id=%s",
                                  (defect["id"],)), [(Decimal(4),)])
        self.assertEqual(self.expense_state(), expense)

    def test_tool_balance_carries_after_material_fines_without_double_deduction(self):
        self.confirm_defect()
        incident, _, _ = self.confirm_tool_fine("15.00")
        preview = self.preview()
        self.assert_amounts(preview, gross=10, fine=10, net=0, carry=9)
        self.assertEqual([Decimal(str(row["amount"])) for row in preview["fineAllocations"]],
                         [Decimal(4), Decimal(6)])
        first, _ = self.create_act(preview)
        self.assert_amounts(first, gross=10, fine=10, net=0)
        first_snapshot = first["snapshot"]
        second_work = self.second_confirmed_work()
        preview = self.preview()
        self.assert_amounts(preview, gross=10, fine=9, net=1, carry=0)
        self.assertEqual([row["source"] for row in preview["fineAllocations"]], ["tool"])
        second, _ = self.create_act(preview, second_work)
        self.assert_amounts(second, gross=10, fine=9, net=1)
        self.assertEqual(self.sql("SELECT SUM(amount),COUNT(*) FROM tool_fine_allocations WHERE incident_id=%s",
                                  (incident["id"],)), [(Decimal(15), 2)])
        after = self.preview()
        self.assertEqual(next(row["snapshot"] for row in after["acts"] if row["id"] == first["id"]), first_snapshot)
        self.assertEqual(sum(Decimal(str(row["fineAmount"])) for row in after["acts"]), Decimal(19))
        self.assertEqual(Decimal(str(after["carryFineAmount"])), Decimal(0))

    def test_signed_act_payment_is_capped_at_net_after_both_fine_sources(self):
        self.confirm_defect()
        self.confirm_tool_fine()
        act, _ = self.create_act()
        self.sign_act(act["id"])
        before = self.snapshot()
        self.api("director", "POST", "/brigade-payments", self.payment_payload(act["id"], amount="6.00"), expected=400)
        self.assertEqual(self.snapshot(), before)
        payload = self.payment_payload(act["id"], amount="3.00")
        paid = self.api("director", "POST", "/brigade-payments", payload)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", "/brigade-payments", payload), paid)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql("SELECT amount FROM brigade_payments WHERE contract_id=%s", (self.contract_id,)),
                         [(Decimal(3),)])
        self.assertEqual(self.sql("SELECT amount FROM project_payments"), [(Decimal(3),)])

    def test_new_tool_confirmation_invalidates_an_older_zero_fine_act_preview(self):
        incident = self.create_incident()
        payload = self.act_payload(self.preview())
        self.api("director", "POST", self.incident_path(incident["id"]), self.tool_decision_payload())
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts", payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_dispute_removes_unallocated_fine_and_reconfirmation_invalidates_old_decision_id(self):
        incident, _, _ = self.confirm_tool_fine()
        stale = self.act_payload(self.preview())
        self.api("worker", "POST", self.incident_path(incident["id"]), {
            "requestId": str(uuid4()), "decision": "disputed", "reason": "Исполнитель оспаривает ответственность",
        })
        self.assert_amounts(self.preview(), gross=10, fine=0, net=10, carry=0)
        self.api("director", "POST", self.incident_path(incident["id"]), self.tool_decision_payload())
        current = self.preview()
        self.assert_amounts(current, gross=10, fine=3, net=7, carry=0)
        self.assertNotEqual(current["fineAllocations"][0]["decisionId"], stale["fineAllocations"][0]["decisionId"])
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts", stale, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_allocated_tool_decision_cannot_be_cancelled_disputed_or_repriced(self):
        incident, _, _ = self.confirm_tool_fine("15.00")
        self.create_act()
        for actor, changes in (("worker", {"decision": "disputed"}),
                               ("director", {"decision": "cancelled"}),
                               ("director", {"amount": "20.00"})):
            with self.subTest(actor=actor, changes=changes):
                before = self.snapshot()
                self.api(actor, "POST", self.incident_path(incident["id"]),
                         self.tool_decision_payload(**changes), expected=409)
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(Decimal(str(self.preview()["carryFineAmount"])), Decimal(5))

    def test_fine_remains_in_contract_settlement_when_tool_commands_are_disabled(self):
        self.confirm_tool_fine()
        with patch.dict(os.environ, {"TOOL_CUSTODY_ENABLED": "0"}):
            self.assert_amounts(self.preview(), gross=10, fine=3, net=7, carry=0)
            act, _ = self.create_act()
            self.assert_amounts(act, gross=10, fine=3, net=7)

    def test_other_contract_for_same_recipient_cannot_inherit_the_tool_fine(self):
        self.confirm_tool_fine()
        other_id = self.sql("""INSERT INTO brigade_contracts
            (company_id,project_id,project_name,brigade_name,contractor_id,contractor_type,status,work_package)
            SELECT company_id,project_id,project_name,brigade_name,contractor_id,contractor_type,status,work_package
            FROM brigade_contracts WHERE id=%s RETURNING id""", (self.contract_id,))[0][0]
        other = self.api("director", "GET", f"/brigade-contracts/{other_id}/settlement")
        self.assert_amounts(other, gross=0, fine=0, net=0, carry=0)
        self.assertEqual(other["fineAllocations"], [])
        self.assert_amounts(self.preview(), gross=10, fine=3, net=7, carry=0)

    def test_concurrent_act_requests_allocate_the_tool_fine_only_once(self):
        incident, _, _ = self.confirm_tool_fine()
        payload = self.act_payload(self.preview())
        responses = self.race_settlement_requests("brigade_acts", self.contract_path + "/acts", payload,
                                                  {**payload, "requestId": str(uuid4())})
        self.assertEqual([row.status_code for row in responses], [200, 409],
                         [(row.status_code, row.text) for row in responses])
        self.assertEqual(self.sql("SELECT COUNT(*),SUM(amount) FROM tool_fine_allocations WHERE incident_id=%s",
                                  (incident["id"],)), [(1, Decimal(3))])


if __name__ == "__main__":
    unittest.main()
