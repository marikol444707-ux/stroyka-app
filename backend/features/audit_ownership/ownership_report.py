"""Read-only tenant ownership diagnostics for legacy audit_log rows."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
PLATFORM_ACTIONS = {
    "login",
    "logout",
    "password_reset_request",
    "password_reset",
    "2fa_setup",
    "2fa_reset",
}

# Every identifier below is static application metadata, never user input.
ENTITY_SPECS = (
    ("staff", "staff", "id", "company_id", None, "project"),
    ("timesheet", "staff", "id", "company_id", None, "project"),
    ("supply_request", "supply_requests", "id", "company_id", "project_id", "project"),
    ("work_journal", "work_journal", "id", "company_id", "project_id", "project"),
    ("interim_act", "interim_acts", "id", "company_id", "project_id", "project"),
    ("hidden_works_act", "hidden_works_acts", "id", "company_id", "project_id", "project_name"),
    ("supplier_invoice", "supplier_invoices", "id", "company_id", "project_id", "project_name"),
    ("brigade_contract", "brigade_contracts", "id", "company_id", "project_id", "project_name"),
    ("unexpected_work", "unexpected_works", "id", "company_id", "project_id", "project_name"),
    (
        "estimate_reconciliation",
        "estimate_reconciliations",
        "id",
        "company_id",
        "project_id",
        "project_name",
    ),
    ("project_document", "project_documents", "id", "company_id", "project_id", "project_name"),
    (
        "project_launch_draft",
        "project_launch_drafts",
        "id",
        "company_id",
        "project_id",
        "project_name",
    ),
    (
        "marketing_publication",
        "marketing_publications",
        "id",
        "company_id",
        "project_id",
        "project_name",
    ),
    ("crm_lead", "crm_leads", "id", "company_id", "project_id", "project_name"),
    ("site_price_rule", "site_price_rules", "id", "company_id", None, None),
    ("invite_code", "invite_codes", "id", "company_id", None, "project_name"),
    (
        "project_site_publication",
        "project_site_publications",
        "id",
        "company_id",
        "project_id",
        "project_name",
    ),
    ("supplier", "company_supplier_links", "supplier_id", "company_id", None, None),
)
SUPPORTED_ENTITY_TYPES = {"project", "user", "director_agent", "supplier_invoice_template"} | {
    spec[0] for spec in ENTITY_SPECS
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _owner(company_id, project_id=None, scope="company"):
    return {
        "scope": scope,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
    }


def _owner_key(owner):
    return owner.get("scope"), owner.get("companyId"), owner.get("projectId")


def _dedupe_owners(owners):
    return list({_owner_key(owner): owner for owner in owners if owner}.values())


def _project_indexes(rows):
    by_id = {}
    by_name = defaultdict(list)
    for raw in rows or []:
        row = dict(raw or {})
        project_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        if not project_id or not company_id:
            continue
        owner = dict(_owner(company_id, project_id), projectName=str(row.get("name") or "").strip())
        by_id[project_id] = owner
        by_name[owner["projectName"]].append(owner)
    return by_id, by_name


def _membership_index(rows):
    result = defaultdict(set)
    for raw in rows or []:
        row = dict(raw or {})
        if row.get("active") is False:
            continue
        user_id = _positive_int(row.get("user_id"))
        company_id = _positive_int(row.get("company_id"))
        if user_id and company_id:
            result[user_id].add(company_id)
    return result


def _raw_entity_owners(row, projects_by_id, projects_by_name):
    item = dict(row or {})
    company_id = _positive_int(item.get("company_id"))
    project_id = _positive_int(item.get("project_id"))
    project_name = str(item.get("project_name") or "").strip()

    if project_id:
        project = projects_by_id.get(project_id)
        if not project:
            return [], "entity_project_not_found"
        if company_id and company_id != project["companyId"]:
            return [], "entity_project_company_mismatch"
        if project_name and project_name != project.get("projectName"):
            return [], "entity_project_name_mismatch"
        return [project], ""
    if project_name:
        candidates = list(projects_by_name.get(project_name, []))
        if company_id:
            candidates = [owner for owner in candidates if owner["companyId"] == company_id]
        if not candidates:
            return [], "entity_project_not_found"
        return candidates, "" if len(candidates) == 1 else "entity_project_ambiguous"
    if company_id:
        return [_owner(company_id)], ""
    return [], "entity_owner_missing"


def _entity_index(rows, projects_by_id, projects_by_name, user_companies):
    indexed = defaultdict(lambda: {"owners": [], "issues": []})
    for raw in rows or []:
        row = dict(raw or {})
        entity_type = str(row.get("entity_type") or "").strip()
        entity_id = _positive_int(row.get("entity_id"))
        if not entity_type or not entity_id:
            continue
        owners, issue = _raw_entity_owners(row, projects_by_id, projects_by_name)
        indexed[(entity_type, entity_id)]["owners"].extend(owners)
        if issue:
            indexed[(entity_type, entity_id)]["issues"].append(issue)

    for project_id, owner in projects_by_id.items():
        indexed[("project", project_id)]["owners"].append(owner)
    for user_id, company_ids in user_companies.items():
        indexed[("user", user_id)]["owners"].extend(_owner(company_id) for company_id in company_ids)

    for entry in indexed.values():
        entry["owners"] = _dedupe_owners(entry["owners"])
        entry["issues"] = sorted(set(entry["issues"]))
    return indexed


def _classification(row, status, reason, owner=None):
    item = dict(row or {})
    owner = owner or {}
    return {
        "recordId": _positive_int(item.get("id")),
        "entityType": str(item.get("entity_type") or "").strip(),
        "scope": owner.get("scope") if status == "verified" else None,
        "companyId": owner.get("companyId") if status == "verified" else None,
        "projectId": owner.get("projectId") if status == "verified" else None,
        "status": status,
        "reason": reason,
    }


def _filter_by_actor(owners, actor_companies):
    if not actor_companies:
        return owners
    return [owner for owner in owners if owner.get("companyId") in actor_companies]


def _intersect_owners(left, right):
    matches = []
    for first in left:
        for second in right:
            if first.get("companyId") != second.get("companyId"):
                continue
            first_project = first.get("projectId")
            second_project = second.get("projectId")
            if first_project and second_project and first_project != second_project:
                continue
            matches.append(first if first_project else second)
    return _dedupe_owners(matches)


def classify_audit_row(row, projects_by_name, entities, user_companies):
    item = dict(row or {})
    action = str(item.get("action") or "").strip().lower()
    entity_type = str(item.get("entity_type") or "").strip()
    entity_id = _positive_int(item.get("entity_id"))
    actor_companies = set(user_companies.get(_positive_int(item.get("user_id")), set()))

    if action in PLATFORM_ACTIONS and entity_type in {"", "user"}:
        return _classification(item, "verified", "platform_identity_event", _owner(None, None, "platform"))

    project_name = str(item.get("project_name") or "").strip()
    project_candidates = list(projects_by_name.get(project_name, [])) if project_name else []
    project_issue = ""
    if project_name and not project_candidates:
        project_issue = "project_not_found"
    elif len(project_candidates) > 1:
        project_issue = "project_name_ambiguous"

    entity_entry = entities.get((entity_type, entity_id)) if entity_type and entity_id else None
    entity_candidates = list((entity_entry or {}).get("owners", []))
    entity_issues = list((entity_entry or {}).get("issues", []))

    if project_candidates and entity_candidates:
        candidates = _intersect_owners(project_candidates, entity_candidates)
        if not candidates:
            return _classification(item, "mismatched", "project_entity_owner_mismatch")
    elif project_candidates:
        candidates = project_candidates
    elif entity_candidates:
        if project_issue:
            return _classification(item, "mismatched", "project_entity_owner_mismatch")
        candidates = entity_candidates
    else:
        candidates = []

    if candidates:
        actor_candidates = _filter_by_actor(candidates, actor_companies)
        if actor_companies and not actor_candidates:
            return _classification(item, "mismatched", "actor_parent_company_mismatch")
        candidates = actor_candidates or candidates
        if len(candidates) == 1:
            reason = "verified_project_and_entity" if project_candidates and entity_candidates else (
                "verified_project_owner" if project_candidates else "verified_entity_parent"
            )
            return _classification(item, "verified", reason, candidates[0])
        return _classification(
            item,
            "ambiguous",
            "project_name_ambiguous" if project_issue else "entity_owner_ambiguous",
        )

    if project_issue:
        return _classification(
            item,
            "ambiguous" if project_issue == "project_name_ambiguous" else "unresolved",
            project_issue,
        )
    if entity_issues:
        issue = entity_issues[0]
        status = "mismatched" if "mismatch" in issue else "ambiguous" if "ambiguous" in issue else "unresolved"
        return _classification(item, status, issue)
    if entity_type and entity_id:
        reason = (
            "entity_parent_not_found"
            if entity_type in SUPPORTED_ENTITY_TYPES
            else "entity_parent_unsupported"
        )
    else:
        reason = "owner_evidence_missing"

    if len(actor_companies) == 1:
        company_id = next(iter(actor_companies))
        return _classification(item, "verified", "unique_actor_company", _owner(company_id))
    if len(actor_companies) > 1:
        return _classification(item, "ambiguous", "actor_company_ambiguous")
    return _classification(item, "unresolved", reason)


def build_report_from_rows(rows):
    projects_by_id, projects_by_name = _project_indexes(rows.get("projects", []))
    user_companies = _membership_index(rows.get("user_company_roles", []))
    entities = _entity_index(
        rows.get("entity_owners", []), projects_by_id, projects_by_name, user_companies
    )
    classified = [
        classify_audit_row(row, projects_by_name, entities, user_companies)
        for row in rows.get("audit_log", [])
    ]
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "verified"]
    ready_by_company = Counter(
        str(item["companyId"])
        for item in classified
        if item["status"] == "verified" and item.get("companyId")
    )
    by_entity_type = Counter(item["entityType"] or "(missing)" for item in classified)
    review_by_reason = Counter(item["reason"] for item in review)
    review_by_entity_type = Counter(item["entityType"] or "(missing)" for item in review)
    review_plan = [
        {
            "recordId": item["recordId"],
            "entityType": item["entityType"],
            "status": item["status"],
            "reason": item["reason"],
        }
        for item in review
    ]
    review_plan_sha256 = hashlib.sha256(
        json.dumps(review_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    review_ids = [item["recordId"] for item in review if item.get("recordId")]
    return {
        "ok": True,
        "dryRun": True,
        "table": "audit_log",
        "writesAttempted": 0,
        "readyForMigration": not review,
        "reportConsistent": len(classified)
        == sum(counts[name] for name in ("verified", "ambiguous", "unresolved", "mismatched")),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "platformRows": sum(
                1 for item in classified if item.get("scope") == "platform"
            ),
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byEntityType": dict(sorted(by_entity_type.items())),
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "reviewCount": len(review),
        "reviewByReason": dict(sorted(review_by_reason.items())),
        "reviewByEntityType": dict(sorted(review_by_entity_type.items())),
        "reviewIdRange": {
            "first": min(review_ids) if review_ids else None,
            "last": max(review_ids) if review_ids else None,
        },
        "reviewPlanSha256": review_plan_sha256,
        "needsReview": [
            {
                "recordId": item["recordId"],
                "entityType": item["entityType"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def _available_columns(cur):
    table_names = sorted({spec[1] for spec in ENTITY_SPECS})
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name = ANY(%s)
            ORDER BY table_name,column_name""",
        (table_names,),
    )
    result = defaultdict(set)
    for row in cur.fetchall() or []:
        item = dict(row or {})
        result[str(item.get("table_name") or "")].add(str(item.get("column_name") or ""))
    return result


def _column_expr(column, available, alias, cast=""):
    if column and column in available:
        suffix = cast if cast else ""
        return f"{column}{suffix} AS {alias}"
    return f"NULL AS {alias}"


def load_ownership_rows(cur):
    rows = {}
    cur.execute("SELECT id,name,company_id FROM projects ORDER BY id")
    rows["projects"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        "SELECT id,user_id,action,entity_type,entity_id,project_name FROM audit_log ORDER BY id"
    )
    rows["audit_log"] = [dict(row or {}) for row in (cur.fetchall() or [])]

    actor_user_ids = {
        _positive_int(row.get("user_id"))
        for row in rows["audit_log"]
        if _positive_int(row.get("user_id"))
    }
    target_user_ids = {
        _positive_int(row.get("entity_id"))
        for row in rows["audit_log"]
        if str(row.get("entity_type") or "").strip() == "user"
        and _positive_int(row.get("entity_id"))
    }
    relevant_user_ids = sorted(actor_user_ids | target_user_ids)
    if relevant_user_ids:
        cur.execute(
            """SELECT user_id,company_id,active FROM user_company_roles
                WHERE user_id=ANY(%s) ORDER BY user_id,company_id""",
            (relevant_user_ids,),
        )
        rows["user_company_roles"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    else:
        rows["user_company_roles"] = []

    referenced_entity_ids = defaultdict(set)
    for row in rows["audit_log"]:
        entity_type = str(row.get("entity_type") or "").strip()
        entity_id = _positive_int(row.get("entity_id"))
        if entity_type and entity_id:
            referenced_entity_ids[entity_type].add(entity_id)

    available_by_table = _available_columns(cur)
    entity_rows = []
    for entity_type, table, id_col, company_col, project_id_col, project_name_col in ENTITY_SPECS:
        entity_ids = sorted(referenced_entity_ids.get(entity_type, set()))
        if not entity_ids:
            continue
        available = available_by_table.get(table, set())
        if id_col not in available:
            continue
        select = ",".join(
            (
                f"'{entity_type}' AS entity_type",
                _column_expr(id_col, available, "entity_id"),
                _column_expr(company_col, available, "company_id"),
                _column_expr(project_id_col, available, "project_id"),
                _column_expr(project_name_col, available, "project_name", "::text"),
            )
        )
        cur.execute(
            f"SELECT {select} FROM {table} WHERE {id_col}=ANY(%s) ORDER BY {id_col}",
            (entity_ids,),
        )
        entity_rows.extend(dict(row or {}) for row in (cur.fetchall() or []))
    rows["entity_owners"] = entity_rows
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
