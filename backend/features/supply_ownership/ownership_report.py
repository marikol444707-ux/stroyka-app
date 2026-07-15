"""Read-only ownership report for the core supply request chain."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("supply_requests", "supply_request_recipients", "supplier_offers")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _project_name(value):
    return str(value or "").strip()


def _item(
    table,
    record_id,
    status,
    reason,
    company_id=None,
    project_id=None,
    request_id=None,
):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "requestId": _positive_int(request_id),
    }


def _classify_request(row, company_ids, projects_by_name):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    project_name = _project_name(row.get("project"))
    if not company_id:
        return _item("supply_requests", record_id, "unresolved", "company_owner_missing")
    if company_id not in company_ids:
        return _item(
            "supply_requests", record_id, "unresolved", "company_not_found",
            company_id=company_id,
        )
    if not project_name:
        return _item(
            "supply_requests", record_id, "unresolved", "project_owner_missing",
            company_id=company_id,
        )

    candidates = projects_by_name.get(project_name, [])
    company_candidates = [
        project for project in candidates
        if _positive_int(project.get("company_id")) == company_id
    ]
    if not company_candidates:
        reason = "project_company_mismatch" if candidates else "project_not_found"
        status = "mismatched" if candidates else "unresolved"
        return _item(
            "supply_requests", record_id, status, reason, company_id=company_id,
        )
    if len(company_candidates) != 1:
        return _item(
            "supply_requests", record_id, "ambiguous", "project_owner_ambiguous",
            company_id=company_id,
        )
    return _item(
        "supply_requests", record_id, "verified", "verified_company_and_project",
        company_id=company_id,
        project_id=company_candidates[0].get("id"),
    )


def _classify_child(table, row, company_ids, requests):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    request_id = _positive_int(row.get("request_id"))
    if not company_id:
        return _item(table, record_id, "unresolved", "company_owner_missing", request_id=request_id)
    if company_id not in company_ids:
        return _item(
            table, record_id, "unresolved", "company_not_found",
            company_id=company_id, request_id=request_id,
        )
    if not request_id:
        return _item(
            table, record_id, "unresolved", "request_parent_missing",
            company_id=company_id,
        )
    request = requests.get(request_id)
    if not request:
        return _item(
            table, record_id, "unresolved", "request_parent_not_found",
            company_id=company_id, request_id=request_id,
        )
    if request["status"] != "verified":
        return _item(
            table, record_id, "unresolved", "request_parent_unresolved",
            company_id=company_id, project_id=request["projectId"], request_id=request_id,
        )
    if request["companyId"] != company_id:
        return _item(
            table, record_id, "mismatched", "request_company_mismatch",
            company_id=company_id, project_id=request["projectId"], request_id=request_id,
        )
    return _item(
        table, record_id, "verified", "verified_request_parent",
        company_id=company_id, project_id=request["projectId"], request_id=request_id,
    )


def _plan_sha256(classified):
    plan = [
        [
            item["table"], item["recordId"], item["status"], item["reason"],
            item["companyId"], item["projectId"], item["requestId"],
        ]
        for item in classified
    ]
    normalized = sorted(
        plan,
        key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")),
    )
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report_from_rows(rows):
    company_ids = {
        company_id
        for row in (rows.get("companies") or [])
        for company_id in [_positive_int((row or {}).get("id"))]
        if company_id
    }
    projects_by_name = defaultdict(list)
    for row in (rows.get("projects") or []):
        project = dict(row or {})
        name = _project_name(project.get("name"))
        if name:
            projects_by_name[name].append(project)

    request_items = [
        _classify_request(row, company_ids, projects_by_name)
        for row in (rows.get("supply_requests") or [])
    ]
    requests = {
        item["recordId"]: item for item in request_items if item["recordId"]
    }
    classified = request_items
    classified += [
        _classify_child("supply_request_recipients", row, company_ids, requests)
        for row in (rows.get("supply_request_recipients") or [])
    ]
    classified += [
        _classify_child("supplier_offers", row, company_ids, requests)
        for row in (rows.get("supplier_offers") or [])
    ]

    counts = Counter(item["status"] for item in classified)
    statuses = ("verified", "unresolved", "ambiguous", "mismatched")
    by_table = {}
    for table in TABLES:
        table_counts = Counter(item["status"] for item in classified if item["table"] == table)
        by_table[table] = {
            "totalRows": sum(table_counts.values()),
            **{status: table_counts[status] for status in statuses},
        }
    review = [item for item in classified if item["status"] != "verified"]
    verified = [item for item in classified if item["status"] == "verified"]
    ready_by_company = Counter(str(item["companyId"]) for item in verified)
    return {
        "ok": True,
        "dryRun": True,
        "tables": list(TABLES),
        "writesAttempted": 0,
        "readyForStrictRuntime": not review,
        "reportConsistent": len(classified) == sum(counts[status] for status in statuses),
        "summary": {
            "totalRows": len(classified),
            **{status: counts[status] for status in statuses},
        },
        "byTable": by_table,
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "planSha256": _plan_sha256(classified),
        "verifiedPreview": verified[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "previewTruncated": len(verified) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    rows = {}
    queries = {
        "companies": "SELECT id FROM companies ORDER BY id",
        "projects": "SELECT id,company_id,name FROM projects ORDER BY id",
        "supply_requests": "SELECT id,company_id,project FROM supply_requests ORDER BY id",
        "supply_request_recipients": (
            "SELECT id,company_id,request_id FROM supply_request_recipients ORDER BY id"
        ),
        "supplier_offers": "SELECT id,company_id,request_id FROM supplier_offers ORDER BY id",
    }
    for table, query in queries.items():
        cur.execute(query)
        rows[table] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows


def run_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_report_from_rows(load_ownership_rows(cur))
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(run_ownership_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
