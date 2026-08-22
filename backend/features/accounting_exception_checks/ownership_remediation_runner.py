"""Transactional exact-record accounting ownership remediation."""

import hashlib
import json
import re

import psycopg2.extras

from backend.features.accounting_exception_checks.ownership_backfill import (
    _apply_ready_rows,
)
from backend.features.accounting_exception_checks.ownership_remediation import (
    build_accounting_ownership_remediation_request,
)
from backend.features.accounting_exception_checks.schema_contract import (
    _schema_contract_is_exact,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCES = (
    "staff", "accountable_payments", "accountable_expenses",
    "expense_reports", "salary_payments", "own_expenses", "expenses",
)
_PROJECT_SOURCES = frozenset((
    "accountable_payments", "accountable_expenses", "expense_reports",
    "own_expenses", "expenses",
))
_OPERATOR_ROLES = ("директор", "зам_директора", "бухгалтер")
_TARGET_QUERIES = {
    "staff": "SELECT id,company_id,company_scope_verified FROM public.staff WHERE id=%s",
    "accountable_payments": (
        "SELECT id,company_id,project_id,company_scope_verified,given_to_id "
        "FROM public.accountable_payments WHERE id=%s"
    ),
    "accountable_expenses": (
        "SELECT id,company_id,project_id,company_scope_verified,payment_id "
        "FROM public.accountable_expenses WHERE id=%s"
    ),
    "expense_reports": (
        "SELECT id,company_id,project_id,company_scope_verified,employee_id "
        "FROM public.expense_reports WHERE id=%s"
    ),
    "salary_payments": (
        "SELECT id,company_id,company_scope_verified,staff_id "
        "FROM public.salary_payments WHERE id=%s"
    ),
    "own_expenses": (
        "SELECT id,company_id,project_id,company_scope_verified "
        "FROM public.own_expenses WHERE id=%s"
    ),
    "expenses": (
        "SELECT id,company_id,project_id,company_scope_verified,own_expense_id "
        "FROM public.expenses WHERE id=%s"
    ),
}
_LINK_FIELDS = {
    "staff": (),
    "accountable_payments": ("given_to_id",),
    "accountable_expenses": ("payment_id",),
    "expense_reports": ("employee_id",),
    "salary_payments": ("staff_id",),
    "own_expenses": (),
    "expenses": ("own_expense_id",),
}


def _fixed_input_error():
    return ValueError("accounting_remediation_input_invalid")


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


def _validated_request(value):
    if type(value) is not dict:
        raise _fixed_input_error() from None
    try:
        rebuilt = build_accounting_ownership_remediation_request(
            source=value.get("source"), record_id=value.get("recordId"),
            company_id=value.get("companyId"), project_id=value.get("projectId"),
            operator_user_id=value.get("operatorUserId"),
        )
    except ValueError:
        raise _fixed_input_error() from None
    if value != rebuilt:
        raise _fixed_input_error() from None
    return rebuilt


def _one_row(cursor, sql, params, *, lock=None):
    if lock not in (None, "FOR KEY SHARE", "FOR UPDATE"):
        raise _fixed_input_error() from None
    cursor.execute(sql + (" " + lock if lock else ""), params)
    rows = list(cursor.fetchall() or [])
    if len(rows) != 1:
        raise RuntimeError("accounting_remediation_owner_invalid") from None
    return dict(rows[0] or {})


def _verified_owner(
    cursor, table, record_id, company_id, project_id=None, *, lock=False,
):
    if table not in _SOURCES or _positive_int(record_id) is None:
        raise RuntimeError("accounting_remediation_owner_invalid") from None
    project_clause = " AND project_id=%s" if project_id is not None else ""
    params = (record_id, company_id, project_id) if project_id is not None else (record_id, company_id)
    _one_row(
        cursor,
        f"SELECT id FROM public.{table} WHERE id=%s AND company_id=%s "
        f"AND company_scope_verified IS TRUE{project_clause}",
        params,
        lock="FOR KEY SHARE" if lock else None,
    )


def _evidence_sha256(request, target, state):
    source = request["source"]
    evidence_payload = {
        "requestSha256": request["requestSha256"],
        "state": state,
        "storedCompanyId": target.get("company_id"),
        "storedProjectId": (
            target.get("project_id") if source in _PROJECT_SOURCES else None
        ),
        "storedVerified": target.get("company_scope_verified"),
        "linkIds": {
            field: target.get(field)
            for field in _LINK_FIELDS[source]
        },
    }
    encoded = json.dumps(evidence_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _inspect_request(cursor, request, *, lock=False):
    request = _validated_request(request)
    if not _schema_contract_is_exact(cursor):
        raise RuntimeError("accounting_remediation_schema_not_ready") from None
    shared_lock = "FOR KEY SHARE" if lock else None
    _one_row(
        cursor,
        "SELECT id FROM public.companies WHERE id=%s AND active IS TRUE",
        (request["companyId"],),
        lock=shared_lock,
    )
    _one_row(
        cursor,
        "SELECT u.id FROM public.users u WHERE u.id=%s "
        "AND u.active IS TRUE AND EXISTS ("
        "SELECT 1 FROM public.user_company_roles r "
        "WHERE r.user_id=u.id AND r.company_id=%s "
        "AND r.active IS TRUE AND r.role=ANY(%s))",
        (
            request["operatorUserId"], request["companyId"],
            list(_OPERATOR_ROLES),
        ),
        lock=shared_lock,
    )
    if request["source"] in _PROJECT_SOURCES:
        _one_row(
            cursor,
            "SELECT id FROM public.projects WHERE id=%s AND company_id=%s",
            (request["projectId"], request["companyId"]),
            lock=shared_lock,
        )
    target = _one_row(
        cursor,
        _TARGET_QUERIES[request["source"]],
        (request["recordId"],),
        lock="FOR UPDATE" if lock else None,
    )

    source = request["source"]
    company_id = request["companyId"]
    project_id = request["projectId"]
    if source == "accountable_payments":
        _verified_owner(
            cursor, "staff", target.get("given_to_id"), company_id,
            lock=lock,
        )
    elif source == "expense_reports":
        _verified_owner(
            cursor, "staff", target.get("employee_id"), company_id,
            lock=lock,
        )
    elif source == "accountable_expenses":
        _verified_owner(
            cursor, "accountable_payments", target.get("payment_id"),
            company_id, project_id, lock=lock,
        )
    elif source == "salary_payments":
        _verified_owner(
            cursor, "staff", target.get("staff_id"), company_id,
            lock=lock,
        )
    elif source == "expenses" and target.get("own_expense_id") is not None:
        _verified_owner(
            cursor, "own_expenses", target.get("own_expense_id"),
            company_id, project_id, lock=lock,
        )

    stored_company = target.get("company_id")
    stored_project = target.get("project_id") if source in _PROJECT_SOURCES else None
    verified = target.get("company_scope_verified")
    if type(verified) is not bool:
        raise RuntimeError("accounting_remediation_owner_invalid") from None
    exact = stored_company == company_id and (
        source not in _PROJECT_SOURCES or stored_project == project_id
    )
    if verified:
        state = "already_verified" if exact else "blocked"
    elif source == "staff":
        state = "ready" if stored_company in (None, company_id) else "blocked"
    else:
        state = "ready" if stored_company is None and stored_project is None else "blocked"
    return {
        **request,
        "state": state,
        "evidenceSha256": _evidence_sha256(request, target, state),
    }


def _insert_audit_event(cursor, request):
    cursor.execute(
        """INSERT INTO public.audit_log
             (user_id,user_name,user_role,action,entity_type,entity_id,
              description,owner_scope,company_id,project_id)
           VALUES (%s,'system','migration','accounting_ownership_remediated',
                   %s,%s,'exact-id ownership remediation','company',%s,%s)
           RETURNING id""",
        (
            request["operatorUserId"], request["source"], request["recordId"],
            request["companyId"], request["projectId"],
        ),
    )
    row = cursor.fetchone()
    audit_id = _positive_int(dict(row or {}).get("id"))
    if audit_id is None:
        raise RuntimeError("accounting_remediation_audit_failed") from None
    return audit_id


def run_accounting_ownership_remediation(
    connection, request, *, apply=False, expected_evidence_sha256=None,
):
    request = _validated_request(request)
    if apply and (
        type(expected_evidence_sha256) is not str
        or not _SHA256_RE.fullmatch(expected_evidence_sha256)
    ):
        raise ValueError("accounting_remediation_apply_guard_invalid") from None
    cursor = None
    try:
        connection.set_session(
            readonly=not apply, autocommit=False,
            **({"isolation_level": "SERIALIZABLE"} if apply else {}),
        )
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if not apply:
            return {**_inspect_request(cursor, request), "rolledBack": True}
        cursor.execute("SET LOCAL lock_timeout='5s'")
        cursor.execute("SET LOCAL statement_timeout='60s'")
        before = _inspect_request(cursor, request, lock=True)
        if before["evidenceSha256"] != expected_evidence_sha256:
            raise RuntimeError("accounting_remediation_evidence_changed") from None
        if before["state"] == "blocked":
            raise RuntimeError("accounting_remediation_owner_invalid") from None
        if before["state"] == "already_verified":
            connection.commit()
            return {**before, "dryRun": False, "applyAllowed": False,
                    "writesAttempted": 0, "auditWritesAttempted": 0,
                    "auditEventId": None, "rolledBack": False, "complete": True}
        _apply_ready_rows(cursor, [{
            "source": request["source"], "recordId": request["recordId"],
            "companyId": request["companyId"], "projectId": request["projectId"],
        }])
        audit_id = _insert_audit_event(cursor, request)
        after = _inspect_request(cursor, request, lock=True)
        if after["state"] != "already_verified":
            raise RuntimeError("accounting_remediation_postcheck_failed") from None
        connection.commit()
        return {**after, "dryRun": False, "applyAllowed": False,
                "writesAttempted": 1, "auditWritesAttempted": 1,
                "auditEventId": audit_id, "rolledBack": False, "complete": True}
    except BaseException:
        if cursor is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            if not apply:
                connection.rollback()
            cursor.close()
