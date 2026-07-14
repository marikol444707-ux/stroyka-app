"""Guarded ownership migration for legacy api_errors rows."""

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

from backend.features.api_error_ownership.ownership_report import (
    _positive_int,
    classify_ownership_rows,
    load_ownership_rows,
    review_plan_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_API_ERROR_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OWNER_COLUMNS = {"owner_scope", "company_id", "project_id"}
REVIEW_STATUSES = {"unresolved", "ambiguous", "mismatched"}
PREVIEW_LIMIT = 100


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


def _stored_owner_tuple(row):
    return (
        str(row.get("owner_scope") or "").strip() or None,
        _positive_int(row.get("company_id")),
        _positive_int(row.get("project_id")),
    )


def _migration_result(evidence, status, reason, scope=None, company_id=None, project_id=None):
    return {
        "recordId": evidence.get("recordId"),
        "status": status,
        "reason": reason,
        "proposedScope": scope,
        "proposedCompanyId": company_id,
        "proposedProjectId": project_id,
    }


def classify_migration_row(evidence, stored_owner=None, allow_legacy=False):
    item = dict(evidence or {})
    stored_scope, stored_company_id, stored_project_id = _stored_owner_tuple(stored_owner or {})
    has_stored_values = bool(stored_scope or stored_company_id or stored_project_id)

    if has_stored_values:
        if stored_scope == "legacy" and not stored_company_id and not stored_project_id:
            return _migration_result(item, "stored", "stored_legacy_owner", "legacy")
        if stored_scope == "platform" and not stored_company_id and not stored_project_id:
            if item.get("status") == "verified" and item.get("scope") == "platform":
                return _migration_result(item, "stored", "stored_platform_owner", "platform")
            return _migration_result(item, "mismatched", "stored_platform_owner_unverified")
        if stored_scope == "company" and stored_company_id and not stored_project_id:
            expected = (item.get("scope"), item.get("companyId"))
            stored = (stored_scope, stored_company_id)
            if item.get("status") == "verified" and expected == stored:
                return _migration_result(
                    item,
                    "stored",
                    "stored_company_owner",
                    stored_scope,
                    stored_company_id,
                )
            return _migration_result(item, "mismatched", "stored_company_owner_mismatch")
        return _migration_result(item, "mismatched", "stored_owner_shape_invalid")

    if item.get("status") == "verified":
        return _migration_result(
            item,
            "ready",
            item.get("reason") or "verified_owner",
            item.get("scope"),
            item.get("companyId"),
        )
    if allow_legacy and item.get("status") == "unresolved":
        return _migration_result(item, "ready", "explicit_review_set_as_legacy", "legacy")
    return _migration_result(
        item,
        item.get("status") or "unresolved",
        item.get("reason") or "unresolved",
    )


def build_migration_report(columns, classified, review_hash):
    items = list(classified or [])
    counts = Counter(item.get("status") for item in items)
    review = [item for item in items if item.get("status") in REVIEW_STATUSES]
    ready = [item for item in items if item.get("status") == "ready"]
    stored = [item for item in items if item.get("status") == "stored"]
    columns_ready = OWNER_COLUMNS.issubset(set(columns or set()))
    report_consistent = len(items) == len(ready) + len(stored) + len(review)
    return {
        "ok": True,
        "table": "api_errors",
        "columns": {
            "ownerScope": "owner_scope" in columns,
            "companyId": "company_id" in columns,
            "projectId": "project_id" in columns,
        },
        "reportConsistent": report_consistent,
        "readyForMigration": report_consistent and not review,
        "readyForStrictRuntime": report_consistent and columns_ready and not ready and not review,
        "summary": {
            "totalRows": len(items),
            "storedRows": len(stored),
            "storedCompanyRows": sum(
                1 for item in stored if item.get("proposedScope") == "company"
            ),
            "storedPlatformRows": sum(
                1 for item in stored if item.get("proposedScope") == "platform"
            ),
            "storedLegacyRows": sum(
                1 for item in stored if item.get("proposedScope") == "legacy"
            ),
            "legacyRows": len(items) - len(stored),
            "ready": len(ready),
            "unresolved": counts["unresolved"],
            "ambiguous": counts["ambiguous"],
            "mismatched": counts["mismatched"],
        },
        "reviewPlanSha256": review_hash,
        "backfillPreview": [
            {
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
                "recordId": item["recordId"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def _api_error_columns(cur):
    cur.execute(
        """SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='api_errors'
            ORDER BY column_name"""
    )
    return {str(dict(row or {}).get("column_name") or "") for row in (cur.fetchall() or [])}


def _stored_owners(cur, columns):
    if not OWNER_COLUMNS.issubset(columns):
        return {}
    cur.execute("SELECT id,owner_scope,company_id,project_id FROM api_errors ORDER BY id")
    return {_positive_int(row.get("id")): dict(row or {}) for row in (cur.fetchall() or [])}


def collect_ownership(cur, legacy_review_sha=None):
    evidence = classify_ownership_rows(load_ownership_rows(cur))
    current_review_hash = review_plan_sha256(evidence)
    review_count = sum(1 for item in evidence if item.get("status") != "verified")
    normalized_legacy_sha = str(legacy_review_sha or "").strip().lower()
    if normalized_legacy_sha and normalized_legacy_sha != current_review_hash:
        raise RuntimeError("legacy review set changed; rerun ownership audit")
    allow_legacy = bool(normalized_legacy_sha and review_count)
    columns = _api_error_columns(cur)
    stored = _stored_owners(cur, columns)
    classified = [
        classify_migration_row(item, stored.get(item.get("recordId")), allow_legacy)
        for item in evidence
    ]
    return columns, classified, current_review_hash


def _plan_sha256(classified):
    plan = []
    for item in classified or []:
        if item.get("status") != "ready":
            continue
        record_id = _positive_int(item.get("recordId"))
        scope = item.get("proposedScope")
        company_id = _positive_int(item.get("proposedCompanyId"))
        project_id = _positive_int(item.get("proposedProjectId"))
        if not record_id or scope not in {"company", "platform", "legacy"}:
            raise ValueError("ready api error row has invalid owner identity")
        if scope == "company" and not company_id:
            raise ValueError("company api error row has no company")
        if scope in {"platform", "legacy"} and (company_id or project_id):
            raise ValueError("non-company api error row contains tenant IDs")
        plan.append([record_id, scope, company_id or 0, project_id or 0])
    return hashlib.sha256(json.dumps(sorted(plan), separators=(",", ":")).encode()).hexdigest()


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")
    cur.execute("LOCK TABLE api_errors IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE api_errors ADD COLUMN IF NOT EXISTS owner_scope TEXT")
    cur.execute("ALTER TABLE api_errors ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE api_errors ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_errors_owner "
        "ON api_errors(owner_scope,company_id,project_id,created_at DESC)"
    )
    cur.execute(
        """DO $$ BEGIN
               IF NOT EXISTS (
                   SELECT 1 FROM pg_constraint
                   WHERE conname='ck_api_errors_owner_scope'
                     AND conrelid='api_errors'::regclass
               ) THEN
                   ALTER TABLE api_errors ADD CONSTRAINT ck_api_errors_owner_scope CHECK (
                       (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                       (owner_scope='company' AND company_id IS NOT NULL) OR
                       (owner_scope IN ('platform','legacy') AND company_id IS NULL AND project_id IS NULL)
                   );
               END IF;
           END $$"""
    )


def _apply_ready_rows(cur, ready):
    selected = list(ready or [])
    if not selected:
        return 0
    cur.execute(
        """UPDATE api_errors e
              SET owner_scope=owners.owner_scope,
                  company_id=owners.company_id,
                  project_id=owners.project_id
             FROM UNNEST(%s::INT[],%s::TEXT[],%s::INT[],%s::INT[])
                  AS owners(id,owner_scope,company_id,project_id)
            WHERE e.id=owners.id
              AND e.owner_scope IS NULL AND e.company_id IS NULL AND e.project_id IS NULL""",
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
        "updated": 0,
        "writeConflicts": 0,
        "rolledBack": False,
        "complete": report.get("readyForStrictRuntime") is True,
    }


def run_migration(
    conn,
    legacy_review_sha=None,
    apply=False,
    expected_ready_count=None,
    expected_plan_sha256=None,
):
    if apply and (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("apply requires a non-negative expected_ready_count")
    normalized_plan_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(normalized_plan_sha):
        raise ValueError("apply requires a valid expected_plan_sha256")

    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            columns, classified, review_hash = collect_ownership(cur, legacy_review_sha)
            result = _base_result(
                build_migration_report(columns, classified, review_hash),
                "dry-run",
                classified,
            )
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
        columns, classified, review_hash = collect_ownership(cur, legacy_review_sha)
        report = build_migration_report(columns, classified, review_hash)
        result = _base_result(report, "apply", classified)
        if result["reviewCount"] or report.get("reportConsistent") is not True:
            conn.rollback()
            result.update({"ok": False, "failureReason": "needs_review", "rolledBack": True})
            return result
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError("migration count changed; rerun dry-run")
        if result["planSha256"] != normalized_plan_sha:
            raise RuntimeError("migration plan changed; rerun dry-run")
        ready = [item for item in classified if item.get("status") == "ready"]
        updated = _apply_ready_rows(cur, ready)
        conflicts = max(result["readyCount"] - updated, 0)
        result.update(
            writesAttempted=result["readyCount"],
            updated=updated,
            writeConflicts=conflicts,
        )
        if conflicts:
            conn.rollback()
            result.update({"ok": False, "failureReason": "write_conflict", "rolledBack": True})
            return result
        post_columns, post_classified, post_review_hash = collect_ownership(cur)
        post_report = build_migration_report(post_columns, post_classified, post_review_hash)
        result["postSummary"] = post_report["summary"]
        if (
            post_report.get("readyForStrictRuntime") is not True
            or post_report["summary"]["totalRows"] != report["summary"]["totalRows"]
        ):
            conn.rollback()
            result.update({"ok": False, "failureReason": "postcheck_failed", "rolledBack": True})
            return result
        conn.commit()
        result.update(columns=post_report["columns"], complete=True)
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
    parser = argparse.ArgumentParser(description="Guarded ownership migration for api_errors")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--legacy-review-sha", type=_sha256_arg, default=None)
    parser.add_argument("--expected-ready-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("choose either --dry-run or --apply")
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
            args.legacy_review_sha,
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
