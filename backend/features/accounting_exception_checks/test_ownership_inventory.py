import unittest

from backend.features.accounting_exception_checks.ownership_inventory import (
    SOURCE_LIMIT,
    classify_accounting_ownership,
    run_accounting_ownership_inventory,
)


class _Cursor:
    def __init__(self, result_sets):
        self._result_sets = list(result_sets)
        self._rows = []
        self.calls = []
        self.closed = False

    def execute(self, query, params=()):
        self.calls.append((query, tuple(params or ())))
        self._rows = self._result_sets.pop(0)

    def fetchall(self):
        return list(self._rows)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, result_sets):
        self.cursor_value = _Cursor(result_sets)
        self.session_calls = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(dict(kwargs))

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def _by_record(report):
    return {
        (item["source"], item["recordId"]): item
        for item in report["records"]
    }


class AccountingOwnershipClassificationTests(unittest.TestCase):
    def test_classifies_only_exact_owner_proofs_and_quarantines_conflicts(self):
        report = classify_accounting_ownership({
            "projects": [
                {"id": 10, "company_id": 1, "name": "Точный"},
                {"id": 20, "company_id": 2, "name": "Чужой"},
                {"id": 30, "company_id": 1, "name": "Дубль"},
                {"id": 31, "company_id": 2, "name": "Дубль"},
            ],
            "staff": [
                {"id": 100, "company_id": 1, "project": "Точный"},
                {"id": 101, "company_id": 1, "project": ""},
                {"id": 102, "company_id": 2, "project": "Точный"},
            ],
            "accountable_payments": [
                {"id": 200, "project_name": "Точный", "given_to_id": 100},
                {"id": 201, "project_name": "Точный", "given_to_id": 102},
                {"id": 202, "project_name": "Точный", "given_to_id": 999},
                {"id": 203, "project_name": "Дубль", "given_to_id": None},
            ],
            "accountable_expenses": [
                {"id": 300, "payment_id": 200, "project_name": "Точный"},
                {"id": 301, "payment_id": 200, "project_name": "Чужой"},
                {"id": 302, "payment_id": 999, "project_name": "Точный"},
            ],
            "expense_reports": [
                {"id": 400, "employee_id": 100, "project_name": "Точный"},
                {"id": 401, "employee_id": 102, "project_name": "Точный"},
                {"id": 402, "employee_id": None, "project_name": "Дубль"},
            ],
            "salary_payments": [
                {"id": 500, "staff_id": 100},
                {"id": 501, "staff_id": 101},
                {"id": 502, "staff_id": 999},
            ],
            "own_expenses": [
                {"id": 600, "project_name": "Точный", "employee_id": 999},
                {"id": 601, "project_name": "Дубль", "employee_id": 100},
                {"id": 602, "project_name": "Нет проекта", "employee_id": 100},
            ],
            "expenses": [
                {"id": 700, "project": "Точный", "own_expense_id": 600},
                {"id": 701, "project": "Чужой", "own_expense_id": 600},
                {"id": 702, "project": "Точный", "own_expense_id": 999},
                {"id": 703, "project": "Точный", "own_expense_id": None},
                {"id": 704, "project": "", "own_expense_id": None},
            ],
        })

        records = _by_record(report)
        self.assertEqual(records[("staff", 100)]["classification"], "provable")
        self.assertEqual(records[("staff", 101)]["reason"], "staff_owner_unverified")
        self.assertEqual(records[("staff", 102)]["classification"], "conflicting")
        self.assertEqual(records[("accountable_payments", 200)]["companyId"], 1)
        self.assertEqual(records[("accountable_payments", 200)]["projectId"], 10)
        self.assertEqual(records[("accountable_payments", 201)]["reason"], "staff_project_owner_mismatch")
        self.assertEqual(records[("accountable_payments", 202)]["classification"], "orphaned")
        self.assertEqual(records[("accountable_payments", 203)]["classification"], "ambiguous")
        self.assertEqual(records[("accountable_expenses", 300)]["classification"], "provable")
        self.assertEqual(records[("accountable_expenses", 301)]["classification"], "conflicting")
        self.assertEqual(records[("accountable_expenses", 302)]["classification"], "orphaned")
        self.assertEqual(records[("expense_reports", 400)]["classification"], "provable")
        self.assertEqual(records[("expense_reports", 401)]["classification"], "conflicting")
        self.assertEqual(records[("expense_reports", 402)]["classification"], "ambiguous")
        self.assertEqual(records[("salary_payments", 500)]["classification"], "provable")
        self.assertEqual(records[("salary_payments", 501)]["classification"], "ambiguous")
        self.assertEqual(records[("salary_payments", 502)]["classification"], "orphaned")
        self.assertEqual(records[("own_expenses", 600)]["companyId"], 1)
        self.assertEqual(records[("own_expenses", 600)]["projectId"], 10)
        self.assertEqual(records[("own_expenses", 601)]["classification"], "ambiguous")
        self.assertEqual(records[("own_expenses", 602)]["classification"], "orphaned")
        self.assertEqual(records[("expenses", 700)]["reason"], "own_expense_parent_owner_exact")
        self.assertEqual(records[("expenses", 701)]["classification"], "conflicting")
        self.assertEqual(records[("expenses", 702)]["classification"], "orphaned")
        self.assertEqual(records[("expenses", 703)]["companyId"], 1)
        self.assertEqual(records[("expenses", 704)]["classification"], "ambiguous")
        self.assertEqual(
            report["summary"],
            {"provable": 8, "ambiguous": 6, "orphaned": 5, "conflicting": 5},
        )

    def test_own_expense_employee_id_never_proves_company_ownership(self):
        report = classify_accounting_ownership({
            "projects": [{"id": 10, "company_id": 1, "name": "Точный"}],
            "staff": [{"id": 100, "company_id": 1, "project": "Точный"}],
            "accountable_payments": [],
            "accountable_expenses": [],
            "expense_reports": [],
            "salary_payments": [],
            "own_expenses": [{"id": 600, "project_name": "", "employee_id": 100}],
            "expenses": [],
        })

        row = _by_record(report)[("own_expenses", 600)]
        self.assertEqual(row["classification"], "ambiguous")
        self.assertEqual(row["reason"], "own_expense_owner_unverified")
        self.assertIsNone(row["companyId"])
        self.assertIsNone(row["projectId"])

    def test_output_is_allowlisted_and_does_not_copy_sensitive_fields(self):
        marker = "PRIVATE_SALARY_AND_PURPOSE"
        report = classify_accounting_ownership({
            "projects": [{"id": 10, "company_id": 1, "name": "Точный"}],
            "staff": [{
                "id": 100,
                "company_id": 1,
                "project": "Точный",
                "name": marker,
                "salary": marker,
            }],
            "accountable_payments": [{
                "id": 200,
                "project_name": "Точный",
                "given_to_id": 100,
                "purpose": marker,
                "amount": marker,
            }],
            "accountable_expenses": [],
            "expense_reports": [],
            "salary_payments": [],
            "own_expenses": [{
                "id": 600,
                "project_name": "Точный",
                "employee_name": marker,
                "description": marker,
                "amount": marker,
            }],
            "expenses": [{
                "id": 700,
                "project": "Точный",
                "own_expense_id": 600,
                "note": marker,
                "amount": marker,
            }],
        })

        self.assertNotIn(marker, repr(report))
        self.assertEqual(
            set(report["records"][0]),
            {"source", "recordId", "classification", "reason", "companyId", "projectId"},
        )

    def test_rejects_duplicate_record_ids_and_caps_public_records(self):
        with self.assertRaisesRegex(ValueError, "accounting_ownership_input_invalid"):
            classify_accounting_ownership({
                "projects": [],
                "staff": [{"id": 1}, {"id": 1}],
                "accountable_payments": [],
                "accountable_expenses": [],
                "expense_reports": [],
                "salary_payments": [],
            })

        report = classify_accounting_ownership({
            "projects": [],
            "staff": [{"id": index} for index in range(1, 106)],
            "accountable_payments": [],
            "accountable_expenses": [],
            "expense_reports": [],
            "salary_payments": [],
        }, max_records=100)
        self.assertEqual(len(report["records"]), 100)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["totalRecords"], 105)


class AccountingOwnershipInventoryRunnerTests(unittest.TestCase):
    def test_runner_returns_every_collected_record_by_default(self):
        connection = _Connection([
            [{"id": 10, "company_id": 1, "name": "Точный"}],
            [
                {"id": record_id, "company_id": 1, "project": "Точный"}
                for record_id in range(1, 106)
            ],
            [],
            [],
            [],
            [],
            [],
            [],
        ])

        report = run_accounting_ownership_inventory(connection)

        self.assertEqual(report["totalRecords"], 105)
        self.assertEqual(len(report["records"]), 105)
        self.assertFalse(report["truncated"])

    def test_runner_is_bounded_read_only_and_always_rolls_back(self):
        connection = _Connection([
            [{"id": 10, "company_id": 1, "name": "Точный"}],
            [{"id": 100, "company_id": 1, "project": "Точный"}],
            [{"id": 200, "project_name": "Точный", "given_to_id": 100}],
            [{"id": 300, "payment_id": 200, "project_name": "Точный"}],
            [{"id": 400, "employee_id": 100, "project_name": "Точный"}],
            [{"id": 500, "staff_id": 100}],
            [{"id": 600, "project_name": "Точный", "employee_id": 100}],
            [{"id": 700, "project": "Точный", "own_expense_id": 600}],
        ])

        report = run_accounting_ownership_inventory(connection)

        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertFalse(connection.closed)
        self.assertEqual(len(connection.cursor_value.calls), 8)
        for query, params in connection.cursor_value.calls:
            self.assertTrue(query.lstrip().upper().startswith("SELECT"))
            self.assertNotRegex(query.upper(), r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b")
            self.assertEqual(params, (SOURCE_LIMIT + 1,))
        self.assertEqual(report["summary"], {"provable": 7, "ambiguous": 0, "orphaned": 0, "conflicting": 0})

    def test_source_limit_fails_closed_without_partial_classification(self):
        oversized = [{"id": index} for index in range(1, SOURCE_LIMIT + 2)]
        connection = _Connection([oversized, [], [], [], [], []])

        with self.assertRaisesRegex(ValueError, "accounting_ownership_source_limit"):
            run_accounting_ownership_inventory(connection)

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)


if __name__ == "__main__":
    unittest.main()
