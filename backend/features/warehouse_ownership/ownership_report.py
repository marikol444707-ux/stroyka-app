"""Read-only ownership report for warehouse invoices and warehouse history."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras

from backend.features.supply_execution_ownership.ownership_report import (
    classify_supply_execution_rows,
)


MAIN_WAREHOUSE = "Основной склад"
PREVIEW_LIMIT = 100
TABLES = ("warehouse_invoices", "warehouse_history")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _text(value):
    return str(value or "").strip()


def _item(
    table,
    record_id,
    status,
    reason,
    company_id=None,
    project_id=None,
    request_id=None,
    delivery_id=None,
    supplier_invoice_id=None,
):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "requestId": _positive_int(request_id),
        "deliveryId": _positive_int(delivery_id),
        "supplierInvoiceId": _positive_int(supplier_invoice_id),
    }


def _project_owner(
    table,
    record_id,
    company_id,
    project_name,
    company_ids,
    projects_by_name,
    *,
    allow_main=False,
):
    company_id = _positive_int(company_id)
    name = _text(project_name)
    if not company_id:
        return _item(table, record_id, "unresolved", "company_owner_missing")
    if company_id not in company_ids:
        return _item(
            table, record_id, "unresolved", "company_not_found", company_id=company_id
        )
    if allow_main and name == MAIN_WAREHOUSE:
        return _item(
            table,
            record_id,
            "verified",
            "verified_company_main_warehouse",
            company_id=company_id,
        )
    if not name:
        return _item(
            table,
            record_id,
            "unresolved",
            "warehouse_scope_missing" if allow_main else "project_owner_missing",
            company_id=company_id,
        )
    candidates = projects_by_name.get(name, [])
    owned = [
        project
        for project in candidates
        if _positive_int(project.get("company_id")) == company_id
    ]
    if not owned:
        return _item(
            table,
            record_id,
            "mismatched" if candidates else "unresolved",
            "project_company_mismatch" if candidates else "project_not_found",
            company_id=company_id,
        )
    if len(owned) != 1:
        return _item(
            table,
            record_id,
            "ambiguous",
            "project_owner_ambiguous",
            company_id=company_id,
        )
    return _item(
        table,
        record_id,
        "verified",
        "verified_company_and_project",
        company_id=company_id,
        project_id=owned[0].get("id"),
    )


def _warehouse_invoice_owner(row, company_ids, projects_by_name):
    row = dict(row or {})
    target = _text(row.get("warehouse_target")).lower()
    project_name = _text(row.get("project"))
    location = _text(row.get("location"))
    if not project_name and location and location != MAIN_WAREHOUSE:
        project_name = location
    if not target:
        target = "object" if project_name else "main"
    if target == "main" and project_name:
        return _item(
            "warehouse_invoices",
            row.get("id"),
            "mismatched",
            "warehouse_target_project_mismatch",
            company_id=row.get("company_id"),
            request_id=row.get("supply_request_id"),
            delivery_id=row.get("supply_delivery_id"),
            supplier_invoice_id=row.get("supplier_invoice_id"),
        )
    if target not in {"main", "object", "project"}:
        return _item(
            "warehouse_invoices",
            row.get("id"),
            "unresolved",
            "warehouse_target_invalid",
            company_id=row.get("company_id"),
        )
    if target in {"object", "project"}:
        base = _project_owner(
            "warehouse_invoices",
            row.get("id"),
            row.get("company_id"),
            project_name,
            company_ids,
            projects_by_name,
        )
    else:
        base = _project_owner(
            "warehouse_invoices",
            row.get("id"),
            row.get("company_id"),
            MAIN_WAREHOUSE,
            company_ids,
            projects_by_name,
            allow_main=True,
        )
    return {
        **base,
        "requestId": _positive_int(row.get("supply_request_id")),
        "deliveryId": _positive_int(row.get("supply_delivery_id")),
        "supplierInvoiceId": _positive_int(row.get("supplier_invoice_id")),
    }


def _parent_failure(base, parent, prefix):
    status = parent.get("status") or "unresolved"
    if status == "verified":
        return None
    if status not in {"unresolved", "ambiguous", "mismatched"}:
        status = "unresolved"
    return {**base, "status": status, "reason": f"{prefix}_parent_{status}"}


def _check_parent_owner(base, parent, prefix):
    failure = _parent_failure(base, parent, prefix)
    if failure:
        return failure
    if parent.get("companyId") != base.get("companyId"):
        return {**base, "status": "mismatched", "reason": f"{prefix}_company_mismatch"}
    if parent.get("projectId") != base.get("projectId"):
        return {**base, "status": "mismatched", "reason": f"{prefix}_project_mismatch"}
    return None


def _classify_request_rows(rows, company_ids, projects_by_name):
    result = {}
    for row in rows.get("supply_requests") or []:
        row = dict(row or {})
        item = _project_owner(
            "supply_requests",
            row.get("id"),
            row.get("company_id"),
            row.get("project"),
            company_ids,
            projects_by_name,
        )
        if item["recordId"]:
            result[item["recordId"]] = item
    return result


def _classify_warehouse_invoice(base, requests, deliveries, supplier_invoices, invoice_rows):
    if base["status"] != "verified":
        return base

    request_id = base["requestId"]
    delivery_id = base["deliveryId"]
    supplier_invoice_id = base["supplierInvoiceId"]

    if request_id:
        request = requests.get(request_id)
        if not request:
            return {**base, "status": "unresolved", "reason": "request_parent_not_found"}
        mismatch = _check_parent_owner(base, request, "request")
        if mismatch:
            return mismatch

    if delivery_id:
        delivery = deliveries.get(delivery_id)
        if not delivery:
            return {**base, "status": "unresolved", "reason": "delivery_parent_not_found"}
        mismatch = _check_parent_owner(base, delivery, "delivery")
        if mismatch:
            return mismatch
        if request_id and delivery.get("requestId") != request_id:
            return {**base, "status": "mismatched", "reason": "delivery_request_mismatch"}

    if supplier_invoice_id:
        supplier_invoice = supplier_invoices.get(supplier_invoice_id)
        if not supplier_invoice:
            return {
                **base,
                "status": "unresolved",
                "reason": "supplier_invoice_parent_not_found",
            }
        mismatch = _check_parent_owner(base, supplier_invoice, "supplier_invoice")
        if mismatch:
            return mismatch
        if (
            request_id
            and supplier_invoice.get("requestId")
            and supplier_invoice.get("requestId") != request_id
        ):
            return {
                **base,
                "status": "mismatched",
                "reason": "supplier_invoice_request_mismatch",
            }
        raw_parent = invoice_rows.get(supplier_invoice_id) or {}
        reverse_id = _positive_int(raw_parent.get("warehouse_invoice_id"))
        if reverse_id and reverse_id != base["recordId"]:
            return {
                **base,
                "status": "mismatched",
                "reason": "supplier_invoice_reverse_link_mismatch",
            }

    parent_request_ids = {
        parent_request_id
        for parent_request_id in (
            request_id,
            deliveries.get(delivery_id, {}).get("requestId") if delivery_id else None,
            supplier_invoices.get(supplier_invoice_id, {}).get("requestId")
            if supplier_invoice_id
            else None,
        )
        if parent_request_id
    }
    if len(parent_request_ids) > 1:
        return {**base, "status": "mismatched", "reason": "document_request_mismatch"}

    reason = base["reason"]
    if request_id or delivery_id or supplier_invoice_id:
        reason = "verified_document_chain"
    return {**base, "reason": reason}


def _plan_sha256(classified):
    plan = [
        [
            item["table"],
            item["recordId"],
            item["status"],
            item["reason"],
            item["companyId"],
            item["projectId"],
            item["requestId"],
            item["deliveryId"],
            item["supplierInvoiceId"],
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
    for row in rows.get("projects") or []:
        project = dict(row or {})
        name = _text(project.get("name"))
        if name:
            projects_by_name[name].append(project)

    execution = classify_supply_execution_rows(rows)
    deliveries = {
        item["recordId"]: item
        for item in execution
        if item["table"] == "supply_deliveries" and item["recordId"]
    }
    supplier_invoices = {
        item["recordId"]: item
        for item in execution
        if item["table"] == "supplier_invoices" and item["recordId"]
    }
    invoice_rows = {
        _positive_int(row.get("id")): dict(row or {})
        for row in (rows.get("supplier_invoices") or [])
        if _positive_int((row or {}).get("id"))
    }
    requests = _classify_request_rows(rows, company_ids, projects_by_name)

    classified = []
    for row in rows.get("warehouse_invoices") or []:
        base = _warehouse_invoice_owner(row, company_ids, projects_by_name)
        classified.append(
            _classify_warehouse_invoice(
                base,
                requests,
                deliveries,
                supplier_invoices,
                invoice_rows,
            )
        )
    for row in rows.get("warehouse_history") or []:
        row = dict(row or {})
        classified.append(
            _project_owner(
                "warehouse_history",
                row.get("id"),
                row.get("company_id"),
                row.get("project"),
                company_ids,
                projects_by_name,
                allow_main=True,
            )
        )

    statuses = ("verified", "unresolved", "ambiguous", "mismatched")
    counts = Counter(item["status"] for item in classified)
    by_table = {}
    for table in TABLES:
        table_counts = Counter(
            item["status"] for item in classified if item["table"] == table
        )
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
        "reportConsistent": len(classified)
        == sum(counts[status] for status in statuses),
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
            "SELECT id,company_id,project_name,request_id,offer_id,warehouse_invoice_id "
            "FROM supplier_invoices ORDER BY id"
        ),
        "supply_deliveries": (
            "SELECT id,company_id,project,request_id,offer_id "
            "FROM supply_deliveries ORDER BY id"
        ),
        "warehouse_invoices": (
            "SELECT id,company_id,project,location,warehouse_target,supply_delivery_id,"
            "supply_request_id,supplier_invoice_id FROM warehouse_invoices ORDER BY id"
        ),
        "warehouse_history": (
            "SELECT id,company_id,project FROM warehouse_history ORDER BY id"
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
