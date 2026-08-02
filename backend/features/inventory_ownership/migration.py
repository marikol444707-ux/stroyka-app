"""Guarded tenant-ownership migration for tools and inventory tables."""

import argparse
import hashlib
import json
import re
import psycopg2.extensions
import psycopg2.extras

from .ownership_report import TABLES, _positive_int, _tool_owner_map, build_report_from_rows, load_ownership_rows


APPLY_CONFIRMATION = "APPLY_INVENTORY_OWNERSHIP"
OWNER_COLUMNS = ("owner_scope", "company_id", "project_id")
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _table_columns(cur, table):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name=%s AND column_name IN ('owner_scope','company_id','project_id')",
        (table,),
    )
    return {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}


def _schema_state(cur):
    columns = {table: _table_columns(cur, table) for table in TABLES}
    return {
        table: {column: column in columns[table] for column in OWNER_COLUMNS}
        for table in TABLES
    }


def _plan_sha256(classified):
    plan = []
    for item in classified:
        if item.get("status") != "verified" or not item.get("reason", "").startswith("explicit_"):
            continue
        table = item.get("table")
        record_id = _positive_int(item.get("recordId"))
        scope = item.get("ownerScope")
        company_id = _positive_int(item.get("companyId"))
        project_id = _positive_int(item.get("projectId")) or 0
        if table != "tools" or not record_id or scope != "company" or not company_id or project_id:
            raise ValueError("Manual tool ownership plan is invalid")
        plan.append([table, record_id, scope, company_id, project_id])
    return hashlib.sha256(json.dumps(sorted(plan), separators=(",", ":")).encode("utf-8")).hexdigest()


def _base_result(schema, report, classified, mode):
    counts = report["summary"]
    ready = [item for item in classified if item.get("status") == "verified" and item.get("reason", "").startswith("explicit_")]
    stored_rows = sum(
        1 for item in classified if item.get("reason", "").startswith("stored_") and item.get("status") == "verified"
    )
    review = [item for item in classified if item.get("status") != "verified"]
    return {
        "ok": True,
        "tables": list(TABLES),
        "columns": schema,
        "reportConsistent": report["reportConsistent"],
        "readyForMigration": not review,
        "readyForStrictRuntime": all(all(values.values()) for values in schema.values()) and not review and not ready,
        "summary": {
            "totalRows": counts["totalRows"], "storedRows": stored_rows,
            "legacyRows": counts["totalRows"] - stored_rows, "ready": len(ready),
            "unresolved": counts["unresolved"], "ambiguous": counts["ambiguous"], "mismatched": counts["mismatched"],
        },
        "backfillPreview": [
            {"table": item["table"], "recordId": item["recordId"], "ownerScope": item["ownerScope"],
             "companyId": item["companyId"], "projectId": item["projectId"], "reason": item["reason"]}
            for item in ready[:100]
        ],
        "needsReview": report["needsReview"],
        "previewTruncated": report["previewTruncated"],
        "reviewListTruncated": report["reviewListTruncated"],
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": len(ready),
        "reviewCount": len(review),
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updatedTools": 0,
        "writeConflicts": 0,
        "rolledBack": mode == "dry-run",
        "complete": False,
    }


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE companies IN SHARE MODE")
    for table in TABLES:
        cur.execute("LOCK TABLE " + table + " IN ACCESS EXCLUSIVE MODE")
    for table in TABLES:
        cur.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS owner_scope TEXT")
        cur.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS company_id INT")
        cur.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS project_id INT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_" + table + "_owner ON " + table + "(owner_scope,company_id,project_id)")
        cur.execute(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_" + table + "_owner') "
            "THEN ALTER TABLE " + table + " ADD CONSTRAINT ck_" + table + "_owner CHECK "
            "((owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR "
            "(owner_scope='company' AND company_id IS NOT NULL AND project_id IS NULL) OR "
            "(owner_scope='project' AND company_id IS NOT NULL AND project_id IS NOT NULL)); END IF; END $$"
        )


def _apply_tools(cur, ready):
    if not ready:
        return 0
    cur.execute(
        "UPDATE tools AS t SET owner_scope=owners.owner_scope,company_id=owners.company_id,project_id=NULL "
        "FROM UNNEST(%s::INT[],%s::TEXT[],%s::INT[]) AS owners(id,owner_scope,company_id) "
        "WHERE t.id=owners.id AND t.owner_scope IS NULL AND t.company_id IS NULL AND t.project_id IS NULL",
        ([item["recordId"] for item in ready], [item["ownerScope"] for item in ready], [item["companyId"] for item in ready]),
    )
    return cur.rowcount


def run_migration(conn, manual_tool_owners=None, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    owners = manual_tool_owners or {}
    if apply and (not isinstance(expected_ready_count, int) or expected_ready_count < 0):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(expected_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    if apply:
        conn.set_session(
            readonly=False, autocommit=False,
            isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE,
        )
    else:
        conn.set_session(readonly=True, autocommit=False)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if apply:
            _ensure_schema(cur)
        schema = _schema_state(cur)
        # This migration deliberately accepts only explicitly approved company-owned tools.
        # A truncated report must be split before it can be applied.
        rows = load_ownership_rows(cur)
        full_report = build_report_from_rows(rows, owners)
        if full_report["previewTruncated"] or full_report["reviewListTruncated"]:
            raise RuntimeError("Inventory ownership report is truncated; split the migration before applying")
        classified = full_report["verifiedPreview"] + full_report["needsReview"]
        result = _base_result(schema, full_report, classified, "apply" if apply else "dry-run")
        if not apply:
            conn.rollback()
            return result
        if not result["readyForMigration"] or not result["reportConsistent"]:
            raise RuntimeError("Migration is blocked by review rows")
        if result["readyCount"] != expected_ready_count or result["planSha256"] != expected_sha:
            raise RuntimeError("Migration plan changed after schema lock; rerun dry-run")
        ready = [item for item in classified if item.get("status") == "verified" and item.get("reason", "").startswith("explicit_")]
        result["writesAttempted"] = len(ready)
        result["updatedTools"] = _apply_tools(cur, ready)
        result["writeConflicts"] = len(ready) - result["updatedTools"]
        post_report = build_report_from_rows(load_ownership_rows(cur), owners)
        post_schema = _schema_state(cur)
        post_rows = post_report["verifiedPreview"] + post_report["needsReview"]
        post_result = _base_result(post_schema, post_report, post_rows, "apply")
        if not post_result["readyForStrictRuntime"] or result["writeConflicts"]:
            raise RuntimeError("Inventory ownership post-check failed")
        conn.commit()
        result["columns"] = post_schema
        result["postSummary"] = post_result["summary"]
        result["complete"] = True
        result["rolledBack"] = False
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded inventory ownership migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg)
    parser.add_argument("--tool-owner", action="append", default=[])
    args = parser.parse_args(argv)
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error("--apply requires --confirm " + APPLY_CONFIRMATION)
    if args.apply and (args.expected_ready_count is None or args.expected_plan_sha256 is None):
        parser.error("--apply requires exact dry-run count and SHA")
    try:
        owners = _tool_owner_map(args.tool_owner)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    conn = get_db()
    try:
        result = run_migration(conn, owners, args.apply, args.expected_ready_count, args.expected_plan_sha256)
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
