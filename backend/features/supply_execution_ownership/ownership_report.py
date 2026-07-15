"""Read-only ownership report for supplier invoices and supply deliveries."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("supplier_invoices", "supply_deliveries")


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
    offer_id=None,
):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "requestId": _positive_int(request_id),
        "offerId": _positive_int(offer_id),
    }


def _classify_project_owner(table, row, project_field, company_ids, projects_by_name):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    request_id = _positive_int(row.get("request_id"))
    offer_id = _positive_int(row.get("offer_id"))
    name = _project_name(row.get(project_field))
    if not company_id:
        return _item(
            table, record_id, "unresolved", "company_owner_missing",
            request_id=request_id, offer_id=offer_id,
        )
    if company_id not in company_ids:
        return _item(
            table, record_id, "unresolved", "company_not_found",
            company_id=company_id, request_id=request_id, offer_id=offer_id,
        )
    if not name:
        return _item(
            table, record_id, "unresolved", "project_owner_missing",
            company_id=company_id, request_id=request_id, offer_id=offer_id,
        )
    candidates = projects_by_name.get(name, [])
    owned = [
        project for project in candidates
        if _positive_int(project.get("company_id")) == company_id
    ]
    if not owned:
        return _item(
            table,
            record_id,
            "mismatched" if candidates else "unresolved",
            "project_company_mismatch" if candidates else "project_not_found",
            company_id=company_id,
            request_id=request_id,
            offer_id=offer_id,
        )
    if len(owned) != 1:
        return _item(
            table, record_id, "ambiguous", "project_owner_ambiguous",
            company_id=company_id, request_id=request_id, offer_id=offer_id,
        )
    return _item(
        table, record_id, "verified", "verified_company_and_project",
        company_id=company_id,
        project_id=owned[0].get("id"),
        request_id=request_id,
        offer_id=offer_id,
    )


def _classify_request(row, company_ids, projects_by_name):
    return _classify_project_owner(
        "supply_requests", row, "project", company_ids, projects_by_name
    )


def _classify_offer(row, company_ids, requests):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    request_id = _positive_int(row.get("request_id"))
    if not company_id:
        return _item(
            "supplier_offers", record_id, "unresolved", "company_owner_missing",
            request_id=request_id,
        )
    if company_id not in company_ids:
        return _item(
            "supplier_offers", record_id, "unresolved", "company_not_found",
            company_id=company_id, request_id=request_id,
        )
    if not request_id:
        return _item(
            "supplier_offers", record_id, "unresolved", "request_parent_missing",
            company_id=company_id,
        )
    request = requests.get(request_id)
    if not request:
        return _item(
            "supplier_offers", record_id, "unresolved", "request_parent_not_found",
            company_id=company_id, request_id=request_id,
        )
    if request["status"] != "verified":
        return _item(
            "supplier_offers", record_id, "unresolved", "request_parent_unresolved",
            company_id=company_id, project_id=request["projectId"], request_id=request_id,
        )
    if request["companyId"] != company_id:
        return _item(
            "supplier_offers", record_id, "mismatched", "request_company_mismatch",
            company_id=company_id, project_id=request["projectId"], request_id=request_id,
        )
    return _item(
        "supplier_offers", record_id, "verified", "verified_request_parent",
        company_id=company_id, project_id=request["projectId"], request_id=request_id,
    )


def _with_parent_status(base, requests, offers, require_request, require_offer):
    if base["status"] != "verified":
        return base
    request_id = base["requestId"]
    offer_id = base["offerId"]
    if require_request and not request_id:
        return {**base, "status": "unresolved", "reason": "request_parent_missing"}
    if require_offer and not offer_id:
        return {**base, "status": "unresolved", "reason": "offer_parent_missing"}

    request = requests.get(request_id) if request_id else None
    if request_id and not request:
        return {**base, "status": "unresolved", "reason": "request_parent_not_found"}
    if request and request["status"] != "verified":
        return {**base, "status": "unresolved", "reason": "request_parent_unresolved"}
    if request and request["companyId"] != base["companyId"]:
        return {**base, "status": "mismatched", "reason": "request_company_mismatch"}
    if request and request["projectId"] != base["projectId"]:
        return {**base, "status": "mismatched", "reason": "request_project_mismatch"}

    offer = offers.get(offer_id) if offer_id else None
    if offer_id and not offer:
        return {**base, "status": "unresolved", "reason": "offer_parent_not_found"}
    if offer and offer["status"] != "verified":
        return {**base, "status": "unresolved", "reason": "offer_parent_unresolved"}
    if offer and offer["companyId"] != base["companyId"]:
        return {**base, "status": "mismatched", "reason": "offer_company_mismatch"}
    if offer and offer["projectId"] != base["projectId"]:
        return {**base, "status": "mismatched", "reason": "offer_project_mismatch"}
    if offer and request_id and offer["requestId"] != request_id:
        return {**base, "status": "mismatched", "reason": "offer_request_mismatch"}

    effective_request_id = request_id or (offer and offer["requestId"])
    reason = "verified_company_and_project"
    if offer:
        reason = "verified_request_and_offer_chain"
    elif request:
        reason = "verified_request_parent"
    return {**base, "requestId": effective_request_id, "reason": reason}


def _plan_sha256(classified):
    plan = [
        [
            item["table"], item["recordId"], item["status"], item["reason"],
            item["companyId"], item["projectId"], item["requestId"], item["offerId"],
        ]
        for item in classified
    ]
    normalized = sorted(
        plan,
        key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")),
    )
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_supply_execution_rows(rows):
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
    requests = {item["recordId"]: item for item in request_items if item["recordId"]}
    offer_items = [
        _classify_offer(row, company_ids, requests)
        for row in (rows.get("supplier_offers") or [])
    ]
    offers = {item["recordId"]: item for item in offer_items if item["recordId"]}

    classified = [
        _with_parent_status(
            _classify_project_owner(
                "supplier_invoices", row, "project_name", company_ids, projects_by_name
            ),
            requests,
            offers,
            require_request=False,
            require_offer=False,
        )
        for row in (rows.get("supplier_invoices") or [])
    ]
    classified += [
        _with_parent_status(
            _classify_project_owner(
                "supply_deliveries", row, "project", company_ids, projects_by_name
            ),
            requests,
            offers,
            require_request=True,
            require_offer=True,
        )
        for row in (rows.get("supply_deliveries") or [])
    ]
    return classified


def build_report_from_rows(rows):
    classified = classify_supply_execution_rows(rows)

    statuses = ("verified", "unresolved", "ambiguous", "mismatched")
    counts = Counter(item["status"] for item in classified)
    by_table = {}
    for table in TABLES:
        table_counts = Counter(item["status"] for item in classified if item["table"] == table)
        by_table[table] = {
            "totalRows": sum(table_counts.values()),
            **{status: table_counts[status] for status in statuses},
        }
    verified = [item for item in classified if item["status"] == "verified"]
    review = [item for item in classified if item["status"] != "verified"]
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
    queries = {
        "companies": "SELECT id FROM companies ORDER BY id",
        "projects": "SELECT id,company_id,name FROM projects ORDER BY id",
        "supply_requests": "SELECT id,company_id,project FROM supply_requests ORDER BY id",
        "supplier_offers": "SELECT id,company_id,request_id FROM supplier_offers ORDER BY id",
        "supplier_invoices": (
            "SELECT id,company_id,project_name,request_id,offer_id "
            "FROM supplier_invoices ORDER BY id"
        ),
        "supply_deliveries": (
            "SELECT id,company_id,project,request_id,offer_id "
            "FROM supply_deliveries ORDER BY id"
        ),
    }
    rows = {}
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
