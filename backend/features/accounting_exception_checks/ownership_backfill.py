"""Private provable-only ownership backfill for legacy accounting rows.

Dry-run is the default.  The guarded apply path accepts only the exact count
and SHA-256 produced by a preceding dry-run, reclassifies under table locks and
never assigns an owner to a quarantined record.
"""

import copy
import hashlib
import json
import re

import psycopg2.extras

from backend.features.accounting_exception_checks.ownership_inventory import (
    SOURCE_LIMIT,
    _classify_accounting_ownership_records,
    _collect_accounting_ownership_rows,
)
from backend.features.accounting_exception_checks.schema_contract import (
    _schema_contract_is_exact,
)


_VERSION = "accounting-ownership-backfill-v1"
_PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCES = (
    "staff",
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "salary_payments",
    "own_expenses",
    "expenses",
)
_NO_PROJECT_COLUMN = frozenset(("staff", "salary_payments"))
_CLASSIFICATIONS = frozenset(("provable", "ambiguous", "orphaned", "conflicting"))

_STATE_QUERIES = {
    source: (
        f"SELECT id,company_id,company_scope_verified "
        f"FROM public.{source} ORDER BY id LIMIT %s"
        if source in _NO_PROJECT_COLUMN
        else (
            f"SELECT id,company_id,project_id,company_scope_verified "
            f"FROM public.{source} ORDER BY id LIMIT %s"
        )
    )
    for source in _SOURCES
}


def _input_error():
    return ValueError("accounting_backfill_input_invalid")


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


def _normalize_records(records):
    if type(records) not in (list, tuple):
        raise _input_error() from None
    normalized = []
    seen = set()
    for raw in records:
        try:
            row = dict(raw or {})
        except (TypeError, ValueError):
            raise _input_error() from None
        source = row.get("source")
        record_id = _positive_int(row.get("recordId"))
        classification = row.get("classification")
        identity = (source, record_id)
        if (
            source not in _SOURCES
            or record_id is None
            or classification not in _CLASSIFICATIONS
            or identity in seen
        ):
            raise _input_error() from None
        seen.add(identity)
        company_id = row.get("companyId")
        project_id = row.get("projectId")
        if classification == "provable":
            company_id = _positive_int(company_id)
            project_id = _positive_int(project_id)
            if company_id is None or project_id is None:
                raise _input_error() from None
        elif company_id is not None or project_id is not None:
            raise _input_error() from None
        normalized.append({
            "source": source,
            "recordId": record_id,
            "classification": classification,
            "reason": str(row.get("reason") or ""),
            "companyId": company_id,
            "projectId": project_id,
        })
    return sorted(normalized, key=lambda item: (_SOURCES.index(item["source"]), item["recordId"]))


def _normalize_stored_rows(stored_rows_by_source):
    if type(stored_rows_by_source) is not dict or set(stored_rows_by_source) != set(_SOURCES):
        raise _input_error() from None
    normalized = {}
    for source in _SOURCES:
        raw_rows = stored_rows_by_source[source]
        if type(raw_rows) not in (list, tuple):
            raise _input_error() from None
        rows = {}
        for raw in raw_rows:
            try:
                row = dict(raw or {})
            except (TypeError, ValueError):
                raise _input_error() from None
            record_id = _positive_int(row.get("id"))
            verified = row.get("company_scope_verified")
            company_id = row.get("company_id")
            project_id = row.get("project_id") if source not in _NO_PROJECT_COLUMN else None
            if (
                record_id is None
                or record_id in rows
                or type(verified) is not bool
                or (company_id is not None and _positive_int(company_id) is None)
                or (project_id is not None and _positive_int(project_id) is None)
            ):
                raise _input_error() from None
            rows[record_id] = {
                "companyId": company_id,
                "projectId": project_id,
                "verified": verified,
            }
        normalized[source] = rows
    return normalized


def _status_for(decision, stored):
    if decision["classification"] != "provable":
        return "conflicting" if stored["verified"] else "quarantined"
    company_matches = stored["companyId"] == decision["companyId"]
    project_matches = (
        decision["source"] in _NO_PROJECT_COLUMN
        or stored["projectId"] == decision["projectId"]
    )
    if stored["verified"]:
        return "verified" if company_matches and project_matches else "conflicting"
    if decision["source"] == "staff":
        return "ready" if stored["companyId"] in (None, decision["companyId"]) else "conflicting"
    if stored["companyId"] is not None or stored["projectId"] is not None:
        return "conflicting"
    return "ready"


def build_accounting_ownership_backfill_plan(records, stored_rows_by_source):
    decisions = _normalize_records(records)
    stored_by_source = _normalize_stored_rows(stored_rows_by_source)
    classified = []
    for decision in decisions:
        stored = stored_by_source[decision["source"]].get(decision["recordId"])
        if stored is None:
            raise _input_error() from None
        classified.append({
            **decision,
            "storedCompanyId": stored["companyId"],
            "storedProjectId": stored["projectId"],
            "storedVerified": stored["verified"],
            "backfillStatus": _status_for(decision, stored),
        })
    if sum(len(rows) for rows in stored_by_source.values()) != len(classified):
        raise _input_error() from None

    payload = json.dumps(classified, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    ready = [
        {
            "source": item["source"],
            "recordId": item["recordId"],
            "companyId": item["companyId"],
            "projectId": item["projectId"],
        }
        for item in classified
        if item["backfillStatus"] == "ready"
    ]
    counts = {
        status: sum(item["backfillStatus"] == status for item in classified)
        for status in ("ready", "verified", "quarantined", "conflicting")
    }
    return {
        "version": _VERSION,
        "dryRun": True,
        "writesAttempted": 0,
        "totalRecords": len(classified),
        "readyCount": counts["ready"],
        "verifiedCount": counts["verified"],
        "quarantinedCount": counts["quarantined"],
        "conflictingCount": counts["conflicting"],
        "planSha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        "ready": ready,
    }


def _collect_stored_rows(cursor):
    result = {}
    for source in _SOURCES:
        cursor.execute(_STATE_QUERIES[source], (SOURCE_LIMIT + 1,))
        rows = list(cursor.fetchall() or [])
        if len(rows) > SOURCE_LIMIT:
            raise ValueError("accounting_backfill_source_limit") from None
        result[source] = rows
    return result


def _collect_backfill_plan(cursor):
    if not _schema_contract_is_exact(cursor):
        raise RuntimeError("accounting_backfill_schema_not_ready") from None
    rows_by_source = _collect_accounting_ownership_rows(cursor)
    records, _summary = _classify_accounting_ownership_records(rows_by_source)
    return build_accounting_ownership_backfill_plan(records, _collect_stored_rows(cursor))


def _validate_apply_guard(expected_ready_count, expected_plan_sha256):
    if (
        type(expected_ready_count) is not int
        or expected_ready_count < 0
        or type(expected_plan_sha256) is not str
        or not _PLAN_SHA256_RE.fullmatch(expected_plan_sha256)
    ):
        raise ValueError("accounting_backfill_apply_guard_invalid") from None


def _apply_ready_rows(cursor, ready):
    for item in ready:
        source = item["source"]
        company_id = item["companyId"]
        project_id = item["projectId"]
        record_id = item["recordId"]
        if source == "staff":
            sql = (
                "UPDATE public.staff SET company_id=%s,company_scope_verified=TRUE "
                "WHERE id=%s AND company_scope_verified IS FALSE "
                "AND (company_id IS NULL OR company_id=%s)"
            )
            params = (company_id, record_id, company_id)
        elif source == "salary_payments":
            sql = (
                "UPDATE public.salary_payments SET company_id=%s,"
                "company_scope_verified=TRUE WHERE id=%s "
                "AND company_scope_verified IS FALSE AND company_id IS NULL"
            )
            params = (company_id, record_id)
        else:
            sql = (
                f"UPDATE public.{source} SET company_id=%s,project_id=%s,"
                "company_scope_verified=TRUE WHERE id=%s "
                "AND company_scope_verified IS FALSE "
                "AND company_id IS NULL AND project_id IS NULL"
            )
            params = (company_id, project_id, record_id)
        cursor.execute(sql, params)
        if cursor.rowcount != 1:
            raise RuntimeError("accounting_backfill_write_conflict") from None


def run_accounting_ownership_backfill(
    connection,
    *,
    apply=False,
    expected_ready_count=None,
    expected_plan_sha256=None,
):
    if apply:
        _validate_apply_guard(expected_ready_count, expected_plan_sha256)
    cursor = None
    try:
        if not apply:
            connection.set_session(readonly=True, autocommit=False)
            cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            result = _collect_backfill_plan(cursor)
            result = copy.deepcopy(result)
            result["rolledBack"] = True
            return result

        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SET LOCAL lock_timeout='5s'")
        cursor.execute("SET LOCAL statement_timeout='60s'")
        cursor.execute("LOCK TABLE public.projects IN SHARE MODE")
        for source in _SOURCES:
            cursor.execute(f"LOCK TABLE public.{source} IN ACCESS EXCLUSIVE MODE")
        before = _collect_backfill_plan(cursor)
        if before["conflictingCount"]:
            raise RuntimeError("accounting_backfill_stored_conflict") from None
        if (
            before["readyCount"] != expected_ready_count
            or before["planSha256"] != expected_plan_sha256
        ):
            raise RuntimeError("accounting_backfill_plan_changed") from None
        _apply_ready_rows(cursor, before["ready"])
        after = _collect_backfill_plan(cursor)
        if (
            after["readyCount"] != 0
            or after["conflictingCount"] != 0
            or after["verifiedCount"] != before["verifiedCount"] + before["readyCount"]
            or after["quarantinedCount"] != before["quarantinedCount"]
        ):
            raise RuntimeError("accounting_backfill_postcheck_failed") from None
        connection.commit()
        result = copy.deepcopy(after)
        result.update({
            "dryRun": False,
            "writesAttempted": before["readyCount"],
            "updated": before["readyCount"],
            "rolledBack": False,
            "complete": True,
            "appliedPlanSha256": before["planSha256"],
        })
        return result
    except BaseException:
        if cursor is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            if not apply:
                connection.rollback()
            cursor.close()
