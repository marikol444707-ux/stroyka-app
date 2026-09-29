"""Authenticated acceptance/rework conservation on disposable socket-only PG."""
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.features.work_material_accounting import test_postgres as support
from backend.features.work_material_accounting import test_defects_postgres as files


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class WorkAcceptancePostgresTests(unittest.TestCase):
    sql = support.WorkMaterialAccountingPostgresTests.sql
    api = support.WorkMaterialAccountingPostgresTests.api
    payload = support.WorkMaterialAccountingPostgresTests.payload
    balance = support.WorkMaterialAccountingPostgresTests.balance
    work_payload = support.WorkMaterialAccountingPostgresTests.work_payload
    request = support.WorkMaterialAccountingPostgresTests.request
    consumption_payload = support.WorkMaterialAccountingPostgresTests.consumption_payload
    create_consumption = support.WorkMaterialAccountingPostgresTests.create_consumption
    stock_quantity = support.WorkMaterialAccountingPostgresTests.stock_quantity
    registered_file = files.MaterialDefectsPostgresTests.registered_file

    @classmethod
    def setUpClass(cls):
        support.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)
        flag = patch.dict(os.environ, {"WORK_ACCEPTANCE_ENABLED": "1"})
        flag.start()
        cls.addClassCleanup(flag.stop)
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0028_work_acceptance.py"
        spec = importlib.util.spec_from_file_location("acceptance_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType("alembic")
        alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(migration)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                before = {row[0] for row in cur.fetchall()}
                with patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                    migration.upgrade()
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                cls.new_tables = sorted(set(cls.new_tables) | ({row[0] for row in cur.fetchall()} - before))
        finally:
            conn.close()

    def setUp(self):
        support.WorkMaterialAccountingPostgresTests.setUp(self)
        for table in ("brigade_payments", "project_payments", "interim_acts", "piecework", "file_ownership"):
            self.sql("DELETE FROM " + table)
        self.contract_id = self.sql("SELECT contract_id FROM brigade_contract_items WHERE id=%s",
                                    (self.contract_item,))[0][0]
        self.sql("UPDATE brigade_contracts SET contractor_type='Субподрядчик',status='Подписан' WHERE id=%s",
                 (self.contract_id,))
        self.photo = self.registered_file(content_type="image/jpeg")
        journal, self.submission = self.create_consumption(
            personal=1, warehouse=1, roomName="Synthetic acceptance room", photoUrl=self.photo,
            comment="Исходный объём предъявлен к приёмке")
        self.journal_id = journal["id"]
        self.path = "/work-journal/" + str(self.journal_id)
        self.contract_path = "/brigade-contracts/" + str(self.contract_id)
        self.original_entries = self.sql("SELECT * FROM work_material_entries WHERE journal_id=%s ORDER BY id",
                                         (self.journal_id,))

    def snapshot(self):
        tables = ("brigade_contracts", "brigade_acts", "brigade_payments", "project_payments",
                  "interim_acts", "piecework", "file_ownership")
        return support.WorkMaterialAccountingPostgresTests.snapshot(self) + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in tables)

    def expense_state(self):
        return tuple((table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
                     for table in ("materials", "material_transfers", "warehouse_history", "work_material_entries"))

    def view(self, journal_id=None, actor="director"):
        return self.api(actor, "GET", "/work-journal/" + str(journal_id or self.journal_id) + "/acceptance")

    def review_payload(self, journal_id=None, **changes):
        view = self.view(journal_id)
        return {"requestId": str(uuid4()), "expectedState": view["expectedState"], "decision": "accept",
                "acceptedQuantity": view["quantity"], "reason": "", "photos": [], **changes}

    def review(self, journal_id=None, **changes):
        journal_id = journal_id or self.journal_id
        payload = self.review_payload(journal_id, **changes)
        result = self.api("director", "POST", "/work-journal/" + str(journal_id) + "/acceptance", payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["journalId"], journal_id)
        self.assertTrue(result["reviewId"])
        return result, payload

    def partial(self):
        result, _ = self.review(acceptedQuantity="0.6", reason="Доработать оставшийся участок")
        self.assertTrue(result["reworkJournalId"])
        return result["reworkJournalId"]

    def resubmit_payload(self, child_id, **changes):
        return {"requestId": str(uuid4()), "expectedState": self.view(child_id, "worker")["expectedState"],
                "comment": "Замечания устранены, повторная сдача", "photos": [self.photo],
                "materialsUsed": [], **changes}

    def resubmit(self, child_id, **changes):
        payload = self.resubmit_payload(child_id, **changes)
        result = self.api("worker", "POST", f"/work-journal/{child_id}/resubmit", payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["journalId"], child_id)
        return result, payload

    def assert_rejected_unchanged(self, actor, method, path, payload, expected):
        before = self.snapshot()
        self.api(actor, method, path, payload, expected=expected)
        self.assertEqual(self.snapshot(), before)

    def assert_original_entries_unchanged(self):
        self.assertEqual(self.sql("SELECT * FROM work_material_entries WHERE journal_id=%s ORDER BY id",
                                  (self.journal_id,)), self.original_entries)

    def assert_work(self, journal_id, status, quantity):
        row = self.sql("""SELECT status,quantity,company_id,project,master_id,contract_item_id,work_package
            FROM work_journal WHERE id=%s""", (journal_id,))[0]
        self.assertEqual(row[0], status)
        self.assertEqual(Decimal(str(row[1])), Decimal(str(quantity)))
        self.assertEqual(row[2:], (2, self.f["project"], self.f["users"]["worker"]["id"],
                                  self.contract_item, self.f["workPackage"]))

    def create_act(self, journal_id):
        preview = self.api("director", "GET", self.contract_path + "/settlement")
        self.assertEqual([row["id"] for row in preview["eligibleWorks"]], [journal_id])
        work_date = str(self.sql("SELECT date FROM work_journal WHERE id=%s", (journal_id,))[0][0])
        return self.api("director", "POST", self.contract_path + "/acts", {
            "requestId": str(uuid4()), "workJournalIds": [journal_id],
            "expectedGrossAmount": str(preview["grossAmount"]), "expectedFineAmount": str(preview["fineAmount"]),
            "fineAllocations": preview["fineAllocations"], "periodFrom": work_date, "periodTo": work_date,
        })

    def test_preview_exposes_state_history_and_role_actions(self):
        director = self.view()
        self.assertEqual(director["journalId"], self.journal_id)
        self.assertEqual(director["status"], "На проверке")
        self.assertEqual(director["quantity"], 1)
        self.assertTrue(director["expectedState"])
        self.assertTrue(director["canReview"])
        self.assertFalse(director["canResubmit"])
        self.assertEqual(director["history"], [])
        self.assertIsNone(director["reworkJournalId"])
        self.assertIsNone(director["parentJournalId"])
        worker = self.view(actor="worker")
        self.assertFalse(worker["canReview"])
        self.assertFalse(worker["canResubmit"])

    def test_partial_resubmit_accept_conserves_volume_materials_and_total_gross(self):
        expense = self.expense_state()
        child = self.partial()
        self.assert_work(self.journal_id, "Подтверждено", "0.6")
        self.assert_work(child, "На доработке", "0.4")
        self.assertEqual(self.view()["reworkJournalId"], child)
        child_view = self.view(child, "worker")
        self.assertEqual(child_view["parentJournalId"], self.journal_id)
        self.assertTrue(child_view["canResubmit"])
        self.assertEqual(len(self.view()["history"]), 1)
        self.resubmit(child)
        self.assert_work(child, "На проверке", "0.4")
        accepted, _ = self.review(child)
        self.assertIsNone(accepted["reworkJournalId"])
        self.assert_work(child, "Подтверждено", "0.4")
        preview = self.api("director", "GET", self.contract_path + "/settlement")
        self.assertEqual({row["id"] for row in preview["eligibleWorks"]}, {self.journal_id, child})
        self.assertEqual(Decimal(str(preview["grossAmount"])), Decimal("10"))
        self.assertEqual(self.expense_state(), expense)
        self.assert_original_entries_unchanged()

    def test_full_return_creates_full_rework_without_reversing_materials(self):
        expense = self.expense_state()
        result, _ = self.review(decision="return", acceptedQuantity=None, reason="Работа не принята")
        self.assert_work(self.journal_id, "Отклонено", 1)
        self.assert_work(result["reworkJournalId"], "На доработке", 1)
        self.assertEqual(self.expense_state(), expense)
        self.assertEqual(self.balance(), dict(issued=2, used=1, returned=0, available=1))

    def test_review_replay_returns_same_child_and_changed_command_is_conflict(self):
        result, payload = self.review(acceptedQuantity="0.6", reason="Доработать участок")
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", self.path + "/acceptance", payload), result)
        self.assertEqual(self.snapshot(), before)
        for changed in ({**payload, "acceptedQuantity": "0.5"}, {**payload, "requestId": str(uuid4())}):
            self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance", changed, 409)

    def test_acceptance_invalid_volumes_or_missing_rework_reason_leave_everything_unchanged(self):
        for changes in ({"acceptedQuantity": 0}, {"acceptedQuantity": -1}, {"acceptedQuantity": 2},
                        {"acceptedQuantity": "0.6"}, {"decision": "return", "acceptedQuantity": None}):
            with self.subTest(changes=changes):
                self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance",
                                               self.review_payload(**changes), 400)

    def test_review_requires_reviewer_and_foreign_company_cannot_read_or_decide(self):
        payload = self.review_payload()
        for actor in ("worker", "accountant"):
            self.assert_rejected_unchanged(actor, "POST", self.path + "/acceptance", payload, 403)
        for method, data in (("GET", None), ("POST", payload)):
            self.assert_rejected_unchanged("stranger", method, self.path + "/acceptance", data, 404)

    def test_new_review_photo_must_belong_to_exact_active_company_and_project(self):
        other_project = self.sql("INSERT INTO projects(name,company_id) VALUES('Other acceptance project',2) RETURNING id")[0][0]
        for fields in ({"company_id": 3}, {"project_id": other_project}, {"deletion_status": "deleted"}):
            with self.subTest(file=fields):
                photo = self.registered_file(content_type="image/jpeg", **fields)
                self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance",
                                               self.review_payload(photos=[photo]), 404)

    def test_hidden_work_accepted_only_with_owned_existing_photo(self):
        self.sql("UPDATE work_journal SET hidden_work=TRUE,photo_url=%s WHERE id=%s",
                 (self.registered_file(company_id=3, content_type="image/jpeg"), self.journal_id))
        self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance", self.review_payload(), 404)
        self.sql("UPDATE work_journal SET photo_url=%s WHERE id=%s", (self.photo, self.journal_id))
        self.review()
        self.assert_work(self.journal_id, "Подтверждено", 1)

    def test_resubmit_requires_original_worker_comment_and_owned_photo(self):
        child = self.partial()
        path = f"/work-journal/{child}/resubmit"
        payload = self.resubmit_payload(child)
        for actor in ("director", "foreman", "other_worker"):
            self.assert_rejected_unchanged(actor, "POST", path, payload, 403)
        for changes in ({"comment": ""}, {"photos": []}):
            self.assert_rejected_unchanged("worker", "POST", path, {**payload, **changes}, 400)
        foreign = self.registered_file(company_id=3, content_type="image/jpeg")
        self.assert_rejected_unchanged("worker", "POST", path, {**payload, "photos": [foreign]}, 404)

    def test_resubmit_additional_materials_are_atomic_and_replayed_only_once(self):
        child = self.partial()
        path = f"/work-journal/{child}/resubmit"
        too_much = self.consumption_payload(personal=2)["materialsUsed"]
        self.assert_rejected_unchanged("worker", "POST", path,
                                       self.resubmit_payload(child, materialsUsed=too_much), 400)
        extra = self.consumption_payload(personal=0.5, warehouse=0.25)["materialsUsed"]
        result, payload = self.resubmit(child, materialsUsed=extra)
        self.assert_work(child, "На проверке", "0.4")
        self.assertEqual(self.stock_quantity(), 0.75)
        self.assertEqual(self.balance(), dict(issued=2, used=1.5, returned=0, available=0.5))
        self.assert_original_entries_unchanged()
        before = self.snapshot()
        self.assertEqual(self.api("worker", "POST", path, payload), result)
        self.assertEqual(self.snapshot(), before)
        self.assert_rejected_unchanged("worker", "POST", path, {**payload, "comment": "Changed"}, 409)

    def test_managed_parent_and_child_cannot_be_changed_or_deleted_when_flag_is_off(self):
        child = self.partial()
        for enabled in ("1", "0"):
            with patch.dict(os.environ, {"WORK_ACCEPTANCE_ENABLED": enabled}):
                for journal in (self.journal_id, child):
                    for method, payload in (("PUT", {"quantity": 0.2}), ("DELETE", None)):
                        with self.subTest(enabled=enabled, journal=journal, method=method):
                            self.assert_rejected_unchanged("director", method, f"/work-journal/{journal}", payload, 409)

    def test_accepted_rework_does_not_rewrite_already_formed_parent_act(self):
        child = self.partial()
        first = self.create_act(self.journal_id)
        self.assertEqual(Decimal(str(first["totalAmount"])), Decimal("6"))
        saved = self.sql("SELECT row_to_json(t)::text FROM brigade_acts t WHERE id=%s", (first["id"],))
        self.resubmit(child)
        self.review(child)
        second = self.create_act(child)
        self.assertEqual(Decimal(str(second["totalAmount"])), Decimal("4"))
        self.assertEqual(Decimal(str(first["totalAmount"])) + Decimal(str(second["totalAmount"])), Decimal("10"))
        self.assertEqual(self.sql("SELECT row_to_json(t)::text FROM brigade_acts t WHERE id=%s", (first["id"],)), saved)
        self.assert_original_entries_unchanged()


if __name__ == "__main__":
    unittest.main()
