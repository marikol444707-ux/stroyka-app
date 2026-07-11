"""Guarded ownership migration for legacy unexpected works."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.extensions

from backend.features.estimate_changes.ownership_report import (
    build_estimate_change_report_from_classified,
    collect_estimate_change_ownership,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_ESTIMATE_CHANGES"
REVIEW_STATUSES = ("ambiguous", "unresolved", "mismatched")
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


def _load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config():
    env = _load_env()

    def value(name, default):
        return os.getenv(name) or env.get(name) or default

    return {
        "dbname": value("DB_NAME", "stroyka"),
        "user": value("DB_USER", "stroyka"),
        "password": value("DB_PASSWORD", "password123"),
        "host": value("DB_HOST", "localhost"),
        "port": value("DB_PORT", "5432"),
    }


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '60s'")
    cur.execute("LOCK TABLE projects IN SHARE MODE")
    cur.execute("LOCK TABLE estimates IN SHARE MODE")
    cur.execute("LOCK TABLE unexpected_works IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute("ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_unexpected_works_project_id "
        "ON unexpected_works(project_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_unexpected_works_company_id "
        "ON unexpected_works(company_id)"
    )


def _apply_ready_rows(cur, ready_rows):
    updated = 0
    for item in ready_rows or ():
        project_id = item.get("proposedProjectId")
        company_id = item.get("proposedCompanyId")
        change_id = item.get("changeId")
        if not all(isinstance(value, int) and value > 0 for value in (project_id, company_id, change_id)):
            raise ValueError("Ready ownership row is missing a positive change/project/company ID")
        cur.execute(
            """UPDATE unexpected_works
                  SET project_id=%s,
                      company_id=%s
                WHERE id=%s
                  AND project_id IS NULL
                  AND company_id IS NULL""",
            (project_id, company_id, change_id),
        )
        updated += cur.rowcount
    return updated


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        identity = (
            item.get("changeId"),
            item.get("proposedCompanyId"),
            item.get("proposedProjectId"),
        )
        if not all(isinstance(value, int) and value > 0 for value in identity):
            raise ValueError("Ready ownership row is missing a positive change/company/project ID")
        plan.append([identity[0], identity[1], identity[2], str(item.get("source") or "")])
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base_result(report, mode, plan_sha256):
    summary = report.get("summary") or {}
    review_count = sum(int(summary.get(status) or 0) for status in REVIEW_STATUSES)
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": int(summary.get("ready") or 0),
        "reviewCount": review_count,
        "planSha256": plan_sha256,
        "writesAttempted": 0,
        "attemptedUpdated": 0,
        "updated": 0,
        "writeConflicts": 0,
        "rolledBack": False,
        "complete": False,
    }


def _is_complete(report, expected_total):
    summary = report.get("summary") or {}
    review_count = sum(int(summary.get(status) or 0) for status in REVIEW_STATUSES)
    return (
        report.get("reportConsistent") is True
        and int(summary.get("totalRows") or 0) == expected_total
        and int(summary.get("storedRows") or 0) == expected_total
        and int(summary.get("legacyRows") or 0) == 0
        and int(summary.get("ready") or 0) == 0
        and review_count == 0
    )


def run_migration(conn, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    if apply and (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    if apply and not PLAN_SHA256_RE.fullmatch(str(expected_plan_sha256 or "").strip().lower()):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    normalized_expected_plan = str(expected_plan_sha256 or "").strip().lower()

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            columns, classified = collect_estimate_change_ownership(cur)
            report = build_estimate_change_report_from_classified(columns, classified)
            result = _base_result(report, "dry-run", _plan_sha256(classified))
            conn.rollback()
            result["rolledBack"] = True
            result["complete"] = (
                report.get("reportConsistent") is True
                and result["reviewCount"] == 0
                and int((report.get("summary") or {}).get("legacyRows") or 0) == 0
                and result["readyCount"] == 0
            )
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
        columns, classified = collect_estimate_change_ownership(cur)
        report = build_estimate_change_report_from_classified(columns, classified)
        current_plan_sha256 = _plan_sha256(classified)
        result = _base_result(report, "apply", current_plan_sha256)
        ready_rows = [item for item in classified if item.get("status") == "ready"]
        expected_total = int((report.get("summary") or {}).get("totalRows") or 0)

        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback()
            result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError(
                f"Expected {expected_ready_count} ready rows, found {result['readyCount']}; rerun dry-run"
            )
        if current_plan_sha256 != normalized_expected_plan:
            raise RuntimeError(
                f"Expected plan SHA-256 {normalized_expected_plan}, found {current_plan_sha256}; rerun dry-run"
            )

        attempted_updated = _apply_ready_rows(cur, ready_rows)
        write_conflicts = max(result["readyCount"] - attempted_updated, 0)
        result.update({
            "writesAttempted": result["readyCount"],
            "attemptedUpdated": attempted_updated,
            "writeConflicts": write_conflicts,
        })
        if write_conflicts:
            conn.rollback()
            result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result

        post_columns, post_classified = collect_estimate_change_ownership(cur)
        post_report = build_estimate_change_report_from_classified(post_columns, post_classified)
        result["postSummary"] = post_report["summary"]
        if not _is_complete(post_report, expected_total):
            conn.rollback()
            result.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return result

        conn.commit()
        result.update({
            "columns": post_report["columns"],
            "updated": attempted_updated,
            "complete": True,
        })
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Dry-run/backfill stored tenant ownership for legacy unexpected works"
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report mappings; this is the default")
    parser.add_argument("--apply", action="store_true", help="Write only revalidated ownership mappings")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {APPLY_CONFIRMATION}")
    parser.add_argument(
        "--expected-ready-count",
        type=_non_negative_int,
        default=None,
        help="Required for --apply; must equal the immediately preceding dry-run readyCount",
    )
    parser.add_argument(
        "--expected-plan-sha256",
        type=_sha256_arg,
        default=None,
        help="Required for --apply; must equal the immediately preceding dry-run planSha256",
    )
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
        result = run_migration(
            conn,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
