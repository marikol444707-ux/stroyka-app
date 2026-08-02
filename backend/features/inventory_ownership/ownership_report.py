"""Read-only ownership report for tools, tool history and inventory records."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("tools", "tool_history", "inventory", "inventory_items")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _text(value):
    return str(value or "").strip()


def _item(table, record_id, status, reason, company_id=None, project_id=None, tool_id=None, inventory_id=None):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "toolId": _positive_int(tool_id),
        "inventoryId": _positive_int(inventory_id),
    }


def _project_owner(table, record_id, project_name, company_ids, projects_by_name, **relations):
    name = _text(project_name)
    if not name:
        return _item(table, record_id, "unresolved", "project_owner_missing", **relations)
    candidates = projects_by_name.get(name, [])
    if not candidates:
        return _item(table, record_id, "unresolved", "project_not_found", **relations)
    if len(candidates) != 1:
        return _item(table, record_id, "ambiguous", "project_owner_ambiguous", **relations)
    project = candidates[0]
    company_id = _positive_int(project.get("company_id"))
    if not company_id:
        return _item(table, record_id, "unresolved", "project_company_missing", project_id=project.get("id"), **relations)
    if company_id not in company_ids:
        return _item(table, record_id, "unresolved", "company_not_found", company_id=company_id, project_id=project.get("id"), **relations)
    return _item(
        table,
        record_id,
        "verified",
        "verified_unique_project",
        company_id=company_id,
        project_id=project.get("id"),
        **relations,
    )


def _parent_failure(table, row, parent, prefix, relation_key):
    status = parent.get("status") or "unresolved"
    if status == "verified":
        return None
    if status not in {"unresolved", "ambiguous", "mismatched"}:
        status = "unresolved"
    return _item(
        table,
        row.get("id"),
        status,
        f"{prefix}_parent_{status}",
        tool_id=row.get("tool_id") if relation_key == "tool" else None,
        inventory_id=row.get("inventory_id") if relation_key == "inventory" else None,
    )


def _classify_tool_history(row, tools, tool_rows):
    row = dict(row or {})
    tool_id = _positive_int(row.get("tool_id"))
    if not tool_id:
        return _item("tool_history", row.get("id"), "unresolved", "tool_parent_missing")
    parent = tools.get(tool_id)
    if not parent:
        return _item("tool_history", row.get("id"), "unresolved", "tool_parent_not_found", tool_id=tool_id)
    failure = _parent_failure("tool_history", row, parent, "tool", "tool")
    if failure:
        return failure
    parent_project = _text((tool_rows.get(tool_id) or {}).get("project"))
    history_project = _text(row.get("project"))
    if history_project and history_project != parent_project:
        return _item(
            "tool_history", row.get("id"), "mismatched", "tool_project_mismatch",
            company_id=parent.get("companyId"), project_id=parent.get("projectId"), tool_id=tool_id,
        )
    return _item(
        "tool_history", row.get("id"), "verified", "verified_tool_parent",
        company_id=parent.get("companyId"), project_id=parent.get("projectId"), tool_id=tool_id,
    )


def _classify_inventory_item(row, inventories):
    row = dict(row or {})
    inventory_id = _positive_int(row.get("inventory_id"))
    if not inventory_id:
        return _item("inventory_items", row.get("id"), "unresolved", "inventory_parent_missing")
    parent = inventories.get(inventory_id)
    if not parent:
        return _item("inventory_items", row.get("id"), "unresolved", "inventory_parent_not_found", inventory_id=inventory_id)
    failure = _parent_failure("inventory_items", row, parent, "inventory", "inventory")
    if failure:
        return failure
    return _item(
        "inventory_items", row.get("id"), "verified", "verified_inventory_parent",
        company_id=parent.get("companyId"), project_id=parent.get("projectId"), inventory_id=inventory_id,
    )


def _plan_sha256(classified):
    plan = [
        [
            item["table"], item["recordId"], item["status"], item["reason"], item["companyId"],
            item["projectId"], item["toolId"], item["inventoryId"],
        ]
        for item in classified
    ]
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
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
        if _text(project.get("name")):
            projects_by_name[_text(project.get("name"))].append(project)

    tools = {}
    tool_rows = {}
    for row in rows.get("tools") or []:
        row = dict(row or {})
        item = _project_owner("tools", row.get("id"), row.get("project"), company_ids, projects_by_name)
        if item["recordId"]:
            tools[item["recordId"]] = item
            tool_rows[item["recordId"]] = row

    inventories = {}
    for row in rows.get("inventory") or []:
        row = dict(row or {})
        item = _project_owner("inventory", row.get("id"), row.get("project"), company_ids, projects_by_name)
        if item["recordId"]:
            inventories[item["recordId"]] = item

    classified = list(tools.values())
    classified.extend(
        _classify_tool_history(row, tools, tool_rows)
        for row in (rows.get("tool_history") or [])
    )
    classified.extend(inventories.values())
    classified.extend(
        _classify_inventory_item(row, inventories)
        for row in (rows.get("inventory_items") or [])
    )

    statuses = ("verified", "unresolved", "ambiguous", "mismatched")
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "verified"]
    verified = [item for item in classified if item["status"] == "verified"]
    by_table = {}
    for table in TABLES:
        table_counts = Counter(item["status"] for item in classified if item["table"] == table)
        by_table[table] = {"totalRows": sum(table_counts.values()), **{status: table_counts[status] for status in statuses}}
    ready_by_company = Counter(str(item["companyId"]) for item in verified)
    return {
        "ok": True,
        "dryRun": True,
        "tables": list(TABLES),
        "writesAttempted": 0,
        "readyForStrictRuntime": not review,
        "reportConsistent": len(classified) == sum(counts[status] for status in statuses),
        "summary": {"totalRows": len(classified), **{status: counts[status] for status in statuses}},
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
        "tools": "SELECT id,project FROM tools ORDER BY id",
        "tool_history": "SELECT id,tool_id,project FROM tool_history ORDER BY id",
        "inventory": "SELECT id,project FROM inventory ORDER BY id",
        "inventory_items": "SELECT id,inventory_id FROM inventory_items ORDER BY id",
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
