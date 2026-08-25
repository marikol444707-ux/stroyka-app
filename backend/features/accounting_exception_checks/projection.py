"""Pure hard-contradiction projection for verified accounting rows.

This private A11.4 module has no database, HTTP, filesystem, or registration
surface.  It accepts only detached, one-company normalized rows and returns a
small allowlisted review result.
"""

from collections import defaultdict
from decimal import Decimal
import re


ACCOUNTING_EXCEPTION_SOURCES = (
    "brigade_contracts",
    "brigade_payments",
    "project_payments",
    "supplier_invoices",
    "warehouse_invoices",
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "staff",
    "salary_payments",
    "own_expenses",
    "expenses",
)

MAX_ACCOUNTING_EXCEPTION_FINDINGS = 100
MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS = 1000
_MAX_MONEY_DIGITS = 64
_VERSION = "accounting-exception-projection-v1"
_INPUT_BLOCKER = "accounting_exception_projection_input_invalid"
_SOURCE_BLOCKER = "accounting_exception_projection_source_incomplete"
_MONTH_RE = re.compile(r"^(?!0000)[0-9]{4}-(?:0[1-9]|1[0-2])$")

_REASON_ORDER = (
    "accounting_brigade_ledger_link_missing",
    "accounting_brigade_ledger_not_found",
    "accounting_brigade_ledger_project_mismatch",
    "accounting_brigade_ledger_amount_mismatch",
    "accounting_supplier_warehouse_link_not_found",
    "accounting_supplier_warehouse_link_nonreciprocal",
    "accounting_supplier_invoice_overpaid",
    "accounting_accountable_expense_parent_not_found",
    "accounting_accountable_expense_parent_project_mismatch",
    "accounting_accountable_spent_sum_mismatch",
    "accounting_accountable_advance_exceeded",
    "accounting_expense_report_balance_mismatch",
    "accounting_salary_staff_not_found",
    "accounting_salary_month_invalid",
    "accounting_own_expense_link_not_found",
    "accounting_own_expense_link_nonreciprocal",
    "accounting_own_expense_link_project_mismatch",
)
_REASON_RANK = {reason: index for index, reason in enumerate(_REASON_ORDER)}


class _ProjectionInputError(Exception):
    pass


def _positive_int(value):
    if type(value) is not int or value <= 0:
        raise _ProjectionInputError
    return value


def _optional_positive_int(value):
    if value is None:
        return None
    return _positive_int(value)


def _money(value, *, nonnegative=True):
    if type(value) is int:
        value = Decimal(value)
    if type(value) is not Decimal or not value.is_finite():
        raise _ProjectionInputError
    if nonnegative and value < 0:
        raise _ProjectionInputError
    digits = value.as_tuple().digits
    adjusted = value.adjusted() if value else 0
    if (
        len(digits) > _MAX_MONEY_DIGITS
        or adjusted >= _MAX_MONEY_DIGITS
        or adjusted <= -(_MAX_MONEY_DIGITS - 1)
    ):
        raise _ProjectionInputError
    return value


def _money_text(value):
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _require_fields(row, fields):
    if any(field not in row for field in fields):
        raise _ProjectionInputError


def _normalize_row(source, row, company_id):
    if type(row) is not dict:
        raise _ProjectionInputError
    result = dict(row)
    result["id"] = _positive_int(result.get("id"))
    if _positive_int(result.get("company_id")) != company_id:
        raise _ProjectionInputError
    if result.get("owner_status") != "verified":
        raise _ProjectionInputError

    if source == "brigade_contracts":
        _require_fields(result, ("project_id",))
        result["project_id"] = _positive_int(result["project_id"])
    elif source == "brigade_payments":
        _require_fields(
            result, ("contract_id", "project_payment_id", "amount")
        )
        result["contract_id"] = _positive_int(result["contract_id"])
        result["project_payment_id"] = _optional_positive_int(
            result["project_payment_id"]
        )
        result["amount"] = _money(result["amount"])
    elif source == "project_payments":
        _require_fields(result, ("project_id", "amount"))
        result["project_id"] = _positive_int(result["project_id"])
        result["amount"] = _money(result["amount"], nonnegative=False)
    elif source == "supplier_invoices":
        _require_fields(
            result,
            (
                "project_id",
                "warehouse_invoice_id",
                "amount",
                "paid_amount",
            ),
        )
        result["project_id"] = _optional_positive_int(result["project_id"])
        result["warehouse_invoice_id"] = _optional_positive_int(
            result["warehouse_invoice_id"]
        )
        result["amount"] = _money(result["amount"])
        result["paid_amount"] = _money(result["paid_amount"])
    elif source == "warehouse_invoices":
        _require_fields(result, ("project_id", "supplier_invoice_id"))
        result["project_id"] = _optional_positive_int(result["project_id"])
        result["supplier_invoice_id"] = _optional_positive_int(
            result["supplier_invoice_id"]
        )
    elif source == "accountable_payments":
        _require_fields(result, ("project_id", "amount", "spent_amount"))
        result["project_id"] = _positive_int(result["project_id"])
        result["amount"] = _money(result["amount"])
        result["spent_amount"] = _money(result["spent_amount"])
    elif source == "accountable_expenses":
        _require_fields(result, ("project_id", "payment_id", "amount"))
        result["project_id"] = _positive_int(result["project_id"])
        result["payment_id"] = _positive_int(result["payment_id"])
        result["amount"] = _money(result["amount"])
    elif source == "expense_reports":
        _require_fields(
            result,
            ("project_id", "issued_amount", "spent_amount", "balance"),
        )
        result["project_id"] = _positive_int(result["project_id"])
        result["issued_amount"] = _money(result["issued_amount"])
        result["spent_amount"] = _money(result["spent_amount"])
        result["balance"] = _money(result["balance"], nonnegative=False)
    elif source == "staff":
        pass
    elif source == "salary_payments":
        _require_fields(result, ("staff_id", "month"))
        result["staff_id"] = _positive_int(result["staff_id"])
        if type(result["month"]) is not str:
            raise _ProjectionInputError
    elif source == "own_expenses":
        _require_fields(result, ("project_id", "expense_id"))
        result["project_id"] = _optional_positive_int(result["project_id"])
        result["expense_id"] = _optional_positive_int(result["expense_id"])
    elif source == "expenses":
        _require_fields(result, ("project_id", "own_expense_id"))
        result["project_id"] = _optional_positive_int(result["project_id"])
        result["own_expense_id"] = _optional_positive_int(
            result["own_expense_id"]
        )
    else:
        raise _ProjectionInputError
    return result


def _normalize_sources(company_id, rows_by_source):
    if type(rows_by_source) is not dict:
        raise _ProjectionInputError
    if set(rows_by_source) != set(ACCOUNTING_EXCEPTION_SOURCES):
        raise _ProjectionInputError
    normalized = {}
    for source in ACCOUNTING_EXCEPTION_SOURCES:
        rows = rows_by_source[source]
        if type(rows) not in (list, tuple):
            raise _ProjectionInputError
        if len(rows) > MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS:
            raise _ProjectionInputError
        seen = set()
        clean = []
        for raw in rows:
            row = _normalize_row(source, raw, company_id)
            if row["id"] in seen:
                raise _ProjectionInputError
            seen.add(row["id"])
            clean.append(row)
        normalized[source] = sorted(clean, key=lambda item: item["id"])
    return normalized


def _empty_result(company_id, *, blocker, counts=None):
    return {
        "version": _VERSION,
        "companyId": company_id,
        "state": "incomplete",
        "scanComplete": False,
        "sourceCounts": counts or {
            source: 0 for source in ACCOUNTING_EXCEPTION_SOURCES
        },
        "findingCount": 0,
        "findings": [],
        "truncated": False,
        "blockers": [blocker],
    }


def _finding(reason, kind, subject_id, project_id, **details):
    return {
        "reasonCode": reason,
        "subjectKind": kind,
        "subjectId": subject_id,
        "projectId": project_id,
        **details,
    }


def _indexes(rows):
    return {
        source: {row["id"]: row for row in source_rows}
        for source, source_rows in rows.items()
    }


def _brigade_findings(rows, by_id):
    findings = []
    contracts = by_id["brigade_contracts"]
    ledgers = by_id["project_payments"]
    for payment in rows["brigade_payments"]:
        contract = contracts.get(payment["contract_id"])
        if contract is None:
            raise _ProjectionInputError
        project_id = contract["project_id"]
        ledger_id = payment["project_payment_id"]
        if ledger_id is None:
            findings.append(_finding(
                "accounting_brigade_ledger_link_missing",
                "brigade_payment",
                payment["id"],
                project_id,
            ))
            continue
        ledger = ledgers.get(ledger_id)
        if ledger is None:
            findings.append(_finding(
                "accounting_brigade_ledger_not_found",
                "brigade_payment",
                payment["id"],
                project_id,
                relatedId=ledger_id,
            ))
            continue
        if ledger["project_id"] != project_id:
            findings.append(_finding(
                "accounting_brigade_ledger_project_mismatch",
                "brigade_payment",
                payment["id"],
                project_id,
                relatedId=ledger_id,
            ))
        if ledger["amount"] != payment["amount"]:
            findings.append(_finding(
                "accounting_brigade_ledger_amount_mismatch",
                "brigade_payment",
                payment["id"],
                project_id,
                storedAmount=_money_text(payment["amount"]),
                linkedAmount=_money_text(ledger["amount"]),
            ))
    return findings


def _supplier_findings(rows, by_id):
    findings = []
    suppliers = by_id["supplier_invoices"]
    warehouses = by_id["warehouse_invoices"]
    for supplier in rows["supplier_invoices"]:
        warehouse_id = supplier["warehouse_invoice_id"]
        if warehouse_id is not None:
            warehouse = warehouses.get(warehouse_id)
            if warehouse is None:
                findings.append(_finding(
                    "accounting_supplier_warehouse_link_not_found",
                    "supplier_invoice",
                    supplier["id"],
                    supplier["project_id"],
                    relatedId=warehouse_id,
                ))
            elif warehouse["supplier_invoice_id"] != supplier["id"]:
                findings.append(_finding(
                    "accounting_supplier_warehouse_link_nonreciprocal",
                    "supplier_invoice",
                    supplier["id"],
                    supplier["project_id"],
                    relatedId=warehouse_id,
                ))
        if supplier["paid_amount"] > supplier["amount"]:
            findings.append(_finding(
                "accounting_supplier_invoice_overpaid",
                "supplier_invoice",
                supplier["id"],
                supplier["project_id"],
                invoiceAmount=_money_text(supplier["amount"]),
                paidAmount=_money_text(supplier["paid_amount"]),
            ))
    for warehouse in rows["warehouse_invoices"]:
        supplier_id = warehouse["supplier_invoice_id"]
        if supplier_id is None:
            continue
        supplier = suppliers.get(supplier_id)
        if supplier is None:
            findings.append(_finding(
                "accounting_supplier_warehouse_link_not_found",
                "warehouse_invoice",
                warehouse["id"],
                warehouse["project_id"],
                relatedId=supplier_id,
            ))
        elif supplier["warehouse_invoice_id"] != warehouse["id"]:
            findings.append(_finding(
                "accounting_supplier_warehouse_link_nonreciprocal",
                "warehouse_invoice",
                warehouse["id"],
                warehouse["project_id"],
                relatedId=supplier_id,
            ))
    return findings


def _accountable_findings(rows, by_id):
    findings = []
    payments = by_id["accountable_payments"]
    child_sums = defaultdict(Decimal)
    for expense in rows["accountable_expenses"]:
        parent = payments.get(expense["payment_id"])
        if parent is None:
            findings.append(_finding(
                "accounting_accountable_expense_parent_not_found",
                "accountable_expense",
                expense["id"],
                expense["project_id"],
                relatedId=expense["payment_id"],
            ))
            continue
        child_sums[parent["id"]] += expense["amount"]
        if expense["project_id"] != parent["project_id"]:
            findings.append(_finding(
                "accounting_accountable_expense_parent_project_mismatch",
                "accountable_expense",
                expense["id"],
                expense["project_id"],
                relatedId=parent["id"],
            ))
    for payment in rows["accountable_payments"]:
        child_sum = child_sums[payment["id"]]
        if child_sum != payment["spent_amount"]:
            findings.append(_finding(
                "accounting_accountable_spent_sum_mismatch",
                "accountable_payment",
                payment["id"],
                payment["project_id"],
                storedSpentAmount=_money_text(payment["spent_amount"]),
                childAmountSum=_money_text(child_sum),
            ))
        if child_sum > payment["amount"]:
            findings.append(_finding(
                "accounting_accountable_advance_exceeded",
                "accountable_payment",
                payment["id"],
                payment["project_id"],
                advanceAmount=_money_text(payment["amount"]),
                childAmountSum=_money_text(child_sum),
            ))
    return findings


def _report_findings(rows):
    findings = []
    for report in rows["expense_reports"]:
        expected = report["issued_amount"] - report["spent_amount"]
        if report["balance"] != expected:
            findings.append(_finding(
                "accounting_expense_report_balance_mismatch",
                "expense_report",
                report["id"],
                report["project_id"],
                issuedAmount=_money_text(report["issued_amount"]),
                spentAmount=_money_text(report["spent_amount"]),
                storedBalance=_money_text(report["balance"]),
                expectedBalance=_money_text(expected),
            ))
    return findings


def _salary_findings(rows, by_id):
    findings = []
    staff = by_id["staff"]
    for payment in rows["salary_payments"]:
        if payment["staff_id"] not in staff:
            findings.append(_finding(
                "accounting_salary_staff_not_found",
                "salary_payment",
                payment["id"],
                None,
                relatedId=payment["staff_id"],
            ))
        if not _MONTH_RE.fullmatch(payment["month"]):
            findings.append(_finding(
                "accounting_salary_month_invalid",
                "salary_payment",
                payment["id"],
                None,
            ))
    return findings


def _own_expense_findings(rows, by_id):
    findings = []
    own_rows = by_id["own_expenses"]
    expense_rows = by_id["expenses"]
    for own in rows["own_expenses"]:
        expense_id = own["expense_id"]
        if expense_id is None:
            continue
        expense = expense_rows.get(expense_id)
        if expense is None:
            findings.append(_finding(
                "accounting_own_expense_link_not_found",
                "own_expense",
                own["id"],
                own["project_id"],
                relatedId=expense_id,
            ))
            continue
        if expense["own_expense_id"] != own["id"]:
            findings.append(_finding(
                "accounting_own_expense_link_nonreciprocal",
                "own_expense",
                own["id"],
                own["project_id"],
                relatedId=expense_id,
            ))
        if expense["project_id"] != own["project_id"]:
            findings.append(_finding(
                "accounting_own_expense_link_project_mismatch",
                "own_expense",
                own["id"],
                own["project_id"],
                relatedId=expense_id,
            ))
    for expense in rows["expenses"]:
        own_id = expense["own_expense_id"]
        if own_id is None:
            continue
        own = own_rows.get(own_id)
        if own is None:
            findings.append(_finding(
                "accounting_own_expense_link_not_found",
                "manual_expense",
                expense["id"],
                expense["project_id"],
                relatedId=own_id,
            ))
        elif own["expense_id"] != expense["id"]:
            findings.append(_finding(
                "accounting_own_expense_link_nonreciprocal",
                "manual_expense",
                expense["id"],
                expense["project_id"],
                relatedId=own_id,
            ))
        if (
            own is not None
            and own["expense_id"] != expense["id"]
            and own["project_id"] != expense["project_id"]
        ):
            findings.append(_finding(
                "accounting_own_expense_link_project_mismatch",
                "manual_expense",
                expense["id"],
                expense["project_id"],
                relatedId=own_id,
            ))
    return findings


def _sorted_findings(findings):
    unique = {}
    for finding in findings:
        key = tuple(sorted(finding.items()))
        unique[key] = finding
    return sorted(
        unique.values(),
        key=lambda item: (
            _REASON_RANK[item["reasonCode"]],
            item["subjectKind"],
            item["subjectId"],
            item.get("relatedId") or 0,
        ),
    )


def build_accounting_exception_projection(
    company_id,
    rows_by_source,
    *,
    scan_complete=True,
    max_findings=MAX_ACCOUNTING_EXCEPTION_FINDINGS,
):
    """Return a detached, deterministic review projection for one company."""

    if type(company_id) is not int or company_id <= 0:
        raise ValueError(_INPUT_BLOCKER) from None
    if type(scan_complete) is not bool:
        raise ValueError(_INPUT_BLOCKER) from None
    if (
        type(max_findings) is not int
        or max_findings < 1
        or max_findings > MAX_ACCOUNTING_EXCEPTION_FINDINGS
    ):
        raise ValueError(_INPUT_BLOCKER) from None

    try:
        rows = _normalize_sources(company_id, rows_by_source)
        counts = {
            source: len(rows[source]) for source in ACCOUNTING_EXCEPTION_SOURCES
        }
        if not scan_complete:
            return _empty_result(
                company_id, blocker=_SOURCE_BLOCKER, counts=counts
            )
        by_id = _indexes(rows)
        findings = _sorted_findings(
            _brigade_findings(rows, by_id)
            + _supplier_findings(rows, by_id)
            + _accountable_findings(rows, by_id)
            + _report_findings(rows)
            + _salary_findings(rows, by_id)
            + _own_expense_findings(rows, by_id)
        )
    except _ProjectionInputError:
        return _empty_result(company_id, blocker=_INPUT_BLOCKER)

    total = len(findings)
    return {
        "version": _VERSION,
        "companyId": company_id,
        "state": "review_required" if findings else "clear",
        "scanComplete": True,
        "sourceCounts": counts,
        "findingCount": total,
        "findings": [dict(item) for item in findings[:max_findings]],
        "truncated": total > max_findings,
        "blockers": [],
    }
