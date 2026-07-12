"""Read-only ownership diagnostics for MAX files and messenger outbox rows."""

import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
TABLES = ("messenger_channels", "messenger_files", "messenger_outbox")
MESSENGER_ITEM_TABLES = ("messenger_files", "messenger_outbox")
SUPPORTED_ENTITY_TYPES = {
    "ai_task",
    "marketing_publication",
    "max_invoice_draft",
    "messenger_channel",
    "supply_request",
    "warehouse_invoice",
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _owner(company_id, project_id=None, source=""):
    return {
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "source": source,
    }


def _project_indexes(rows):
    by_id = {}
    by_name = defaultdict(list)
    for raw in rows or []:
        row = dict(raw or {})
        owner = _owner(row.get("company_id"), row.get("id"), "project")
        if not owner["companyId"] or not owner["projectId"]:
            continue
        by_id[owner["projectId"]] = owner
        by_name[str(row.get("name") or "").strip()].append(owner)
    return by_id, by_name


def _recipient_company_indexes(rows):
    user_companies = defaultdict(set)
    for raw in rows.get("user_company_roles", []) or []:
        row = dict(raw or {})
        if row.get("active") is False:
            continue
        user_id = _positive_int(row.get("user_id"))
        company_id = _positive_int(row.get("company_id"))
        if user_id and company_id:
            user_companies[user_id].add(company_id)

    staff_companies = {}
    for raw in rows.get("staff", []) or []:
        row = dict(raw or {})
        staff_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        if staff_id and company_id:
            staff_companies[staff_id] = company_id

    accounts = {}
    for raw in rows.get("messenger_accounts", []) or []:
        row = dict(raw or {})
        account_id = _positive_int(row.get("id"))
        if account_id:
            accounts[account_id] = row
    return user_companies, staff_companies, accounts


def _entity_index(rows, projects_by_id, projects_by_name):
    entities = defaultdict(lambda: {"owners": [], "issues": []})
    for raw in rows or []:
        row = dict(raw or {})
        entity_type = str(row.get("entity_type") or "").strip()
        entity_id = _positive_int(row.get("entity_id"))
        if not entity_type or not entity_id:
            continue
        entry = entities[(entity_type, entity_id)]
        candidates = []
        project_id = _positive_int(row.get("project_id"))
        company_id = _positive_int(row.get("company_id"))
        if project_id and project_id in projects_by_id:
            project_owner = projects_by_id[project_id]
            if company_id and company_id != project_owner["companyId"]:
                entry["issues"].append(("mismatched", "entity_project_company_mismatch"))
            else:
                candidates = [dict(project_owner, source="entity_parent")]
        elif project_id:
            entry["issues"].append(("unresolved", "entity_project_not_found"))
        elif company_id:
            project_name = str(row.get("project_name") or "").strip()
            if project_name:
                candidates = [
                    dict(item, source="entity_parent")
                    for item in projects_by_name.get(project_name, [])
                    if item["companyId"] == company_id
                ]
                if not candidates:
                    entry["issues"].append(("unresolved", "entity_project_not_found"))
            else:
                candidates = [_owner(company_id, None, "entity_parent")]
        else:
            project_name = str(row.get("project_name") or "").strip()
            candidates = [dict(item, source="entity_parent") for item in projects_by_name.get(project_name, [])]
            if project_name and not candidates:
                entry["issues"].append(("unresolved", "entity_project_not_found"))
            elif not project_name:
                entry["issues"].append(("unresolved", "entity_owner_missing"))
        entry["owners"].extend(candidates)
    return entities


def _recipient_companies(row, user_companies, staff_companies, accounts):
    user_ids = set()
    staff_ids = set()
    user_id = _positive_int(row.get("user_id"))
    staff_id = _positive_int(row.get("staff_id"))
    if user_id:
        user_ids.add(user_id)
    if staff_id:
        staff_ids.add(staff_id)
    account = accounts.get(_positive_int(row.get("messenger_account_id")))
    if account:
        account_user = _positive_int(account.get("user_id"))
        account_staff = _positive_int(account.get("staff_id"))
        if account_user:
            user_ids.add(account_user)
        if account_staff:
            staff_ids.add(account_staff)
    companies = set()
    for item in user_ids:
        companies.update(user_companies.get(item, set()))
    for item in staff_ids:
        company_id = staff_companies.get(item)
        if company_id:
            companies.add(company_id)
    return companies


def _dedupe_owners(owners):
    by_company = defaultdict(dict)
    for owner in owners:
        if owner.get("companyId"):
            by_company[owner["companyId"]][owner.get("projectId")] = owner
    result = []
    for company_owners in by_company.values():
        exact_projects = [owner for project_id, owner in company_owners.items() if project_id]
        if exact_projects:
            result.extend(exact_projects)
        elif None in company_owners:
            result.append(company_owners[None])
    return result


def _classification(table, row, status, reason, owner=None):
    owner = owner or {}
    row_status = str(row.get("status") or "").strip()
    if table == "messenger_channels":
        row_status = "enabled" if row.get("enabled") is not False else "disabled"
    return {
        "table": table,
        "recordId": _positive_int(row.get("id")),
        "entityType": str(row.get("entity_type") or "").strip(),
        "entityId": _positive_int(row.get("entity_id")),
        "channelType": str(row.get("channel_type") or "").strip(),
        "rowStatus": row_status,
        "createdAt": str(row.get("created_at") or ""),
        "companyId": owner.get("companyId") if status == "verified" else None,
        "projectId": owner.get("projectId") if status == "verified" else None,
        "status": status,
        "reason": reason,
    }


def classify_channel(row, projects_by_name):
    item = dict(row or {})
    project_name = str(item.get("project_name") or "").strip()
    if not project_name:
        result = _classification("messenger_channels", item, "unresolved", "channel_owner_missing")
        result["recipientCompanyIds"] = []
        return result
    owners = _dedupe_owners(projects_by_name.get(project_name, []))
    if not owners:
        result = _classification("messenger_channels", item, "unresolved", "channel_project_not_found")
    elif len(owners) > 1:
        result = _classification("messenger_channels", item, "ambiguous", "channel_project_ambiguous")
    else:
        result = _classification("messenger_channels", item, "verified", "verified_channel_project", owners[0])
    result["recipientCompanyIds"] = []
    return result


def classify_row(table, row, projects_by_name, entities, user_companies, staff_companies, accounts):
    item = dict(row or {})
    recipient_companies = _recipient_companies(item, user_companies, staff_companies, accounts)

    def result(status, reason, owner=None):
        classified = _classification(table, item, status, reason, owner)
        classified["recipientCompanyIds"] = sorted(recipient_companies)
        return classified

    strong_owners = []
    project_name = str(item.get("project_name") or "").strip()
    if project_name:
        strong_owners.extend(dict(owner, source="project_name") for owner in projects_by_name.get(project_name, []))
    entity_type = str(item.get("entity_type") or "").strip()
    entity_id = _positive_int(item.get("entity_id"))
    if bool(entity_type) != bool(entity_id):
        return result("unresolved", "entity_parent_incomplete")
    if entity_type and entity_id:
        entity = entities.get((entity_type, entity_id))
        if not entity:
            reason = "entity_parent_not_found" if entity_type in SUPPORTED_ENTITY_TYPES else "entity_parent_unsupported"
            return result("unresolved", reason)
        if entity["issues"]:
            status, reason = entity["issues"][0]
            return result(status, reason)
        strong_owners.extend(entity["owners"])
    strong_owners = _dedupe_owners(strong_owners)

    if recipient_companies and strong_owners:
        matching = [owner for owner in strong_owners if owner["companyId"] in recipient_companies]
        if not matching:
            return result("mismatched", "recipient_owner_mismatch")
        strong_owners = matching
    if len(strong_owners) == 1:
        reason = "verified_project_or_entity_owner"
        return result("verified", reason, strong_owners[0])
    if len(strong_owners) > 1:
        return result("ambiguous", "project_or_entity_owner_ambiguous")
    if len(recipient_companies) == 1:
        company_id = next(iter(recipient_companies))
        return result("verified", "verified_recipient_company", _owner(company_id))
    if len(recipient_companies) > 1:
        return result("ambiguous", "recipient_company_ambiguous")
    return result("unresolved", "owner_evidence_missing")


def build_report_from_rows(rows):
    projects_by_id, projects_by_name = _project_indexes(rows.get("projects"))
    user_companies, staff_companies, accounts = _recipient_company_indexes(rows)
    entities = _entity_index(rows.get("entity_owners"), projects_by_id, projects_by_name)
    classified_by_table = {
        table: [
            classify_row(
                table,
                row,
                projects_by_name,
                entities,
                user_companies,
                staff_companies,
                accounts,
            )
            for row in rows.get(table, []) or []
        ]
        for table in MESSENGER_ITEM_TABLES
    }
    classified_by_table["messenger_channels"] = [
        classify_channel(row, projects_by_name)
        for row in rows.get("messenger_channels", []) or []
    ]
    classified = [item for table in TABLES for item in classified_by_table[table]]
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "verified"]
    ready_by_company = Counter(
        str(item["companyId"])
        for item in classified
        if item["status"] == "verified" and item.get("companyId")
    )
    entity_types = Counter(
        table + ":" + (str((row or {}).get("entity_type") or "").strip() or "(none)")
        for table in MESSENGER_ITEM_TABLES
        for row in (rows.get(table, []) or [])
    )
    row_statuses = Counter(
        item["table"] + ":" + item["rowStatus"]
        for item in classified
        if item.get("rowStatus")
    )
    by_table = {}
    for table in TABLES:
        table_rows = classified_by_table[table]
        table_counts = Counter(item["status"] for item in table_rows)
        by_table[table] = {
            "totalRows": len(table_rows),
            "verified": table_counts["verified"],
            "ambiguous": table_counts["ambiguous"],
            "unresolved": table_counts["unresolved"],
            "mismatched": table_counts["mismatched"],
        }
    return {
        "ok": True,
        "dryRun": True,
        "tables": list(TABLES),
        "writesAttempted": 0,
        "readyForMigration": not review,
        "reportConsistent": len(classified) == sum(
            counts[name] for name in ("verified", "ambiguous", "unresolved", "mismatched")
        ),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byTable": by_table,
        "byEntityType": dict(sorted(entity_types.items())),
        "byStatus": dict(sorted(row_statuses.items())),
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "needsReview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "entityType": item["entityType"],
                "entityId": item["entityId"],
                "channelType": item["channelType"],
                "rowStatus": item["rowStatus"],
                "createdAt": item["createdAt"],
                "recipientCompanyIds": item["recipientCompanyIds"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    rows = {}
    cur.execute("SELECT id,company_id,name FROM projects ORDER BY id")
    rows["projects"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT user_id,company_id,active FROM user_company_roles ORDER BY user_id,company_id")
    rows["user_company_roles"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,company_id FROM staff ORDER BY id")
    rows["staff"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,user_id,staff_id FROM messenger_accounts ORDER BY id")
    rows["messenger_accounts"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,channel_type,project_name,enabled,created_at FROM messenger_channels ORDER BY id")
    rows["messenger_channels"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        "SELECT id,messenger_account_id,user_id,staff_id,project_name,entity_type,entity_id,created_at "
        "FROM messenger_files ORDER BY id"
    )
    rows["messenger_files"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        "SELECT id,messenger_account_id,user_id,staff_id,entity_type,entity_id,status,created_at "
        "FROM messenger_outbox ORDER BY id"
    )
    rows["messenger_outbox"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        """SELECT 'max_invoice_draft'::TEXT AS entity_type,id AS entity_id,
                         NULL::INT AS company_id,NULL::INT AS project_id,project_name
                     FROM max_invoice_drafts
                   UNION ALL
                   SELECT 'supply_request',id,company_id,NULL::INT,project FROM supply_requests
                   UNION ALL
                   SELECT 'warehouse_invoice',id,company_id,NULL::INT,project FROM warehouse_invoices
                   UNION ALL
                   SELECT 'ai_task',id,company_id,project_id,project_name FROM ai_tasks
                   UNION ALL
                   SELECT 'marketing_publication',mp.id,NULL::INT,mp.project_id,p.name
                     FROM marketing_publications mp LEFT JOIN projects p ON p.id=mp.project_id
                   UNION ALL
                   SELECT 'messenger_channel',mc.id,NULL::INT,NULL::INT,mc.project_name
                     FROM messenger_channels mc
                   ORDER BY entity_type,entity_id"""
    )
    rows["entity_owners"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows


def run_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_report_from_rows(load_ownership_rows(cur))
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
