"""Read-only ownership report for CRM leads and their child records."""

import hashlib
import json
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _item(table, record_id, status, reason, company_id=None, project_id=None):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
    }


def _classify_lead(row, projects, company_ids):
    record_id = _positive_int((row or {}).get("id"))
    project_id = _positive_int((row or {}).get("project_id"))
    if not project_id:
        return _item("crm_leads", record_id, "unresolved", "project_owner_missing")
    project = projects.get(project_id)
    if not project:
        return _item(
            "crm_leads", record_id, "unresolved", "project_not_found", project_id=project_id
        )
    company_id = _positive_int(project.get("company_id"))
    if not company_id:
        return _item(
            "crm_leads",
            record_id,
            "unresolved",
            "project_company_missing",
            project_id=project_id,
        )
    if company_id not in company_ids:
        return _item(
            "crm_leads",
            record_id,
            "unresolved",
            "company_not_found",
            company_id=company_id,
            project_id=project_id,
        )
    return _item(
        "crm_leads",
        record_id,
        "verified",
        "verified_project_parent",
        company_id=company_id,
        project_id=project_id,
    )


def _classify_child(table, row, leads):
    record_id = _positive_int((row or {}).get("id"))
    lead_id = _positive_int((row or {}).get("lead_id"))
    if not lead_id:
        return _item(table, record_id, "unresolved", "lead_parent_missing")
    lead = leads.get(lead_id)
    if not lead:
        return _item(table, record_id, "unresolved", "lead_parent_not_found")
    if lead["status"] != "verified":
        return _item(table, record_id, "unresolved", "lead_parent_unresolved")
    return _item(
        table,
        record_id,
        "verified",
        "verified_lead_parent",
        company_id=lead["companyId"],
        project_id=lead["projectId"],
    )


def _plan_sha256(classified):
    plan = [
        [
            item["table"],
            item["recordId"],
            item["status"],
            item["reason"],
            item["companyId"],
            item["projectId"],
        ]
        for item in classified
    ]
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report_from_rows(rows):
    company_ids = {
        company_id
        for row in (rows.get("companies", []) or [])
        for company_id in [_positive_int((row or {}).get("id"))]
        if company_id
    }
    projects = {
        project_id: dict(row or {})
        for row in (rows.get("projects", []) or [])
        for project_id in [_positive_int((row or {}).get("id"))]
        if project_id
    }
    lead_items = [
        _classify_lead(dict(row or {}), projects, company_ids)
        for row in (rows.get("crm_leads", []) or [])
    ]
    leads = {item["recordId"]: item for item in lead_items if item["recordId"]}
    classified = list(lead_items)
    for table in ("crm_lead_documents", "crm_lead_tasks"):
        classified.extend(
            _classify_child(table, dict(row or {}), leads)
            for row in (rows.get(table, []) or [])
        )

    counts = Counter(item["status"] for item in classified)
    by_table = {}
    for table in ("crm_leads", "crm_lead_documents", "crm_lead_tasks"):
        table_items = [item for item in classified if item["table"] == table]
        table_counts = Counter(item["status"] for item in table_items)
        by_table[table] = {
            "totalRows": len(table_items),
            "verified": table_counts["verified"],
            "unresolved": table_counts["unresolved"],
        }
    review = [item for item in classified if item["status"] != "verified"]
    verified = [item for item in classified if item["status"] == "verified"]
    ready_by_company = Counter(str(item["companyId"]) for item in verified)
    review_by_reason = Counter(item["reason"] for item in review)
    return {
        "ok": True,
        "dryRun": True,
        "tables": ["crm_leads", "crm_lead_documents", "crm_lead_tasks"],
        "writesAttempted": 0,
        "readyForMigration": not review,
        "reportConsistent": len(classified) == counts["verified"] + counts["unresolved"],
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "unresolved": counts["unresolved"],
        },
        "byTable": by_table,
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "reviewByReason": dict(sorted(review_by_reason.items())),
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
        "projects": "SELECT id,company_id FROM projects ORDER BY id",
        "crm_leads": "SELECT id,project_id FROM crm_leads ORDER BY id",
        "crm_lead_documents": "SELECT id,lead_id FROM crm_lead_documents ORDER BY id",
        "crm_lead_tasks": "SELECT id,lead_id FROM crm_lead_tasks ORDER BY id",
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
