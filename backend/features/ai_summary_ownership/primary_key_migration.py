"""Guarded primary-key cutover for tenant-owned project AI summaries."""

import argparse
import hashlib
import json
import os
import re
import sys

import psycopg2
import psycopg2.extras
import psycopg2.extensions

from .migration import ENV_PATH, build_report, collect_ownership


APPLY_CONFIRMATION = "APPLY_AI_SUMMARY_PRIMARY_KEY"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEGACY_PRIMARY_KEY = ["project_name"]
TENANT_PRIMARY_KEY = ["company_id", "project_id"]


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


def _primary_key(cur):
    cur.execute(
        """SELECT tc.constraint_name,kcu.column_name,kcu.ordinal_position
             FROM information_schema.table_constraints tc
             JOIN information_schema.key_column_usage kcu
               ON kcu.constraint_schema=tc.constraint_schema
              AND kcu.constraint_name=tc.constraint_name
              AND kcu.table_name=tc.table_name
            WHERE tc.table_schema='public'
              AND tc.table_name='project_ai_summary'
              AND tc.constraint_type='PRIMARY KEY'
            ORDER BY kcu.ordinal_position"""
    )
    rows = [dict(row) for row in (cur.fetchall() or [])]
    names = {str(row.get("constraint_name") or "") for row in rows}
    return {
        "constraintName": next(iter(names)) if len(names) == 1 else "",
        "columns": [str(row.get("column_name") or "") for row in rows],
    }


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "stored":
            continue
        plan.append([
            item.get("projectName"),
            item.get("storedCompanyId"),
            item.get("storedProjectId"),
        ])
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _duplicate_owner_count(cur):
    cur.execute(
        """SELECT COUNT(*) AS duplicate_groups
             FROM (
                 SELECT company_id,project_id
                   FROM project_ai_summary
                  WHERE company_id IS NOT NULL AND project_id IS NOT NULL
                  GROUP BY company_id,project_id
                 HAVING COUNT(*)>1
             ) duplicates"""
    )
    row = cur.fetchone()
    if isinstance(row, dict):
        return int(row.get("duplicate_groups") or 0)
    return int(row[0] or 0) if row else 0


def build_cutover_report(cur):
    columns, classified = collect_ownership(cur)
    ownership = build_report(columns, classified)
    primary_key = _primary_key(cur)
    duplicate_groups = _duplicate_owner_count(cur)
    summary = ownership.get("summary") or {}
    total_rows = int(summary.get("totalRows") or 0)
    strict_owner = ownership.get("readyForStrictRuntime") is True
    legacy_pk = primary_key["constraintName"] == "project_ai_summary_pkey" and primary_key["columns"] == LEGACY_PRIMARY_KEY
    tenant_pk = primary_key["constraintName"] == "project_ai_summary_pkey" and primary_key["columns"] == TENANT_PRIMARY_KEY
    return {
        "ok": True,
        "table": "project_ai_summary",
        "columns": ownership.get("columns"),
        "totalRows": total_rows,
        "storedRows": int(summary.get("storedRows") or 0),
        "legacyRows": int(summary.get("legacyRows") or 0),
        "ownershipReady": strict_owner,
        "primaryKey": primary_key,
        "duplicateOwnerGroups": duplicate_groups,
        "legacyPrimaryKey": legacy_pk,
        "tenantPrimaryKey": tenant_pk,
        "readyForCutover": strict_owner and legacy_pk and duplicate_groups == 0,
        "complete": strict_owner and tenant_pk and duplicate_groups == 0,
        "planSha256": _plan_sha256(classified),
    }


def _apply_cutover(cur):
    cur.execute("ALTER TABLE project_ai_summary ALTER COLUMN company_id SET NOT NULL")
    cur.execute("ALTER TABLE project_ai_summary ALTER COLUMN project_id SET NOT NULL")
    cur.execute("ALTER TABLE project_ai_summary DROP CONSTRAINT project_ai_summary_pkey")
    cur.execute(
        "ALTER TABLE project_ai_summary ADD CONSTRAINT project_ai_summary_pkey "
        "PRIMARY KEY (company_id,project_id)"
    )


def run_migration(conn, apply=False, expected_row_count=None, expected_plan_sha256=None):
    if apply and (isinstance(expected_row_count, bool) or not isinstance(expected_row_count, int) or expected_row_count < 0):
        raise ValueError("Apply requires a non-negative expected_row_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_cutover_report(cur)
            result.update({"mode": "dry-run", "dryRun": True, "schemaWritesAttempted": 0, "rolledBack": True})
            conn.rollback()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    conn.set_session(readonly=False, autocommit=False, isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SET LOCAL lock_timeout = '5s'")
        cur.execute("SET LOCAL statement_timeout = '60s'")
        cur.execute("LOCK TABLE projects IN SHARE MODE")
        cur.execute("LOCK TABLE project_ai_summary IN ACCESS EXCLUSIVE MODE")
        before = build_cutover_report(cur)
        before.update({"mode": "apply", "dryRun": False, "schemaWritesAttempted": 0, "rolledBack": False})
        if before["complete"]:
            if before["totalRows"] != expected_row_count or before["planSha256"] != normalized_sha:
                raise RuntimeError("Completed cutover does not match expected row count or plan SHA-256")
            conn.commit()
            return before
        if not before["readyForCutover"]:
            conn.rollback()
            before.update({"ok": False, "failureReason": "not_ready", "rolledBack": True})
            return before
        if before["totalRows"] != expected_row_count:
            raise RuntimeError(f"Expected {expected_row_count} rows, found {before['totalRows']}; rerun dry-run")
        if before["planSha256"] != normalized_sha:
            raise RuntimeError(f"Expected plan SHA-256 {normalized_sha}, found {before['planSha256']}; rerun dry-run")
        _apply_cutover(cur)
        after = build_cutover_report(cur)
        if not after["complete"] or after["totalRows"] != expected_row_count or after["planSha256"] != normalized_sha:
            conn.rollback()
            before.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return before
        conn.commit()
        return {
            **after,
            "mode": "apply",
            "dryRun": False,
            "schemaWritesAttempted": 1,
            "rolledBack": False,
        }
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
    parser = argparse.ArgumentParser(description="Guarded primary-key cutover for project AI summaries")
    parser.add_argument("--dry-run", action="store_true", help="Only report cutover readiness; this is the default")
    parser.add_argument("--apply", action="store_true", help="Replace legacy project_name primary key")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {APPLY_CONFIRMATION}")
    parser.add_argument("--expected-row-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_row_count is None:
        parser.error("--apply requires --expected-row-count from the immediately preceding dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from the immediately preceding dry-run")
    if not args.apply and (args.expected_row_count is not None or args.expected_plan_sha256 is not None):
        parser.error("--expected-row-count/--expected-plan-sha256 are only valid with --apply")
    conn = psycopg2.connect(**_db_config())
    try:
        result = run_migration(conn, args.apply, args.expected_row_count, args.expected_plan_sha256)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
