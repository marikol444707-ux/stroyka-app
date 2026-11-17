"""HTTP regressions for reimbursement on the owned disposable audit fixture.

Each test creates its own synthetic expense; fixture teardown owns cleanup.
The payment list deduplicates identical stored rows. Guarded Unix-socket reads
also verify physical uniqueness; one test installs a marker-scoped failure
trigger in this disposable fixture and removes it after testing rollback.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import threading
import unittest
from uuid import uuid4

from backend.features.master_cabinet import test_profile_http as profile_http


@unittest.skipUnless(profile_http.RUN, "Requires the owned local audit API")
class ReimbursementHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_http.MasterProfileHttpTests.setUpClass.__func__(cls)
        cls.company_id = cls.users["master"]["company_id"]
        cls.project_id = cls.users["master"]["project_id"]
        cls.project_name = cls.users["master"]["project_name"]

    def setUp(self):
        self.description = f"HTTP reimbursement regression {uuid4().hex}"
        self.amount = Decimal("317.25")
        status, created = self.request("master", "/own-expenses", "POST", {
            "projectId": self.project_id, "description": self.description,
            "amount": float(self.amount), "date": "2026-11-08", "category": "other",
        })
        self.assertEqual(status, 200, created)
        self.expense_id = created["id"]
        self.original = self.expense()
        self.assertEqual(self.original["status"], "Ожидает")
        self.assertEqual(self.original["description"], self.description)
        self.assertEqual(self.payments(), [])

    def expense(self):
        status, rows = self.request("master", "/own-expenses")
        self.assertEqual(status, 200, rows)
        selected = [row for row in rows if row["id"] == self.expense_id]
        self.assertEqual(len(selected), 1, "Created expense must remain visible to its owner")
        return selected[0]

    def payments(self):
        status, rows = self.request("accountant", "/project-payments")
        self.assertEqual(status, 200, rows)
        return [row for row in rows if self.description in row.get("note", "")]

    def reimburse(self, role="accountant"):
        return self.request(role, f"/own-expenses/{self.expense_id}", "PUT", {"status": "Возмещено"})

    @contextmanager
    def fixture_db(self):
        # Never derive a connection from app config, DATABASE_URL, or .env.
        profile_http.require_owned_fixture()
        marker = json.loads((profile_http.ROOT / "tmp/master-audit/fixture.json").read_text())
        work = Path(marker["root"]).resolve()
        import psycopg2
        conn = psycopg2.connect(
            host=str(work), port=6548, user="chain_test", password="",
            dbname="supply_chain_test_master_audit", connect_timeout=5,
            passfile=str(work / "no-password-file"),
            options="-c statement_timeout=5000 -c lock_timeout=3000",
        )
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""SELECT current_database(),current_user,
                        current_setting('listen_addresses'),current_setting('data_directory')""")
                    if cur.fetchone() != (
                        "supply_chain_test_master_audit", "chain_test", "", str(work / "data"),
                    ):
                        raise RuntimeError("Refusing a database outside the socket-only audit fixture")
                    yield cur
        finally:
            conn.close()

    def physical_payment_count(self):
        with self.fixture_db() as cur:
            # Count every physical row bearing this expense's unique marker,
            # including a mistakenly written row in another company.
            cur.execute("SELECT count(*) FROM public.project_payments WHERE strpos(COALESCE(note,''),%s)>0",
                        (self.description,))
            return cur.fetchone()[0]

    def financial_snapshot(self):
        with self.fixture_db() as cur:
            cur.execute("SELECT to_jsonb(e) FROM public.own_expenses e WHERE id=%s AND company_id=%s",
                        (self.expense_id, self.company_id))
            own_expense = cur.fetchone()
            self.assertIsNotNone(own_expense)
            cur.execute("""SELECT to_jsonb(e) FROM public.expenses e
                           WHERE own_expense_id=%s AND company_id=%s ORDER BY id""",
                        (self.expense_id, self.company_id))
            return own_expense, cur.fetchall()

    def remove_failure_trigger(self, name):
        from psycopg2 import sql
        with self.fixture_db() as cur:
            cur.execute(sql.SQL("DROP TRIGGER IF EXISTS {} ON public.project_payments").format(sql.Identifier(name)))
            cur.execute(sql.SQL("DROP FUNCTION IF EXISTS public.{}()").format(sql.Identifier(name)))
        with self.fixture_db() as cur:
            cur.execute("SELECT count(*) FROM pg_trigger WHERE tgname=%s", (name,))
            self.assertEqual(cur.fetchone()[0], 0, "Failure trigger must be removed after the test")
            cur.execute("SELECT to_regprocedure(%s)", (f"public.{name}()",))
            self.assertIsNone(cur.fetchone()[0], "Failure function must be removed after the test")

    def test_two_concurrent_reimbursements_create_one_payment_and_retry_preserves_it(self):
        barrier = threading.Barrier(2)

        def submit():
            barrier.wait(timeout=10)
            return self.reimburse()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))
        self.assertIn(200, [status for status, _body in results], results)
        for status, body in results:
            self.assertIn(status, (200, 409), body)
        expense = self.expense()
        self.assertEqual(expense["status"], "Возмещено")
        self.assertEqual(expense["approvedBy"], self.users["accountant"]["name"])
        payments = self.payments()
        self.assertEqual(len(payments), 1, "Successful reimbursement must create exactly one visible payment")
        payment = payments[0]
        self.assertEqual(Decimal(str(payment["amount"])), -self.amount)
        self.assertEqual(payment["companyId"], self.company_id)
        self.assertEqual(payment["projectName"], self.project_name)
        self.assertEqual(payment["addedBy"], self.users["accountant"]["name"])
        self.assertEqual(payment["note"], f"Возмещение «{self.description}» — {expense['employeeName']}")
        self.assertEqual(self.physical_payment_count(), 1, "Concurrent PUTs must insert one physical payment row")
        status, body = self.reimburse()
        self.assertIn(status, (200, 409), body)
        self.assertEqual(self.payments(), payments, "A retry must not replace or duplicate the payment")
        self.assertEqual(self.physical_payment_count(), 1, "Retry must not create hidden duplicate payment rows")

    def test_payment_insert_failure_rolls_back_expense_and_allows_safe_retry(self):
        from psycopg2 import sql
        before = self.financial_snapshot()
        self.assertEqual(self.physical_payment_count(), 0)
        name = "master_reimburse_fail_" + uuid4().hex
        self.addCleanup(self.remove_failure_trigger, name)
        with self.fixture_db() as cur:
            cur.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
                LANGUAGE plpgsql AS $test_failure$
                BEGIN
                    RAISE EXCEPTION 'synthetic reimbursement insert failure' USING ERRCODE='P0001';
                END
                $test_failure$""").format(sql.Identifier(name)))
            cur.execute(sql.SQL("""CREATE TRIGGER {} AFTER INSERT ON public.project_payments
                FOR EACH ROW WHEN (NEW.company_id={} AND strpos(COALESCE(NEW.note,''),{})>0)
                EXECUTE FUNCTION public.{}()""").format(
                    sql.Identifier(name), sql.Literal(self.company_id),
                    sql.Literal(self.description), sql.Identifier(name),
                ))
        try:
            status, body = self.reimburse()
            self.assertEqual(status, 500, body)
            self.assertEqual(self.expense(), self.original, "Failed payment must not mark the expense reimbursed")
            self.assertEqual(self.financial_snapshot(), before, "Rollback must preserve expense and finance mirror")
            self.assertEqual(self.payments(), [])
            self.assertEqual(self.physical_payment_count(), 0, "Failed INSERT must leave no physical payment")
        finally:
            self.remove_failure_trigger(name)
        status, body = self.reimburse()
        self.assertEqual(status, 200, body)
        self.assertEqual(self.expense()["status"], "Возмещено")
        self.assertEqual(len(self.payments()), 1)
        self.assertEqual(self.physical_payment_count(), 1, "Retry after rollback must create one physical payment")

    def test_verified_expense_get_returns_exact_company_and_project_ids(self):
        self.assertEqual(self.original.get("companyId"), self.company_id)
        self.assertEqual(self.original.get("projectId"), self.project_id)

    def test_master_cannot_reimburse_own_expense_or_create_payment(self):
        status, body = self.reimburse("master")
        self.assertIn(status, (403, 404), body)
        self.assertEqual(self.expense(), self.original)
        self.assertEqual(self.payments(), [])

    def test_foreign_director_cannot_reimburse_expense_or_create_payment(self):
        status, body = self.reimburse("stranger")
        self.assertIn(status, (403, 404), body)
        self.assertEqual(self.expense(), self.original)
        self.assertEqual(self.payments(), [])
        status, foreign_payments = self.request("stranger", "/project-payments")
        self.assertEqual(status, 200, foreign_payments)
        self.assertFalse(any(self.description in row.get("note", "") for row in foreign_payments))

    def test_invalid_transition_request_leaves_expense_and_payments_unchanged(self):
        status, body = self.request("accountant", f"/own-expenses/{self.expense_id}", "PUT",
                                    {"status": "invalid-status"})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.expense(), self.original)
        self.assertEqual(self.payments(), [])

    def test_declining_expense_does_not_create_reimbursement_payment(self):
        status, body = self.request("accountant", f"/own-expenses/{self.expense_id}", "PUT",
                                    {"status": "Отклонено"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.expense()["status"], "Отклонено")
        self.assertEqual(self.payments(), [])


if __name__ == "__main__":
    unittest.main()
