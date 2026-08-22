"""Closed exact-ID request contract for manual accounting ownership repair.

This A11.2b1 slice is deliberately pure: it validates and fingerprints an
operator request but cannot connect to a database or apply any change.
"""

import hashlib
import json


_VERSION = "accounting-ownership-remediation-v1"
_COMPANY_ONLY_SOURCES = frozenset(("staff", "salary_payments"))
_PROJECT_SOURCES = frozenset((
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "own_expenses",
    "expenses",
))
_SOURCES = _COMPANY_ONLY_SOURCES | _PROJECT_SOURCES


def _input_error():
    return ValueError("accounting_remediation_input_invalid")


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


def build_accounting_ownership_remediation_request(
    *,
    source,
    record_id,
    company_id,
    project_id,
    operator_user_id,
):
    if type(source) is not str or source not in _SOURCES:
        raise _input_error() from None
    record_id = _positive_int(record_id)
    company_id = _positive_int(company_id)
    operator_user_id = _positive_int(operator_user_id)
    if record_id is None or company_id is None or operator_user_id is None:
        raise _input_error() from None
    if source in _COMPANY_ONLY_SOURCES:
        if project_id is not None:
            raise _input_error() from None
    else:
        project_id = _positive_int(project_id)
        if project_id is None:
            raise _input_error() from None

    identity = {
        "version": _VERSION,
        "source": source,
        "recordId": record_id,
        "companyId": company_id,
        "projectId": project_id,
        "operatorUserId": operator_user_id,
    }
    payload = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "version": _VERSION,
        "dryRun": True,
        "applyAllowed": False,
        "writesAttempted": 0,
        "auditWritesAttempted": 0,
        "source": source,
        "recordId": record_id,
        "companyId": company_id,
        "projectId": project_id,
        "operatorUserId": operator_user_id,
        "requestSha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
    }
