"""Guarded owner migration for messenger files and outbox rows."""

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

from backend.features.messenger_ownership.ownership_report import (
    MESSENGER_ITEM_TABLES,
    _entity_index,
    _positive_int,
    _project_indexes,
    _recipient_company_indexes,
    classify_row,
    load_ownership_rows,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_MESSENGER_ITEM_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OWNER_COLUMNS = {"owner_scope", "company_id", "project_id"}
REVIEW_STATUSES = ("unresolved", "ambiguous", "mismatched")
PREVIEW_LIMIT = 100


def _non_negative_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return result


def _positive_int_arg(value):
    result = _positive_int(value)
    if not result:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def _sha256_arg(value):
    normalized = str(value or "").strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError("must be a 64-character SHA-256 hex digest")
    return normalized


def _stored_tuple(item):
    return (
        str(item.get("stored_scope") or "").strip() or None,
        _positive_int(item.get("stored_company_id")),
        _positive_int(item.get("stored_project_id")),
    )


def _proposed_tuple(item):
    return (
        item.get("proposedScope"),
        item.get("proposedCompanyId"),
        item.get("proposedProjectId"),
    )


def classify_item(table, row, owner_result, legacy_outbox_ids):
    item = dict(row or {})
    owner = dict(owner_result or {})
    record_id = _positive_int(item.get("id"))
    row_status = str(item.get("status") or "").strip().lower()
    stored_scope, stored_company, stored_project = _stored_tuple(item)
    any_stored = bool(stored_scope or stored_company or stored_project)

    result = {
        "table": table,
        "recordId": record_id,
        "rowStatus": row_status,
        "entityType": str(item.get("entity_type") or "").strip(),
        "entityId": _positive_int(item.get("entity_id")),
        "proposedScope": None,
        "proposedCompanyId": None,
        "proposedProjectId": None,
        "status": owner.get("status") or "unresolved",
        "reason": owner.get("reason") or "owner_evidence_missing",
    }
    if not record_id:
        result.update({"status": "unresolved", "reason": "record_id_invalid"})
        return result

    if any_stored:
        if stored_scope == "company" and stored_company:
            if owner.get("status") == "verified" and (
                owner.get("companyId"), owner.get("projectId")
            ) != (stored_company, stored_project):
                result.update({"status": "mismatched", "reason": "stored_owner_mismatch"})
                return result
            if owner.get("status") == "mismatched":
                result.update({"status": "mismatched", "reason": owner.get("reason")})
                return result
            result.update(
                {
                    "proposedScope": "company",
                    "proposedCompanyId": stored_company,
                    "proposedProjectId": stored_project,
                    "status": "stored",
                    "reason": "stored_owner_verified",
                }
            )
            return result
        if (
            stored_scope == "legacy"
            and table == "messenger_outbox"
            and not stored_company
            and not stored_project
            and row_status in ("failed", "skipped")
            and owner.get("status") == "unresolved"
            and owner.get("reason") == "entity_parent_not_found"
            and not owner.get("recipientCompanyIds")
        ):
            result.update(
                {
                    "proposedScope": "legacy",
                    "status": "stored",
                    "reason": "stored_owner_verified",
                }
            )
            return result
        result.update({"status": "mismatched", "reason": "stored_owner_invalid"})
        return result

    if owner.get("status") == "verified" and _positive_int(owner.get("companyId")):
        result.update(
            {
                "proposedScope": "company",
                "proposedCompanyId": _positive_int(owner.get("companyId")),
                "proposedProjectId": _positive_int(owner.get("projectId")),
                "status": "ready",
                "reason": owner.get("reason") or "verified_owner",
            }
        )
        return result

    if table == "messenger_outbox" and record_id in set(legacy_outbox_ids or ()):
        if row_status not in ("failed", "skipped"):
            result.update({"status": "mismatched", "reason": "legacy_outbox_not_terminal"})
        elif owner.get("status") != "unresolved" or owner.get("reason") != "entity_parent_not_found":
            result.update({"status": "mismatched", "reason": "legacy_outbox_not_orphan"})
        elif owner.get("recipientCompanyIds"):
            result.update({"status": "mismatched", "reason": "legacy_outbox_has_recipient_owner"})
        else:
            result.update(
                {
                    "proposedScope": "legacy",
                    "status": "ready",
                    "reason": "explicit_legacy_failed_orphan",
                }
            )
    return result


def build_report(file_columns, outbox_columns, classified, requested_legacy_ids=None, seen_outbox_ids=None):
    requested = set(requested_legacy_ids or ())
    unknown = sorted(requested - set(seen_outbox_ids or ()))
    if unknown:
        raise ValueError("unknown outbox IDs: " + ",".join(str(item) for item in unknown))
    rows = list(classified or [])
    counts = Counter(item.get("status") for item in rows)
    ready = [item for item in rows if item.get("status") == "ready"]
    review = [item for item in rows if item.get("status") in REVIEW_STATUSES]
    columns_ready = OWNER_COLUMNS.issubset(file_columns) and OWNER_COLUMNS.issubset(outbox_columns)
    table_totals = Counter(item.get("table") for item in rows)
    table_stored = Counter(item.get("table") for item in rows if item.get("status") == "stored")
    table_ready = Counter(item.get("table") for item in ready)
    return {
        "ok": True,
        "tables": list(MESSENGER_ITEM_TABLES),
        "columns": {
            "messengerFiles": {key: key in file_columns for key in sorted(OWNER_COLUMNS)},
            "messengerOutbox": {key: key in outbox_columns for key in sorted(OWNER_COLUMNS)},
        },
        "reportConsistent": len(rows)
        == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": columns_ready and not ready and not review,
        "summary": {
            "totalRows": len(rows),
            "storedRows": counts["stored"],
            "legacyRows": len(rows) - counts["stored"],
            "ready": counts["ready"],
            "unresolved": counts["unresolved"],
            "ambiguous": counts["ambiguous"],
            "mismatched": counts["mismatched"],
        },
        "byTable": {
            table: {
                "totalRows": table_totals[table],
                "storedRows": table_stored[table],
                "ready": table_ready[table],
            }
            for table in MESSENGER_ITEM_TABLES
        },
        "backfillPreview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "ownerScope": item["proposedScope"],
                "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {
                "table": item["table"],
                "recordId": item["recordId"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def _table_columns(cur, table):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name=%s AND column_name IN ('owner_scope','company_id','project_id')",
        (table,),
    )
    return {
        str(row.get("column_name") if isinstance(row, dict) else row[0])
        for row in (cur.fetchall() or [])
    }


def _stored_owner_rows(cur, table, columns):
    scope_sql = "owner_scope" if "owner_scope" in columns else "NULL::TEXT"
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"SELECT id,{scope_sql} AS stored_scope,{company_sql} AS stored_company_id,"
        f"{project_sql} AS stored_project_id FROM {table} ORDER BY id"
    )
    return {_positive_int(row.get("id")): dict(row) for row in (cur.fetchall() or [])}


def collect_ownership(cur, legacy_outbox_ids=None):
    file_columns = _table_columns(cur, "messenger_files")
    outbox_columns = _table_columns(cur, "messenger_outbox")
    rows = load_ownership_rows(cur)
    projects_by_id, projects_by_name = _project_indexes(rows.get("projects"))
    user_companies, staff_companies, accounts = _recipient_company_indexes(rows)
    entities = _entity_index(rows.get("entity_owners"), projects_by_id, projects_by_name)
    stored_by_table = {
        "messenger_files": _stored_owner_rows(cur, "messenger_files", file_columns),
        "messenger_outbox": _stored_owner_rows(cur, "messenger_outbox", outbox_columns),
    }
    classified = []
    for table in MESSENGER_ITEM_TABLES:
        for raw in rows.get(table, []) or []:
            item = dict(raw or {})
            item.update(stored_by_table[table].get(_positive_int(item.get("id")), {}))
            owner_result = classify_row(
                table,
                item,
                projects_by_name,
                entities,
                user_companies,
                staff_companies,
                accounts,
            )
            classified.append(classify_item(table, item, owner_result, legacy_outbox_ids or set()))
    seen_outbox_ids = {
        _positive_int(row.get("id")) for row in rows.get("messenger_outbox", []) or []
    }
    return file_columns, outbox_columns, classified, seen_outbox_ids


def _plan_sha256(classified):
    plan = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        table = item.get("table")
        record_id = item.get("recordId")
        scope = item.get("proposedScope")
        company_id = item.get("proposedCompanyId") or 0
        project_id = item.get("proposedProjectId") or 0
        if table not in MESSENGER_ITEM_TABLES or not _positive_int(record_id):
            raise ValueError("ready messenger item has invalid identity")
        if scope == "company" and not _positive_int(company_id):
            raise ValueError("company messenger item has no company")
        if scope == "legacy" and (company_id or project_id):
            raise ValueError("legacy messenger item contains tenant IDs")
        if scope not in ("company", "legacy"):
            raise ValueError("ready messenger item has invalid owner scope")
        plan.append([table, record_id, scope, company_id, project_id])
    return hashlib.sha256(json.dumps(sorted(plan), separators=(",", ":")).encode()).hexdigest()


def _ensure_table_schema(cur, table, constraint_name, index_name):
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner_scope TEXT")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}(owner_scope,company_id,project_id)")
    cur.execute(
        f"""DO $$ BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='{constraint_name}') THEN
                   ALTER TABLE {table} ADD CONSTRAINT {constraint_name} CHECK (
                       (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                       (owner_scope='company' AND company_id IS NOT NULL) OR
                       (owner_scope='legacy' AND company_id IS NULL AND project_id IS NULL)
                   );
               END IF;
           END $$"""
    )


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE messenger_files IN ACCESS EXCLUSIVE MODE")
    cur.execute("LOCK TABLE messenger_outbox IN ACCESS EXCLUSIVE MODE")
    _ensure_table_schema(
        cur, "messenger_files", "ck_messenger_files_owner_scope", "idx_messenger_files_owner"
    )
    _ensure_table_schema(
        cur, "messenger_outbox", "ck_messenger_outbox_owner_scope", "idx_messenger_outbox_owner"
    )
    cur.execute(
        """DO $$ BEGIN
               IF NOT EXISTS (
                   SELECT 1 FROM pg_constraint WHERE conname='ck_messenger_outbox_legacy_terminal'
               ) THEN
                   ALTER TABLE messenger_outbox ADD CONSTRAINT ck_messenger_outbox_legacy_terminal
                   CHECK (owner_scope IS DISTINCT FROM 'legacy' OR status IN ('failed','skipped'));
               END IF;
           END $$"""
    )


def _apply_rows(cur, table, alias, rows):
    selected = list(rows or [])
    if not selected:
        return 0
    cur.execute(
        f"""UPDATE {table} {alias}
              SET owner_scope=owners.owner_scope,company_id=owners.company_id,project_id=owners.project_id
             FROM UNNEST(%s::INT[],%s::TEXT[],%s::INT[],%s::INT[])
                  AS owners(id,owner_scope,company_id,project_id)
            WHERE {alias}.id=owners.id AND {alias}.owner_scope IS NULL
              AND {alias}.company_id IS NULL AND {alias}.project_id IS NULL""",
        (
            [item["recordId"] for item in selected],
            [item["proposedScope"] for item in selected],
            [item["proposedCompanyId"] for item in selected],
            [item["proposedProjectId"] for item in selected],
        ),
    )
    return cur.rowcount


def _base_result(report, mode, classified):
    summary = report["summary"]
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": int(summary.get("ready") or 0),
        "reviewCount": sum(int(summary.get(name) or 0) for name in REVIEW_STATUSES),
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updatedFiles": 0,
        "updatedOutbox": 0,
        "writeConflicts": 0,
        "rolledBack": False,
        "complete": report.get("readyForStrictRuntime") is True,
    }


def run_migration(
    conn,
    legacy_outbox_ids=None,
    apply=False,
    expected_ready_count=None,
    expected_plan_sha256=None,
):
    legacy_ids = set(legacy_outbox_ids or ())
    if apply and (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("apply requires a non-negative expected_ready_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("apply requires a valid expected_plan_sha256")

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            file_columns, outbox_columns, classified, seen = collect_ownership(cur, legacy_ids)
            report = build_report(file_columns, outbox_columns, classified, legacy_ids, seen)
            result = _base_result(report, "dry-run", classified)
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
        _ensure_schema(cur)
        file_columns, outbox_columns, classified, seen = collect_ownership(cur, legacy_ids)
        report = build_report(file_columns, outbox_columns, classified, legacy_ids, seen)
        result = _base_result(report, "apply", classified)
        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback()
            result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError("migration count changed; rerun dry-run")
        if result["planSha256"] != normalized_sha:
            raise RuntimeError("migration plan changed; rerun dry-run")
        ready = [item for item in classified if item.get("status") == "ready"]
        updated_files = _apply_rows(
            cur, "messenger_files", "f", [item for item in ready if item["table"] == "messenger_files"]
        )
        updated_outbox = _apply_rows(
            cur, "messenger_outbox", "o", [item for item in ready if item["table"] == "messenger_outbox"]
        )
        updated = updated_files + updated_outbox
        conflicts = max(result["readyCount"] - updated, 0)
        result.update(
            {
                "writesAttempted": result["readyCount"],
                "updatedFiles": updated_files,
                "updatedOutbox": updated_outbox,
                "writeConflicts": conflicts,
            }
        )
        if conflicts:
            conn.rollback()
            result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result
        post_file_columns, post_outbox_columns, post_classified, post_seen = collect_ownership(
            cur, legacy_ids
        )
        post_report = build_report(
            post_file_columns, post_outbox_columns, post_classified, legacy_ids, post_seen
        )
        result["postSummary"] = post_report["summary"]
        if (
            post_report.get("readyForStrictRuntime") is not True
            or post_report["summary"]["totalRows"] != report["summary"]["totalRows"]
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
    parser = argparse.ArgumentParser(description="Guarded ownership migration for messenger items")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    parser.add_argument("--legacy-outbox", action="append", type=_positive_int_arg, default=[])
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("choose either --dry-run or --apply")
    if len(args.legacy_outbox) != len(set(args.legacy_outbox)):
        parser.error("duplicate --legacy-outbox ID")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (
        args.expected_ready_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("expected guards are valid only with --apply")
    conn = psycopg2.connect(**_db_config())
    try:
        result = run_migration(
            conn,
            set(args.legacy_outbox),
            args.apply,
            args.expected_ready_count,
            args.expected_plan_sha256,
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
