"""Guarded explicit owner-scope migration for AI tasks."""

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

from backend.features.ai_ownership.ownership_report import _project_index, classify_task, resolve_project


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_AI_TASKS_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEW_STATUSES = ("unresolved", "mismatched")
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


def classify_stored_task(row, projects, findings):
    item = dict(row or {})
    base = classify_task(item, projects, findings)
    task_id = _positive_int(item.get("id"))
    stored_scope = str(item.get("stored_scope") or "").strip() or None
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    proposed_scope = "platform" if base.get("scope") == "system" else "company"
    proposed_company = _positive_int(base.get("companyId")) if proposed_scope == "company" else None
    proposed_project = _positive_int(base.get("projectId")) if proposed_scope == "company" else None

    if base.get("status") != "verified":
        status, reason = base.get("status"), base.get("reason")
    elif not stored_scope and not stored_company and not stored_project:
        status, reason = "ready", base.get("reason")
    elif not stored_scope:
        status, reason = "mismatched", "stored_scope_missing"
    elif stored_scope not in ("company", "platform"):
        status, reason = "mismatched", "stored_scope_invalid"
    elif proposed_scope == "platform":
        if stored_scope != "platform":
            status, reason = "mismatched", "platform_scope_mismatch"
        elif stored_company or stored_project:
            status, reason = "mismatched", "platform_owner_contains_tenant_ids"
        else:
            status, reason = "stored", "stored_owner_verified"
    elif stored_scope != "company":
        status, reason = "mismatched", "company_scope_mismatch"
    elif not stored_company or not stored_project:
        status, reason = "mismatched", "company_owner_incomplete"
    elif stored_company != proposed_company or stored_project != proposed_project:
        status, reason = "mismatched", "stored_owner_mismatch"
    else:
        status, reason = "stored", "stored_owner_verified"
    return {
        "taskId": task_id,
        "storedScope": stored_scope,
        "storedCompanyId": stored_company,
        "storedProjectId": stored_project,
        "proposedScope": proposed_scope,
        "proposedCompanyId": proposed_company,
        "proposedProjectId": proposed_project,
        "status": status,
        "reason": reason,
    }


def build_report(columns, classified):
    counts = Counter(item["status"] for item in classified)
    ready = [item for item in classified if item["status"] == "ready"]
    review = [item for item in classified if item["status"] in REVIEW_STATUSES]
    scope_counts = Counter(item["proposedScope"] for item in ready)
    return {
        "ok": True,
        "table": "ai_tasks",
        "columns": {
            "ownerScope": "owner_scope" in columns,
            "companyId": "company_id" in columns,
            "projectId": "project_id" in columns,
        },
        "reportConsistent": len(classified) == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": not review and not ready,
        "summary": {
            "totalRows": len(classified), "storedRows": counts["stored"],
            "legacyRows": len(classified) - counts["stored"], "ready": counts["ready"],
            "unresolved": counts["unresolved"], "mismatched": counts["mismatched"],
        },
        "readyByScope": dict(sorted(scope_counts.items())),
        "backfillPreview": [
            {
                "taskId": item["taskId"], "ownerScope": item["proposedScope"],
                "companyId": item["proposedCompanyId"], "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {"taskId": item["taskId"], "status": item["status"], "reason": item["reason"]}
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def collect_ownership(cur):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='ai_tasks' AND column_name IN ('owner_scope','company_id','project_id')"
    )
    columns = {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}
    scope_sql = "owner_scope" if "owner_scope" in columns else "NULL::TEXT"
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"SELECT id,finding_id,project_name,{scope_sql} AS stored_scope,"
        f"{company_sql} AS stored_company_id,{project_sql} AS stored_project_id FROM ai_tasks ORDER BY id"
    )
    tasks = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,name,company_id FROM projects ORDER BY id")
    project_rows = [dict(row) for row in (cur.fetchall() or [])]
    projects = _project_index(project_rows)
    cur.execute("SELECT id,company_id,project_id,project_name FROM ai_findings ORDER BY id")
    findings = {}
    for row in (cur.fetchall() or []):
        item = dict(row)
        owner = resolve_project(item.get("project_name"), projects)
        finding_id = _positive_int(item.get("id"))
        if (
            owner.get("status") == "verified" and owner.get("scope") == "tenant"
            and _positive_int(item.get("company_id")) == _positive_int(owner.get("companyId"))
            and _positive_int(item.get("project_id")) == _positive_int(owner.get("projectId"))
        ):
            findings[finding_id] = {**owner, "status": "verified"}
        else:
            findings[finding_id] = {"status": "unresolved", "reason": "finding_stored_owner_not_verified"}
    return columns, [classify_stored_task(row, projects, findings) for row in tasks]


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        task_id = item.get("taskId")
        scope = item.get("proposedScope")
        company_id = item.get("proposedCompanyId") or 0
        project_id = item.get("proposedProjectId") or 0
        if not isinstance(task_id, int) or task_id <= 0 or scope not in ("company", "platform"):
            raise ValueError("Ready task contains an invalid owner")
        if scope == "company" and (company_id <= 0 or project_id <= 0):
            raise ValueError("Company task is missing owner IDs")
        if scope == "platform" and (company_id or project_id):
            raise ValueError("Platform task contains tenant IDs")
        plan.append([task_id, scope, company_id, project_id])
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE projects IN SHARE MODE")
    cur.execute("LOCK TABLE ai_findings IN SHARE MODE")
    cur.execute("LOCK TABLE ai_tasks IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS owner_scope TEXT")
    cur.execute("ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_tasks_company_id ON ai_tasks(company_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_tasks_project_id ON ai_tasks(project_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_tasks_owner_status ON ai_tasks(owner_scope,company_id,project_id,status)")
    cur.execute(
        """DO $$ BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_ai_tasks_owner_scope') THEN
                   ALTER TABLE ai_tasks ADD CONSTRAINT ck_ai_tasks_owner_scope CHECK (
                       owner_scope IS NULL OR
                       (owner_scope='company' AND company_id IS NOT NULL AND project_id IS NOT NULL) OR
                       (owner_scope='platform' AND company_id IS NULL AND project_id IS NULL)
                   );
               END IF;
           END $$"""
    )


def _apply_ready_rows(cur, ready_rows):
    rows = list(ready_rows or [])
    if not rows:
        return 0
    cur.execute(
        """UPDATE ai_tasks t
              SET owner_scope=owners.owner_scope,company_id=owners.company_id,project_id=owners.project_id
             FROM UNNEST(%s::INT[],%s::TEXT[],%s::INT[],%s::INT[])
                  AS owners(id,owner_scope,company_id,project_id)
            WHERE t.id=owners.id AND t.owner_scope IS NULL AND t.company_id IS NULL AND t.project_id IS NULL""",
        (
            [item["taskId"] for item in rows], [item["proposedScope"] for item in rows],
            [item["proposedCompanyId"] for item in rows], [item["proposedProjectId"] for item in rows],
        ),
    )
    return cur.rowcount


def _base_result(report, mode, classified):
    summary = report["summary"]
    return {
        **report, "mode": mode, "dryRun": mode == "dry-run",
        "readyCount": int(summary.get("ready") or 0),
        "reviewCount": sum(int(summary.get(status) or 0) for status in REVIEW_STATUSES),
        "planSha256": _plan_sha256(classified), "writesAttempted": 0, "updated": 0,
        "writeConflicts": 0, "rolledBack": False,
        "complete": report.get("readyForStrictRuntime") is True,
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
            columns, classified = collect_ownership(cur)
            result = _base_result(build_report(columns, classified), "dry-run", classified)
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
        columns, classified = collect_ownership(cur)
        report = build_report(columns, classified)
        result = _base_result(report, "apply", classified)
        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback(); result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError(f"Expected {expected_ready_count} ready rows, found {result['readyCount']}; rerun dry-run")
        if result["planSha256"] != normalized_sha:
            raise RuntimeError(f"Expected plan SHA-256 {normalized_sha}, found {result['planSha256']}; rerun dry-run")
        updated = _apply_ready_rows(cur, [item for item in classified if item["status"] == "ready"])
        conflicts = max(result["readyCount"] - updated, 0)
        result.update({"writesAttempted": result["readyCount"], "updated": updated, "writeConflicts": conflicts})
        if conflicts:
            conn.rollback(); result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result
        post_columns, post_classified = collect_ownership(cur)
        post_report = build_report(post_columns, post_classified)
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
    parser = argparse.ArgumentParser(description="Guarded ownership migration for AI tasks")
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
