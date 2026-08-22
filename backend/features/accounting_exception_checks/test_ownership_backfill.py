import inspect
import unittest
from unittest import mock

from backend.features.accounting_exception_checks import ownership_backfill


SOURCES = (
    "staff",
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "salary_payments",
    "own_expenses",
    "expenses",
)


def _decision(source, record_id, classification="provable", company_id=4, project_id=19):
    return {
        "source": source,
        "recordId": record_id,
        "classification": classification,
        "reason": "exact" if classification == "provable" else "review",
        "companyId": company_id if classification == "provable" else None,
        "projectId": project_id if classification == "provable" else None,
    }


def _stored(source, record_id, *, company_id=None, project_id=None, verified=False):
    row = {
        "id": record_id,
        "company_id": company_id,
        "company_scope_verified": verified,
    }
    if source not in ("staff", "salary_payments"):
        row["project_id"] = project_id
    return row


def _empty_stored():
    return {source: [] for source in SOURCES}


class _Cursor:
    def __init__(self, rowcounts=()):
        self.calls = []
        self.closed = False
        self.rowcount = 0
        self._rowcounts = list(rowcounts)

    def execute(self, query, params=()):
        normalized = " ".join(str(query).split())
        self.calls.append((normalized, tuple(params or ())))
        if normalized.startswith("UPDATE public."):
            self.rowcount = self._rowcounts.pop(0) if self._rowcounts else 0

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rowcounts=()):
        self.cursor_value = _Cursor(rowcounts)
        self.sessions = []
        self.commits = 0
        self.rollbacks = 0

    def set_session(self, **kwargs):
        self.sessions.append(dict(kwargs))

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class AccountingOwnershipBackfillPlanTests(unittest.TestCase):
    def test_plan_updates_only_unverified_provable_rows_and_quarantines_the_rest(self):
        records = [
            _decision("staff", 1),
            _decision("accountable_payments", 2),
            _decision("accountable_expenses", 3, "ambiguous"),
            _decision("expense_reports", 4, "orphaned"),
            _decision("salary_payments", 5, "conflicting"),
            _decision("own_expenses", 6),
            _decision("expenses", 7),
        ]
        stored = _empty_stored()
        stored["staff"] = [_stored("staff", 1, company_id=4)]
        stored["accountable_payments"] = [_stored("accountable_payments", 2)]
        stored["accountable_expenses"] = [_stored("accountable_expenses", 3)]
        stored["expense_reports"] = [_stored("expense_reports", 4)]
        stored["salary_payments"] = [_stored("salary_payments", 5)]
        stored["own_expenses"] = [_stored("own_expenses", 6, company_id=4, project_id=19, verified=True)]
        stored["expenses"] = [_stored("expenses", 7, company_id=9)]

        plan = ownership_backfill.build_accounting_ownership_backfill_plan(records, stored)

        self.assertEqual(plan["version"], "accounting-ownership-backfill-v1")
        self.assertEqual(plan["readyCount"], 2)
        self.assertEqual(plan["verifiedCount"], 1)
        self.assertEqual(plan["quarantinedCount"], 3)
        self.assertEqual(plan["conflictingCount"], 1)
        self.assertRegex(plan["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            [(row["source"], row["recordId"]) for row in plan["ready"]],
            [("staff", 1), ("accountable_payments", 2)],
        )
        self.assertNotIn(("expenses", 7), {
            (row["source"], row["recordId"]) for row in plan["ready"]
        })

    def test_plan_is_deterministic_and_rejects_missing_duplicate_or_forged_state(self):
        records = [_decision("accountable_payments", 2)]
        stored = _empty_stored()
        stored["accountable_payments"] = [_stored("accountable_payments", 2)]
        first = ownership_backfill.build_accounting_ownership_backfill_plan(records, stored)
        second = ownership_backfill.build_accounting_ownership_backfill_plan(list(reversed(records)), stored)
        self.assertEqual(first, second)

        for invalid in (
            _empty_stored(),
            {**stored, "accountable_payments": stored["accountable_payments"] * 2},
            {**stored, "accountable_payments": [{**stored["accountable_payments"][0], "company_scope_verified": 1}]},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "accounting_backfill_input_invalid"):
                    ownership_backfill.build_accounting_ownership_backfill_plan(records, invalid)

    def test_runtime_has_no_registration_get_db_or_automatic_apply(self):
        source = inspect.getsource(ownership_backfill)
        self.assertNotIn("backend.main", source)
        self.assertNotIn("get_db", source)
        self.assertNotIn("register_", source)
        self.assertNotIn("if __name__", source)


class AccountingOwnershipBackfillRunnerTests(unittest.TestCase):
    def test_dry_run_is_read_only_rolls_back_and_writes_nothing(self):
        connection = _Connection()
        plan = ownership_backfill.build_accounting_ownership_backfill_plan(
            [_decision("staff", 1)],
            {**_empty_stored(), "staff": [_stored("staff", 1, company_id=4)]},
        )

        with mock.patch.object(ownership_backfill, "_collect_backfill_plan", return_value=plan):
            report = ownership_backfill.run_accounting_ownership_backfill(connection)

        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.sessions, [{"readonly": True, "autocommit": False}])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertFalse(any(sql.startswith("UPDATE ") for sql, _ in connection.cursor_value.calls))

    def test_apply_requires_exact_count_and_hash_before_any_database_call(self):
        connection = _Connection()

        with self.assertRaisesRegex(ValueError, "accounting_backfill_apply_guard_invalid"):
            ownership_backfill.run_accounting_ownership_backfill(
                connection,
                apply=True,
                expected_ready_count=1,
                expected_plan_sha256="not-a-sha",
            )

        self.assertEqual(connection.sessions, [])
        self.assertEqual(connection.cursor_value.calls, [])
        self.assertEqual(connection.rollbacks, 0)

    def test_apply_revalidates_under_locks_updates_ready_rows_and_commits(self):
        before = ownership_backfill.build_accounting_ownership_backfill_plan(
            [_decision("staff", 1), _decision("accountable_payments", 2), _decision("expenses", 3, "ambiguous")],
            {
                **_empty_stored(),
                "staff": [_stored("staff", 1, company_id=4)],
                "accountable_payments": [_stored("accountable_payments", 2)],
                "expenses": [_stored("expenses", 3)],
            },
        )
        after = {
            **before,
            "ready": [],
            "readyCount": 0,
            "verifiedCount": 2,
        }
        connection = _Connection(rowcounts=(1, 1))

        with mock.patch.object(ownership_backfill, "_collect_backfill_plan", side_effect=[before, after]):
            report = ownership_backfill.run_accounting_ownership_backfill(
                connection,
                apply=True,
                expected_ready_count=before["readyCount"],
                expected_plan_sha256=before["planSha256"],
            )

        self.assertTrue(report["complete"])
        self.assertEqual(report["updated"], 2)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        sql = [query for query, _params in connection.cursor_value.calls]
        self.assertEqual(sum(query.startswith("LOCK TABLE public.") for query in sql), 8)
        updates = [(query, params) for query, params in connection.cursor_value.calls if query.startswith("UPDATE public.")]
        self.assertEqual(len(updates), 2)
        self.assertTrue(all("company_scope_verified IS FALSE" in query for query, _ in updates))

    def test_apply_does_not_write_when_plan_drifted_or_contains_stored_conflicts(self):
        ready = ownership_backfill.build_accounting_ownership_backfill_plan(
            [_decision("accountable_payments", 2)],
            {**_empty_stored(), "accountable_payments": [_stored("accountable_payments", 2)]},
        )
        conflict = ownership_backfill.build_accounting_ownership_backfill_plan(
            [_decision("accountable_payments", 2)],
            {**_empty_stored(), "accountable_payments": [_stored("accountable_payments", 2, company_id=9)]},
        )
        for current in (conflict, {**ready, "planSha256": "f" * 64}):
            connection = _Connection()
            with self.subTest(current=current):
                with mock.patch.object(ownership_backfill, "_collect_backfill_plan", return_value=current):
                    with self.assertRaisesRegex(RuntimeError, "accounting_backfill_plan_changed|accounting_backfill_stored_conflict"):
                        ownership_backfill.run_accounting_ownership_backfill(
                            connection,
                            apply=True,
                            expected_ready_count=ready["readyCount"],
                            expected_plan_sha256=ready["planSha256"],
                        )
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)
                self.assertFalse(any(sql.startswith("UPDATE ") for sql, _ in connection.cursor_value.calls))

    def test_write_conflict_or_failed_postcheck_rolls_back_every_update(self):
        before = ownership_backfill.build_accounting_ownership_backfill_plan(
            [_decision("staff", 1)],
            {**_empty_stored(), "staff": [_stored("staff", 1, company_id=4)]},
        )
        for rowcounts, plans, message in (
            ((0,), [before], "accounting_backfill_write_conflict"),
            ((1,), [before, before], "accounting_backfill_postcheck_failed"),
        ):
            connection = _Connection(rowcounts=rowcounts)
            with self.subTest(message=message):
                with mock.patch.object(ownership_backfill, "_collect_backfill_plan", side_effect=plans):
                    with self.assertRaisesRegex(RuntimeError, message):
                        ownership_backfill.run_accounting_ownership_backfill(
                            connection,
                            apply=True,
                            expected_ready_count=1,
                            expected_plan_sha256=before["planSha256"],
                        )
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
