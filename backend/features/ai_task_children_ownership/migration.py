"""Guarded owner-scope migration for AI task reports and attachments."""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extensions
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_AI_TASK_CHILDREN_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEW_STATUSES = ("unresolved", "mismatched")
OWNER_COLUMNS = {"owner_scope", "company_id", "project_id"}
PREVIEW_LIMIT = 100


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


def _task_owner(row):
    item = dict(row or {})
    task_id = _positive_int(item.get("id") or item.get("taskId"))
    scope = str(item.get("owner_scope") or item.get("scope") or "").strip()
    company_id = _positive_int(item.get("company_id") or item.get("companyId"))
    project_id = _positive_int(item.get("project_id") or item.get("projectId"))
    valid_company = scope == "company" and company_id and project_id
    valid_platform = scope == "platform" and not company_id and not project_id
    return {
        "taskId": task_id,
        "scope": scope,
        "companyId": company_id,
        "projectId": project_id,
        "status": "verified" if task_id and (valid_company or valid_platform) else "unresolved",
    }


def _owner_tuple(item):
    return (item.get("proposedScope") or item.get("scope"), item.get("proposedCompanyId") or item.get("companyId"), item.get("proposedProjectId") or item.get("projectId"))


def _classify_stored(row, proposed):
    item = dict(row or {})
    stored_scope = str(item.get("stored_scope") or "").strip() or None
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    proposed_scope, proposed_company, proposed_project = _owner_tuple(proposed)
    if not stored_scope and not stored_company and not stored_project:
        return "ready", proposed.get("reason") or "verified_parent"
    if stored_scope not in ("company", "platform"):
        return "mismatched", "stored_scope_invalid"
    if stored_scope == "platform":
        if stored_company or stored_project:
            return "mismatched", "platform_owner_contains_tenant_ids"
    elif not stored_company or not stored_project:
        return "mismatched", "company_owner_incomplete"
    if (stored_scope, stored_company, stored_project) != (proposed_scope, proposed_company, proposed_project):
        return "mismatched", "stored_owner_mismatch"
    return "stored", "stored_owner_verified"


def classify_report(row, tasks):
    item = dict(row or {})
    report_id = _positive_int(item.get("id"))
    task_id = _positive_int(item.get("task_id"))
    parent = tasks.get(task_id)
    if not report_id:
        status, reason, parent = "unresolved", "report_id_invalid", None
    elif not task_id or not parent:
        status, reason, parent = "unresolved", "task_not_found", None
    elif parent.get("status") != "verified":
        status, reason = "unresolved", "task_owner_not_verified"
    else:
        proposed = {
            "scope": parent.get("scope"), "companyId": parent.get("companyId"),
            "projectId": parent.get("projectId"), "reason": "verified_task_parent",
        }
        status, reason = _classify_stored(item, proposed)
    return {
        "table": "ai_task_reports", "recordId": report_id, "taskId": task_id,
        "proposedScope": parent.get("scope") if parent else None,
        "proposedCompanyId": parent.get("companyId") if parent else None,
        "proposedProjectId": parent.get("projectId") if parent else None,
        "status": status, "reason": reason,
    }


def classify_attachment(row, reports, tasks):
    item = dict(row or {})
    attachment_id = _positive_int(item.get("id"))
    report_id = _positive_int(item.get("report_id"))
    task_id = _positive_int(item.get("task_id"))
    report = reports.get(report_id)
    parent = tasks.get(task_id)
    if not attachment_id:
        status, reason, parent = "unresolved", "attachment_id_invalid", None
    elif not report_id or not report:
        status, reason, parent = "unresolved", "report_not_found", None
    elif not task_id or not parent:
        status, reason, parent = "unresolved", "task_not_found", None
    elif report.get("status") not in ("ready", "stored"):
        status, reason = "unresolved", "report_owner_not_verified"
    elif parent.get("status") != "verified":
        status, reason = "unresolved", "task_owner_not_verified"
    elif report.get("taskId") != task_id:
        status, reason = "mismatched", "report_task_mismatch"
    elif _owner_tuple(report) != _owner_tuple(parent):
        status, reason = "mismatched", "report_task_owner_mismatch"
    else:
        proposed = {
            "scope": parent.get("scope"), "companyId": parent.get("companyId"),
            "projectId": parent.get("projectId"), "reason": "verified_report_and_task_parents",
        }
        status, reason = _classify_stored(item, proposed)
    return {
        "table": "ai_task_attachments", "recordId": attachment_id,
        "taskId": task_id, "reportId": report_id,
        "proposedScope": parent.get("scope") if parent else None,
        "proposedCompanyId": parent.get("companyId") if parent else None,
        "proposedProjectId": parent.get("projectId") if parent else None,
        "status": status, "reason": reason,
    }


def build_report(report_columns, attachment_columns, classified):
    rows = list(classified or [])
    counts = Counter(item["status"] for item in rows)
    ready = [item for item in rows if item["status"] == "ready"]
    review = [item for item in rows if item["status"] in REVIEW_STATUSES]
    table_counts = Counter(item["table"] for item in ready)
    totals = Counter(item["table"] for item in rows)
    stored = Counter(item["table"] for item in rows if item["status"] == "stored")
    columns_ready = OWNER_COLUMNS.issubset(report_columns) and OWNER_COLUMNS.issubset(attachment_columns)
    return {
        "ok": True,
        "tables": ["ai_task_reports", "ai_task_attachments"],
        "columns": {
            "aiTaskReports": {key: key in report_columns for key in sorted(OWNER_COLUMNS)},
            "aiTaskAttachments": {key: key in attachment_columns for key in sorted(OWNER_COLUMNS)},
        },
        "reportConsistent": len(rows) == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": columns_ready and not review and not ready,
        "summary": {
            "totalRows": len(rows), "storedRows": counts["stored"],
            "legacyRows": len(rows) - counts["stored"], "ready": counts["ready"],
            "unresolved": counts["unresolved"], "mismatched": counts["mismatched"],
        },
        "byTable": {
            table: {"totalRows": totals[table], "storedRows": stored[table], "ready": table_counts[table]}
            for table in ("ai_task_reports", "ai_task_attachments")
        },
        "readyByTable": dict(sorted(table_counts.items())),
        "backfillPreview": [
            {
                "table": item["table"], "recordId": item["recordId"],
                "ownerScope": item["proposedScope"], "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"], "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {"table": item["table"], "recordId": item["recordId"], "status": item["status"], "reason": item["reason"]}
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def _table_columns(cur, table):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name=%s AND column_name IN ('owner_scope','company_id','project_id')",
        (table,),
    )
    return {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}


def _child_rows(cur, table, columns, extra_columns):
    scope_sql = "owner_scope" if "owner_scope" in columns else "NULL::TEXT"
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"SELECT id,{extra_columns},{scope_sql} AS stored_scope,{company_sql} AS stored_company_id,"
        f"{project_sql} AS stored_project_id FROM {table} ORDER BY id"
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def collect_ownership(cur):
    report_columns = _table_columns(cur, "ai_task_reports")
    attachment_columns = _table_columns(cur, "ai_task_attachments")
    cur.execute("SELECT id,owner_scope,company_id,project_id FROM ai_tasks ORDER BY id")
    tasks = {_positive_int(row.get("id")): _task_owner(row) for row in (cur.fetchall() or [])}
    report_rows = _child_rows(cur, "ai_task_reports", report_columns, "task_id")
    reports = [classify_report(row, tasks) for row in report_rows]
    reports_by_id = {item["recordId"]: item for item in reports if item.get("recordId")}
    attachment_rows = _child_rows(cur, "ai_task_attachments", attachment_columns, "report_id,task_id")
    attachments = [classify_attachment(row, reports_by_id, tasks) for row in attachment_rows]
    return report_columns, attachment_columns, reports + attachments


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        table = item.get("table")
        record_id = item.get("recordId")
        scope = item.get("proposedScope")
        company_id = item.get("proposedCompanyId") or 0
        project_id = item.get("proposedProjectId") or 0
        if table not in ("ai_task_reports", "ai_task_attachments") or not isinstance(record_id, int) or record_id <= 0:
            raise ValueError("Ready child contains an invalid identity")
        if scope not in ("company", "platform"):
            raise ValueError("Ready child contains an invalid owner scope")
        if scope == "company" and (company_id <= 0 or project_id <= 0):
            raise ValueError("Company child is missing owner IDs")
        if scope == "platform" and (company_id or project_id):
            raise ValueError("Platform child contains tenant IDs")
        plan.append([table, record_id, scope, company_id, project_id])
    return hashlib.sha256(json.dumps(sorted(plan), separators=(",", ":")).encode("utf-8")).hexdigest()


def _ensure_table_schema(cur, table, constraint, owner_index):
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner_scope TEXT")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute(f"CREATE INDEX IF NOT EXISTS {owner_index} ON {table}(owner_scope,company_id,project_id)")
    cur.execute(
        f"""DO $$ BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='{constraint}') THEN
                   ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK (
                       (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                       (owner_scope='company' AND company_id IS NOT NULL AND project_id IS NOT NULL) OR
                       (owner_scope='platform' AND company_id IS NULL AND project_id IS NULL)
                   );
               END IF;
           END $$"""
    )


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE ai_tasks IN SHARE MODE")
    cur.execute("LOCK TABLE ai_task_reports IN ACCESS EXCLUSIVE MODE")
    cur.execute("LOCK TABLE ai_task_attachments IN ACCESS EXCLUSIVE MODE")
    _ensure_table_schema(cur, "ai_task_reports", "ck_ai_task_reports_owner_scope", "idx_ai_task_reports_owner")
    _ensure_table_schema(cur, "ai_task_attachments", "ck_ai_task_attachments_owner_scope", "idx_ai_task_attachments_owner")


def _apply_rows(cur, table, alias, rows):
    selected = list(rows or [])
    if not selected:
        return 0
    cur.execute(
        f"""UPDATE {table} {alias}
              SET owner_scope=owners.owner_scope,company_id=owners.company_id,project_id=owners.project_id
             FROM UNNEST(%s::INT[],%s::TEXT[],%s::INT[],%s::INT[])
                  AS owners(id,owner_scope,company_id,project_id)
            WHERE {alias}.id=owners.id AND {alias}.owner_scope IS NULL
              AND {alias}.company_id IS NULL AND {alias}.project_id IS NULL""",
        (
            [item["recordId"] for item in selected], [item["proposedScope"] for item in selected],
            [item["proposedCompanyId"] for item in selected], [item["proposedProjectId"] for item in selected],
        ),
    )
    return cur.rowcount


def _base_result(report, mode, classified):
    summary = report["summary"]
    return {
        **report, "mode": mode, "dryRun": mode == "dry-run",
        "readyCount": int(summary.get("ready") or 0),
        "reviewCount": sum(int(summary.get(status) or 0) for status in REVIEW_STATUSES),
        "planSha256": _plan_sha256(classified), "writesAttempted": 0,
        "updatedReports": 0, "updatedAttachments": 0, "writeConflicts": 0,
        "rolledBack": False, "complete": report.get("readyForStrictRuntime") is True,
    }


def run_migration(conn, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    if apply and (isinstance(expected_ready_count, bool) or not isinstance(expected_ready_count, int) or expected_ready_count < 0):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            report_columns, attachment_columns, classified = collect_ownership(cur)
            result = _base_result(build_report(report_columns, attachment_columns, classified), "dry-run", classified)
            conn.rollback(); result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close()

    conn.set_session(readonly=False, autocommit=False, isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _ensure_schema(cur)
        report_columns, attachment_columns, classified = collect_ownership(cur)
        report = build_report(report_columns, attachment_columns, classified)
        result = _base_result(report, "apply", classified)
        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback(); result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError(f"Expected {expected_ready_count} ready rows, found {result['readyCount']}; rerun dry-run")
        if result["planSha256"] != normalized_sha:
            raise RuntimeError(f"Expected plan SHA-256 {normalized_sha}, found {result['planSha256']}; rerun dry-run")
        ready = [item for item in classified if item["status"] == "ready"]
        updated_reports = _apply_rows(cur, "ai_task_reports", "r", [item for item in ready if item["table"] == "ai_task_reports"])
        updated_attachments = _apply_rows(cur, "ai_task_attachments", "a", [item for item in ready if item["table"] == "ai_task_attachments"])
        updated = updated_reports + updated_attachments
        conflicts = max(result["readyCount"] - updated, 0)
        result.update({
            "writesAttempted": result["readyCount"], "updatedReports": updated_reports,
            "updatedAttachments": updated_attachments, "writeConflicts": conflicts,
        })
        if conflicts:
            conn.rollback(); result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result
        post_report_columns, post_attachment_columns, post_classified = collect_ownership(cur)
        post_report = build_report(post_report_columns, post_attachment_columns, post_classified)
        result["postSummary"] = post_report["summary"]
        if post_report.get("readyForStrictRuntime") is not True or post_report["summary"]["totalRows"] != report["summary"]["totalRows"]:
            conn.rollback(); result.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return result
        conn.commit(); result.update({"columns": post_report["columns"], "complete": True})
        return result
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close()


def _load_env():
    values = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config():
    env = _load_env()
    return {
        "dbname": os.getenv("DB_NAME") or env.get("DB_NAME") or "stroyka",
        "user": os.getenv("DB_USER") or env.get("DB_USER") or "stroyka",
        "password": os.getenv("DB_PASSWORD") or env.get("DB_PASSWORD") or "password123",
        "host": os.getenv("DB_HOST") or env.get("DB_HOST") or "localhost",
        "port": os.getenv("DB_PORT") or env.get("DB_PORT") or "5432",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded ownership migration for AI task children")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (args.expected_ready_count is not None or args.expected_plan_sha256 is not None):
        parser.error("expected guards are valid only with --apply")
    conn = psycopg2.connect(**_db_config())
    try:
        result = run_migration(conn, args.apply, args.expected_ready_count, args.expected_plan_sha256)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
