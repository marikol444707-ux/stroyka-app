"""Guarded company/project ownership migration for CRM leads and children."""

import argparse
import hashlib
import json
import re
from collections import Counter

import psycopg2.extensions
import psycopg2.extras


APPLY_CONFIRMATION = "APPLY_CRM_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_LIMIT = 100
REVIEW_STATUSES = ("unresolved", "mismatched")
TABLE_COLUMNS = {
    "crm_leads": {"company_id"},
    "crm_lead_documents": {"company_id", "project_id"},
    "crm_lead_tasks": {"company_id", "project_id"},
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _non_negative_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return result


def _sha256_arg(value):
    normalized = str(value or "").strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError("must be a 64-character SHA-256 hex digest")
    return normalized


def parse_lead_owner(value):
    parts = str(value or "").strip().split(":")
    if len(parts) != 2:
        raise ValueError("lead owner must use LEAD_ID:COMPANY_ID")
    lead_id = _positive_int(parts[0])
    company_id = _positive_int(parts[1])
    if not lead_id or not company_id:
        raise ValueError("lead owner IDs must be positive integers")
    return {"leadId": lead_id, "companyId": company_id}


def _result(table, record_id, status, reason, company_id=None, project_id=None, lead_id=None):
    return {
        "table": table,
        "recordId": _positive_int(record_id),
        "leadId": _positive_int(lead_id),
        "proposedCompanyId": _positive_int(company_id),
        "proposedProjectId": _positive_int(project_id),
        "status": status,
        "reason": reason,
    }


def classify_lead(row, projects, companies, manual_owners):
    item = dict(row or {})
    lead_id = _positive_int(item.get("id"))
    project_id = _positive_int(item.get("project_id"))
    stored_company = _positive_int(item.get("stored_company_id"))
    manual = (manual_owners or {}).get(lead_id)
    manual_company = _positive_int((manual or {}).get("companyId"))
    if not lead_id:
        return _result("crm_leads", lead_id, "unresolved", "lead_id_invalid")

    project_company = None
    if project_id:
        project = projects.get(project_id)
        if not project:
            return _result(
                "crm_leads", lead_id, "unresolved", "project_not_found", project_id=project_id
            )
        project_company = _positive_int(project.get("company_id"))
        if not project_company:
            return _result(
                "crm_leads",
                lead_id,
                "unresolved",
                "project_company_missing",
                project_id=project_id,
            )
        if project_company not in companies:
            return _result(
                "crm_leads",
                lead_id,
                "unresolved",
                "company_not_found",
                project_company,
                project_id,
            )

    if stored_company:
        if stored_company not in companies:
            return _result(
                "crm_leads", lead_id, "unresolved", "stored_company_not_found", stored_company, project_id
            )
        if project_company and stored_company != project_company:
            return _result(
                "crm_leads", lead_id, "mismatched", "stored_project_company_mismatch", stored_company, project_id
            )
        if manual_company and manual_company != stored_company:
            return _result(
                "crm_leads", lead_id, "mismatched", "manual_owner_conflicts_with_stored", stored_company, project_id
            )
        return _result(
            "crm_leads", lead_id, "stored", "stored_owner_verified", stored_company, project_id
        )

    if project_company:
        if manual_company and manual_company != project_company:
            return _result(
                "crm_leads", lead_id, "mismatched", "manual_project_company_mismatch", project_company, project_id
            )
        return _result(
            "crm_leads", lead_id, "ready", "verified_project_parent", project_company, project_id
        )

    if not manual_company:
        return _result(
            "crm_leads", lead_id, "unresolved", "manual_company_owner_required"
        )
    if manual_company not in companies:
        return _result(
            "crm_leads", lead_id, "unresolved", "manual_company_not_found", manual_company
        )
    return _result(
        "crm_leads", lead_id, "ready", "explicit_company_owner", manual_company
    )


def classify_child(table, row, leads):
    if table not in ("crm_lead_documents", "crm_lead_tasks"):
        raise ValueError("unsupported CRM child table")
    item = dict(row or {})
    record_id = _positive_int(item.get("id"))
    lead_id = _positive_int(item.get("lead_id"))
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    if not record_id:
        return _result(table, record_id, "unresolved", "record_id_invalid", lead_id=lead_id)
    if not lead_id:
        return _result(table, record_id, "unresolved", "lead_parent_missing")
    lead = (leads or {}).get(lead_id)
    if not lead:
        return _result(table, record_id, "unresolved", "lead_parent_not_found", lead_id=lead_id)
    if lead.get("status") not in ("ready", "stored"):
        return _result(table, record_id, "unresolved", "lead_owner_not_verified", lead_id=lead_id)

    company_id = _positive_int(lead.get("proposedCompanyId"))
    project_id = _positive_int(lead.get("proposedProjectId"))
    if stored_project and not stored_company:
        return _result(
            table, record_id, "mismatched", "stored_owner_incomplete", company_id, project_id, lead_id
        )
    if stored_company or stored_project:
        if (stored_company, stored_project) != (company_id, project_id):
            return _result(
                table, record_id, "mismatched", "stored_owner_mismatch", company_id, project_id, lead_id
            )
        return _result(
            table, record_id, "stored", "stored_owner_verified", company_id, project_id, lead_id
        )
    return _result(
        table, record_id, "ready", "verified_lead_parent", company_id, project_id, lead_id
    )


def build_report(columns, classified):
    rows = list(classified or [])
    counts = Counter(item["status"] for item in rows)
    ready = [item for item in rows if item["status"] == "ready"]
    review = [item for item in rows if item["status"] in REVIEW_STATUSES]
    columns_ready = all(TABLE_COLUMNS[table].issubset(columns.get(table, set())) for table in TABLE_COLUMNS)
    table_totals = Counter(item["table"] for item in rows)
    table_stored = Counter(item["table"] for item in rows if item["status"] == "stored")
    table_ready = Counter(item["table"] for item in ready)
    return {
        "ok": True,
        "tables": list(TABLE_COLUMNS),
        "columns": {
            table: {column: column in columns.get(table, set()) for column in sorted(required)}
            for table, required in TABLE_COLUMNS.items()
        },
        "reportConsistent": len(rows)
        == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": columns_ready and not ready and not review,
        "summary": {
            "totalRows": len(rows),
            "storedRows": counts["stored"],
            "legacyRows": len(rows) - counts["stored"],
            "ready": counts["ready"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byTable": {
            table: {
                "totalRows": table_totals[table],
                "storedRows": table_stored[table],
                "ready": table_ready[table],
            }
            for table in TABLE_COLUMNS
        },
        "backfillPreview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def _table_columns(cur, table):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name=%s AND column_name IN ('company_id','project_id')",
        (table,),
    )
    return {
        str(row.get("column_name") if isinstance(row, dict) else row[0])
        for row in (cur.fetchall() or [])
    }


def _validate_manual_lead_ids(leads, manual_owners):
    lead_ids = {_positive_int((row or {}).get("id")) for row in (leads or [])}
    unknown = sorted(lead_id for lead_id in (manual_owners or {}) if lead_id not in lead_ids)
    if unknown:
        raise ValueError("manual ownership references unknown lead IDs: " + ", ".join(map(str, unknown)))


def collect_ownership(cur, manual_owners=None):
    manual_owners = manual_owners or {}
    columns = {table: _table_columns(cur, table) for table in TABLE_COLUMNS}
    lead_company_sql = "company_id" if "company_id" in columns["crm_leads"] else "NULL::INT"
    cur.execute(
        "SELECT id,project_id," + lead_company_sql + " AS stored_company_id "
        "FROM crm_leads ORDER BY id"
    )
    lead_rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    _validate_manual_lead_ids(lead_rows, manual_owners)
    cur.execute("SELECT id FROM companies ORDER BY id")
    companies = {
        _positive_int(row.get("id") if isinstance(row, dict) else row[0])
        for row in (cur.fetchall() or [])
    }
    cur.execute("SELECT id,company_id FROM projects ORDER BY id")
    projects = {
        _positive_int((row or {}).get("id")): dict(row or {})
        for row in (cur.fetchall() or [])
        if _positive_int((row or {}).get("id"))
    }
    leads = [classify_lead(row, projects, companies, manual_owners) for row in lead_rows]
    leads_by_id = {item["recordId"]: item for item in leads if item.get("recordId")}
    classified = list(leads)
    for table in ("crm_lead_documents", "crm_lead_tasks"):
        company_sql = "company_id" if "company_id" in columns[table] else "NULL::INT"
        project_sql = "project_id" if "project_id" in columns[table] else "NULL::INT"
        cur.execute(
            "SELECT id,lead_id,"
            + company_sql
            + " AS stored_company_id,"
            + project_sql
            + " AS stored_project_id FROM "
            + table
            + " ORDER BY id"
        )
        classified.extend(
            classify_child(table, dict(row or {}), leads_by_id)
            for row in (cur.fetchall() or [])
        )
    return columns, classified


def _plan_sha256(classified):
    plan = [
        [item["table"], item["recordId"], item["proposedCompanyId"], item["proposedProjectId"]]
        for item in (classified or [])
        if item.get("status") == "ready"
    ]
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_child_schema(cur, table, constraint_name):
    cur.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_"
        + table
        + "_company_lead ON "
        + table
        + "(company_id,lead_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_"
        + table
        + "_company_project ON "
        + table
        + "(company_id,project_id)"
    )
    cur.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='"
        + constraint_name
        + "') THEN ALTER TABLE "
        + table
        + " ADD CONSTRAINT "
        + constraint_name
        + " CHECK (project_id IS NULL OR company_id IS NOT NULL); END IF; END $$"
    )


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE companies IN SHARE MODE")
    cur.execute("LOCK TABLE projects IN SHARE MODE")
    cur.execute("LOCK TABLE crm_leads IN ACCESS EXCLUSIVE MODE")
    cur.execute("LOCK TABLE crm_lead_documents IN ACCESS EXCLUSIVE MODE")
    cur.execute("LOCK TABLE crm_lead_tasks IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_company ON crm_leads(company_id,id)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_company_project ON crm_leads(company_id,project_id)"
    )
    cur.execute(
        """DO $$ BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_crm_leads_owner') THEN
                   ALTER TABLE crm_leads ADD CONSTRAINT ck_crm_leads_owner
                   CHECK (project_id IS NULL OR company_id IS NOT NULL);
               END IF;
           END $$"""
    )
    _ensure_child_schema(cur, "crm_lead_documents", "ck_crm_lead_documents_owner")
    _ensure_child_schema(cur, "crm_lead_tasks", "ck_crm_lead_tasks_owner")


def _apply_leads(cur, ready):
    updated = 0
    for item in ready or []:
        cur.execute(
            "UPDATE crm_leads SET company_id=%s WHERE id=%s AND company_id IS NULL",
            (item["proposedCompanyId"], item["recordId"]),
        )
        updated += cur.rowcount
    return updated


def _apply_children(cur, table, alias, ready):
    selected = list(ready or [])
    if not selected:
        return 0
    cur.execute(
        "UPDATE "
        + table
        + " "
        + alias
        + " SET company_id=owners.company_id,project_id=owners.project_id "
        + "FROM UNNEST(%s::INT[],%s::INT[],%s::INT[]) AS owners(id,company_id,project_id) "
        + "WHERE "
        + alias
        + ".id=owners.id AND "
        + alias
        + ".company_id IS NULL AND "
        + alias
        + ".project_id IS NULL",
        (
            [item["recordId"] for item in selected],
            [item["proposedCompanyId"] for item in selected],
            [item["proposedProjectId"] for item in selected],
        ),
    )
    return cur.rowcount


def _base_result(report, mode, classified):
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": int(report["summary"]["ready"]),
        "reviewCount": sum(int(report["summary"][status]) for status in REVIEW_STATUSES),
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updatedLeads": 0,
        "updatedDocuments": 0,
        "updatedTasks": 0,
        "writeConflicts": 0,
        "rolledBack": mode == "dry-run",
        "complete": report["readyForStrictRuntime"],
    }


def run_migration(conn, manual_owners=None, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    manual_owners = manual_owners or {}
    if apply and (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(expected_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            columns, classified = collect_ownership(cur, manual_owners)
            result = _base_result(build_report(columns, classified), "dry-run", classified)
            conn.rollback()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    conn.set_session(
        readonly=False,
        autocommit=False,
        isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE,
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _ensure_schema(cur)
        columns, classified = collect_ownership(cur, manual_owners)
        report = build_report(columns, classified)
        result = _base_result(report, "apply", classified)
        if not report["readyForMigration"] or report["reportConsistent"] is not True:
            raise RuntimeError("Migration is blocked by review rows")
        if result["readyCount"] != expected_ready_count or result["planSha256"] != expected_sha:
            raise RuntimeError("Migration plan changed after schema lock; rerun dry-run")
        ready = [item for item in classified if item["status"] == "ready"]
        lead_rows = [item for item in ready if item["table"] == "crm_leads"]
        document_rows = [item for item in ready if item["table"] == "crm_lead_documents"]
        task_rows = [item for item in ready if item["table"] == "crm_lead_tasks"]
        result["writesAttempted"] = len(ready)
        result["updatedLeads"] = _apply_leads(cur, lead_rows)
        result["updatedDocuments"] = _apply_children(
            cur, "crm_lead_documents", "d", document_rows
        )
        result["updatedTasks"] = _apply_children(cur, "crm_lead_tasks", "t", task_rows)
        updated = result["updatedLeads"] + result["updatedDocuments"] + result["updatedTasks"]
        result["writeConflicts"] = len(ready) - updated
        post_columns, post_classified = collect_ownership(cur, manual_owners)
        post_report = build_report(post_columns, post_classified)
        if not post_report["readyForStrictRuntime"] or result["writeConflicts"]:
            raise RuntimeError("CRM ownership post-check failed")
        conn.commit()
        result["complete"] = True
        result["columns"] = post_report["columns"]
        result["postSummary"] = post_report["summary"]
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _manual_owner_map(values):
    owners = {}
    for value in values or []:
        owner = parse_lead_owner(value)
        lead_id = owner["leadId"]
        if lead_id in owners:
            raise ValueError("duplicate --lead-owner for lead " + str(lead_id))
        owners[lead_id] = owner
    return owners


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded CRM ownership migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg)
    parser.add_argument("--lead-owner", action="append", default=[])
    args = parser.parse_args(argv)
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error("--apply requires --confirm " + APPLY_CONFIRMATION)
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (args.expected_ready_count is not None or args.expected_plan_sha256 is not None):
        parser.error("expected guards are valid only with --apply")
    try:
        owners = _manual_owner_map(args.lead_owner)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    conn = get_db()
    try:
        result = run_migration(
            conn,
            manual_owners=owners,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
