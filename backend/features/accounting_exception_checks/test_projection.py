import copy
from pathlib import Path
import unittest
from decimal import Decimal

from backend.features.accounting_exception_checks.projection import (
    ACCOUNTING_EXCEPTION_SOURCES,
    build_accounting_exception_projection,
    MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS,
)


def _owned(record_id, **values):
    return {
        "id": record_id,
        "company_id": 1,
        "owner_status": "verified",
        **values,
    }


def _clear_rows():
    return {
        "brigade_contracts": [_owned(10, project_id=100)],
        "brigade_payments": [
            _owned(
                30,
                contract_id=10,
                project_payment_id=20,
                amount=Decimal("100.00"),
            )
        ],
        "project_payments": [
            _owned(20, project_id=100, amount=Decimal("100.00"))
        ],
        "supplier_invoices": [
            _owned(
                40,
                project_id=100,
                warehouse_invoice_id=50,
                amount=Decimal("200.00"),
                paid_amount=Decimal("100.00"),
            )
        ],
        "warehouse_invoices": [
            _owned(50, project_id=100, supplier_invoice_id=40)
        ],
        "accountable_payments": [
            _owned(
                60,
                project_id=100,
                amount=Decimal("300.00"),
                spent_amount=Decimal("50.00"),
            )
        ],
        "accountable_expenses": [
            _owned(
                70,
                project_id=100,
                payment_id=60,
                amount=Decimal("50.00"),
            )
        ],
        "expense_reports": [
            _owned(
                80,
                project_id=100,
                issued_amount=Decimal("100.00"),
                spent_amount=Decimal("40.00"),
                balance=Decimal("60.00"),
            )
        ],
        "staff": [_owned(90)],
        "salary_payments": [_owned(100, staff_id=90, month="2026-08")],
        "own_expenses": [_owned(110, project_id=100, expense_id=120)],
        "expenses": [_owned(120, project_id=100, own_expense_id=110)],
    }


def _reason_codes(report):
    return [finding["reasonCode"] for finding in report["findings"]]


class AccountingExceptionProjectionTests(unittest.TestCase):
    def test_clear_snapshot_is_one_company_bounded_and_detached(self):
        rows = _clear_rows()
        original = copy.deepcopy(rows)

        report = build_accounting_exception_projection(1, rows)

        self.assertEqual(report, {
            "version": "accounting-exception-projection-v1",
            "companyId": 1,
            "state": "clear",
            "scanComplete": True,
            "sourceCounts": {
                source: len(rows[source]) for source in ACCOUNTING_EXCEPTION_SOURCES
            },
            "findingCount": 0,
            "findings": [],
            "truncated": False,
            "blockers": [],
        })
        self.assertEqual(rows, original)
        report["sourceCounts"]["staff"] = 999
        self.assertEqual(rows, original)

    def test_fixed_codes_cover_every_approved_hard_contradiction(self):
        cases = []

        def case(reason, source, patch):
            rows = _clear_rows()
            rows[source][0].update(patch)
            cases.append((reason, rows))

        case(
            "accounting_brigade_ledger_link_missing",
            "brigade_payments",
            {"project_payment_id": None},
        )
        case(
            "accounting_brigade_ledger_not_found",
            "brigade_payments",
            {"project_payment_id": 999},
        )
        case(
            "accounting_brigade_ledger_project_mismatch",
            "project_payments",
            {"project_id": 101},
        )
        case(
            "accounting_brigade_ledger_amount_mismatch",
            "project_payments",
            {"amount": Decimal("99.00")},
        )
        case(
            "accounting_supplier_warehouse_link_not_found",
            "supplier_invoices",
            {"warehouse_invoice_id": 999},
        )
        case(
            "accounting_supplier_warehouse_link_nonreciprocal",
            "warehouse_invoices",
            {"supplier_invoice_id": None},
        )
        case(
            "accounting_supplier_invoice_overpaid",
            "supplier_invoices",
            {"paid_amount": Decimal("200.01")},
        )
        case(
            "accounting_accountable_expense_parent_not_found",
            "accountable_expenses",
            {"payment_id": 999},
        )
        case(
            "accounting_accountable_expense_parent_project_mismatch",
            "accountable_expenses",
            {"project_id": 101},
        )
        case(
            "accounting_accountable_spent_sum_mismatch",
            "accountable_payments",
            {"spent_amount": Decimal("50.01")},
        )
        case(
            "accounting_accountable_advance_exceeded",
            "accountable_payments",
            {"amount": Decimal("49.99")},
        )
        case(
            "accounting_expense_report_balance_mismatch",
            "expense_reports",
            {"balance": Decimal("60.01")},
        )
        case(
            "accounting_salary_staff_not_found",
            "salary_payments",
            {"staff_id": 999},
        )
        case(
            "accounting_salary_month_invalid",
            "salary_payments",
            {"month": "0000-01"},
        )
        case(
            "accounting_own_expense_link_not_found",
            "own_expenses",
            {"expense_id": 999},
        )
        case(
            "accounting_own_expense_link_nonreciprocal",
            "expenses",
            {"own_expense_id": None},
        )
        case(
            "accounting_own_expense_link_project_mismatch",
            "expenses",
            {"project_id": 101},
        )

        for expected_reason, rows in cases:
            with self.subTest(expected_reason):
                report = build_accounting_exception_projection(1, rows)
                self.assertEqual(report["state"], "review_required")
                self.assertIn(expected_reason, _reason_codes(report))

        reciprocal_project_mismatch = cases[-1][1]
        mismatch_report = build_accounting_exception_projection(
            1, reciprocal_project_mismatch
        )
        self.assertEqual(
            _reason_codes(mismatch_report).count(
                "accounting_own_expense_link_project_mismatch"
            ),
            1,
        )

    def test_numeric_findings_expose_only_the_exact_required_decimal_values(self):
        rows = _clear_rows()
        rows["project_payments"][0]["amount"] = Decimal("99.990")
        rows["supplier_invoices"][0]["paid_amount"] = Decimal("200.010")
        rows["accountable_payments"][0].update({
            "amount": Decimal("49.990"),
            "spent_amount": Decimal("50.010"),
        })
        rows["expense_reports"][0]["balance"] = Decimal("60.010")

        report = build_accounting_exception_projection(1, rows)
        findings = {finding["reasonCode"]: finding for finding in report["findings"]}

        self.assertEqual(
            findings["accounting_brigade_ledger_amount_mismatch"],
            {
                "reasonCode": "accounting_brigade_ledger_amount_mismatch",
                "subjectKind": "brigade_payment",
                "subjectId": 30,
                "projectId": 100,
                "storedAmount": "100",
                "linkedAmount": "99.99",
            },
        )
        self.assertEqual(
            findings["accounting_supplier_invoice_overpaid"]["invoiceAmount"],
            "200",
        )
        self.assertEqual(
            findings["accounting_supplier_invoice_overpaid"]["paidAmount"],
            "200.01",
        )
        self.assertEqual(
            findings["accounting_accountable_spent_sum_mismatch"]["childAmountSum"],
            "50",
        )
        self.assertEqual(
            findings["accounting_accountable_advance_exceeded"]["advanceAmount"],
            "49.99",
        )
        self.assertEqual(
            findings["accounting_expense_report_balance_mismatch"]["expectedBalance"],
            "60",
        )

    def test_decimal_arithmetic_is_exact_and_never_uses_binary_float(self):
        rows = _clear_rows()
        rows["accountable_payments"][0].update({
            "amount": Decimal("0.30"),
            "spent_amount": Decimal("0.30"),
        })
        rows["accountable_expenses"] = [
            _owned(
                70,
                project_id=100,
                payment_id=60,
                amount=Decimal("0.10"),
            ),
            _owned(
                71,
                project_id=100,
                payment_id=60,
                amount=Decimal("0.20"),
            ),
        ]

        report = build_accounting_exception_projection(1, rows)

        self.assertEqual(report["state"], "clear")
        self.assertEqual(report["findingCount"], 0)

        rows["accountable_expenses"][0]["amount"] = 0.1
        rejected = build_accounting_exception_projection(1, rows)
        self.assertEqual(rejected["state"], "incomplete")
        self.assertEqual(rejected["findings"], [])

    def test_findings_are_deterministic_capped_and_counted_before_truncation(self):
        rows = _clear_rows()
        rows["staff"] = [
            _owned(1000 + index) for index in range(1, 106)
        ]
        rows["salary_payments"] = [
            _owned(
                index,
                staff_id=1000 + index,
                month="2026-99",
            )
            for index in range(105, 0, -1)
        ]
        original = copy.deepcopy(rows)

        first = build_accounting_exception_projection(1, rows)
        rows["salary_payments"].reverse()
        rows["staff"].reverse()
        second = build_accounting_exception_projection(1, rows)

        self.assertEqual(first, second)
        self.assertEqual(first["state"], "review_required")
        self.assertEqual(first["findingCount"], 105)
        self.assertEqual(len(first["findings"]), 100)
        self.assertTrue(first["truncated"])
        self.assertEqual(
            [finding["subjectId"] for finding in first["findings"]],
            list(range(1, 101)),
        )
        self.assertEqual(rows["salary_payments"], list(reversed(original["salary_payments"])))

    def test_foreign_quarantined_unknown_and_malformed_rows_fail_closed(self):
        marker = "PRIVATE_ACCOUNTING_CONTENT"
        cases = []

        foreign = _clear_rows()
        foreign["staff"][0]["company_id"] = 2
        cases.append(foreign)

        quarantined = _clear_rows()
        quarantined["expenses"][0]["owner_status"] = "quarantined"
        cases.append(quarantined)

        unknown = _clear_rows()
        unknown["salary_payments"][0]["owner_status"] = "mystery"
        cases.append(unknown)

        duplicate = _clear_rows()
        duplicate["staff"].append(dict(duplicate["staff"][0]))
        cases.append(duplicate)

        malformed = _clear_rows()
        malformed["supplier_invoices"][0]["amount"] = Decimal("NaN")
        malformed["brigade_payments"][0]["project_payment_id"] = None
        cases.append(malformed)

        missing_source = _clear_rows()
        missing_source.pop("staff")
        cases.append(missing_source)

        unknown_source = _clear_rows()
        unknown_source["private_rows"] = []
        cases.append(unknown_source)

        for rows in cases:
            for source_rows in rows.values():
                if type(source_rows) is list:
                    for row in source_rows:
                        row["private_note"] = marker
            with self.subTest(case=len(cases)):
                report = build_accounting_exception_projection(1, rows)
                self.assertEqual(report["state"], "incomplete")
                self.assertFalse(report["scanComplete"])
                self.assertEqual(report["findingCount"], 0)
                self.assertEqual(report["findings"], [])
                self.assertEqual(
                    report["blockers"],
                    ["accounting_exception_projection_input_invalid"],
                )
                self.assertNotIn(marker, repr(report))

    def test_incomplete_scan_has_no_partial_findings(self):
        rows = _clear_rows()
        rows["brigade_payments"][0]["project_payment_id"] = None

        report = build_accounting_exception_projection(
            1, rows, scan_complete=False
        )

        self.assertEqual(report["state"], "incomplete")
        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            report["blockers"],
            ["accounting_exception_projection_source_incomplete"],
        )

    def test_explicit_reverse_links_are_checked_from_both_sides(self):
        warehouse_rows = _clear_rows()
        warehouse_rows["supplier_invoices"] = []
        warehouse = build_accounting_exception_projection(1, warehouse_rows)
        self.assertIn(
            "accounting_supplier_warehouse_link_not_found",
            _reason_codes(warehouse),
        )

        expense_rows = _clear_rows()
        expense_rows["own_expenses"][0].update({
            "project_id": 101,
            "expense_id": None,
        })
        own = build_accounting_exception_projection(1, expense_rows)
        self.assertIn(
            "accounting_own_expense_link_nonreciprocal",
            _reason_codes(own),
        )
        self.assertIn(
            "accounting_own_expense_link_project_mismatch",
            _reason_codes(own),
        )

    def test_output_is_allowlisted_and_never_copies_raw_content(self):
        marker = "PRIVATE_NOTE_PHOTO_BANK_FILE_JSON"
        rows = _clear_rows()
        for source_rows in rows.values():
            for row in source_rows:
                row.update({
                    "note": marker,
                    "purpose": marker,
                    "photo_url": marker,
                    "items_json": {"private": marker},
                })
        rows["project_payments"][0]["amount"] = Decimal("99")

        report = build_accounting_exception_projection(1, rows)

        self.assertNotIn(marker, repr(report))
        allowed = {
            "reasonCode", "subjectKind", "subjectId", "projectId",
            "relatedId", "storedAmount", "linkedAmount", "invoiceAmount",
            "paidAmount", "storedSpentAmount", "childAmountSum",
            "advanceAmount", "issuedAmount", "spentAmount", "storedBalance",
            "expectedBalance",
        }
        self.assertTrue(report["findings"])
        self.assertTrue(all(set(finding) <= allowed for finding in report["findings"]))

    def test_module_stays_private_and_has_no_io_or_registration_surface(self):
        root = Path(__file__).resolve().parents[3]
        source = (Path(__file__).with_name("projection.py")).read_text(
            encoding="utf-8"
        )
        package_source = (Path(__file__).with_name("__init__.py")).read_text(
            encoding="utf-8"
        )
        main_source = (root / "backend/main.py").read_text(encoding="utf-8")

        self.assertNotIn("psycopg", source)
        self.assertNotIn("fastapi", source.lower())
        self.assertNotIn("backend.db", source)
        self.assertNotRegex(source.upper(), r"\b(SELECT|INSERT|UPDATE|DELETE)\b")
        self.assertNotIn("projection", package_source)
        self.assertNotIn("accounting_exception_checks.projection", main_source)

    def test_source_rows_and_decimal_rendering_are_bounded(self):
        at_limit = _clear_rows()
        at_limit["staff"] = [
            _owned(index) for index in range(1, MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS + 1)
        ]
        at_limit["salary_payments"] = []
        accepted = build_accounting_exception_projection(1, at_limit)
        self.assertEqual(accepted["state"], "clear")
        self.assertEqual(
            accepted["sourceCounts"]["staff"],
            MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS,
        )

        too_many = copy.deepcopy(at_limit)
        too_many["staff"].append(
            _owned(MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS + 1)
        )
        rejected = build_accounting_exception_projection(1, too_many)
        self.assertEqual(rejected["state"], "incomplete")
        self.assertEqual(rejected["findings"], [])

        huge_decimal = _clear_rows()
        huge_decimal["supplier_invoices"][0]["amount"] = Decimal("1e1000")
        rejected = build_accounting_exception_projection(1, huge_decimal)
        self.assertEqual(rejected["state"], "incomplete")
        self.assertLess(len(repr(rejected)), 2000)

        decimal_boundary = _clear_rows()
        decimal_boundary["supplier_invoices"][0].update({
            "amount": Decimal("1e-62"),
            "paid_amount": Decimal("0"),
        })
        self.assertEqual(
            build_accounting_exception_projection(1, decimal_boundary)["state"],
            "clear",
        )
        decimal_boundary["supplier_invoices"][0]["amount"] = Decimal("1e-63")
        self.assertEqual(
            build_accounting_exception_projection(1, decimal_boundary)["state"],
            "incomplete",
        )

    def test_control_parameters_use_exact_builtin_types(self):
        rows = _clear_rows()
        for company_id in (True, 0, -1, "1"):
            with self.subTest(company_id=company_id):
                with self.assertRaisesRegex(
                    ValueError, "accounting_exception_projection_input_invalid"
                ):
                    build_accounting_exception_projection(company_id, rows)

        for max_findings in (True, 0, 101, 1.0):
            with self.subTest(max_findings=max_findings):
                with self.assertRaisesRegex(
                    ValueError, "accounting_exception_projection_input_invalid"
                ):
                    build_accounting_exception_projection(
                        1, rows, max_findings=max_findings
                    )

        with self.assertRaisesRegex(
            ValueError, "accounting_exception_projection_input_invalid"
        ):
            build_accounting_exception_projection(1, rows, scan_complete=1)


if __name__ == "__main__":
    unittest.main()
