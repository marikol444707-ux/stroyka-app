"""Default-off HTTP adapter for read-only accounting exception checks."""

import re
from typing import Optional

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from backend.auth import CookieSessionAuthenticationError

from .projection import (
    ACCOUNTING_EXCEPTION_SOURCES,
    MAX_ACCOUNTING_EXCEPTION_FINDINGS,
    MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS,
)


_MAX_ID = 9223372036854775807
_MAX_ALLOWED_COMPANIES = 100
_MAX_TOTAL_FINDINGS = 20000
_PATH = "/accounting-exception-checks"
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, X-Company-Id, X-Company-Mode",
}
_AUTHENTICATION_REQUIRED = (
    "accounting_exception_review_authentication_required"
)
_REQUEST_FORBIDDEN = "accounting_exception_review_request_forbidden"
_NOT_FOUND = "accounting_exception_review_not_found"
_REQUEST_INVALID = "accounting_exception_review_request_invalid"
_UNAVAILABLE = "accounting_exception_review_unavailable"
_PUBLIC_FIELDS = frozenset({
    "version", "companyId", "state", "scanComplete", "sourceCounts",
    "findingCount", "findings", "truncated", "blockers",
})
_BASE_FINDING_FIELDS = frozenset({
    "reasonCode", "subjectKind", "subjectId", "projectId",
})
_MONEY_RE = re.compile(
    r"^-?(?:0|[1-9][0-9]{0,63})(?:\.[0-9]{1,64})?$"
)
_FINDING_CONTRACTS = {
    "accounting_brigade_ledger_link_missing": (
        frozenset({"brigade_payment"}), frozenset(), frozenset(),
    ),
    "accounting_brigade_ledger_not_found": (
        frozenset({"brigade_payment"}), frozenset({"relatedId"}), frozenset(),
    ),
    "accounting_brigade_ledger_project_mismatch": (
        frozenset({"brigade_payment"}), frozenset({"relatedId"}), frozenset(),
    ),
    "accounting_brigade_ledger_amount_mismatch": (
        frozenset({"brigade_payment"}),
        frozenset(),
        frozenset({"storedAmount", "linkedAmount"}),
    ),
    "accounting_supplier_warehouse_link_not_found": (
        frozenset({"supplier_invoice", "warehouse_invoice"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_supplier_warehouse_link_nonreciprocal": (
        frozenset({"supplier_invoice", "warehouse_invoice"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_supplier_invoice_overpaid": (
        frozenset({"supplier_invoice"}),
        frozenset(),
        frozenset({"invoiceAmount", "paidAmount"}),
    ),
    "accounting_accountable_expense_parent_not_found": (
        frozenset({"accountable_expense"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_accountable_expense_parent_project_mismatch": (
        frozenset({"accountable_expense"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_accountable_spent_sum_mismatch": (
        frozenset({"accountable_payment"}),
        frozenset(),
        frozenset({"storedSpentAmount", "childAmountSum"}),
    ),
    "accounting_accountable_advance_exceeded": (
        frozenset({"accountable_payment"}),
        frozenset(),
        frozenset({"advanceAmount", "childAmountSum"}),
    ),
    "accounting_expense_report_balance_mismatch": (
        frozenset({"expense_report"}),
        frozenset(),
        frozenset({
            "issuedAmount", "spentAmount", "storedBalance",
            "expectedBalance",
        }),
    ),
    "accounting_salary_staff_not_found": (
        frozenset({"salary_payment"}), frozenset({"relatedId"}), frozenset(),
    ),
    "accounting_salary_month_invalid": (
        frozenset({"salary_payment"}), frozenset(), frozenset(),
    ),
    "accounting_own_expense_link_not_found": (
        frozenset({"own_expense", "manual_expense"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_own_expense_link_nonreciprocal": (
        frozenset({"own_expense", "manual_expense"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
    "accounting_own_expense_link_project_mismatch": (
        frozenset({"own_expense", "manual_expense"}),
        frozenset({"relatedId"}),
        frozenset(),
    ),
}
_BLOCKERS = frozenset({
    "accounting_exception_projection_input_invalid",
    "accounting_exception_projection_source_incomplete",
})


def _response(content, *, status_code=200, retry_after=None):
    headers = dict(_RESPONSE_HEADERS)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _error(status_code, detail, *, retry_after=None):
    return _response(
        {"detail": detail}, status_code=status_code, retry_after=retry_after,
    )


def _valid_allowlist(value):
    return (
        type(value) is frozenset
        and 0 < len(value) <= _MAX_ALLOWED_COMPANIES
        and all(type(item) is int and 0 < item <= _MAX_ID for item in value)
    )


def _valid_finance_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(type(item) is str and 0 < len(item) <= 64 for item in value)
    )


def _company_id(value, mode):
    if (
        type(mode) is not str
        or mode != "company"
        or type(value) is not str
        or not value
        or len(value) > 19
        or value[0] not in "123456789"
        or not value.isascii()
        or not value.isdecimal()
    ):
        return None
    parsed = int(value)
    return parsed if parsed <= _MAX_ID else None


def _valid_authentication(value):
    if (
        type(value) is not dict
        or set(value) != {"authenticationKind", "sessionHash"}
        or value.get("authenticationKind") != "cookie_session"
    ):
        return False
    session_hash = value.get("sessionHash")
    return (
        type(session_hash) is str
        and len(session_hash) == 64
        and all(character in "0123456789abcdef" for character in session_hash)
    )


def _fixed_error_code(error):
    try:
        state = object.__getattribute__(error, "__dict__")
    except Exception:
        return None
    if type(state) is not dict:
        return None
    code = state.get("code")
    return code if type(code) is str else None


def _runtime_failure(error):
    code = _fixed_error_code(error)
    if code == "accounting_exception_review_input_invalid":
        return _error(422, _REQUEST_INVALID)
    if code == "accounting_exception_review_authentication_required":
        return _error(401, _AUTHENTICATION_REQUIRED)
    if code == "accounting_exception_review_request_forbidden":
        return _error(403, _REQUEST_FORBIDDEN)
    return _error(503, _UNAVAILABLE, retry_after=30)


def _positive_id(value, *, optional=False):
    if optional and value is None:
        return True
    return type(value) is int and 0 < value <= _MAX_ID


def _validated_finding(value):
    if type(value) is not dict:
        raise ValueError("invalid finding")
    reason = value.get("reasonCode")
    contract = _FINDING_CONTRACTS.get(reason)
    if contract is None:
        raise ValueError("invalid finding")
    subject_kinds, id_fields, money_fields = contract
    expected_fields = _BASE_FINDING_FIELDS | id_fields | money_fields
    if (
        set(value) != expected_fields
        or value.get("subjectKind") not in subject_kinds
        or not _positive_id(value.get("subjectId"))
        or not _positive_id(value.get("projectId"), optional=True)
        or any(not _positive_id(value.get(field)) for field in id_fields)
        or any(
            type(value.get(field)) is not str
            or _MONEY_RE.fullmatch(value[field]) is None
            for field in money_fields
        )
    ):
        raise ValueError("invalid finding")
    return dict(value)


def _validated_public_result(value, company_id):
    if (
        type(value) is not dict
        or set(value) != _PUBLIC_FIELDS
        or value.get("version") != "accounting-exception-projection-v1"
        or value.get("companyId") != company_id
        or type(value.get("companyId")) is not int
        or value.get("state") not in {"clear", "review_required", "incomplete"}
        or type(value.get("scanComplete")) is not bool
        or type(value.get("findingCount")) is not int
        or not 0 <= value["findingCount"] <= _MAX_TOTAL_FINDINGS
        or type(value.get("findings")) is not list
        or len(value["findings"]) > MAX_ACCOUNTING_EXCEPTION_FINDINGS
        or type(value.get("truncated")) is not bool
        or type(value.get("blockers")) is not list
    ):
        raise ValueError("invalid result")
    counts = value.get("sourceCounts")
    if (
        type(counts) is not dict
        or set(counts) != set(ACCOUNTING_EXCEPTION_SOURCES)
        or any(
            type(count) is not int
            or not 0 <= count <= MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS
            for count in counts.values()
        )
    ):
        raise ValueError("invalid result")
    findings = [_validated_finding(item) for item in value["findings"]]
    finding_count = value["findingCount"]
    state = value["state"]
    if state == "clear":
        valid_state = (
            value["scanComplete"] is True
            and finding_count == 0
            and findings == []
            and value["truncated"] is False
            and value["blockers"] == []
        )
    elif state == "review_required":
        valid_state = (
            value["scanComplete"] is True
            and finding_count > 0
            and len(findings) == min(
                finding_count, MAX_ACCOUNTING_EXCEPTION_FINDINGS,
            )
            and value["truncated"] is (
                finding_count > MAX_ACCOUNTING_EXCEPTION_FINDINGS
            )
            and value["blockers"] == []
        )
    else:
        valid_state = (
            value["scanComplete"] is False
            and finding_count == 0
            and findings == []
            and value["truncated"] is False
            and len(value["blockers"]) == 1
            and value["blockers"][0] in _BLOCKERS
        )
    if not valid_state:
        raise ValueError("invalid result")
    return {
        "version": value["version"],
        "companyId": company_id,
        "state": state,
        "scanComplete": value["scanComplete"],
        "sourceCounts": {
            source: counts[source] for source in ACCOUNTING_EXCEPTION_SOURCES
        },
        "findingCount": finding_count,
        "findings": findings,
        "truncated": value["truncated"],
        "blockers": list(value["blockers"]),
    }


def register_accounting_exception_check_routes(app, deps):
    """Register one GET route only for an exact enabled configuration."""

    if deps.get("enabled") is not True:
        return None
    allowed_company_ids = deps.get("allowed_company_ids")
    finance_roles = deps.get("finance_roles")
    if (
        not _valid_allowlist(allowed_company_ids)
        or not _valid_finance_roles(finance_roles)
    ):
        return None

    get_db = deps["get_db"]
    build_authentication = deps["build_cookie_session_authentication"]
    run_snapshot = deps["run_authorized_accounting_exception_snapshot"]

    @app.get(_PATH)
    def get_accounting_exception_checks(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_company_id: Optional[str] = Header(
            default=None, alias="X-Company-Id",
        ),
        x_company_mode: Optional[str] = Header(
            default=None, alias="X-Company-Mode",
        ),
    ):
        company_id = _company_id(x_company_id, x_company_mode)
        if company_id is None:
            return _error(422, _REQUEST_INVALID)
        try:
            authentication = build_authentication(
                request,
                authorization,
                None,
                require_csrf=False,
            )
        except CookieSessionAuthenticationError as error:
            if error.code == "cookie_session_csrf_invalid":
                return _error(403, _REQUEST_FORBIDDEN)
            return _error(401, _AUTHENTICATION_REQUIRED)
        except MemoryError:
            raise
        except Exception:
            return _error(503, _UNAVAILABLE, retry_after=30)
        if not _valid_authentication(authentication):
            return _error(503, _UNAVAILABLE, retry_after=30)
        if company_id not in allowed_company_ids:
            return _error(404, _NOT_FOUND)
        try:
            result = run_snapshot(
                get_db,
                authentication,
                company_id,
                finance_roles,
            )
            result = _validated_public_result(result, company_id)
        except MemoryError:
            raise
        except Exception as error:
            return _runtime_failure(error)
        return _response(result)

    return None


__all__ = []
