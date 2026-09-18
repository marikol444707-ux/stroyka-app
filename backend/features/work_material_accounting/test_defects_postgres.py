"""Explicit factual corrections and contractual material-defect responsibility.

Real HTTP/authorization/ledger transactions in a fresh socket-only PostgreSQL.
All records, photographs references and contracts below are synthetic fixtures.
"""
from decimal import Decimal
import json
import os
import unittest
from uuid import uuid4

from backend.features.work_material_accounting import test_postgres as support


def with_initial_contract_type(value):
    """Select the fixture type before its first factual consumption is posted."""
    def configure(test):
        test.initial_contract_type = value
        return test
    return configure


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class MaterialDefectsPostgresTests(unittest.TestCase):
    sql = support.WorkMaterialAccountingPostgresTests.sql
    api = support.WorkMaterialAccountingPostgresTests.api
    payload = support.WorkMaterialAccountingPostgresTests.payload
    balance = support.WorkMaterialAccountingPostgresTests.balance
    work_payload = support.WorkMaterialAccountingPostgresTests.work_payload
    request = support.WorkMaterialAccountingPostgresTests.request
    consumption_payload = support.WorkMaterialAccountingPostgresTests.consumption_payload
    create_consumption = support.WorkMaterialAccountingPostgresTests.create_consumption
    stock_quantity = support.WorkMaterialAccountingPostgresTests.stock_quantity
    snapshot = support.WorkMaterialAccountingPostgresTests.snapshot

    @classmethod
    def setUpClass(cls):
        support.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        support.WorkMaterialAccountingPostgresTests.setUp(self)
        self.contract_id = self.sql("SELECT contract_id FROM brigade_contract_items WHERE id=%s",
                                    (self.contract_item,))[0][0]
        contract_type = getattr(getattr(self, self._testMethodName), "initial_contract_type", "Субподрядчик")
        self.sql("UPDATE brigade_contracts SET contractor_type=%s,status='Подписан' WHERE id=%s",
                 (contract_type, self.contract_id))
        journal, _ = self.create_consumption(personal=1, warehouse=1)
        self.journal_id = journal["id"]
        self.path = "/work-journal/" + str(self.journal_id)
        self.entry_ids = dict(self.sql("SELECT source,id FROM work_material_entries WHERE journal_id=%s",
                                       (self.journal_id,)))

    def correction(self, source="warehouse", target=0.25, expected=1, **changes):
        return {"requestId": str(uuid4()), "entryId": self.entry_ids[source],
                "quantity": target, "expectedQuantity": expected,
                "reason": "Исправление ошибочно указанного фактического расхода", **changes}

    def defect_payload(self, personal=0.5, warehouse=0.25, **changes):
        items = [{"entryId": self.entry_ids[source], "quantity": amount}
                 for source, amount in (("personal", personal), ("warehouse", warehouse)) if amount]
        return {"requestId": str(uuid4()), "reason": "Материал испорчен при выполнении работы",
                "photos": ["/uploads/synthetic-material-defect.jpg"], "items": items, **changes}

    def create_defect(self, **changes):
        payload = self.defect_payload(**changes)
        result = self.api("foreman", "POST", self.path+"/material-defects", payload)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["contractId"], self.contract_id)
        self.assertEqual(Decimal(str(result["amount"])), Decimal("0"))
        return result, payload

    def decision_payload(self, **changes):
        return {"requestId": str(uuid4()), "decision": "confirmed",
                "reason": "Подтверждено по акту брака и договору",
                "contractEvidence": "Договор подряда № SYNTHETIC-1, пункт о материалах",
                "valuations": [
                    {"entryId": self.entry_ids["personal"], "unitPrice": "10.00",
                     "priceEvidence": "Накладная № SYNTHETIC-P"},
                    {"entryId": self.entry_ids["warehouse"], "unitPrice": "20.00",
                     "priceEvidence": "Накладная № SYNTHETIC-W"},
                ], **changes}

    def expense_state(self):
        return tuple(self.sql("SELECT * FROM " + table + " ORDER BY id")
                     for table in ("materials", "warehouse_history", "work_material_entries"))

    def registered_file(self, company_id=2, project_id=None, deletion_status="active", content_type="application/pdf"):
        """Only register synthetic ownership; never contact storage or upload data."""
        project_id = self.f["projectId"] if project_id is None else project_id
        extension = "jpg" if content_type == "image/jpeg" else "pdf"
        key = "companies/" + str(company_id) + "/projects/" + str(project_id) + "/synthetic-" + uuid4().hex + "." + extension
        file_id = self.sql("""INSERT INTO file_ownership(company_id,project_id,file_url,storage_key,
            context,original_name,content_type,uploaded_by_id,uploaded_by,deletion_status)
            VALUES(%s,%s,%s,%s,'work_material_accounting','Synthetic registered file',%s,%s,%s,%s)
            RETURNING id""", (company_id, project_id, "/uploads/" + key, key, content_type,
                              self.f["users"]["director"]["id"], "Synthetic director", deletion_status))[0][0]
        return "/tenant-files/" + str(file_id) + "/content"

    def assert_net_usage(self, personal, warehouse):
        self.assertEqual(self.sql("""SELECT source,SUM(quantity) FROM work_material_entries
            WHERE journal_id=%s GROUP BY source ORDER BY source""", (self.journal_id,)),
                         [("personal", Decimal(str(personal))), ("warehouse", Decimal(str(warehouse)))])
        self.assertEqual(self.balance(), dict(issued=2, used=personal, returned=0, available=2-personal))
        self.assertEqual(self.stock_quantity(), 2-warehouse)
        stored = self.sql("SELECT materials_used FROM work_journal WHERE id=%s", (self.journal_id,))[0][0]
        materials = json.loads(stored) if isinstance(stored, str) else stored
        self.assertEqual(sum(Decimal(str(row["personalQuantity"])) for row in materials), Decimal(str(personal)))
        self.assertEqual(sum(Decimal(str(row["warehouseQuantity"])) for row in materials), Decimal(str(warehouse)))

    def test_accounting_read_exposes_owned_contract_original_entries_and_no_defects(self):
        result = self.api("worker", "GET", self.path+"/material-accounting")
        self.assertEqual(result["journalId"], self.journal_id)
        self.assertEqual(result["contractId"], self.contract_id)
        self.assertEqual(result["defects"], [])
        self.assertEqual({row["source"]: (row["id"], Decimal(str(row["quantity"])))
                          for row in result["entries"]},
                         {source: (entry_id, Decimal("1")) for source, entry_id in self.entry_ids.items()})

    def test_explicit_mixed_corrections_append_deltas_and_replay_without_second_restoration(self):
        originals = self.sql("SELECT * FROM work_material_entries ORDER BY id")
        warehouse = self.correction("warehouse", 0.25)
        first = self.api("director", "POST", self.path+"/material-corrections", warehouse)
        self.assertTrue(first["ok"])
        self.api("director", "POST", self.path+"/material-corrections", self.correction("personal", 0.5))
        self.assert_net_usage(personal=0.5, warehouse=0.25)
        self.assertEqual(self.sql("SELECT * FROM work_material_entries WHERE id=ANY(%s) ORDER BY id",
                                  (list(self.entry_ids.values()),)), originals)
        self.assertEqual(self.sql("SELECT quantity FROM work_material_entries WHERE quantity<0 ORDER BY quantity"),
                         [(Decimal("-0.75"),), (Decimal("-0.5"),)])
        before = self.snapshot()
        replay = self.api("director", "POST", self.path+"/material-corrections", warehouse)
        self.assertEqual(replay, first)
        self.assertEqual(self.snapshot(), before)

    def test_correction_cannot_increase_consumption_beyond_either_source_balance(self):
        for source in ("personal", "warehouse"):
            with self.subTest(source=source):
                before = self.snapshot()
                self.api("director", "POST", self.path+"/material-corrections",
                         self.correction(source, target=3), expected=400)
                self.assertEqual(self.snapshot(), before)
                self.assert_net_usage(personal=1, warehouse=1)

    def test_correction_requires_current_quantity_to_avoid_overwriting_a_previous_correction(self):
        self.api("director", "POST", self.path+"/material-corrections", self.correction(target=0.5))
        before = self.snapshot()
        self.api("director", "POST", self.path+"/material-corrections",
                 self.correction(target=0.25, expected=1), expected=409)
        self.assertEqual(self.snapshot(), before)

    def test_worker_and_foreman_cannot_authorize_material_correction(self):
        for actor in ("worker", "foreman"):
            with self.subTest(actor=actor):
                before = self.snapshot()
                self.api(actor, "POST", self.path+"/material-corrections", self.correction(), expected=403)
                self.assertEqual(self.snapshot(), before)

    def test_defect_records_responsibility_without_second_stock_expense_and_replays_once(self):
        expenses = self.expense_state()
        result, payload = self.create_defect()
        self.assertEqual(self.expense_state(), expenses)
        before = self.snapshot()
        replay = self.api("foreman", "POST", self.path+"/material-defects", payload)
        self.assertEqual(replay, result)
        self.assertEqual(self.snapshot(), before)
        report = self.api("worker", "GET", self.path+"/material-accounting")
        self.assertEqual([defect["id"] for defect in report["defects"]], [result["id"]])
        self.assert_net_usage(personal=1, warehouse=1)

    def test_defect_cannot_exceed_net_consumption_or_reuse_already_reserved_material(self):
        before = self.snapshot()
        self.api("foreman", "POST", self.path+"/material-defects",
                 self.defect_payload(personal=1.1, warehouse=0), expected=400)
        self.assertEqual(self.snapshot(), before)
        self.create_defect(personal=0.75, warehouse=0)
        before = self.snapshot()
        self.api("foreman", "POST", self.path+"/material-defects",
                 self.defect_payload(personal=0.5, warehouse=0), expected=400)
        self.assertEqual(self.snapshot(), before)

    def test_defect_requires_a_reason_and_photographic_evidence(self):
        for changes in ({"reason": "   "}, {"photos": []}):
            with self.subTest(changes=changes):
                before = self.snapshot()
                self.api("foreman", "POST", self.path+"/material-defects",
                         self.defect_payload(**changes), expected=400)
                self.assertEqual(self.snapshot(), before)

    def test_director_confirms_exact_amount_without_changing_gross_work_or_material_expense(self):
        defect, _ = self.create_defect()
        path = self.path+"/material-defects/"+str(defect["id"])+"/decisions"
        gross = self.sql("SELECT quantity,total,execution_total FROM work_journal WHERE id=%s", (self.journal_id,))
        expenses = self.expense_state()
        payload = self.decision_payload()
        result = self.api("director", "POST", path, payload)
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(Decimal(str(result["amount"])), Decimal("10.00"))
        self.assertEqual(self.expense_state(), expenses)
        self.assertEqual(self.sql("SELECT quantity,total,execution_total FROM work_journal WHERE id=%s",
                                  (self.journal_id,)), gross)
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", path, payload), result)
        self.assertEqual(self.snapshot(), before)

    def test_employee_vague_or_unsigned_contract_cannot_create_a_confirmed_penalty(self):
        defect, _ = self.create_defect()
        path = self.path+"/material-defects/"+str(defect["id"])+"/decisions"
        for contract_type, status in (("Трудовой договор", "Подписан"), ("Мастер", "Подписан"),
                                      ("Субподрядчик", "Черновик")):
            with self.subTest(contract_type=contract_type, status=status):
                self.sql("UPDATE brigade_contracts SET contractor_type=%s,status=%s WHERE id=%s",
                         (contract_type, status, self.contract_id))
                before = self.snapshot()
                self.api("director", "POST", path, self.decision_payload(), expected=409)
                self.assertEqual(self.snapshot(), before)

    def test_other_company_cannot_read_correct_create_or_confirm_defects_for_this_work(self):
        defect, _ = self.create_defect()
        before = self.snapshot()
        self.api("stranger", "GET", self.path+"/material-accounting", expected=404)
        self.api("stranger", "POST", self.path+"/material-corrections", self.correction(), expected=404)
        self.api("stranger", "POST", self.path+"/material-defects", self.defect_payload(), expected=404)
        self.api("stranger", "POST", self.path+"/material-defects/"+str(defect["id"])+"/decisions",
                 self.decision_payload(), expected=404)
        self.assertEqual(self.snapshot(), before)

    def contract_financial_snapshot(self):
        tables = ("brigade_contracts", "brigade_acts", "brigade_payments", "project_payments",
                  "interim_acts", "piecework")
        return self.snapshot() + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in tables)

    def piecework_payload(self):
        return {"staffId": str(self.f["users"]["worker"]["id"]), "description": "Synthetic work",
                "unit": "шт", "quantity": 1, "pricePerUnit": 10, "total": 10,
                "project": self.f["project"], "date": "2026-09-18", "workJournalId": self.journal_id}

    @with_initial_contract_type("Трудовой договор")
    def test_employee_factual_consumption_keeps_legacy_earnings_and_cannot_become_material_penalty(self):
        self.assertEqual(self.sql("SELECT material_accounting_version FROM work_journal WHERE id=%s",
                                  (self.journal_id,)), [(2,)])
        self.assertEqual(self.sql("SELECT contractor_type,settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [("Трудовой договор", 1)])
        self.assert_net_usage(personal=1, warehouse=1)
        expenses = self.expense_state()
        defect, _ = self.create_defect()
        before = self.contract_financial_snapshot()
        self.api("director", "POST", self.path + "/material-defects/" + str(defect["id"]) + "/decisions",
                 self.decision_payload(), expected=409)
        self.assertEqual(self.contract_financial_snapshot(), before)
        self.api("director", "PUT", self.path,
                 {"status": "Подтверждено", "roomName": "Synthetic employee room"})
        piecework = self.api("director", "POST", "/piecework", self.piecework_payload())
        self.assertEqual(self.sql("SELECT work_journal_id,total FROM piecework WHERE id=%s", (piecework["id"],)),
                         [(self.journal_id, 10)])
        self.assertEqual(self.sql("SELECT settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [(1,)])
        self.assertEqual(self.expense_state(), expenses)
        self.assert_net_usage(personal=1, warehouse=1)

    @with_initial_contract_type(None)
    def test_unknown_contract_type_enters_canonical_settlement_only_after_valid_contractual_penalty(self):
        self.assertEqual(self.sql("SELECT contractor_type,settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [(None, 1)])
        self.assert_net_usage(personal=1, warehouse=1)
        expenses = self.expense_state()
        defect, _ = self.create_defect()
        decision_path = self.path + "/material-defects/" + str(defect["id"]) + "/decisions"
        before = self.contract_financial_snapshot()
        self.api("director", "POST", decision_path, self.decision_payload(), expected=409)
        self.assertEqual(self.contract_financial_snapshot(), before)
        worker = self.f["users"]["worker"]
        self.api("director", "PUT", "/brigade-contracts/" + str(self.contract_id), {
            "contractorType": "Субподрядчик", "brigadeName": worker["name"], "totalAmount": 1000,
            "status": "Подписан", "signedAt": "2026-09-18", "workPackage": self.f["workPackage"],
        })
        self.assertEqual(self.sql("SELECT settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [(1,)])
        decision = self.api("director", "POST", decision_path, self.decision_payload())
        self.assertEqual(decision["status"], "confirmed")
        self.assertEqual(Decimal(str(decision["amount"])), Decimal("10"))
        self.assertEqual(self.sql("SELECT contractor_type,settlement_version FROM brigade_contracts WHERE id=%s",
                                  (self.contract_id,)), [("Субподрядчик", 2)])
        self.api("director", "PUT", self.path,
                 {"status": "Подтверждено", "roomName": "Synthetic clarified subcontract room"})
        requests = (("/piecework", self.piecework_payload()), ("/interim-acts", {
            "masterId": worker["id"], "masterName": worker["name"], "project": self.f["project"],
            "workPackage": self.f["workPackage"], "periodStart": "2026-09-18", "periodEnd": "2026-09-18",
            "totalAmount": 10, "contractId": self.contract_id, "workJournalIds": [self.journal_id],
        }))
        for path, payload in requests:
            with self.subTest(path=path):
                before = self.contract_financial_snapshot()
                self.api("director", "POST", path, payload, expected=409)
                self.assertEqual(self.contract_financial_snapshot(), before)
        self.assertEqual(self.expense_state(), expenses)
        self.assert_net_usage(personal=1, warehouse=1)

    def test_tenant_defect_photograph_requires_exact_registered_owner_without_stock_changes(self):
        own_url = self.registered_file(content_type="image/jpeg")
        expenses = self.expense_state()
        defect, _ = self.create_defect(photos=[own_url])
        self.assertEqual(defect["photos"], [own_url])
        self.assertEqual(self.expense_state(), expenses)
        foreign_project = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,3) RETURNING id",
                                   ("Synthetic foreign defect photograph " + uuid4().hex,))[0][0]
        foreign_url = self.registered_file(company_id=3, project_id=foreign_project, content_type="image/jpeg")
        before = (self.snapshot(), self.sql("SELECT * FROM file_ownership ORDER BY id"))
        self.api("foreman", "POST", self.path + "/material-defects",
                 self.defect_payload(photos=[foreign_url]), expected=404)
        self.assertEqual((self.snapshot(), self.sql("SELECT * FROM file_ownership ORDER BY id")), before)
        self.assertEqual(self.expense_state(), expenses)


if __name__ == "__main__":
    unittest.main()
