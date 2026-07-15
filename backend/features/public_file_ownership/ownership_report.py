"""Read-only ownership report for tenant files and public lead uploads."""

import hashlib
import json
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("file_ownership", "public_lead_uploads")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _item(table, record_id, status, reason, company_id=None, project_id=None, lead_id=None):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "leadId": _positive_int(lead_id),
    }


def _classify_file(row, company_ids, projects):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    project_id = _positive_int(row.get("project_id"))
    if not company_id:
        return _item("file_ownership", record_id, "unresolved", "company_owner_missing")
    if company_id not in company_ids:
        return _item(
            "file_ownership", record_id, "unresolved", "company_not_found",
            company_id=company_id, project_id=project_id,
        )
    if project_id:
        project = projects.get(project_id)
        if not project:
            return _item(
                "file_ownership", record_id, "unresolved", "project_not_found",
                company_id=company_id, project_id=project_id,
            )
        if _positive_int(project.get("company_id")) != company_id:
            return _item(
                "file_ownership", record_id, "mismatched", "project_company_mismatch",
                company_id=company_id, project_id=project_id,
            )
        reason = "verified_project_parent"
    else:
        reason = "verified_company_owner"
    return _item(
        "file_ownership", record_id, "verified", reason,
        company_id=company_id, project_id=project_id,
    )


def _classify_public_upload(row, company_ids, files, leads):
    row = dict(row or {})
    file_id = _positive_int(row.get("file_ownership_id"))
    company_id = _positive_int(row.get("company_id"))
    lead_id = _positive_int(row.get("lead_id"))
    if not company_id:
        return _item(
            "public_lead_uploads", file_id, "unresolved", "company_owner_missing",
            lead_id=lead_id,
        )
    if company_id not in company_ids:
        return _item(
            "public_lead_uploads", file_id, "unresolved", "company_not_found",
            company_id=company_id, lead_id=lead_id,
        )
    if not file_id:
        return _item(
            "public_lead_uploads", None, "unresolved", "file_parent_missing",
            company_id=company_id, lead_id=lead_id,
        )
    file_item = files.get(file_id)
    if not file_item:
        return _item(
            "public_lead_uploads", file_id, "unresolved", "file_parent_not_found",
            company_id=company_id, lead_id=lead_id,
        )
    if file_item["companyId"] != company_id:
        return _item(
            "public_lead_uploads", file_id, "mismatched", "file_company_mismatch",
            company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
        )
    if file_item["status"] != "verified":
        return _item(
            "public_lead_uploads", file_id, "unresolved", "file_parent_unresolved",
            company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
        )
    if not lead_id:
        return _item(
            "public_lead_uploads", file_id, "verified", "verified_file_parent",
            company_id=company_id, project_id=file_item["projectId"],
        )
    lead = leads.get(lead_id)
    if not lead:
        return _item(
            "public_lead_uploads", file_id, "unresolved", "lead_parent_not_found",
            company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
        )
    lead_company_id = _positive_int(lead.get("company_id"))
    if not lead_company_id:
        return _item(
            "public_lead_uploads", file_id, "unresolved", "lead_company_missing",
            company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
        )
    if lead_company_id != company_id:
        return _item(
            "public_lead_uploads", file_id, "mismatched", "lead_company_mismatch",
            company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
        )
    return _item(
        "public_lead_uploads", file_id, "verified", "verified_file_and_lead_parents",
        company_id=company_id, project_id=file_item["projectId"], lead_id=lead_id,
    )


def _plan_sha256(classified):
    plan = [
        [
            item["table"], item["recordId"], item["status"], item["reason"],
            item["companyId"], item["projectId"], item["leadId"],
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
    projects = {
        project_id: dict(row or {})
        for row in (rows.get("projects") or [])
        for project_id in [_positive_int((row or {}).get("id"))]
        if project_id
    }
    leads = {
        lead_id: dict(row or {})
        for row in (rows.get("crm_leads") or [])
        for lead_id in [_positive_int((row or {}).get("id"))]
        if lead_id
    }
    file_items = [
        _classify_file(row, company_ids, projects)
        for row in (rows.get("file_ownership") or [])
    ]
    files = {item["recordId"]: item for item in file_items if item["recordId"]}
    classified = file_items + [
        _classify_public_upload(row, company_ids, files, leads)
        for row in (rows.get("public_lead_uploads") or [])
    ]
    counts = Counter(item["status"] for item in classified)
    by_table = {}
    for table in TABLES:
        table_counts = Counter(item["status"] for item in classified if item["table"] == table)
        by_table[table] = {
            "totalRows": sum(table_counts.values()),
            "verified": table_counts["verified"],
            "unresolved": table_counts["unresolved"],
            "mismatched": table_counts["mismatched"],
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
        "reportConsistent": len(classified) == sum(counts[name] for name in ("verified", "unresolved", "mismatched")),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
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
        "projects": "SELECT id,company_id FROM projects ORDER BY id",
        "crm_leads": "SELECT id,company_id FROM crm_leads ORDER BY id",
        "file_ownership": "SELECT id,company_id,project_id FROM file_ownership ORDER BY id",
        "public_lead_uploads": (
            "SELECT file_ownership_id,company_id,lead_id "
            "FROM public_lead_uploads ORDER BY file_ownership_id"
        ),
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
