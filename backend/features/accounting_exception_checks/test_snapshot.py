import ast
import inspect
from pathlib import Path
import unittest
from unittest import mock

import backend.features.accounting_exception_checks.snapshot as snapshot
from backend.features.accounting_exception_checks.projection import (
    ACCOUNTING_EXCEPTION_SOURCES,
)
from backend.features.accounting_exception_checks.snapshot import (
    AccountingExceptionSnapshotError,
    run_accounting_exception_snapshot,
)


class _Cursor:
    def __init__(self, result_sets, *, execute_error_at=None, close_error=None):
        self.result_sets = list(result_sets)
        self.calls = []
        self.closed = False
        self.execute_error_at = execute_error_at
        self.close_error = close_error

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if self.execute_error_at is not None and len(self.calls) == self.execute_error_at[0]:
            raise self.execute_error_at[1]

    def fetchall(self):
        return self.result_sets.pop(0)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Connection:
    def __init__(
        self,
        result_sets,
        *,
        execute_error_at=None,
        rollback_error=None,
        cursor_close_error=None,
        close_error=None,
    ):
        self.cursor_value = _Cursor(
            result_sets,
            execute_error_at=execute_error_at,
            close_error=cursor_close_error,
        )
        self.session_calls = []
        self.rollback_calls = 0
        self.commit_calls = 0
        self.closed = False
        self.rollback_error = rollback_error
        self.close_error = close_error

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollback_calls += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


_VARIABLE_FIELDS = {
    "brigade_contracts": (),
    "brigade_payments": ("amount",),
    "project_payments": ("amount",),
    "supplier_invoices": ("amount", "paid_amount"),
    "warehouse_invoices": (),
    "accountable_payments": ("amount", "spent_amount"),
    "accountable_expenses": ("amount",),
    "expense_reports": ("issued_amount", "spent_amount", "balance"),
    "staff": (),
    "salary_payments": ("month",),
    "own_expenses": (),
    "expenses": (),
}


def _bounded(source, rows):
    rows = [dict(row) for row in rows]
    sizes = {
        field: [
            0 if row.get(field) is None else len(row[field].encode("utf-8"))
            for row in rows
        ]
        for field in _VARIABLE_FIELDS[source]
    }
    total = sum(sum(values) for values in sizes.values())
    for index, row in enumerate(rows):
        for field in _VARIABLE_FIELDS[source]:
            row["field_" + field + "_bytes"] = sizes[field][index]
        row.update({
            "query_json_bytes": 0,
            "query_text_bytes": total,
            "query_variable_bytes": total,
            "row_count": len(rows),
            "cardinality_limit_exceeded": False,
            "payload_limit_exceeded": False,
        })
    return rows


def _complete_result_sets():
    rows = {
        "brigade_contracts": [{
            "id": 10, "company_id": 4, "project_id": 17,
        }],
        "brigade_payments": [{
            "id": 11, "company_id": 4, "contract_id": 10,
            "project_payment_id": 12, "amount": "10.25",
        }],
        "project_payments": [{
            "id": 12, "company_id": 4, "project_id": 17,
            "amount": "10.25",
        }],
        "supplier_invoices": [{
            "id": 20, "company_id": 4, "project_id": 17,
            "warehouse_invoice_id": 21, "amount": "100",
            "paid_amount": "50",
        }],
        "warehouse_invoices": [{
            "id": 21, "company_id": 4, "project_id": 17,
            "supplier_invoice_id": 20,
        }],
        "accountable_payments": [{
            "id": 30, "company_id": 4, "project_id": 17,
            "amount": "100", "spent_amount": "40",
        }],
        "accountable_expenses": [{
            "id": 31, "company_id": 4, "project_id": 17,
            "payment_id": 30, "amount": "40",
        }],
        "expense_reports": [{
            "id": 40, "company_id": 4, "project_id": 17,
            "issued_amount": "100", "spent_amount": "40", "balance": "60",
        }],
        "staff": [{"id": 50, "company_id": 4}],
        "salary_payments": [{
            "id": 51, "company_id": 4, "staff_id": 50,
            "month": "2026-08",
        }],
        "own_expenses": [{
            "id": 60, "company_id": 4, "project_id": 17,
            "expense_id": 61,
        }],
        "expenses": [{
            "id": 61, "company_id": 4, "project_id": 17,
            "own_expense_id": 60,
        }],
    }
    return [_bounded(source, rows[source]) for source in ACCOUNTING_EXCEPTION_SOURCES]


class AccountingExceptionSnapshotTests(unittest.TestCase):
    def test_empty_verified_company_snapshot_is_clear_and_read_only(self):
        connection = _Connection([[] for _ in range(12)])

        report = run_accounting_exception_snapshot(lambda: connection, 4)

        self.assertEqual(report["state"], "clear")
        self.assertEqual(report["companyId"], 4)
        self.assertEqual(report["findingCount"], 0)
        self.assertTrue(report["scanComplete"])
        self.assertEqual(set(report["sourceCounts"].values()), {0})
        self.assertEqual(
            connection.session_calls,
            [{
                "readonly": True,
                "autocommit": False,
                "isolation_level": "REPEATABLE READ",
            }],
        )
        self.assertEqual(len(connection.cursor_value.calls), 13)
        self.assertEqual(connection.rollback_calls, 1)
        self.assertEqual(connection.commit_calls, 0)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(all(
            call[0].upper().startswith("SELECT")
            for call in connection.cursor_value.calls
        ))

    def test_verified_rows_are_detached_and_composed_by_the_pure_projection(self):
        result_sets = _complete_result_sets()
        connection = _Connection(result_sets)

        report = run_accounting_exception_snapshot(lambda: connection, 4)

        self.assertEqual(report["state"], "clear")
        self.assertEqual(report["findingCount"], 0)
        self.assertEqual(set(report["sourceCounts"].values()), {1})
        self.assertEqual(connection.rollback_calls, 1)
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.cursor_value.result_sets, [])
        self.assertNotIn("query_variable_bytes", repr(report))

    def test_queries_are_parameterized_select_only_ordered_materialized_gates(self):
        connection = _Connection([[] for _ in ACCOUNTING_EXCEPTION_SOURCES])

        run_accounting_exception_snapshot(lambda: connection, 4)

        source_calls = connection.cursor_value.calls[1:]
        self.assertEqual(len(source_calls), len(ACCOUNTING_EXCEPTION_SOURCES))
        for source, (sql, params) in zip(ACCOUNTING_EXCEPTION_SOURCES, source_calls):
            upper = sql.upper()
            with self.subTest(source=source):
                self.assertTrue(upper.startswith("SELECT"))
                self.assertIn("WITH LIMITED AS MATERIALIZED", upper)
                self.assertIn("SIZED AS MATERIALIZED", upper)
                self.assertIn("COUNT(*) OVER ()", upper)
                self.assertIn("QUERY_VARIABLE_BYTES <= %S", upper)
                self.assertIn("ORDER BY 1 LIMIT %S", upper)
                for field in _VARIABLE_FIELDS[source]:
                    self.assertIn(
                        "MAX(FIELD_" + field.upper() + "_BYTES) OVER () "
                        "AS MAX_FIELD_" + field.upper() + "_BYTES",
                        upper,
                    )
                    self.assertIn(
                        "MAX_FIELD_" + field.upper() + "_BYTES <= %S",
                        upper,
                    )
                self.assertNotRegex(
                    upper,
                    r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|COMMIT|LOCK)\b",
                )
                self.assertEqual(sql.count("%s"), len(params))
                self.assertIn(4, params)
                self.assertIn(1001, params)
                self.assertEqual(
                    upper.count("FROM PUBLIC." + source.upper()),
                    1,
                )
        verified_sources = {
            "project_payments", "accountable_payments",
            "accountable_expenses", "expense_reports", "staff",
            "salary_payments", "own_expenses", "expenses",
        }
        for source, (sql, _params) in zip(
            ACCOUNTING_EXCEPTION_SOURCES, source_calls
        ):
            if source in verified_sources:
                self.assertIn("COMPANY_SCOPE_VERIFIED IS TRUE", sql.upper())

    def test_numeric_64_bytes_is_accepted_and_65_bytes_is_query_wide_denied(self):
        accepted_sets = _complete_result_sets()
        accepted_sets[3] = _bounded("supplier_invoices", [{
            "id": 20, "company_id": 4, "project_id": 17,
            "warehouse_invoice_id": 21, "amount": "9" * 64,
            "paid_amount": "0",
        }])
        accepted = run_accounting_exception_snapshot(
            lambda: _Connection(accepted_sets), 4
        )
        self.assertEqual(accepted["state"], "clear")

        denied_sets = _complete_result_sets()
        denied = _bounded("supplier_invoices", [{
            "id": 20, "company_id": 4, "project_id": 17,
            "warehouse_invoice_id": 21, "amount": "9" * 65,
            "paid_amount": "0",
        }])
        denied[0].update({
            "amount": None,
            "paid_amount": None,
            "payload_limit_exceeded": True,
        })
        denied_sets[3] = denied
        connection = _Connection(denied_sets)

        rejected = run_accounting_exception_snapshot(lambda: connection, 4)

        self.assertEqual(rejected["state"], "incomplete")
        self.assertEqual(rejected["findings"], [])
        self.assertEqual(len(connection.cursor_value.calls), 5)
        self.assertEqual(len(connection.cursor_value.result_sets), 8)

    def test_cardinality_and_month_payload_stop_before_later_sources(self):
        cardinality_sets = _complete_result_sets()
        staff_rows = _bounded("staff", [
            {"id": 1000 + index, "company_id": 4}
            for index in range(1001)
        ])
        for row in staff_rows:
            row["cardinality_limit_exceeded"] = True
        cardinality_sets[8] = staff_rows
        connection = _Connection(cardinality_sets)

        cardinality = run_accounting_exception_snapshot(lambda: connection, 4)

        self.assertEqual(cardinality["state"], "incomplete")
        self.assertEqual(cardinality["findings"], [])
        self.assertEqual(len(connection.cursor_value.calls), 10)
        self.assertEqual(len(connection.cursor_value.result_sets), 3)

        payload_sets = _complete_result_sets()
        salary = _bounded("salary_payments", [{
            "id": 51, "company_id": 4, "staff_id": 50,
            "month": "2026-088",
        }])
        salary[0].update({
            "month": None,
            "payload_limit_exceeded": True,
        })
        payload_sets[9] = salary
        connection = _Connection(payload_sets)

        payload = run_accounting_exception_snapshot(lambda: connection, 4)

        self.assertEqual(payload["state"], "incomplete")
        self.assertEqual(payload["findings"], [])
        self.assertEqual(len(connection.cursor_value.calls), 11)
        self.assertEqual(len(connection.cursor_value.result_sets), 2)

    def test_malformed_metadata_and_denied_raw_value_raise_fixed_error(self):
        for mutation in ("bool-total", "raw-leak"):
            result_sets = _complete_result_sets()
            salary = _bounded("salary_payments", [{
                "id": 51, "company_id": 4, "staff_id": 50,
                "month": "PRIVATE8",
            }])
            if mutation == "bool-total":
                salary[0]["query_variable_bytes"] = True
            else:
                salary[0]["payload_limit_exceeded"] = True
            result_sets[9] = salary
            connection = _Connection(result_sets)

            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(
                    AccountingExceptionSnapshotError,
                    "^accounting_exception_snapshot_contract_invalid$",
                ):
                    run_accounting_exception_snapshot(lambda: connection, 4)
                self.assertEqual(connection.rollback_calls, 1)
                self.assertTrue(connection.closed)

    def test_decimal_rows_feed_exact_fixed_findings_without_raw_fields(self):
        result_sets = _complete_result_sets()
        result_sets[3] = _bounded("supplier_invoices", [{
            "id": 20, "company_id": 4, "project_id": 17,
            "warehouse_invoice_id": 21, "amount": "100",
            "paid_amount": "100.01",
        }])
        result_sets[7] = _bounded("expense_reports", [{
            "id": 40, "company_id": 4, "project_id": 17,
            "issued_amount": "100", "spent_amount": "40", "balance": "61",
        }])
        result_sets[9] = _bounded("salary_payments", [{
            "id": 51, "company_id": 4, "staff_id": 50,
            "month": "2026-13",
        }])

        report = run_accounting_exception_snapshot(
            lambda: _Connection(result_sets), 4
        )

        self.assertEqual(report["state"], "review_required")
        self.assertEqual(report["findingCount"], 3)
        self.assertEqual(
            {finding["reasonCode"] for finding in report["findings"]},
            {
                "accounting_supplier_invoice_overpaid",
                "accounting_expense_report_balance_mismatch",
                "accounting_salary_month_invalid",
            },
        )
        self.assertNotIn("owner_status", repr(report))
        self.assertNotIn("query_text_bytes", repr(report))

    def test_forged_foreign_fixed_owner_fails_closed_without_partial_findings(self):
        result_sets = _complete_result_sets()
        result_sets[3][0]["company_id"] = 999
        result_sets[7] = _bounded("expense_reports", [{
            "id": 40, "company_id": 4, "project_id": 17,
            "issued_amount": "100", "spent_amount": "40", "balance": "61",
        }])

        report = run_accounting_exception_snapshot(
            lambda: _Connection(result_sets), 4
        )

        self.assertEqual(report["state"], "incomplete")
        self.assertEqual(report["findings"], [])

    def test_input_and_database_failures_use_fixed_nonleaking_errors(self):
        factory_calls = []

        def factory():
            factory_calls.append(True)
            return _Connection([[] for _ in ACCOUNTING_EXCEPTION_SOURCES])

        for company_id in (True, 0, -1, "4"):
            with self.subTest(company_id=company_id):
                with self.assertRaisesRegex(
                    AccountingExceptionSnapshotError,
                    "^accounting_exception_snapshot_input_invalid$",
                ):
                    run_accounting_exception_snapshot(factory, company_id)
        self.assertEqual(factory_calls, [])

        private = RuntimeError("PRIVATE_DATABASE_DSN")
        connection = _Connection(
            [[] for _ in ACCOUNTING_EXCEPTION_SOURCES],
            execute_error_at=(2, private),
        )
        with self.assertRaisesRegex(
            AccountingExceptionSnapshotError,
            "^accounting_exception_snapshot_read_failed$",
        ) as caught:
            run_accounting_exception_snapshot(lambda: connection, 4)
        self.assertNotIn("PRIVATE_DATABASE_DSN", str(caught.exception))
        self.assertEqual(connection.rollback_calls, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_rollback_cleanup_and_first_control_precedence(self):
        rollback_connection = _Connection(
            [[] for _ in ACCOUNTING_EXCEPTION_SOURCES],
            rollback_error=RuntimeError("PRIVATE_ROLLBACK"),
        )
        with self.assertRaisesRegex(
            AccountingExceptionSnapshotError,
            "^accounting_exception_snapshot_rollback_failed$",
        ):
            run_accounting_exception_snapshot(lambda: rollback_connection, 4)
        self.assertTrue(rollback_connection.cursor_value.closed)
        self.assertTrue(rollback_connection.closed)

        cleanup_connection = _Connection(
            [[] for _ in ACCOUNTING_EXCEPTION_SOURCES],
            cursor_close_error=RuntimeError("PRIVATE_CURSOR"),
        )
        with self.assertRaisesRegex(
            AccountingExceptionSnapshotError,
            "^accounting_exception_snapshot_cleanup_failed$",
        ):
            run_accounting_exception_snapshot(lambda: cleanup_connection, 4)
        self.assertTrue(cleanup_connection.closed)

        first_control = KeyboardInterrupt("first-control")
        later_control = SystemExit("later-control")
        control_connection = _Connection(
            [[] for _ in ACCOUNTING_EXCEPTION_SOURCES],
            execute_error_at=(2, first_control),
            close_error=later_control,
        )
        with self.assertRaises(KeyboardInterrupt) as caught:
            run_accounting_exception_snapshot(lambda: control_connection, 4)
        self.assertIs(caught.exception, first_control)
        self.assertEqual(control_connection.rollback_calls, 1)
        self.assertTrue(control_connection.cursor_value.closed)
        self.assertTrue(control_connection.closed)

    def test_one_shared_variable_budget_accepts_exact_remaining_atomically(self):
        exact_sets = [[] for _ in ACCOUNTING_EXCEPTION_SOURCES]
        exact_sets[0] = _bounded("brigade_contracts", [{
            "id": 10, "company_id": 4, "project_id": 17,
        }])
        exact_sets[1] = _bounded("brigade_payments", [{
            "id": 11, "company_id": 4, "contract_id": 10,
            "project_payment_id": None, "amount": "10.25",
        }])
        exact_connection = _Connection(exact_sets)
        with mock.patch.object(snapshot, "_MAX_SNAPSHOT_VARIABLE_BYTES", 5):
            exact = run_accounting_exception_snapshot(
                lambda: exact_connection, 4
            )
        self.assertEqual(exact["state"], "review_required")
        self.assertEqual(len(exact_connection.cursor_value.calls), 13)

        denied_sets = [[] for _ in ACCOUNTING_EXCEPTION_SOURCES]
        denied_sets[0] = _bounded("brigade_contracts", [{
            "id": 10, "company_id": 4, "project_id": 17,
        }])
        denied_payment = _bounded("brigade_payments", [{
            "id": 11, "company_id": 4, "contract_id": 10,
            "project_payment_id": None, "amount": "10.25",
        }])
        denied_payment[0].update({
            "amount": None,
            "payload_limit_exceeded": True,
        })
        denied_sets[1] = denied_payment
        denied_connection = _Connection(denied_sets)
        with mock.patch.object(snapshot, "_MAX_SNAPSHOT_VARIABLE_BYTES", 4):
            denied = run_accounting_exception_snapshot(
                lambda: denied_connection, 4
            )
        self.assertEqual(denied["state"], "incomplete")
        self.assertEqual(denied["findings"], [])
        self.assertEqual(len(denied_connection.cursor_value.calls), 3)

    def test_snapshot_stays_private_without_registration_or_database_factory(self):
        self.assertEqual(
            tuple(inspect.signature(run_accounting_exception_snapshot).parameters),
            ("get_db", "company_id"),
        )
        self.assertEqual(snapshot.__all__, [])
        source = inspect.getsource(snapshot)
        root = Path(__file__).resolve().parents[3]
        package_source = (
            root / "backend/features/accounting_exception_checks/__init__.py"
        ).read_text(encoding="utf-8")
        main_source = (root / "backend/main.py").read_text(encoding="utf-8")
        imported_modules = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("backend.db", imported_modules)
        self.assertNotIn("accounting_exception_checks.snapshot", package_source)
        self.assertNotIn("accounting_exception_checks.snapshot", main_source)


if __name__ == "__main__":
    unittest.main()
