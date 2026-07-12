"""Guarded tenant ownership migration for AI findings."""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.extensions

from backend.features.ai_ownership.ownership_report import (
    _entity_index,
    _project_index,
    classify_finding,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_AI_FINDINGS_OWNERSHIP"
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


def classify_stored_finding(row, projects, entities):
    item = dict(row or {})
    base = classify_finding(item, projects, entities)
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    if base["status"] != "verified":
        status, reason = base["status"], base["reason"]
    elif bool(stored_company) != bool(stored_project):
        status, reason = "mismatched", "stored_owner_incomplete"
    elif stored_company and (
        stored_company != _positive_int(base.get("companyId"))
        or stored_project != _positive_int(base.get("projectId"))
    ):
        status, reason = "mismatched", "stored_owner_mismatch"
    elif stored_company:
        status, reason = "stored", "stored_owner_verified"
    else:
        status, reason = "ready", base["reason"]
    return {
        "findingId": _positive_int(item.get("id")),
        "storedCompanyId": stored_company,
        "storedProjectId": stored_project,
        "proposedCompanyId": _positive_int(base.get("companyId")),
        "proposedProjectId": _positive_int(base.get("projectId")),
        "status": status,
        "reason": reason,
    }


def build_report(columns, classified):
    counts = Counter(item["status"] for item in classified)
    ready = [item for item in classified if item["status"] == "ready"]
    review = [item for item in classified if item["status"] in REVIEW_STATUSES]
    ready_by_company = Counter(str(item["proposedCompanyId"]) for item in ready if item.get("proposedCompanyId"))
    return {
        "ok": True,
        "table": "ai_findings",
        "columns": {"companyId": "company_id" in columns, "projectId": "project_id" in columns},
        "reportConsistent": len(classified) == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": not review and not ready,
        "summary": {
            "totalRows": len(classified),
            "storedRows": counts["stored"],
            "legacyRows": len(classified) - counts["stored"],
            "ready": counts["ready"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "backfillPreview": [
            {
                "findingId": item["findingId"],
                "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {"findingId": item["findingId"], "status": item["status"], "reason": item["reason"]}
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def collect_ownership(cur):
    cur.execute(
        """SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ai_findings'
              AND column_name IN ('company_id','project_id')"""
    )
    columns = {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"""SELECT id,project_name,linked_entity_type,linked_entity_id,
                   {company_sql} AS stored_company_id,{project_sql} AS stored_project_id
              FROM ai_findings ORDER BY id"""
    )
    findings = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,name,company_id FROM projects ORDER BY id")
    projects = _project_index(cur.fetchall() or [])
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
    entities = _entity_index(cur.fetchall() or [])
    return columns, [classify_stored_finding(row, projects, entities) for row in findings]


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        identity = (item.get("findingId"), item.get("proposedCompanyId"), item.get("proposedProjectId"))
        if not all(isinstance(value, int) and value > 0 for value in identity):
            raise ValueError("Ready finding is missing a positive finding/company/project ID")
        plan.append(list(identity))
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    for table in ("projects", "rooms", "room_windows", "room_doors", "work_journal", "material_norm_suggestions"):
        cur.execute(f"LOCK TABLE {table} IN SHARE MODE")
    cur.execute("LOCK TABLE ai_findings IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE ai_findings ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE ai_findings ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_findings_company_id ON ai_findings(company_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_findings_project_id ON ai_findings(project_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_findings_owner_status ON ai_findings(company_id,project_id,status)")


def _apply_ready_rows(cur, ready_rows):
    rows = list(ready_rows or [])
    if not rows:
        return 0
    ids = [item["findingId"] for item in rows]
    company_ids = [item["proposedCompanyId"] for item in rows]
    project_ids = [item["proposedProjectId"] for item in rows]
    if not all(isinstance(value, int) and value > 0 for value in (*ids, *company_ids, *project_ids)):
        raise ValueError("Ready finding batch contains an invalid owner ID")
    cur.execute(
        """UPDATE ai_findings f
              SET company_id=owners.company_id,
                  project_id=owners.project_id
             FROM UNNEST(%s::INT[],%s::INT[],%s::INT[])
                  AS owners(id,company_id,project_id)
            WHERE f.id=owners.id
              AND f.company_id IS NULL
              AND f.project_id IS NULL""",
        (ids, company_ids, project_ids),
    )
    return cur.rowcount


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
        expected_total = int(report["summary"]["totalRows"])
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
        if post_report.get("readyForStrictRuntime") is not True or int(post_report["summary"]["totalRows"]) != expected_total:
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
    parser = argparse.ArgumentParser(description="Guarded ownership migration for AI findings")
    parser.add_argument("--dry-run", action="store_true", help="Only report mappings; this is the default")
    parser.add_argument("--apply", action="store_true", help="Add owner columns and backfill revalidated findings")
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
