"""Guarded cleanup for orphaned core-supply child rows."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extensions
import psycopg2.extras

from .orphan_report import (
    EXPECTED_SOURCE_COUNT,
    EXPECTED_SOURCE_SHA256,
    build_report_from_rows,
    load_orphan_rows,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_SUPPLY_ORPHAN_CLEANUP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRESERVED_LEGACY_OUTBOX_IDS = {30, 32, 34, 36, 38}
DELETE_TABLES = ("supplier_offers", "supply_request_recipients")


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


def _plan_sha256(delete_rows):
    plan = sorted(
        [
            [
                "delete",
                str(item.get("table") or ""),
                _positive_int(item.get("recordId")),
                _positive_int(item.get("companyId")),
                _positive_int(item.get("requestId")),
            ]
            for item in (delete_rows or [])
        ],
        key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")),
    )
    payload = json.dumps(plan, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_cleanup_plan(rows):
    diagnostic = build_report_from_rows(
        rows,
        expected_source_count=EXPECTED_SOURCE_COUNT,
        expected_source_sha256=EXPECTED_SOURCE_SHA256,
    )
    delete_rows = [
        {
            "table": item["table"],
            "recordId": item["recordId"],
            "companyId": item["companyId"],
            "requestId": item["requestId"],
        }
        for item in diagnostic["orphanRows"]
    ]
    blocking_by_table = {}
    legacy_outbox_ids = set()
    unexpected_outbox_ids = set()
    for item in diagnostic["orphanRows"]:
        for reference in item["references"]:
            record_ids = {_positive_int(value) for value in reference["recordIds"]}
            record_ids.discard(None)
            if reference["table"] == "messenger_outbox":
                legacy_outbox_ids.update(record_ids & PRESERVED_LEGACY_OUTBOX_IDS)
                unexpected_outbox_ids.update(record_ids - PRESERVED_LEGACY_OUTBOX_IDS)
            else:
                blocking_by_table.setdefault(reference["table"], set()).update(record_ids)

    blockers = []
    if not diagnostic["sourceSetMatchesExpected"]:
        blockers.append("source_set_changed")
    if not diagnostic["reportConsistent"]:
        blockers.append("report_inconsistent")
    if diagnostic["summary"]["ownerMismatchLinks"]:
        blockers.append("owner_mismatch_detected")
    if blocking_by_table:
        blockers.append("business_references_detected")
    if unexpected_outbox_ids:
        blockers.append("unexpected_messenger_reference")
    if legacy_outbox_ids != PRESERVED_LEGACY_OUTBOX_IDS:
        blockers.append("legacy_outbox_set_changed")
    legacy_outbox_states = {
        _positive_int(row.get("id")): (
            str(row.get("owner_scope") or "").strip().lower(),
            str(row.get("status") or "").strip().lower(),
        )
        for row in (rows.get("messenger_outbox") or [])
        if _positive_int(row.get("id")) in PRESERVED_LEGACY_OUTBOX_IDS
    }
    if any(
        legacy_outbox_states.get(record_id, (None, None))[0] != "legacy"
        or legacy_outbox_states.get(record_id, (None, None))[1] not in {"failed", "skipped"}
        for record_id in PRESERVED_LEGACY_OUTBOX_IDS
    ):
        blockers.append("legacy_outbox_state_changed")

    delete_by_table = {
        table: sum(item["table"] == table for item in delete_rows)
        for table in DELETE_TABLES
    }
    return {
        "ok": True,
        "sourceCount": diagnostic["sourceCount"],
        "sourceSha256": diagnostic["sourceSha256"],
        "sourceSetMatchesExpected": diagnostic["sourceSetMatchesExpected"],
        "readyForCleanup": not blockers,
        "blockers": blockers,
        "deleteCount": len(delete_rows),
        "deleteByTable": delete_by_table,
        "planSha256": _plan_sha256(delete_rows),
        "deleteRows": delete_rows,
        "preservedLegacyOutboxIds": sorted(legacy_outbox_ids),
        "legacyOutboxStateVerified": "legacy_outbox_state_changed" not in blockers,
        "blockingReferences": [
            {"table": table, "recordIds": sorted(record_ids)}
            for table, record_ids in sorted(blocking_by_table.items())
        ],
        "unexpectedMessengerReferenceIds": sorted(unexpected_outbox_ids),
    }


def collect_cleanup_plan(cur):
    return build_cleanup_plan(load_orphan_rows(cur))


def _lock_tables(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute(
        "LOCK TABLE supply_requests, supply_request_recipients, supplier_offers, "
        "supplier_offer_events, supplier_invoices, supply_deliveries, supply_claims, "
        "supply_history, warehouse_invoices, messenger_outbox IN SHARE ROW EXCLUSIVE MODE"
    )


def _delete_planned_rows(cur, delete_rows):
    deleted = {}
    for table in DELETE_TABLES:
        selected = [item for item in delete_rows if item["table"] == table]
        if not selected:
            deleted[table] = 0
            continue
        cur.execute(
            f"""DELETE FROM {table} child
                  USING UNNEST(%s::INT[],%s::INT[],%s::INT[])
                        AS plan(id,company_id,request_id)
                 WHERE child.id=plan.id
                   AND child.company_id=plan.company_id
                   AND child.request_id=plan.request_id
                   AND NOT EXISTS (
                       SELECT 1 FROM supply_requests parent WHERE parent.id=child.request_id
                   )""",
            (
                [item["recordId"] for item in selected],
                [item["companyId"] for item in selected],
                [item["requestId"] for item in selected],
            ),
        )
        deleted[table] = int(cur.rowcount or 0)
    return deleted


def _postcheck(cur, delete_rows):
    remaining = 0
    for table in DELETE_TABLES:
        ids = [item["recordId"] for item in delete_rows if item["table"] == table]
        cur.execute(f"SELECT id FROM {table} WHERE id=ANY(%s) ORDER BY id", (ids,))
        remaining += len(cur.fetchall() or [])
    cur.execute(
        "SELECT id FROM messenger_outbox WHERE id=ANY(%s) ORDER BY id",
        (sorted(PRESERVED_LEGACY_OUTBOX_IDS),),
    )
    preserved = sorted(
        _positive_int(dict(row or {}).get("id"))
        for row in (cur.fetchall() or [])
        if _positive_int(dict(row or {}).get("id"))
    )
    return {
        "remainingPlannedRows": remaining,
        "preservedLegacyOutboxIds": preserved,
    }


def _base_result(plan, mode):
    return {
        **plan,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "writesAttempted": 0,
        "deleted": 0,
        "deletedByTable": {table: 0 for table in DELETE_TABLES},
        "rolledBack": False,
        "complete": False,
    }


def run_remediation(
    conn,
    apply=False,
    expected_delete_count=None,
    expected_plan_sha256=None,
):
    if apply and (
        isinstance(expected_delete_count, bool)
        or not isinstance(expected_delete_count, int)
        or expected_delete_count < 0
    ):
        raise ValueError("Apply requires a non-negative expected_delete_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = _base_result(collect_cleanup_plan(cur), "dry-run")
            conn.rollback()
            result["rolledBack"] = True
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
        _lock_tables(cur)
        plan = collect_cleanup_plan(cur)
        result = _base_result(plan, "apply")
        if not plan["readyForCleanup"]:
            conn.rollback()
            result.update({"ok": False, "failureReason": "cleanup_blocked", "rolledBack": True})
            return result
        if plan["deleteCount"] != expected_delete_count:
            raise RuntimeError(
                f"Expected {expected_delete_count} delete rows, found {plan['deleteCount']}; rerun dry-run"
            )
        if plan["planSha256"] != normalized_sha:
            raise RuntimeError(
                f"Expected plan SHA-256 {normalized_sha}, found {plan['planSha256']}; rerun dry-run"
            )

        deleted_by_table = _delete_planned_rows(cur, plan["deleteRows"])
        deleted = sum(deleted_by_table.values())
        result.update({
            "writesAttempted": plan["deleteCount"],
            "deleted": deleted,
            "deletedByTable": deleted_by_table,
        })
        if deleted != plan["deleteCount"]:
            conn.rollback()
            result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result

        postcheck = _postcheck(cur, plan["deleteRows"])
        result["postcheck"] = postcheck
        result["preservedLegacyOutboxIds"] = postcheck["preservedLegacyOutboxIds"]
        if (
            postcheck["remainingPlannedRows"]
            or set(postcheck["preservedLegacyOutboxIds"]) != PRESERVED_LEGACY_OUTBOX_IDS
        ):
            conn.rollback()
            result.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return result
        conn.commit()
        result["complete"] = True
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
    parser = argparse.ArgumentParser(description="Guarded cleanup for orphaned core-supply rows")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-delete-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_delete_count is None:
        parser.error("--apply requires --expected-delete-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (
        args.expected_delete_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("expected guards are valid only with --apply")

    conn = psycopg2.connect(**_db_config())
    try:
        result = run_remediation(
            conn,
            apply=args.apply,
            expected_delete_count=args.expected_delete_count,
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
