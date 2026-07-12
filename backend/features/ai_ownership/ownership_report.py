"""Read-only ownership diagnostics for the five AI tables."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
SYSTEM_PROJECT_NAME = "Система"
TABLES = (
    "project_ai_summary",
    "ai_findings",
    "ai_tasks",
    "ai_task_reports",
    "ai_task_attachments",
)
SUPPORTED_ENTITY_TYPES = {
    "room",
    "room_window",
    "room_door",
    "work_journal",
    "material_norm_suggestion",
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _fingerprint(value):
    return "project:" + hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:12]


def _result(table, record_id, status, reason, owner=None):
    owner = owner or {}
    return {
        "table": table,
        "recordId": record_id,
        "companyId": owner.get("companyId") if status == "verified" else None,
        "projectId": owner.get("projectId") if status == "verified" else None,
        "scope": owner.get("scope") if status == "verified" else None,
        "status": status,
        "reason": reason,
    }


def _same_owner(left, right):
    return (
        left.get("scope"),
        left.get("companyId"),
        left.get("projectId"),
    ) == (
        right.get("scope"),
        right.get("companyId"),
        right.get("projectId"),
    )


def _project_index(project_rows):
    index = defaultdict(list)
    for row in project_rows or []:
        item = dict(row or {})
        index[str(item.get("name") or "")].append(item)
    return index


def resolve_project(project_name, projects):
    name = str(project_name or "")
    if name == SYSTEM_PROJECT_NAME:
        return {"status": "verified", "reason": "platform_system_scope", "scope": "system"}
    if not name.strip():
        return {"status": "unresolved", "reason": "project_name_missing"}
    candidates = projects.get(name, [])
    if not candidates:
        return {"status": "unresolved", "reason": "project_not_found"}
    if len(candidates) > 1:
        return {"status": "unresolved", "reason": "project_name_ambiguous"}
    project = candidates[0]
    project_id = _positive_int(project.get("id"))
    company_id = _positive_int(project.get("company_id"))
    if not project_id or not company_id:
        return {"status": "unresolved", "reason": "project_owner_missing"}
    return {
        "status": "verified",
        "reason": "verified_project_owner",
        "scope": "tenant",
        "companyId": company_id,
        "projectId": project_id,
    }


def _entity_index(entity_rows):
    index = defaultdict(list)
    for row in entity_rows or []:
        item = dict(row or {})
        key = (str(item.get("entity_type") or ""), str(item.get("entity_id") or ""))
        index[key].append(item)
    return index


def classify_summary(row, projects):
    item = dict(row or {})
    owner = resolve_project(item.get("project_name"), projects)
    return _result(
        "project_ai_summary",
        _fingerprint(item.get("project_name")),
        owner["status"],
        owner["reason"],
        owner,
    )


def classify_finding(row, projects, entities):
    item = dict(row or {})
    owner = resolve_project(item.get("project_name"), projects)
    finding_id = _positive_int(item.get("id"))
    if owner["status"] != "verified":
        return _result("ai_findings", finding_id, owner["status"], owner["reason"])
    if owner.get("scope") == "system":
        return _result("ai_findings", finding_id, "mismatched", "finding_cannot_use_system_scope")

    entity_type = str(item.get("linked_entity_type") or "").strip()
    entity_id = str(item.get("linked_entity_id") or "").strip()
    if not entity_type and not entity_id:
        return _result("ai_findings", finding_id, "verified", "verified_project_owner", owner)
    if not entity_type or not entity_id:
        return _result("ai_findings", finding_id, "unresolved", "linked_entity_incomplete")
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        return _result("ai_findings", finding_id, "unresolved", "linked_entity_type_unsupported")
    candidates = entities.get((entity_type, entity_id), [])
    if not candidates:
        return _result("ai_findings", finding_id, "unresolved", "linked_entity_not_found")
    if len(candidates) > 1:
        return _result("ai_findings", finding_id, "unresolved", "linked_entity_ambiguous")
    entity_owner = resolve_project(candidates[0].get("project_name"), projects)
    if entity_owner["status"] != "verified":
        return _result("ai_findings", finding_id, entity_owner["status"], "linked_entity_" + entity_owner["reason"])
    if not _same_owner(owner, entity_owner):
        return _result("ai_findings", finding_id, "mismatched", "linked_entity_owner_mismatch")
    return _result("ai_findings", finding_id, "verified", "verified_project_and_entity", owner)


def classify_task(row, projects, findings):
    item = dict(row or {})
    task_id = _positive_int(item.get("id"))
    owner = resolve_project(item.get("project_name"), projects)
    if owner["status"] != "verified":
        return _result("ai_tasks", task_id, owner["status"], owner["reason"])
    finding_id = _positive_int(item.get("finding_id"))
    if not finding_id:
        reason = "verified_system_task" if owner.get("scope") == "system" else "verified_project_task"
        return _result("ai_tasks", task_id, "verified", reason, owner)
    finding = findings.get(finding_id)
    if not finding:
        return _result("ai_tasks", task_id, "unresolved", "finding_not_found")
    if finding["status"] != "verified":
        return _result("ai_tasks", task_id, "unresolved", "finding_owner_not_verified")
    if not _same_owner(owner, finding):
        return _result("ai_tasks", task_id, "mismatched", "finding_owner_mismatch")
    return _result("ai_tasks", task_id, "verified", "verified_finding_parent", owner)


def classify_report(row, tasks):
    item = dict(row or {})
    report_id = _positive_int(item.get("id"))
    task_id = _positive_int(item.get("task_id"))
    if not task_id or task_id not in tasks:
        return _result("ai_task_reports", report_id, "unresolved", "task_not_found")
    task = tasks[task_id]
    if task["status"] != "verified":
        return _result("ai_task_reports", report_id, "unresolved", "task_owner_not_verified")
    return _result("ai_task_reports", report_id, "verified", "verified_task_parent", task)


def classify_attachment(row, reports, tasks):
    item = dict(row or {})
    attachment_id = _positive_int(item.get("id"))
    report_id = _positive_int(item.get("report_id"))
    task_id = _positive_int(item.get("task_id"))
    report = reports.get(report_id)
    task = tasks.get(task_id)
    if not report_id or not report:
        return _result("ai_task_attachments", attachment_id, "unresolved", "report_not_found")
    if not task_id or not task:
        return _result("ai_task_attachments", attachment_id, "unresolved", "task_not_found")
    if report["status"] != "verified":
        return _result("ai_task_attachments", attachment_id, "unresolved", "report_owner_not_verified")
    if task["status"] != "verified":
        return _result("ai_task_attachments", attachment_id, "unresolved", "task_owner_not_verified")
    if _positive_int(item.get("report_task_id")) != task_id:
        return _result("ai_task_attachments", attachment_id, "mismatched", "report_task_mismatch")
    if not _same_owner(report, task):
        return _result("ai_task_attachments", attachment_id, "mismatched", "report_task_owner_mismatch")
    return _result("ai_task_attachments", attachment_id, "verified", "verified_report_and_task_parents", task)


def build_report_from_rows(rows):
    projects = _project_index(rows.get("projects"))
    entities = _entity_index(rows.get("linked_entities"))

    summaries = [classify_summary(row, projects) for row in rows.get("project_ai_summary", [])]
    findings = [classify_finding(row, projects, entities) for row in rows.get("ai_findings", [])]
    findings_by_id = {item["recordId"]: item for item in findings if item.get("recordId")}
    tasks = [classify_task(row, projects, findings_by_id) for row in rows.get("ai_tasks", [])]
    tasks_by_id = {item["recordId"]: item for item in tasks if item.get("recordId")}
    reports = [classify_report(row, tasks_by_id) for row in rows.get("ai_task_reports", [])]
    reports_by_id = {item["recordId"]: item for item in reports if item.get("recordId")}
    report_task_ids = {
        _positive_int(row.get("id")): _positive_int(row.get("task_id"))
        for row in rows.get("ai_task_reports", [])
    }
    attachment_rows = []
    for row in rows.get("ai_task_attachments", []):
        item = dict(row or {})
        item["report_task_id"] = report_task_ids.get(_positive_int(item.get("report_id")))
        attachment_rows.append(item)
    attachments = [classify_attachment(row, reports_by_id, tasks_by_id) for row in attachment_rows]

    classified_by_table = {
        "project_ai_summary": summaries,
        "ai_findings": findings,
        "ai_tasks": tasks,
        "ai_task_reports": reports,
        "ai_task_attachments": attachments,
    }
    all_rows = [item for table in TABLES for item in classified_by_table[table]]
    counts = Counter(item["status"] for item in all_rows)
    review = [item for item in all_rows if item["status"] != "verified"]
    ready_by_company = Counter(
        str(item["companyId"])
        for item in all_rows
        if item["status"] == "verified" and item.get("companyId")
    )
    table_reports = {}
    for table in TABLES:
        table_rows = classified_by_table[table]
        table_counts = Counter(item["status"] for item in table_rows)
        table_reports[table] = {
            "totalRows": len(table_rows),
            "verified": table_counts["verified"],
            "systemRows": sum(1 for item in table_rows if item.get("scope") == "system"),
            "unresolved": table_counts["unresolved"],
            "mismatched": table_counts["mismatched"],
        }
    return {
        "ok": True,
        "dryRun": True,
        "tables": list(TABLES),
        "writesAttempted": 0,
        "readyForStrictRuntime": not review,
        "reportConsistent": len(all_rows) == counts["verified"] + counts["unresolved"] + counts["mismatched"],
        "summary": {
            "totalRows": len(all_rows),
            "verified": counts["verified"],
            "systemRows": sum(1 for item in all_rows if item.get("scope") == "system"),
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byTable": table_reports,
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "needsReview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    queries = {
        "projects": "SELECT id,name,company_id FROM projects ORDER BY id",
        "project_ai_summary": "SELECT project_name FROM project_ai_summary ORDER BY project_name",
        "ai_findings": "SELECT id,project_name,linked_entity_type,linked_entity_id FROM ai_findings ORDER BY id",
        "ai_tasks": "SELECT id,finding_id,project_name FROM ai_tasks ORDER BY id",
        "ai_task_reports": "SELECT id,task_id FROM ai_task_reports ORDER BY id",
        "ai_task_attachments": "SELECT id,report_id,task_id FROM ai_task_attachments ORDER BY id",
    }
    rows = {}
    for key, sql in queries.items():
        cur.execute(sql)
        rows[key] = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute(
        """SELECT 'room' AS entity_type,id::text AS entity_id,project AS project_name FROM rooms
           UNION ALL
           SELECT 'room_window',rw.id::text,r.project FROM room_windows rw JOIN rooms r ON r.id=rw.room_id
           UNION ALL
           SELECT 'room_door',rd.id::text,r.project FROM room_doors rd JOIN rooms r ON r.id=rd.room_id
           UNION ALL
           SELECT 'work_journal',id::text,project FROM work_journal
           UNION ALL
           SELECT 'material_norm_suggestion',id::text,project_name FROM material_norm_suggestions
           ORDER BY entity_type,entity_id"""
    )
    rows["linked_entities"] = [dict(row) for row in (cur.fetchall() or [])]
    return rows


def build_ai_ownership_report(cur):
    return build_report_from_rows(load_ownership_rows(cur))


def run_ai_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_ai_ownership_report(cur)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(run_ai_ownership_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
