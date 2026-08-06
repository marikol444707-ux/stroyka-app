"""Guarded E3.4.2b runner for the strict brigade lineage schema."""

import argparse
import json
import re
import sys

import psycopg2.extensions
import psycopg2.extras

from . import (
    constraint_audit,
    delete_policy_audit,
    readiness_report,
    writer_audit,
)
from .strict_schema import (
    build_strict_migration_report,
    execute_strict_plan,
)


APPLY_CONFIRMATION = "APPLY_BRIGADE_LINEAGE_STRICT_SCHEMA"
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
        raise argparse.ArgumentTypeError(
            "must be a 64-character SHA-256 hex digest"
        )
    return normalized


def collect_strict_reports(cur):
    return (
        constraint_audit.audit_brigade_lineage_constraints(cur),
        writer_audit.audit_brigade_contract_item_writers(),
        delete_policy_audit.audit_estimate_delete_policy(),
        readiness_report.build_readiness_report(cur),
    )


def _validate_apply_guards(expected_change_count, expected_plan_sha256):
    if (
        isinstance(expected_change_count, bool)
        or not isinstance(expected_change_count, int)
        or expected_change_count < 0
    ):
        raise ValueError("apply requires a non-negative expected_change_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("apply requires a valid expected_plan_sha256")
    return normalized_sha


def _set_apply_guards(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute(
        """LOCK TABLE public.estimates,public.estimate_versions,
                          public.brigade_contracts,public.brigade_contract_items
             IN ACCESS EXCLUSIVE MODE"""
    )


def run_strict_migration(
    conn,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    if not apply:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_strict_migration_report(*collect_strict_reports(cur))
            conn.rollback()
            result.update({
                "mode": "dry-run",
                "dryRun": True,
                "schemaWritesAttempted": 0,
                "rolledBack": True,
            })
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    normalized_sha = _validate_apply_guards(
        expected_change_count, expected_plan_sha256
    )
    conn.set_session(
        readonly=False,
        autocommit=False,
        isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE,
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    schema_writes = 0
    try:
        _set_apply_guards(cur)
        before = build_strict_migration_report(*collect_strict_reports(cur))
        if before["changeCount"] != expected_change_count:
            raise RuntimeError("strict migration change count changed; rerun dry-run")
        if before["planSha256"] != normalized_sha:
            raise RuntimeError("strict migration plan changed; rerun dry-run")
        if not before["ok"]:
            conn.rollback()
            return {
                **before,
                "ok": False,
                "mode": "apply",
                "dryRun": False,
                "failureReason": "not_ready",
                "schemaWritesAttempted": 0,
                "rolledBack": True,
            }
        if before["complete"]:
            conn.commit()
            return {
                **before,
                "mode": "apply",
                "dryRun": False,
                "schemaWritesAttempted": 0,
                "rolledBack": False,
            }
        if not before["readyForApply"]:
            conn.rollback()
            return {
                **before,
                "ok": False,
                "mode": "apply",
                "dryRun": False,
                "failureReason": "not_ready",
                "schemaWritesAttempted": 0,
                "rolledBack": True,
            }

        schema_writes = execute_strict_plan(cur, before["plannedChanges"])
        after = build_strict_migration_report(*collect_strict_reports(cur))
        if not after["complete"]:
            conn.rollback()
            return {
                **before,
                "ok": False,
                "mode": "apply",
                "dryRun": False,
                "failureReason": "postcheck_failed",
                "schemaWritesAttempted": schema_writes,
                "rolledBack": True,
                "postSummary": after["summary"],
                "postBlockers": after["blockers"],
            }
        conn.commit()
        return {
            **after,
            "mode": "apply",
            "dryRun": False,
            "changeCount": before["changeCount"],
            "planSha256": before["planSha256"],
            "postPlanSha256": after["planSha256"],
            "expectedPlanSha256": normalized_sha,
            "schemaWritesAttempted": schema_writes,
            "rolledBack": False,
            "preSummary": before["summary"],
            "postSummary": after["summary"],
            "rollbackSql": before["rollbackSql"],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _connect():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    return get_db()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarded E3.4.2b strict brigade lineage migration"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--expected-change-count", type=_non_negative_int, default=None
    )
    parser.add_argument(
        "--expected-plan-sha256", type=_sha256_arg, default=None
    )
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_change_count is None:
        parser.error("--apply requires --expected-change-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (
        args.expected_change_count is not None
        or args.expected_plan_sha256 is not None
    ):
        parser.error("expected guards are valid only with --apply")

    conn = None
    try:
        conn = _connect()
        result = run_strict_migration(
            conn,
            apply=args.apply,
            expected_change_count=args.expected_change_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
