"""Guarded company/project ownership migration for project AI summaries."""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.extensions


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_AI_SUMMARY_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEW_STATUSES = ("ambiguous", "unresolved", "mismatched")
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


def _summary_key(project_name):
    return "project:" + hashlib.sha1(str(project_name or "").encode("utf-8")).hexdigest()[:12]


def classify_summary(row, projects_by_name):
    item = dict(row or {})
    project_name = str(item.get("project_name") or "")
    candidates = projects_by_name.get(project_name, [])
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    status, reason = "ready", "unique_project_name"
    company_id = None
    project_id = None
    if not project_name.strip():
        status, reason = "unresolved", "project_name_missing"
    elif not candidates:
        status, reason = "unresolved", "project_not_found"
    elif len(candidates) > 1:
        status, reason = "ambiguous", "project_name_ambiguous"
    else:
        project = candidates[0]
        company_id = _positive_int(project.get("company_id"))
        project_id = _positive_int(project.get("id"))
        if not company_id or not project_id:
            status, reason = "unresolved", "project_owner_missing"
        elif bool(stored_company) != bool(stored_project):
            status, reason = "mismatched", "stored_owner_incomplete"
        elif stored_company and (stored_company != company_id or stored_project != project_id):
            status, reason = "mismatched", "stored_owner_mismatch"
        elif stored_company:
            status, reason = "stored", "stored_owner_verified"
    return {
        "summaryKey": _summary_key(project_name),
        "projectName": project_name,
        "storedCompanyId": stored_company,
        "storedProjectId": stored_project,
        "proposedCompanyId": company_id,
        "proposedProjectId": project_id,
        "status": status,
        "reason": reason,
    }


def build_report(columns, classified):
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] in REVIEW_STATUSES]
    ready = [item for item in classified if item["status"] == "ready"]
    return {
        "ok": True,
        "table": "project_ai_summary",
        "columns": {
            "companyId": "company_id" in columns,
            "projectId": "project_id" in columns,
        },
        "reportConsistent": len(classified) == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": not review and not ready,
        "summary": {
            "totalRows": len(classified),
            "storedRows": counts["stored"],
            "legacyRows": len(classified) - counts["stored"],
            "ready": counts["ready"],
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "backfillPreview": [
            {
                "summaryKey": item["summaryKey"],
                "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {
                "summaryKey": item["summaryKey"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def collect_ownership(cur):
    cur.execute(
        """SELECT column_name
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name='project_ai_summary'
              AND column_name IN ('company_id','project_id')"""
    )
    columns = {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"SELECT project_name,{company_sql} AS stored_company_id,{project_sql} AS stored_project_id "
        "FROM project_ai_summary ORDER BY project_name"
    )
    summaries = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,name,company_id FROM projects ORDER BY id")
    projects_by_name = defaultdict(list)
    for row in cur.fetchall() or []:
        project = dict(row)
        projects_by_name[str(project.get("name") or "")].append(project)
    return columns, [classify_summary(row, projects_by_name) for row in summaries]


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        company_id = item.get("proposedCompanyId")
        project_id = item.get("proposedProjectId")
        if not all(isinstance(value, int) and value > 0 for value in (company_id, project_id)):
            raise ValueError("Ready AI summary row is missing a positive company/project ID")
        plan.append([item.get("projectName"), company_id, project_id])
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '60s'")
    cur.execute("LOCK TABLE projects IN SHARE MODE")
    cur.execute("LOCK TABLE project_ai_summary IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE project_ai_summary ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE project_ai_summary ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_project_ai_summary_company_id ON project_ai_summary(company_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_project_ai_summary_project_id ON project_ai_summary(project_id)")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_ai_summary_company_project "
        "ON project_ai_summary(company_id,project_id) WHERE company_id IS NOT NULL AND project_id IS NOT NULL"
    )


def _apply_ready_rows(cur, ready_rows):
    updated = 0
    for item in ready_rows or ():
        company_id = item.get("proposedCompanyId")
        project_id = item.get("proposedProjectId")
        project_name = item.get("projectName")
        if not all(isinstance(value, int) and value > 0 for value in (company_id, project_id)):
            raise ValueError("Ready AI summary row is missing a positive company/project ID")
        cur.execute(
            """UPDATE project_ai_summary
                  SET company_id=%s,project_id=%s
                WHERE project_name=%s
                  AND company_id IS NULL
                  AND project_id IS NULL""",
            (company_id, project_id, project_name),
        )
        updated += cur.rowcount
    return updated


def _base_result(report, mode, classified):
    summary = report.get("summary") or {}
    review_count = sum(int(summary.get(status) or 0) for status in REVIEW_STATUSES)
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": int(summary.get("ready") or 0),
        "reviewCount": review_count,
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updated": 0,
        "writeConflicts": 0,
        "rolledBack": False,
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
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    conn.set_session(readonly=False, autocommit=False, isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _ensure_schema(cur)
        columns, classified = collect_ownership(cur)
        report = build_report(columns, classified)
        result = _base_result(report, "apply", classified)
        ready_rows = [item for item in classified if item.get("status") == "ready"]
        expected_total = int((report.get("summary") or {}).get("totalRows") or 0)
        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback()
            result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError(f"Expected {expected_ready_count} ready rows, found {result['readyCount']}; rerun dry-run")
        if result["planSha256"] != normalized_sha:
            raise RuntimeError(f"Expected plan SHA-256 {normalized_sha}, found {result['planSha256']}; rerun dry-run")
        updated = _apply_ready_rows(cur, ready_rows)
        conflicts = max(result["readyCount"] - updated, 0)
        result.update({"writesAttempted": result["readyCount"], "updated": updated, "writeConflicts": conflicts})
        if conflicts:
            conn.rollback()
            result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result
        post_columns, post_classified = collect_ownership(cur)
        post_report = build_report(post_columns, post_classified)
        result["postSummary"] = post_report["summary"]
        if (
            post_report.get("readyForStrictRuntime") is not True
            or int(post_report["summary"]["totalRows"]) != expected_total
        ):
            conn.rollback()
            result.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return result
        conn.commit()
        result.update({"columns": post_report["columns"], "complete": True})
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
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
    parser = argparse.ArgumentParser(description="Guarded ownership migration for project AI summaries")
    parser.add_argument("--dry-run", action="store_true", help="Only report mappings; this is the default")
    parser.add_argument("--apply", action="store_true", help="Add owner columns and backfill only revalidated rows")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {APPLY_CONFIRMATION}")
    parser.add_argument("--expected-ready-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from the immediately preceding dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from the immediately preceding dry-run")
    if not args.apply and (args.expected_ready_count is not None or args.expected_plan_sha256 is not None):
        parser.error("--expected-ready-count/--expected-plan-sha256 are only valid with --apply")
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
