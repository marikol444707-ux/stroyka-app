"""Acceptance integration invariants on the disposable socket-only PG fixture.

SQL arranges synthetic existing documents; decisions and resubmissions always
use authenticated HTTP. No acceptance, stock, scope or synchronization mocks.
"""
from decimal import Decimal
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest

from backend.features.work_acceptance import test_postgres as lifecycle


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class WorkAcceptanceIntegrationPostgresTests(unittest.TestCase):
    # Borrow the lifecycle fixture without collecting its tests a second time.
    sql = lifecycle.WorkAcceptancePostgresTests.sql
    api = lifecycle.WorkAcceptancePostgresTests.api
    payload = lifecycle.WorkAcceptancePostgresTests.payload
    balance = lifecycle.WorkAcceptancePostgresTests.balance
    work_payload = lifecycle.WorkAcceptancePostgresTests.work_payload
    request = lifecycle.WorkAcceptancePostgresTests.request
    consumption_payload = lifecycle.WorkAcceptancePostgresTests.consumption_payload
    create_consumption = lifecycle.WorkAcceptancePostgresTests.create_consumption
    stock_quantity = lifecycle.WorkAcceptancePostgresTests.stock_quantity
    registered_file = lifecycle.WorkAcceptancePostgresTests.registered_file
    expense_state = lifecycle.WorkAcceptancePostgresTests.expense_state
    view = lifecycle.WorkAcceptancePostgresTests.view
    review_payload = lifecycle.WorkAcceptancePostgresTests.review_payload
    review = lifecycle.WorkAcceptancePostgresTests.review
    partial = lifecycle.WorkAcceptancePostgresTests.partial
    resubmit_payload = lifecycle.WorkAcceptancePostgresTests.resubmit_payload
    resubmit = lifecycle.WorkAcceptancePostgresTests.resubmit
    assert_work = lifecycle.WorkAcceptancePostgresTests.assert_work
    assert_original_entries_unchanged = lifecycle.WorkAcceptancePostgresTests.assert_original_entries_unchanged
    assert_rejected_unchanged = lifecycle.WorkAcceptancePostgresTests.assert_rejected_unchanged

    @classmethod
    def setUpClass(cls):
        lifecycle.WorkAcceptancePostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        estimate_id = self.fixture["estimateId"]
        original_sections = self.sql("SELECT sections_json FROM estimates WHERE id=%s", (estimate_id,))[0][0]
        self.addCleanup(self.sql, "UPDATE estimates SET sections_json=%s WHERE id=%s",
                        (original_sections, estimate_id))
        lifecycle.WorkAcceptancePostgresTests.setUp(self)
        self.sql("DELETE FROM hidden_works_acts")

    def snapshot(self):
        return lifecycle.WorkAcceptancePostgresTests.snapshot(self) + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in ("estimates", "hidden_works_acts"))

    def document_snapshot(self, table, record_id):
        self.assertIn(table, ("hidden_works_acts", "interim_acts"))
        return self.sql("SELECT row_to_json(t)::text FROM " + table + " t WHERE id=%s", (record_id,))

    def bind_estimate(self, duplicate_names=False):
        estimate_id = self.f["estimateId"]
        target = {"id": "acceptance-target", "name": "Synthetic work", "unit": "шт",
                  "quantity": 1, "doneQuantity": 1}
        items = [target]
        if duplicate_names:
            items.insert(0, {**target, "id": "acceptance-other", "doneQuantity": 0.25})
        self.sql("UPDATE estimates SET sections_json=%s WHERE id=%s",
                 (json.dumps([{"name": "Acceptance section", "items": items}]), estimate_id))
        self.sql("""UPDATE work_journal SET estimate_id=%s,estimate_item_key=%s,
            section_name='Acceptance section',estimate_item_name='Synthetic work' WHERE id=%s""",
                 (estimate_id, target["id"], self.journal_id))
        self.sql("UPDATE room_works SET estimate_item_key=%s WHERE work_journal_id=%s",
                 (target["id"], self.journal_id))
        return estimate_id

    def estimate_done(self, estimate_id):
        sections = self.sql("SELECT sections_json FROM estimates WHERE id=%s", (estimate_id,))[0][0]
        if isinstance(sections, str):
            sections = json.loads(sections)
        return {item["id"]: Decimal(str(item["doneQuantity"]))
                for section in sections for item in section["items"]}

    def seed_hidden_act(self, status="Черновик", linked=True):
        self.sql("UPDATE work_journal SET hidden_work=TRUE WHERE id=%s", (self.journal_id,))
        return self.sql("""INSERT INTO hidden_works_acts
            (company_id,project_name,estimate_id,act_number,work_name,section_name,work_package,
             brigade,quantity,unit,price_per_unit,total,work_date,status,work_journal_id,photos)
            SELECT company_id,project,estimate_id,'SYNTHETIC-ACCEPTANCE',description,section_name,
                work_package,master_name,quantity,unit,price_per_unit,total,date::date,%s,%s,photo_url
            FROM work_journal WHERE id=%s RETURNING id""",
                        (status, self.journal_id if linked else None, self.journal_id))[0][0]

    def set_contract_capacity(self, quantity):
        self.api("director", "PUT", "/brigade-contract-items/" + str(self.contract_item), {
            "quantity": quantity, "priceBrigade": 10, "priceSmeta": 30,
        })

    def seed_other_accepted_work(self, quantity):
        worker = self.f["users"]["worker"]
        journal_id = self.sql("""INSERT INTO work_journal
            (company_id,master_id,master_name,project,description,unit,quantity,date,status,
             room_name,work_package,contract_item_id,execution_price_per_unit,execution_total)
            VALUES(2,%s,%s,%s,'Other already accepted work','шт',%s,'2026-09-18','Подтверждено',
                'Other accepted room',%s,%s,10,%s) RETURNING id""",
            (worker["id"], worker["name"], self.f["project"], quantity, self.f["workPackage"],
             self.contract_item, Decimal(str(quantity)) * 10))[0][0]
        self.sql("""UPDATE brigade_contract_items SET done_quantity=(SELECT SUM(quantity)
            FROM work_journal WHERE contract_item_id=%s AND status='Подтверждено') WHERE id=%s""",
                 (self.contract_item, self.contract_item))
        return journal_id

    def assert_capacity_rejection(self, journal_id, **changes):
        payload = self.review_payload(journal_id, **changes)
        before = self.snapshot()
        response = self.request("POST", f"/work-journal/{journal_id}/acceptance", payload, actor="director")
        self.assertIn(response.status_code, (400, 409), response.text)
        self.assertEqual(self.snapshot(), before)

    def test_split_keeps_submitted_price_snapshot_after_contract_price_changes(self):
        self.sql("""UPDATE work_journal SET customer_price_per_unit=30,customer_total=30
            WHERE id=%s""", (self.journal_id,))
        self.api("director", "PUT", "/brigade-contract-items/" + str(self.contract_item), {
            "quantity": 100, "priceBrigade": 99, "priceSmeta": 200,
        })
        expense = self.expense_state()
        child = self.partial()
        for journal_id, amount in ((self.journal_id, Decimal("0.6")), (child, Decimal("0.4"))):
            row = self.sql("""SELECT quantity,price_per_unit,total,execution_price_per_unit,
                execution_total,customer_price_per_unit,customer_total FROM work_journal WHERE id=%s""",
                           (journal_id,))[0]
            self.assertEqual(tuple(Decimal(str(value)) for value in row),
                             (amount, Decimal(10), amount * 10, Decimal(10), amount * 10,
                              Decimal(30), amount * 30))
        self.resubmit(child)
        self.review(child)
        preview = self.api("director", "GET", self.contract_path + "/settlement")
        self.assertEqual(Decimal(str(preview["grossAmount"])), Decimal(10))
        self.assertEqual(self.expense_state(), expense)
        self.assert_original_entries_unchanged()

    def test_partial_acceptance_rejects_capacity_overflow_instead_of_clamping_done(self):
        self.set_contract_capacity(1)
        self.seed_other_accepted_work("0.75")
        self.assert_capacity_rejection(self.journal_id, acceptedQuantity="0.6", reason="Доработать остаток")
        self.assert_work(self.journal_id, "На проверке", 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_rework_links"), [(0,)])

    def test_fractional_contract_capacity_accepts_exact_remaining_volume(self):
        self.set_contract_capacity(1)
        self.seed_other_accepted_work("0.1")
        self.seed_other_accepted_work("0.2")
        expense = self.expense_state()
        result, _ = self.review(acceptedQuantity="0.7", reason="Остаток требует доработки")
        self.assert_work(self.journal_id, "Подтверждено", "0.7")
        self.assert_work(result["reworkJournalId"], "На доработке", "0.3")
        accepted = self.sql("""SELECT quantity FROM work_journal
            WHERE contract_item_id=%s AND status='Подтверждено'""", (self.contract_item,))
        self.assertEqual(sum(Decimal(str(row[0])) for row in accepted), Decimal(1))
        self.assertEqual(self.expense_state(), expense)

    def test_fractional_estimate_capacity_accepts_exact_remaining_volume(self):
        # Contract headroom isolates the estimate's own fractional SUM boundary.
        self.set_contract_capacity(10)
        estimate_id = self.bind_estimate()
        prior_ids = [self.seed_other_accepted_work(value) for value in ("0.1", "0.2")]
        self.sql("""UPDATE work_journal SET estimate_id=%s,estimate_item_key='acceptance-target'
            WHERE id=ANY(%s)""", (estimate_id, prior_ids))
        expense = self.expense_state()
        result, _ = self.review(acceptedQuantity="0.7", reason="Остаток требует доработки")
        self.assert_work(self.journal_id, "Подтверждено", "0.7")
        self.assert_work(result["reworkJournalId"], "На доработке", "0.3")
        self.assertEqual(self.estimate_done(estimate_id)["acceptance-target"], Decimal(1))
        self.assertEqual(self.expense_state(), expense)

    def test_pending_rework_quantity_is_not_credited_against_already_used_capacity(self):
        self.set_contract_capacity(1)
        child = self.partial()
        self.resubmit(child)
        self.seed_other_accepted_work("0.4")
        self.assert_capacity_rejection(child)
        self.assert_work(child, "На проверке", "0.4")
        self.assertEqual(Decimal(str(self.sql("""SELECT SUM(quantity) FROM work_journal
            WHERE contract_item_id=%s AND status='Подтверждено'""", (self.contract_item,))[0][0])), Decimal(1))

    def test_estimate_recalculation_prefers_exact_key_over_earlier_duplicate_name(self):
        estimate_id = self.bind_estimate(duplicate_names=True)
        child = self.partial()
        self.assertEqual(self.estimate_done(estimate_id), {
            "acceptance-other": Decimal("0.25"), "acceptance-target": Decimal("0.6"),
        })
        self.resubmit(child)
        self.review(child)
        self.assertEqual(self.estimate_done(estimate_id), {
            "acceptance-other": Decimal("0.25"), "acceptance-target": Decimal(1),
        })
        self.assertEqual(self.sql("""SELECT DISTINCT estimate_id,estimate_item_key FROM work_journal
            WHERE id=ANY(%s)""", ([self.journal_id, child],)), [(estimate_id, "acceptance-target")])

    def test_partial_acceptance_cannot_diverge_from_exact_signed_hidden_act(self):
        hidden_id = self.seed_hidden_act(status="Подписан")
        before = self.document_snapshot("hidden_works_acts", hidden_id)
        self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance",
            self.review_payload(acceptedQuantity="0.6", reason="Нужна частичная доработка"), 409)
        self.assertEqual(self.document_snapshot("hidden_works_acts", hidden_id), before)

    def test_full_return_cannot_diverge_from_exact_signed_hidden_act(self):
        hidden_id = self.seed_hidden_act(status="Подписан")
        before = self.document_snapshot("hidden_works_acts", hidden_id)
        self.assert_rejected_unchanged("director", "POST", self.path + "/acceptance",
            self.review_payload(decision="return", acceptedQuantity=None, reason="Весь объём на доработку"), 409)
        self.assertEqual(self.document_snapshot("hidden_works_acts", hidden_id), before)

    def test_child_room_and_hidden_documents_keep_exact_journal_ownership(self):
        self.bind_estimate()
        unrelated_id = self.seed_hidden_act(status="Подписан", linked=False)
        parent_id = self.seed_hidden_act()
        unrelated = self.document_snapshot("hidden_works_acts", unrelated_id)
        child = self.partial()
        self.assertEqual(self.sql("SELECT work_journal_id,quantity FROM hidden_works_acts WHERE id=%s",
                                  (parent_id,)), [(self.journal_id, Decimal("0.6"))])
        parent_after_review = self.document_snapshot("hidden_works_acts", parent_id)
        replacement_photo = self.registered_file(content_type="image/jpeg")
        self.resubmit(child, photos=[replacement_photo])
        self.review(child)
        self.assertEqual(self.sql("""SELECT work_journal_id,status,quantity,photo_url FROM room_works
            WHERE work_journal_id=ANY(%s) ORDER BY work_journal_id""", ([self.journal_id, child],)), [
            (self.journal_id, "Подтверждено", 0.6, self.photo),
            (child, "Подтверждено", 0.4, replacement_photo),
        ])
        self.assertEqual(self.sql("SELECT work_journal_id,quantity FROM hidden_works_acts WHERE work_journal_id=%s",
                                  (child,)), [(child, Decimal("0.4"))])
        self.assertEqual(self.document_snapshot("hidden_works_acts", parent_id), parent_after_review)
        self.assertEqual(self.document_snapshot("hidden_works_acts", unrelated_id), unrelated)

    def test_full_return_annuls_only_exact_parent_hidden_draft(self):
        parent_id = self.seed_hidden_act()
        unrelated_id = self.seed_hidden_act(linked=False)
        unrelated = self.document_snapshot("hidden_works_acts", unrelated_id)
        result, _ = self.review(decision="return", acceptedQuantity=None, reason="Весь объём на доработку")
        self.assertEqual(self.sql("SELECT status,work_journal_id FROM hidden_works_acts WHERE id=%s",
                                  (parent_id,)), [("Аннулирован", self.journal_id)])
        child = result["reworkJournalId"]
        self.resubmit(child)
        self.assertEqual(self.sql("SELECT work_journal_id,quantity FROM hidden_works_acts WHERE work_journal_id=%s",
                                  (child,)), [(child, Decimal(1))])
        self.assertEqual(self.document_snapshot("hidden_works_acts", unrelated_id), unrelated)

    def test_returned_parent_hidden_act_cannot_be_reopened_or_signed(self):
        parent_id = self.seed_hidden_act()
        self.review(decision="return", acceptedQuantity=None, reason="Весь объём на доработку")
        self.assertEqual(self.sql("SELECT status FROM hidden_works_acts WHERE id=%s", (parent_id,)),
                         [("Аннулирован",)])
        for status in ("Черновик", "Подписан"):
            with self.subTest(status=status):
                self.assert_rejected_unchanged("director", "PUT", f"/hidden-works-acts/{parent_id}",
                                              {"status": status}, 409)

    def test_hidden_signature_waits_for_concurrent_return_and_cannot_revive_parent(self):
        parent_id = self.seed_hidden_act()
        payload = self.review_payload(decision="return", acceptedQuantity=None,
                                      reason="Весь объём на доработку")
        # A real database trigger pauses only scheduling, after review validation.
        # Both competing mutations still execute their production HTTP/SQL paths.
        self.sql("""CREATE FUNCTION acceptance_concurrency_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914230,1); RETURN NEW; END $$""")
        self.addCleanup(self.sql, "DROP FUNCTION acceptance_concurrency_pause() CASCADE")
        self.sql("""CREATE TRIGGER acceptance_concurrency_pause BEFORE INSERT ON work_acceptance_reviews
            FOR EACH ROW EXECUTE FUNCTION acceptance_concurrency_pause()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914230,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", self.path + "/acceptance", payload, actor="director")
                try:
                    deadline = time.monotonic() + 5
                    paused = []
                    while time.monotonic() < deadline:
                        paused = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event='advisory'
                              AND query LIKE 'INSERT INTO work_acceptance_reviews%%'""")
                        if paused:
                            break
                        if first.done():
                            self.fail("Return did not reach its acceptance INSERT: " + first.result().text)
                        time.sleep(0.02)
                    self.assertEqual(len(paused), 1, "Return must pause after validating the hidden act")
                    second = pool.submit(self.request, "PUT", f"/hidden-works-acts/{parent_id}",
                                         {"status": "Подписан"}, actor="director")
                    deadline = time.monotonic() + 5
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT pid FROM pg_stat_activity
                            WHERE datname=current_database() AND wait_event_type='Lock' AND pid<>%s""",
                                           (paused[0][0],))
                        if waiting or second.done():
                            break
                        time.sleep(0.02)
                    self.assertTrue(waiting or second.done(), "Signature must reach its database mutation")
                finally:
                    blocker.rollback()
                reviewed, signed = first.result(timeout=15), second.result(timeout=15)
            self.assertEqual(reviewed.status_code, 200, reviewed.text)
            self.assertEqual(signed.status_code, 409, signed.text)
            self.assert_work(self.journal_id, "Отклонено", 1)
            self.assertEqual(self.sql("SELECT status,quantity FROM hidden_works_acts WHERE id=%s", (parent_id,)),
                             [("Аннулирован", Decimal(1))])
        finally:
            blocker.rollback()
            blocker.close()

    def test_locked_daily_act_is_preserved_and_successor_contains_only_new_numeric_ids(self):
        today = date.today().isoformat()
        self.sql("UPDATE work_journal SET date=%s WHERE id=%s", (today, self.journal_id))
        child = self.partial()
        rows = self.sql("""SELECT id,total_amount,work_journal_ids FROM interim_acts
            WHERE source_type='daily_work' ORDER BY id""")
        self.assertEqual(len(rows), 1)
        locked_id, first_amount, first_ids = rows[0]
        self.assertEqual(Decimal(str(first_amount)), Decimal(6))
        self.assertEqual(json.loads(first_ids), [self.journal_id])
        self.assertIs(type(json.loads(first_ids)[0]), int)
        self.sql("UPDATE interim_acts SET status='Подписан' WHERE id=%s", (locked_id,))
        locked = self.document_snapshot("interim_acts", locked_id)
        self.resubmit(child)
        result, payload = self.review(child)
        self.assertEqual(self.document_snapshot("interim_acts", locked_id), locked)
        successor = self.sql("""SELECT total_amount,paid_amount,status,work_journal_ids,period_start,period_end
            FROM interim_acts WHERE source_type='daily_work' AND id<>%s""", (locked_id,))
        self.assertEqual(len(successor), 1)
        amount, paid, status, work_ids, start, end = successor[0]
        self.assertEqual((Decimal(str(amount)), Decimal(str(paid)), status), (Decimal(4), Decimal(0), "Новый"))
        self.assertEqual(json.loads(work_ids), [child])
        self.assertEqual((str(start), str(end)), (today, today))
        before = self.snapshot()
        self.assertEqual(self.api("director", "POST", f"/work-journal/{child}/acceptance", payload), result)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
