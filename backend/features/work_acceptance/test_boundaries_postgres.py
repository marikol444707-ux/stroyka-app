"""Rework material-package boundaries through real HTTP and PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import unittest
from uuid import uuid4

from psycopg2.extras import Json

from backend.features.work_acceptance import test_postgres as lifecycle


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires fresh explicitly provisioned PostgreSQL database")
class WorkAcceptanceBoundaryPostgresTests(unittest.TestCase):
    sql = lifecycle.WorkAcceptancePostgresTests.sql
    api = lifecycle.WorkAcceptancePostgresTests.api
    payload = lifecycle.WorkAcceptancePostgresTests.payload
    balance = lifecycle.WorkAcceptancePostgresTests.balance
    work_payload = lifecycle.WorkAcceptancePostgresTests.work_payload
    request = lifecycle.WorkAcceptancePostgresTests.request
    consumption_payload = lifecycle.WorkAcceptancePostgresTests.consumption_payload
    create_consumption = lifecycle.WorkAcceptancePostgresTests.create_consumption
    stock_quantity = lifecycle.WorkAcceptancePostgresTests.stock_quantity
    expense_state = lifecycle.WorkAcceptancePostgresTests.expense_state
    registered_file = lifecycle.WorkAcceptancePostgresTests.registered_file
    snapshot = lifecycle.WorkAcceptancePostgresTests.snapshot
    view = lifecycle.WorkAcceptancePostgresTests.view
    review_payload = lifecycle.WorkAcceptancePostgresTests.review_payload
    review = lifecycle.WorkAcceptancePostgresTests.review
    partial = lifecycle.WorkAcceptancePostgresTests.partial
    resubmit_payload = lifecycle.WorkAcceptancePostgresTests.resubmit_payload
    resubmit = lifecycle.WorkAcceptancePostgresTests.resubmit
    assert_rejected_unchanged = lifecycle.WorkAcceptancePostgresTests.assert_rejected_unchanged

    @classmethod
    def setUpClass(cls):
        lifecycle.WorkAcceptancePostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        lifecycle.WorkAcceptancePostgresTests.setUp(self)

    def additional_package(self):
        package = "Synthetic second assigned package"
        worker_id = self.f["users"]["worker"]["id"]
        for table, condition, params in (
                ("users", "id=%s", (worker_id,)),
                ("user_company_roles", "user_id=%s AND company_id=2", (worker_id,))):
            original = self.sql("SELECT assigned_packages FROM " + table + " WHERE " + condition, params)[0][0]
            statement = "UPDATE " + table + " SET assigned_packages=%s WHERE " + condition
            self.addCleanup(self.sql, statement, (Json(original), *params))
            self.sql(statement, (Json([self.f["workPackage"], package]), *params))
        stock_id = self.sql("""INSERT INTO materials(company_id,name,unit,quantity,project,work_package)
            VALUES(2,%s,%s,2,%s,%s) RETURNING id""",
            (self.f["materialName"], self.f["unit"], self.f["project"], package))[0][0]
        return package, stock_id

    def test_resubmit_cannot_charge_another_assigned_package(self):
        package, stock_id = self.additional_package()
        child = self.partial()
        material = self.consumption_payload(warehouse=0.25)["materialsUsed"][0]
        material.update(workPackage=package, warehouseMaterialId=stock_id)
        self.assert_rejected_unchanged("worker", "POST", f"/work-journal/{child}/resubmit",
            self.resubmit_payload(child, materialsUsed=[material]), 400)

    def test_cross_package_personal_charge_cannot_leave_consumed_material_available_for_return(self):
        package, stock_id = self.additional_package()
        sections = [{"name": package, "items": [{"id": "rework-second-package-material",
            "name": self.f["materialName"], "type": "material", "itemType": "material",
            "unit": self.f["unit"], "quantity": 20, "price": 100, "workPackage": package}]}]
        estimate_id = self.sql("""INSERT INTO estimates(company_id,project_id,project_name,name,version,
            sections_json,status,is_template,smeta_type,work_package)
            VALUES(2,%s,%s,'Synthetic additional package allowance','1',%s,'Активная',FALSE,'Заказчик',%s)
            RETURNING id""", (self.f["projectId"], self.f["project"], json.dumps(sections), package))[0][0]
        self.addCleanup(self.sql, "DELETE FROM estimates WHERE id=%s", (estimate_id,))
        transfer = self.api("foreman", "POST", "/material-transfers", self.payload(2, workPackage=package))
        self.api("worker", "PUT", f"/material-transfers/{transfer['id']}/sign")
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE id=%s", (stock_id,)), [(0,)])
        child = self.partial()
        material = self.consumption_payload(personal=1)["materialsUsed"][0]
        material["workPackage"] = package
        before = self.snapshot()
        response = self.request("POST", f"/work-journal/{child}/resubmit",
                                self.resubmit_payload(child, materialsUsed=[material]))
        after = self.snapshot()
        # Returning the two unspent issued units is legitimate only because the
        # wrong-package work request must be rejected. On the buggy route the
        # work succeeds AND the same two units can still be returned in full.
        returned = self.api("worker", "POST", "/material-transfers/return", self.payload(2, workPackage=package))
        extra_entries = self.sql("SELECT source,quantity,work_package FROM work_material_entries WHERE journal_id=%s",
                                 (child,))
        self.assertEqual(response.status_code, 400,
                         f"resubmit={response.text}; returned={returned!r}; persisted extra consumption={extra_entries!r}")
        self.assertEqual(after, before)
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE id=%s", (stock_id,)), [(2,)])

    def test_resubmit_omitted_material_package_inherits_nondefault_work_package(self):
        package, stock_id = self.additional_package()
        item_id = self.sql("""INSERT INTO brigade_contract_items
            (contract_id,description,unit,quantity,price_brigade,work_package)
            VALUES(%s,'Synthetic work','шт',100,10,%s) RETURNING id""", (self.contract_id, package))[0][0]
        submission = self.consumption_payload(warehouse=0.25, workPackage=package,
            contractItemId=item_id, roomName="Second package room", photoUrl=self.photo)
        submission["materialsUsed"][0].update(workPackage=package, warehouseMaterialId=stock_id)
        journal = self.api("worker", "POST", "/work-journal", submission)["id"]
        review, _ = self.review(journal, acceptedQuantity="0.6", reason="Доработать остаток")
        child = review["reworkJournalId"]
        material = self.consumption_payload(warehouse=0.25)["materialsUsed"][0]
        material["warehouseMaterialId"] = stock_id
        self.assertNotIn("workPackage", material)
        self.resubmit(child, materialsUsed=[material])
        self.assertEqual(self.sql("SELECT quantity FROM materials WHERE id=%s", (stock_id,)), [(1.5,)])
        self.assertEqual(self.sql("SELECT DISTINCT work_package FROM work_material_entries WHERE journal_id=%s",
                                  (child,)), [(package,)])

    def test_owned_pdf_does_not_satisfy_required_rework_photo(self):
        child = self.partial()
        pdf = self.registered_file(content_type="application/pdf")
        self.assert_rejected_unchanged("worker", "POST", f"/work-journal/{child}/resubmit",
            self.resubmit_payload(child, photos=[pdf]), 400)

    def test_resubmit_malformed_material_package_is_validation_error_without_mutation(self):
        child = self.partial()
        material = self.consumption_payload(warehouse=0.25)["materialsUsed"][0]
        material["workPackage"] = 123
        before = self.snapshot()
        response = self.request("POST", f"/work-journal/{child}/resubmit",
                                self.resubmit_payload(child, materialsUsed=[material]))
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.snapshot(), before)
        # The failed request must also release its stock transaction.
        self.resubmit(child)

    def test_revoked_package_assignment_prevents_original_worker_resubmission(self):
        child = self.partial()
        payload = self.resubmit_payload(child)
        worker_id = self.f["users"]["worker"]["id"]
        for table, condition, params in (
                ("users", "id=%s", (worker_id,)),
                ("user_company_roles", "user_id=%s AND company_id=2", (worker_id,))):
            original = self.sql("SELECT assigned_packages FROM " + table + " WHERE " + condition, params)[0][0]
            statement = "UPDATE " + table + " SET assigned_packages=%s WHERE " + condition
            self.addCleanup(self.sql, statement, (Json(original), *params))
            self.sql(statement, (Json([]), *params))
        self.assert_rejected_unchanged("worker", "POST", f"/work-journal/{child}/resubmit", payload, 403)

    def test_concurrent_different_decisions_share_one_review_and_one_remainder(self):
        payload = self.review_payload(acceptedQuantity="0.6", reason="Доработать остаток")
        competing = {**payload, "requestId": str(uuid4()), "decision": "return",
                     "acceptedQuantity": None, "reason": "Конкурирующий возврат всего объёма"}
        expenses = self.expense_state()
        self.sql("""CREATE FUNCTION acceptance_boundary_pause() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM pg_advisory_xact_lock(914231,1); RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER acceptance_boundary_pause BEFORE INSERT ON work_acceptance_reviews
            FOR EACH ROW EXECUTE FUNCTION acceptance_boundary_pause()""")
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(914231,1)")
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.request, "POST", self.path + "/acceptance", payload, "director")
                try:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()
                            AND wait_event='advisory' AND query LIKE 'INSERT INTO work_acceptance_reviews%%'""")[0][0]
                        if waiting or first.done():
                            break
                        time.sleep(0.02)
                    self.assertEqual(waiting, 1, "First real decision must pause after validation and before review insertion")
                    second = pool.submit(self.request, "POST", self.path + "/acceptance", competing, "director")
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        waiting = self.sql("""SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()
                            AND wait_event_type='Lock' AND query LIKE 'LOCK TABLE materials, warehouse_main, projects%%'""")[0][0]
                        if waiting or second.done():
                            break
                        time.sleep(0.02)
                    self.assertEqual(waiting, 1, "Competing decision must wait for the first transaction")
                finally:
                    blocker.rollback()
                first_result, second_result = first.result(timeout=20), second.result(timeout=20)
        finally:
            blocker.close()
            self.sql("DROP TRIGGER acceptance_boundary_pause ON work_acceptance_reviews")
            self.sql("DROP FUNCTION acceptance_boundary_pause()")
        self.assertEqual(first_result.status_code, 200, first_result.text)
        self.assertEqual(second_result.status_code, 409, second_result.text)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_acceptance_reviews WHERE journal_id=%s",
                                  (self.journal_id,)), [(1,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM work_rework_links WHERE parent_journal_id=%s",
                                  (self.journal_id,)), [(1,)])
        self.assertEqual(self.sql("SELECT quantity FROM work_journal WHERE id=%s", (self.journal_id,)), [(0.6,)])
        self.assertEqual(self.expense_state(), expenses)


if __name__ == "__main__":
    unittest.main()
