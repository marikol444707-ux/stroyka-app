"""Contract acts settle confirmed factual work and material penalties exactly once.

Real authenticated HTTP against the guarded disposable Unix-socket PostgreSQL.
Contracts, work, scans and all monetary movements are synthetic fixture data.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.work_material_accounting import test_defects_postgres as support


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class MaterialSettlementPostgresTests(unittest.TestCase):
    sql = support.MaterialDefectsPostgresTests.sql
    api = support.MaterialDefectsPostgresTests.api
    payload = support.MaterialDefectsPostgresTests.payload
    balance = support.MaterialDefectsPostgresTests.balance
    work_payload = support.MaterialDefectsPostgresTests.work_payload
    request = support.MaterialDefectsPostgresTests.request
    consumption_payload = support.MaterialDefectsPostgresTests.consumption_payload
    create_consumption = support.MaterialDefectsPostgresTests.create_consumption
    stock_quantity = support.MaterialDefectsPostgresTests.stock_quantity
    defect_payload = support.MaterialDefectsPostgresTests.defect_payload
    create_defect = support.MaterialDefectsPostgresTests.create_defect
    decision_payload = support.MaterialDefectsPostgresTests.decision_payload
    expense_state = support.MaterialDefectsPostgresTests.expense_state
    registered_signature_file = support.MaterialDefectsPostgresTests.registered_file

    @classmethod
    def setUpClass(cls):
        support.MaterialDefectsPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        support.MaterialDefectsPostgresTests.setUp(self)
        # The shared fixture has already truncated new immutable ledgers. These
        # legacy tables are also synthetic and must not carry state across tests.
        for table in ("brigade_payments", "project_payments", "interim_acts", "piecework", "file_ownership"):
            self.sql("DELETE FROM " + table)
        self.contract_path = "/brigade-contracts/" + str(self.contract_id)
        self.confirm_work(self.journal_id, "Synthetic settlement room 1")

    def snapshot(self):
        tables = ("brigade_contracts", "brigade_acts", "brigade_payments", "project_payments",
                  "interim_acts", "piecework", "file_ownership")
        return support.MaterialDefectsPostgresTests.snapshot(self) + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in tables)

    def confirm_work(self, journal_id, room_name):
        self.api("director", "PUT", "/work-journal/" + str(journal_id), {
            "status": "Подтверждено", "roomName": room_name,
        })
        row = self.sql("SELECT status,quantity,execution_total FROM work_journal WHERE id=%s",
                       (journal_id,))[0]
        self.assertEqual(row[0], "Подтверждено")
        self.assertEqual(Decimal(str(row[1])), Decimal("1"))
        self.assertEqual(Decimal(str(row[2])), Decimal("10"))

    def confirm_defect(self, personal=0.2, warehouse=0.1):
        defect, _ = self.create_defect(personal=personal, warehouse=warehouse)
        decision = self.api("director", "POST",
                            self.path + "/material-defects/" + str(defect["id"]) + "/decisions",
                            self.decision_payload())
        self.assertEqual(decision["status"], "confirmed")
        self.assertEqual(Decimal(str(decision["amount"])),
                         Decimal(str(personal))*10 + Decimal(str(warehouse))*20)
        return defect, decision

    def preview(self):
        return self.api("director", "GET", self.contract_path + "/settlement")

    def act_payload(self, preview, journal_id=None, **changes):
        return {
            "requestId": str(uuid4()), "workJournalIds": [journal_id or self.journal_id],
            "expectedGrossAmount": str(preview["grossAmount"]),
            "expectedFineAmount": str(preview["fineAmount"]),
            "fineAllocations": preview["fineAllocations"],
            "periodFrom": "2026-09-18", "periodTo": "2026-09-18", **changes,
        }

    def create_act(self, preview=None, journal_id=None):
        payload = self.act_payload(preview or self.preview(), journal_id)
        result = self.api("director", "POST", self.contract_path + "/acts", payload)
        self.assertEqual(result["status"], "Сформирован")
        return result, payload

    def sign_act(self, act_id):
        path = self.contract_path + "/acts/" + str(act_id) + "/signature"
        payload = {"requestId": str(uuid4()), "scanUrl": self.registered_signature_file()}
        result = self.api("director", "POST", path, payload)
        self.assertEqual(result["status"], "Подписан")
        self.assertEqual(result["scanUrl"], payload["scanUrl"])
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", path, payload), result)
        self.assertEqual(self.snapshot(), before)
        return result

    def payment_payload(self, act_id, amount="6.00", **changes):
        return {"requestId": str(uuid4()), "contractId": self.contract_id,
                "actId": act_id, "amount": amount, "paidDate": "2026-09-18", **changes}

    def assert_amounts(self, result, gross, fine, net, carry=None):
        gross_key = "grossAmount" if "grossAmount" in result else "totalAmount"
        for key, expected in ((gross_key, gross), ("fineAmount", fine), ("netAmount", net)):
            self.assertEqual(Decimal(str(result[key])), Decimal(str(expected)), key)
        if carry is not None:
            self.assertEqual(Decimal(str(result["carryFineAmount"])), Decimal(str(carry)))

    def test_preview_keeps_gross_work_and_deducts_only_confirmed_material_penalty(self):
        defect, _ = self.confirm_defect()
        expenses = self.expense_state()
        preview = self.preview()
        self.assertEqual(self.sql("SELECT settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [(2,)])
        self.assertEqual([row["id"] for row in preview["eligibleWorks"]], [self.journal_id])
        self.assertEqual(preview["acts"], [])
        self.assert_amounts(preview, gross=10, fine=4, net=6, carry=0)
        self.assertEqual({row["defectId"] for row in preview["fineAllocations"]}, {defect["id"]})
        self.assertTrue(all(row["decisionId"] for row in preview["fineAllocations"]))
        self.assertEqual(sum(Decimal(str(row["amount"])) for row in preview["fineAllocations"]), Decimal("4"))
        self.assertEqual(self.expense_state(), expenses)

    def test_act_request_replays_once_and_whole_work_cannot_be_included_in_another_act(self):
        self.confirm_defect()
        act, payload = self.create_act()
        self.assert_amounts(act, gross=10, fine=4, net=6)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.contract_path + "/acts", payload), act)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", self.contract_path + "/acts",
                 {**payload, "expectedGrossAmount": "11.00"}, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", self.contract_path + "/acts",
                 {**payload, "requestId": str(uuid4())}, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.preview()["eligibleWorks"], [])

    def test_payment_requires_signed_act_caps_at_net_and_replays_without_extra_cash_movement(self):
        self.confirm_defect()
        act, _ = self.create_act()
        payment = self.payment_payload(act["id"])
        before = self.snapshot()
        self.api("director", "POST", "/brigade-payments", payment, expected=400)
        self.assertEqual(self.snapshot(), before)
        self.sign_act(act["id"])
        before = self.snapshot()
        self.api("director", "POST", "/brigade-payments",
                 self.payment_payload(act["id"], amount="10.00"), expected=400)
        self.assertEqual(self.snapshot(), before)
        paid = self.api("director", "POST", "/brigade-payments", payment)
        self.assertTrue(paid["id"])
        self.assertEqual(self.sql("SELECT amount FROM brigade_payments WHERE contract_id=%s",
                                  (self.contract_id,)), [(Decimal("6.00"),)])
        self.assertEqual(self.sql("SELECT amount FROM project_payments"), [(Decimal("6.00"),)])
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", "/brigade-payments", payment), paid)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", "/brigade-payments",
                 self.payment_payload(act["id"], amount="0.01"), expected=400)
        self.assertEqual(self.snapshot(), before)

    def test_unallocated_fine_carries_to_next_act_without_negative_net_or_double_deduction(self):
        self.confirm_defect(personal=0.5, warehouse=0.5)
        preview = self.preview()
        self.assert_amounts(preview, gross=10, fine=10, net=0, carry=5)
        first, _ = self.create_act(preview)
        self.assert_amounts(first, gross=10, fine=10, net=0)
        self.assertEqual(Decimal(str(self.preview()["carryFineAmount"])), Decimal("5"))
        payload = self.consumption_payload(personal=1, warehouse=1, roomName="Synthetic settlement room 2")
        second_work = self.api("worker", "POST", "/work-journal", payload)
        self.confirm_work(second_work["id"], "Synthetic settlement room 2")
        preview = self.preview()
        self.assertEqual([row["id"] for row in preview["eligibleWorks"]], [second_work["id"]])
        self.assert_amounts(preview, gross=10, fine=5, net=5, carry=0)
        second, _ = self.create_act(preview, second_work["id"])
        self.assert_amounts(second, gross=10, fine=5, net=5)
        after = self.preview()
        self.assertEqual(after["eligibleWorks"], [])
        self.assertEqual({row["id"] for row in after["acts"]}, {first["id"], second["id"]})
        self.assertEqual(sum(Decimal(str(row["fineAmount"])) for row in after["acts"]), Decimal("15"))
        self.assertEqual(Decimal(str(after["carryFineAmount"])), Decimal("0"))

    def test_foreign_company_cannot_read_create_sign_or_pay_this_contract_act(self):
        self.confirm_defect()
        act, payload = self.create_act()
        before = self.snapshot()
        self.api("stranger", "GET", self.contract_path + "/settlement", expected=404)
        self.api("stranger", "POST", self.contract_path + "/acts", payload, expected=404)
        self.api("stranger", "POST", self.contract_path + "/acts/" + str(act["id"]) + "/signature", {
            "requestId": str(uuid4()), "scanUrl": "/uploads/synthetic-signed.jpg",
        }, expected=404)
        self.api("stranger", "POST", "/brigade-payments", self.payment_payload(act["id"]), expected=404)
        self.assertEqual(self.snapshot(), before)

    def test_worker_cannot_form_financial_act_for_own_confirmed_work(self):
        before = self.snapshot()
        payload = {"requestId": str(uuid4()), "workJournalIds": [self.journal_id],
                   "expectedGrossAmount": "10.00", "expectedFineAmount": "0.00", "fineAllocations": [],
                   "periodFrom": "2026-09-18", "periodTo": "2026-09-18"}
        self.api("worker", "POST", self.contract_path + "/acts", payload, expected=403)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_interim_act_cannot_bypass_canonical_settlement_for_same_work(self):
        worker = self.f["users"]["worker"]
        before = self.snapshot()
        self.api("director", "POST", "/interim-acts", {
            "masterId": worker["id"], "masterName": worker["name"], "project": self.f["project"],
            "workPackage": self.f["workPackage"], "periodStart": "2026-09-18", "periodEnd": "2026-09-18",
            "totalAmount": 10, "contractId": self.contract_id, "workJournalIds": [self.journal_id],
        }, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_piecework_cannot_create_parallel_gross_earnings_for_canonical_contract_work(self):
        before = self.snapshot()
        self.api("director", "POST", "/piecework", {
            "staffId": str(self.f["users"]["worker"]["id"]), "description": "Synthetic work",
            "unit": "шт", "quantity": 1, "pricePerUnit": 10, "total": 10,
            "project": self.f["project"], "date": "2026-09-18", "workJournalId": self.journal_id,
        }, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_newly_confirmed_penalty_invalidates_an_older_zero_fine_preview(self):
        payload = self.act_payload(self.preview())
        self.assertEqual(Decimal(str(payload["expectedFineAmount"])), Decimal("0"))
        self.confirm_defect()
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts", payload, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assert_amounts(self.preview(), gross=10, fine=4, net=6, carry=0)

    def test_changed_fine_amount_or_omitted_allocation_cannot_override_settlement_preview(self):
        self.confirm_defect()
        preview = self.preview()
        for changes in ({"expectedFineAmount": "3.00"}, {"fineAllocations": []}):
            with self.subTest(changes=changes):
                before = self.snapshot()
                self.api("director", "POST", self.contract_path + "/acts",
                         self.act_payload(preview, **changes), expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_external_confirmed_work_fixup_invalidates_preview_before_act_creation(self):
        payload = self.act_payload(self.preview())
        before = self.snapshot()
        self.api("director", "PUT", self.path, {"quantity": 0.5}, expected=409)
        self.assertEqual(self.snapshot(), before)
        # An isolated historical fixup/external writer can stale a preview even
        # though the public API now protects confirmed work from direct edits.
        # No act includes this work yet; allocated work remains immutable.
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_contract_act_items WHERE journal_id=%s",
                                  (self.journal_id,)), [(0,)])
        self.sql("UPDATE work_journal SET quantity=%s,execution_total=%s WHERE id=%s",
                 (Decimal("0.5"), Decimal("5"), self.journal_id))
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts", payload, expected=409)
        self.assertEqual(self.snapshot(), before)
        self.assert_amounts(self.preview(), gross=5, fine=0, net=5, carry=0)

    def test_allocated_defect_cannot_be_disputed_or_cancelled_after_act_creation(self):
        defect, _ = self.confirm_defect()
        self.create_act()
        decision_path = self.path + "/material-defects/" + str(defect["id"]) + "/decisions"
        for actor, decision in (("worker", "disputed"), ("director", "cancelled")):
            with self.subTest(actor=actor, decision=decision):
                before = self.snapshot()
                self.api(actor, "POST", decision_path, {
                    "requestId": str(uuid4()), "decision": decision,
                    "reason": "Попытка пересмотреть штраф, уже включённый в акт",
                }, expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_acted_work_cannot_change_financial_amount_or_be_rejected_or_annulled(self):
        self.create_act()
        changes = (("PUT", {"quantity": 0.5}),
                   ("PUT", {"executionPricePerUnit": 20, "executionTotal": 20}),
                   ("PUT", {"status": "Отклонено"}),
                   ("PUT", {"status": "Аннулировано"}), ("DELETE", None))
        for method, payload in changes:
            with self.subTest(method=method, payload=payload):
                before = self.snapshot()
                self.api("director", method, self.path, payload, expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_legacy_brigade_act_cannot_bypass_canonical_contract_settlement(self):
        before = self.snapshot()
        self.api("director", "POST", "/brigade-acts", {
            "contractId": self.contract_id, "projectName": self.f["project"],
            "periodFrom": "2026-09-18", "periodTo": "2026-09-18", "totalAmount": "10.00",
            "workJournalIds": [self.journal_id],
        }, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_work_in_v2_contract_cannot_use_interim_or_piecework_routes(self):
        # A contract can contain historical v1 work alongside new material
        # accounting. The contract's settlement policy must cover both kinds.
        legacy_payload = self.work_payload(quantity=0)
        legacy_payload.update(materialAccountingVersion=1, roomName="Synthetic legacy room")
        with patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": "0"}):
            legacy = self.api("worker", "POST", "/work-journal", legacy_payload)
        self.confirm_work(legacy["id"], "Synthetic legacy room")
        self.assertEqual(self.sql("""SELECT w.material_accounting_version,c.settlement_version
            FROM work_journal w JOIN brigade_contract_items i ON i.id=w.contract_item_id
            JOIN brigade_contracts c ON c.id=i.contract_id WHERE w.id=%s""", (legacy["id"],)), [(1, 2)])
        worker = self.f["users"]["worker"]
        requests = (("/interim-acts", {
            "masterId": worker["id"], "masterName": worker["name"], "project": self.f["project"],
            "workPackage": self.f["workPackage"], "periodStart": "2026-09-18", "periodEnd": "2026-09-18",
            "totalAmount": 10, "contractId": self.contract_id, "workJournalIds": [legacy["id"]],
        }), ("/piecework", {
            "staffId": str(worker["id"]), "description": "Synthetic work", "unit": "шт",
            "quantity": 1, "pricePerUnit": 10, "total": 10, "project": self.f["project"],
            "date": "2026-09-18", "workJournalId": legacy["id"],
        }))
        for path, payload in requests:
            with self.subTest(path=path):
                before = self.snapshot()
                self.api("director", "POST", path, payload, expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_unsigned_or_employee_contract_cannot_form_canonical_financial_act(self):
        preview = self.preview()
        for contractor_type, status in (("Субподрядчик", "Черновик"), ("Трудовой договор", "Подписан")):
            with self.subTest(contractor_type=contractor_type, status=status):
                self.sql("UPDATE brigade_contracts SET contractor_type=%s,status=%s WHERE id=%s",
                         (contractor_type, status, self.contract_id))
                before = self.snapshot()
                self.api("director", "POST", self.contract_path + "/acts",
                         self.act_payload(preview), expected=409)
                self.assertEqual(self.snapshot(), before)

    def seed_legacy_paid_interim(self, status="Частично оплачен"):
        # Synthetic imported legacy history: an existing payment obligation
        # must survive promotion of the contract to managed settlement.
        worker = self.f["users"]["worker"]
        return self.sql("""INSERT INTO interim_acts(company_id,master_id,master_name,project,
            work_package,period_start,period_end,total_amount,paid_amount,contract_id,
            status,source_type,work_journal_ids)
            VALUES(2,%s,%s,%s,%s,'2026-09-18','2026-09-18',10,4,%s,%s,'',%s) RETURNING id""",
            (worker["id"], worker["name"], self.f["project"], self.f["workPackage"],
             self.contract_id, status, json.dumps([self.journal_id])))[0][0]

    def test_paid_legacy_interim_cannot_be_deleted_to_remove_reconciliation_obligation(self):
        act_id = self.seed_legacy_paid_interim()
        before = self.snapshot()
        self.api("director", "DELETE", "/interim-acts/" + str(act_id), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_piecework_cannot_be_deleted_to_hide_existing_contract_earnings(self):
        piecework_id = self.sql("""INSERT INTO piecework(staff_id,description,unit,quantity,
            price_per_unit,total,project,date,work_journal_id)
            VALUES(%s,'Synthetic historical earnings','шт',1,10,10,%s,'2026-09-18',%s) RETURNING id""",
            (str(self.f["users"]["worker"]["id"]), self.f["project"], self.journal_id))[0][0]
        before = self.snapshot()
        self.api("director", "DELETE", "/piecework/" + str(piecework_id), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_annulled_legacy_interim_with_payment_still_blocks_first_canonical_act(self):
        payload = self.act_payload(self.preview())
        self.seed_legacy_paid_interim(status="Аннулирован")
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts", payload, expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_project_payment_reversal_cannot_bypass_canonical_contract_payment_ledger(self):
        self.confirm_defect()
        act, _ = self.create_act()
        self.sign_act(act["id"])
        payment = self.api("director", "POST", "/brigade-payments", self.payment_payload(act["id"]))
        self.assertEqual(self.sql("SELECT amount FROM project_payments WHERE id=%s",
                                  (payment["projectPaymentId"],)), [(Decimal("6.00"),)])
        before = self.snapshot()
        self.api("director", "DELETE", "/project-payments/" + str(payment["projectPaymentId"]), expected=409)
        self.assertEqual(self.snapshot(), before)

    def race_settlement_requests(self, table, path, first_payload, second_payload):
        """Pause the first actual INSERT and observe the competing HTTP lock wait."""
        self.assertIn(table, ("brigade_acts", "brigade_payments"))
        self.assertNotEqual(first_payload["requestId"], second_payload["requestId"])
        self.sql("""CREATE FUNCTION settlement_concurrency_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914229,1); RETURN NEW; END $$""")
        self.sql("CREATE TRIGGER settlement_concurrency_pause BEFORE INSERT ON " + table +
                 " FOR EACH ROW EXECUTE FUNCTION settlement_concurrency_pause()")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914229,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", path, first_payload, actor="director")
                try:
                    deadline = time.monotonic() + 5
                    paused = []
                    while time.monotonic() < deadline:
                        paused = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event='advisory'
                              AND query LIKE %s""", ("INSERT INTO " + table + "%",))
                        if paused:
                            break
                        if first.done():
                            self.fail("First request did not reach its financial INSERT: " + first.result().text)
                        time.sleep(0.02)
                    self.assertEqual(len(paused), 1, "First financial write must be paused after validation")
                    second = pool.submit(self.request, "POST", path, second_payload, actor="director")
                    deadline = time.monotonic() + 5
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock'
                              AND pid<>%s""", (paused[0][0],))
                        if waiting:
                            break
                        if second.done():
                            self.fail("Competing request did not wait for the first financial write: " + second.result().text)
                        time.sleep(0.02)
                    self.assertTrue(waiting, "Competing HTTP transaction must wait before using the same balance")
                finally:
                    blocker.rollback()
                return [first.result(timeout=15), second.result(timeout=15)]
        finally:
            blocker.close()
            self.sql("DROP TRIGGER settlement_concurrency_pause ON " + table)
            self.sql("DROP FUNCTION settlement_concurrency_pause()")

    def test_concurrent_acts_cannot_include_the_same_work_or_deduct_the_same_fine_twice(self):
        self.confirm_defect()
        preview = self.preview()
        expenses = self.expense_state()
        responses = self.race_settlement_requests("brigade_acts", self.contract_path + "/acts",
                                                  self.act_payload(preview), self.act_payload(preview))
        self.assertEqual([response.status_code for response in responses], [200, 409],
                         [response.text for response in responses])
        self.assert_amounts(responses[0].json(), gross=10, fine=4, net=6)
        self.assertEqual(self.sql("""SELECT COUNT(*),SUM(gross_amount),SUM(fine_amount),SUM(net_amount)
            FROM work_contract_acts WHERE contract_id=%s""", (self.contract_id,)),
                         [(1, Decimal("10"), Decimal("4"), Decimal("6"))])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_contract_act_items WHERE journal_id=%s",
                                  (self.journal_id,)), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*),SUM(amount) FROM work_contract_fine_allocations"),
                         [(1, Decimal("4"))])
        self.assertEqual(self.expense_state(), expenses)

    def test_concurrent_payments_cannot_spend_the_same_six_ruble_net_balance_twice(self):
        self.confirm_defect()
        act, _ = self.create_act()
        self.sign_act(act["id"])
        expenses = self.expense_state()
        responses = self.race_settlement_requests("brigade_payments", "/brigade-payments",
                                                  self.payment_payload(act["id"]), self.payment_payload(act["id"]))
        self.assertEqual([response.status_code for response in responses], [200, 400],
                         [response.text for response in responses])
        self.assertEqual(self.sql("SELECT COUNT(*),SUM(amount) FROM brigade_payments WHERE contract_id=%s",
                                  (self.contract_id,)), [(1, Decimal("6"))])
        self.assertEqual(self.sql("SELECT COUNT(*),SUM(amount) FROM project_payments"), [(1, Decimal("6"))])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_contract_act_payments WHERE act_id=%s",
                                  (act["id"],)), [(1,)])
        saved_act = self.preview()["acts"][0]
        self.assertEqual(saved_act["status"], "Оплачен")
        self.assertEqual(Decimal(str(saved_act["remainingAmount"])), Decimal("0"))
        self.assertEqual(self.expense_state(), expenses)

    def test_contract_item_of_acted_legacy_work_cannot_be_deleted_without_material_account(self):
        legacy_item = self.sql("""INSERT INTO brigade_contract_items(contract_id,description,unit,
            quantity,price_brigade,work_package) VALUES(%s,'Synthetic legacy work','шт',100,10,%s) RETURNING id""",
            (self.contract_id, self.f["workPackage"]))[0][0]
        payload = self.work_payload(quantity=0)
        payload.update(materialAccountingVersion=1, contractItemId=legacy_item,
                       description="Synthetic legacy work", roomName="Synthetic acted legacy room")
        with patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": "0"}):
            work = self.api("worker", "POST", "/work-journal", payload)
        self.confirm_work(work["id"], "Synthetic acted legacy room")
        self.assertEqual(self.sql("SELECT material_accounting_version FROM work_journal WHERE id=%s",
                                  (work["id"],)), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_material_accounts WHERE journal_id=%s",
                                  (work["id"],)), [(0,)])
        act, _ = self.create_act({"grossAmount": "10.00", "fineAmount": "0.00", "fineAllocations": []}, work["id"])
        self.assertEqual(self.sql("SELECT act_id FROM work_contract_act_items WHERE journal_id=%s",
                                  (work["id"],)), [(act["id"],)])
        before = self.snapshot()
        self.api("director", "DELETE", "/brigade-contract-items/" + str(legacy_item), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_interim_contract_number_collision_does_not_match_managed_brigade(self):
        from backend.features.work_material_accounting.settlement_guards import require_legacy_interim
        # interim.contract_id identifies `contracts`, a different ID namespace.
        # An imported act for another executor has no links to our work journal.
        interim_id = self.seed_legacy_paid_interim()
        other_worker = self.f["users"]["other_worker"]
        self.sql("""UPDATE interim_acts SET master_id=%s,master_name=%s,work_journal_ids='[]'
            WHERE id=%s""", (other_worker["id"], other_worker["name"], interim_id))
        self.assertEqual(self.sql("SELECT contract_id FROM interim_acts WHERE id=%s", (interim_id,)),
                         [(self.contract_id,)])
        before = self.snapshot()
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                require_legacy_interim(cur, interim_id)
        finally:
            conn.close()
        self.assertEqual(self.snapshot(), before)
        legacy_row = self.sql("SELECT * FROM interim_acts WHERE id=%s", (interim_id,))
        act, _ = self.create_act()
        self.assert_amounts(act, gross=10, fine=0, net=10)
        self.assertEqual(self.sql("SELECT * FROM interim_acts WHERE id=%s", (interim_id,)), legacy_row)

    def assert_unowned_signature_rejected(self, scan_url, status=404):
        self.confirm_defect()
        act, _ = self.create_act()
        before = self.snapshot()
        self.api("director", "POST", self.contract_path + "/acts/" + str(act["id"]) + "/signature",
                 {"requestId": str(uuid4()), "scanUrl": scan_url}, expected=status)
        self.assertEqual(self.snapshot(), before)
        self.api("director", "POST", "/brigade-payments", self.payment_payload(act["id"]), expected=400)
        self.assertEqual(self.snapshot(), before)
        saved_act = self.preview()["acts"][0]
        self.assertEqual(saved_act["status"], "Сформирован")
        self.assertEqual(saved_act["scanUrl"], "")

    def test_signature_requires_an_existing_file_registry_record(self):
        missing_id = self.sql("SELECT COALESCE(MAX(id),0)+1000 FROM file_ownership")[0][0]
        self.assert_unowned_signature_rejected("/tenant-files/" + str(missing_id) + "/content")

    def test_signature_cannot_use_a_registered_file_from_another_company(self):
        project_id = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,3) RETURNING id",
                              ("Synthetic foreign signature project " + uuid4().hex,))[0][0]
        self.assert_unowned_signature_rejected(self.registered_signature_file(company_id=3, project_id=project_id))

    def test_signature_cannot_use_a_registered_file_from_another_project_of_same_company(self):
        project_id = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,2) RETURNING id",
                              ("Synthetic other signature project " + uuid4().hex,))[0][0]
        self.assert_unowned_signature_rejected(self.registered_signature_file(project_id=project_id))

    def test_signature_cannot_use_an_inactive_file_registry_record(self):
        self.assert_unowned_signature_rejected(self.registered_signature_file(deletion_status="deleted"))

    def test_signature_cannot_treat_an_external_url_as_a_verified_owned_signed_act(self):
        self.assert_unowned_signature_rejected("https://unowned-synthetic.invalid/signed.pdf", status=400)

    def test_signature_cannot_treat_a_legacy_fake_upload_url_as_a_verified_signed_act(self):
        self.assert_unowned_signature_rejected("/uploads/synthetic-file-that-does-not-exist.pdf", status=400)

    def test_payment_rechecks_that_the_registered_signature_file_is_still_active(self):
        self.confirm_defect()
        act, _ = self.create_act()
        signed = self.sign_act(act["id"])
        file_id = int(signed["scanUrl"].split("/")[2])
        self.sql("UPDATE file_ownership SET deletion_status='deleted' WHERE id=%s", (file_id,))
        before = self.snapshot()
        self.api("director", "POST", "/brigade-payments", self.payment_payload(act["id"]), expected=404)
        self.assertEqual(self.snapshot(), before)

    def test_preview_fails_closed_when_legacy_work_moves_outside_its_contract_package(self):
        payload = self.work_payload(quantity=0)
        payload.update(materialAccountingVersion=1, roomName="Synthetic legacy package mismatch")
        with patch.dict(os.environ, {"WORK_MATERIAL_ACCOUNTING_ENABLED": "0"}):
            work = self.api("worker", "POST", "/work-journal", payload)
        self.confirm_work(work["id"], "Synthetic legacy package mismatch")
        self.api("director", "PUT", "/work-journal/" + str(work["id"]), {"workPackage": "Other package"})
        self.assertEqual(self.sql("SELECT work_package FROM work_journal WHERE id=%s", (work["id"],)),
                         [("Other package",)])
        before = self.snapshot()
        result = self.api("worker", "GET", self.contract_path + "/settlement", expected=409)
        self.assertFalse({"eligibleWorks", "grossAmount", "fineAmount", "netAmount", "fineAllocations", "acts"} & set(result))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
