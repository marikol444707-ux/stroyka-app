"""Guarded M7 migration for the verified work-journal tenant index."""

import argparse
import hashlib
import json
import os
import re
import sys

import psycopg2
import psycopg2.extensions
import psycopg2.extras

from .report import ENV_PATH


APPLY_CONFIRMATION = "APPLY_TENANT_READINESS_INDEXES"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INDEX_NAME = "idx_work_journal_company_project"
TARGET = {
    "resource": "work_journal",
    "indexName": INDEX_NAME,
    "columns": ("company_id", "project"),
    "createSql": (
        "CREATE INDEX IF NOT EXISTS idx_work_journal_company_project "
        "ON work_journal(company_id,project)"
    ),
    "rollbackSql": "DROP INDEX IF EXISTS idx_work_journal_company_project;",
}


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


def _index_columns(index_definition):
    match = re.search(r"\(([^()]*)\)", str(index_definition or ""))
    if not match:
        return ()
    columns = []
    for expression in match.group(1).split(","):
        normalized = expression.strip().strip('"').lower()
        columns.append(normalized.split()[0] if normalized else "")
    return tuple(columns)


def _target_index(indexes):
    required = TARGET["columns"]
    for raw in indexes or []:
        item = dict(raw or {})
        definition = str(item.get("definition") or "")
        if re.search(r"\sWHERE\s", definition, flags=re.IGNORECASE):
            continue
        columns = _index_columns(definition)
        if columns[:len(required)] == required:
            return str(item.get("name") or "")
    return ""


def _plan_sha256(missing):
    plan = [
        [
            item["resource"],
            item["indexName"],
            list(item["columns"]),
            int(item.get("rows") or 0),
        ]
        for item in missing or []
    ]
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_index_report(table_facts):
    fact = dict((table_facts or {}).get(TARGET["resource"]) or {})
    columns = set(fact.get("columns") or set())
    missing_columns = sorted(set(TARGET["columns"]) - columns)
    blockers = []
    if not fact.get("exists"):
        blockers.append({"resource": TARGET["resource"], "reason": "table_missing"})
    elif missing_columns:
        blockers.append({
            "resource": TARGET["resource"],
            "reason": "columns_missing",
            "columns": missing_columns,
        })
    matching_index = _target_index(fact.get("indexes") or [])
    missing = []
    if not blockers and not matching_index:
        missing.append({
            "resource": TARGET["resource"],
            "indexName": TARGET["indexName"],
            "columns": list(TARGET["columns"]),
            "rows": int(fact.get("totalRows") or 0),
        })
    complete = not blockers and not missing
    return {
        "ok": True,
        "table": TARGET["resource"],
        "reportConsistent": len(blockers) <= 1,
        "readyForApply": not blockers and bool(missing),
        "complete": complete,
        "summary": {
            "targetIndexes": 1,
            "missingIndexes": len(missing),
            "blockers": len(blockers),
            "tableRows": int(fact.get("totalRows") or 0),
        },
        "missingCount": len(missing),
        "planSha256": _plan_sha256(missing),
        "matchingIndex": matching_index or None,
        "missingIndexes": missing,
        "blockers": blockers,
        "rollbackSql": [TARGET["rollbackSql"]] if missing else [],
    }


def collect_index_facts(cur):
    cur.execute(
        """SELECT column_name
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name='work_journal'
            ORDER BY ordinal_position"""
    )
    columns = {str(dict(row or {}).get("column_name") or "") for row in (cur.fetchall() or [])}
    exists = bool(columns)
    cur.execute(
        """SELECT indexname,indexdef
             FROM pg_indexes
            WHERE schemaname='public' AND tablename='work_journal'
            ORDER BY indexname"""
    )
    indexes = [
        {
            "name": str(dict(row or {}).get("indexname") or ""),
            "definition": str(dict(row or {}).get("indexdef") or ""),
        }
        for row in (cur.fetchall() or [])
    ]
    rows = 0
    if exists:
        cur.execute("SELECT COUNT(*) AS total_rows FROM work_journal")
        row = cur.fetchone()
        rows = int(dict(row or {}).get("total_rows") or 0)
    return {
        TARGET["resource"]: {
            "exists": exists,
            "columns": columns,
            "indexes": indexes,
            "totalRows": rows,
        }
    }


def run_index_migration(
    conn,
    apply=False,
    expected_missing_count=None,
    expected_plan_sha256=None,
):
    if apply and (
        isinstance(expected_missing_count, bool)
        or not isinstance(expected_missing_count, int)
        or expected_missing_count < 0
    ):
        raise ValueError("apply requires a non-negative expected_missing_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("apply requires a valid expected_plan_sha256")

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_index_report(collect_index_facts(cur))
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

    conn.set_session(
        readonly=False,
        autocommit=False,
        isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE,
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SET LOCAL lock_timeout = '5s'")
        cur.execute("SET LOCAL statement_timeout = '60s'")
        before = build_index_report(collect_index_facts(cur))
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
        if before["missingCount"] != expected_missing_count:
            raise RuntimeError("index count changed; rerun dry-run")
        if before["planSha256"] != normalized_sha:
            raise RuntimeError("index plan changed; rerun dry-run")
        cur.execute(TARGET["createSql"])
        after = build_index_report(collect_index_facts(cur))
        if not after["complete"]:
            conn.rollback()
            return {
                **before,
                "ok": False,
                "mode": "apply",
                "dryRun": False,
                "failureReason": "postcheck_failed",
                "schemaWritesAttempted": 1,
                "rolledBack": True,
            }
        conn.commit()
        return {
            **after,
            "mode": "apply",
            "dryRun": False,
            "expectedPlanSha256": before["planSha256"],
            "schemaWritesAttempted": 1,
            "rolledBack": False,
            "postSummary": after["summary"],
            "rollbackSql": [TARGET["rollbackSql"]],
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
    parser = argparse.ArgumentParser(description="Guarded M7 work-journal tenant index migration")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-missing-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_missing_count is None:
        parser.error("--apply requires --expected-missing-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (
        args.expected_missing_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("expected guards are valid only with --apply")
    conn = None
    try:
        conn = psycopg2.connect(**_db_config())
        result = run_index_migration(
            conn,
            apply=args.apply,
            expected_missing_count=args.expected_missing_count,
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
