import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_COMPANY_MESSAGES"


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _company_ids(value):
    if isinstance(value, (list, tuple, set)):
        source = value
    elif isinstance(value, str):
        source = value.strip("{}").split(",") if value.strip("{}") else []
    else:
        source = []
    return sorted({company_id for item in source for company_id in [_positive_int(item)] if company_id})


def _non_negative_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return result


def classify_legacy_message(row):
    item = dict(row or {})
    message_id = _positive_int(item.get("message_id"))
    author_id = _positive_int(item.get("author_id"))
    result = {
        "messageId": message_id,
        "authorId": author_id,
        "status": "needs_review",
        "companyId": None,
        "reason": "",
    }
    if not message_id:
        result["reason"] = "message_missing"
        return result
    if not author_id:
        result["reason"] = "author_missing"
        return result
    if not _positive_int(item.get("user_id")):
        result["reason"] = "author_not_found"
        return result
    user_company_id = _positive_int(item.get("user_company_id"))
    if not user_company_id:
        result["reason"] = "author_company_missing"
        return result
    linked_companies = set(_company_ids(item.get("membership_company_ids")))
    linked_companies.add(user_company_id)
    if len(linked_companies) != 1:
        result["reason"] = "multiple_company_links"
        return result
    result.update({
        "status": "ready",
        "companyId": user_company_id,
        "reason": "single_company",
    })
    return result


def plan_legacy_message_migration(rows):
    ready_by_company = defaultdict(list)
    needs_review = []
    for row in rows or ():
        decision = classify_legacy_message(row)
        if decision["status"] == "ready":
            ready_by_company[decision["companyId"]].append(decision["messageId"])
        else:
            needs_review.append(decision)
    normalized_ready = {
        company_id: sorted(message_id for message_id in message_ids if message_id)
        for company_id, message_ids in sorted(ready_by_company.items())
    }
    return {
        "readyByCompany": normalized_ready,
        "readyCount": sum(len(message_ids) for message_ids in normalized_ready.values()),
        "reviewCount": len(needs_review),
        "needsReview": needs_review,
    }


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


def _messages_have_company_id(cur):
    cur.execute(
        """SELECT EXISTS (
               SELECT 1
                 FROM information_schema.columns
                WHERE table_schema=current_schema()
                  AND table_name='messages'
                  AND column_name='company_id'
           ) AS exists"""
    )
    row = cur.fetchone() or {}
    return bool(row.get("exists") if isinstance(row, dict) else row[0])


def _load_legacy_rows(cur, has_company_id=True):
    if not has_company_id:
        raise RuntimeError("messages.company_id is missing; deploy M6.4a before running M6.4c")
    cur.execute(
        """SELECT m.id AS message_id,
                   m.author_id,
                   u.id AS user_id,
                   u.company_id AS user_company_id,
                   COALESCE(
                       ARRAY_AGG(DISTINCT membership.company_id)
                           FILTER (WHERE membership.company_id IS NOT NULL),
                       ARRAY[]::INT[]
                   ) AS membership_company_ids
              FROM messages m
              LEFT JOIN users u ON u.id=m.author_id
              LEFT JOIN user_company_roles membership ON membership.user_id=u.id
             WHERE m.company_id IS NULL
               AND m.chat_type='company'
             GROUP BY m.id,m.author_id,u.id,u.company_id
             ORDER BY m.id"""
    )
    return list(cur.fetchall())


def _apply_ready_rows(cur, ready_by_company):
    updated = 0
    for company_id, message_ids in sorted((ready_by_company or {}).items()):
        if not message_ids:
            continue
        cur.execute(
            """UPDATE messages AS m
                  SET company_id=%s
                WHERE m.id=ANY(%s)
                  AND m.company_id IS NULL
                  AND m.chat_type='company'
                  AND EXISTS (
                      SELECT 1
                        FROM users u
                       WHERE u.id=m.author_id
                         AND u.company_id=%s
                         AND NOT EXISTS (
                             SELECT 1
                               FROM user_company_roles membership
                              WHERE membership.user_id=u.id
                                AND membership.company_id<>%s
                         )
                  )""",
            (company_id, message_ids, company_id, company_id),
        )
        updated += cur.rowcount
    return updated


def run_migration(conn, apply=False, expected_ready_count=None):
    if apply and (isinstance(expected_ready_count, bool) or not isinstance(expected_ready_count, int) or expected_ready_count < 0):
        raise ValueError("Apply requires a non-negative expected_ready_count")

    conn.set_session(readonly=not apply, autocommit=False)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        has_company_id = _messages_have_company_id(cur)
        if not has_company_id:
            raise RuntimeError("messages.company_id is missing; deploy M6.4a before running M6.4c")
        rows = _load_legacy_rows(cur, has_company_id)
        plan = plan_legacy_message_migration(rows)
        result = {
            "ok": True,
            "mode": "apply" if apply else "dry-run",
            "dryRun": not apply,
            "columnExists": True,
            "legacyRows": len(rows),
            "readyCount": plan["readyCount"],
            "reviewCount": plan["reviewCount"],
            "readyByCompany": plan["readyByCompany"],
            "needsReview": plan["needsReview"][:50],
            "reviewListTruncated": len(plan["needsReview"]) > 50,
            "writesAttempted": 0,
            "attemptedUpdated": 0,
            "updated": 0,
            "writeConflicts": 0,
            "rolledBack": False,
            "complete": False,
        }
        if not apply:
            conn.rollback()
            result["rolledBack"] = True
            result["complete"] = plan["reviewCount"] == 0 and plan["readyCount"] == 0
            return result

        if plan["reviewCount"]:
            conn.rollback()
            result.update({
                "ok": False,
                "failureReason": "needs_review",
                "rolledBack": True,
            })
            return result
        if plan["readyCount"] != expected_ready_count:
            raise RuntimeError(
                f"Expected {expected_ready_count} ready rows, found {plan['readyCount']}; rerun dry-run"
            )

        attempted_updated = _apply_ready_rows(cur, plan["readyByCompany"])
        write_conflicts = max(plan["readyCount"] - attempted_updated, 0)
        result.update({
            "writesAttempted": plan["readyCount"],
            "attemptedUpdated": attempted_updated,
            "writeConflicts": write_conflicts,
        })
        if write_conflicts:
            conn.rollback()
            result.update({
                "ok": False,
                "failureReason": "write_conflict",
                "rolledBack": True,
            })
            return result

        conn.commit()
        result.update({
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
    parser = argparse.ArgumentParser(description="Dry-run/backfill company ownership for legacy chat messages")
    parser.add_argument("--dry-run", action="store_true", help="Only report mappings; this is the default")
    parser.add_argument("--apply", action="store_true", help="Write only unambiguous company_id mappings")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {APPLY_CONFIRMATION}")
    parser.add_argument(
        "--expected-ready-count",
        type=_non_negative_int,
        default=None,
        help="Required for --apply; must equal the immediately preceding dry-run readyCount",
    )
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from the immediately preceding dry-run")
    if not args.apply and args.expected_ready_count is not None:
        parser.error("--expected-ready-count is only valid with --apply")
    conn = psycopg2.connect(**_db_config())
    try:
        result = run_migration(
            conn,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
