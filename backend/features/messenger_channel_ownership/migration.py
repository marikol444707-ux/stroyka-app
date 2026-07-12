"""Guarded company/project ownership migration for messenger channels."""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict

import psycopg2.extensions
import psycopg2.extras


APPLY_CONFIRMATION = "APPLY_MESSENGER_CHANNEL_OWNERSHIP"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OWNER_COLUMNS = {"company_id", "project_id"}
REVIEW_STATUSES = ("ambiguous", "unresolved", "mismatched")
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


def parse_channel_owner(value):
    parts = str(value or "").strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError("channel owner must be CHANNEL_ID:COMPANY_ID[:PROJECT_ID]")
    channel_id = _positive_int(parts[0])
    company_id = _positive_int(parts[1])
    project_id = _positive_int(parts[2]) if len(parts) == 3 else None
    if not channel_id or not company_id or (len(parts) == 3 and not project_id):
        raise ValueError("channel owner IDs must be positive integers")
    return {"channelId": channel_id, "companyId": company_id, "projectId": project_id}


def _result(row, status, reason, company_id=None, project_id=None):
    item = dict(row or {})
    return {
        "channelId": _positive_int(item.get("id")),
        "channelType": str(item.get("channel_type") or "").strip(),
        "projectName": str(item.get("project_name") or "").strip(),
        "storedCompanyId": _positive_int(item.get("stored_company_id")),
        "storedProjectId": _positive_int(item.get("stored_project_id")),
        "proposedCompanyId": _positive_int(company_id),
        "proposedProjectId": _positive_int(project_id),
        "status": status,
        "reason": reason,
    }


def _manual_candidate(channel_id, project_name, projects_by_id, projects_by_name, companies, manual_owners):
    manual = manual_owners.get(channel_id)
    if not manual:
        return None
    company_id = _positive_int(manual.get("companyId"))
    project_id = _positive_int(manual.get("projectId"))
    if company_id not in companies:
        return "unresolved", "manual_company_not_found", None, None
    if project_id:
        project = projects_by_id.get(project_id)
        if not project:
            return "unresolved", "manual_project_not_found", None, None
        if _positive_int(project.get("company_id")) != company_id:
            return "mismatched", "manual_project_company_mismatch", None, None
        if project_name and str(project.get("name") or "").strip() != project_name:
            return "mismatched", "manual_project_name_mismatch", None, None
        return "ready", "explicit_project_owner", company_id, project_id
    if project_name:
        candidates = [
            project for project in projects_by_name.get(project_name, [])
            if _positive_int(project.get("company_id")) == company_id
        ]
        if not candidates:
            return "unresolved", "manual_project_not_found", None, None
        if len(candidates) > 1:
            return "ambiguous", "manual_project_ambiguous", None, None
        return "ready", "explicit_company_resolved_project", company_id, _positive_int(candidates[0].get("id"))
    return "ready", "explicit_company_owner", company_id, None


def classify_channel(row, projects_by_id, projects_by_name, companies, manual_owners):
    item = dict(row or {})
    channel_id = _positive_int(item.get("id"))
    project_name = str(item.get("project_name") or "").strip()
    stored_company = _positive_int(item.get("stored_company_id"))
    stored_project = _positive_int(item.get("stored_project_id"))
    if not channel_id:
        return _result(item, "unresolved", "channel_id_invalid")
    if stored_project and not stored_company:
        return _result(item, "mismatched", "stored_owner_incomplete")
    if stored_company:
        if stored_company not in companies:
            return _result(item, "unresolved", "stored_company_not_found")
        if stored_project:
            project = projects_by_id.get(stored_project)
            if not project:
                return _result(item, "unresolved", "stored_project_not_found")
            if _positive_int(project.get("company_id")) != stored_company:
                return _result(item, "mismatched", "stored_project_company_mismatch")
            if project_name and str(project.get("name") or "").strip() != project_name:
                return _result(item, "mismatched", "stored_project_name_mismatch")
        elif project_name:
            return _result(item, "mismatched", "stored_project_missing")
        if manual_owners.get(channel_id):
            manual_candidate = _manual_candidate(
                channel_id, project_name, projects_by_id, projects_by_name, companies, manual_owners,
            )
            status, _reason, manual_company, manual_project = manual_candidate
            if status != "ready" or (manual_company, manual_project) != (stored_company, stored_project):
                return _result(item, "mismatched", "manual_owner_conflicts_with_stored")
        return _result(item, "stored", "stored_owner_verified", stored_company, stored_project)

    manual_candidate = _manual_candidate(
        channel_id, project_name, projects_by_id, projects_by_name, companies, manual_owners,
    )
    if manual_candidate:
        status, reason, company_id, project_id = manual_candidate
        return _result(item, status, reason, company_id, project_id)
    if not project_name:
        return _result(item, "unresolved", "manual_company_owner_required")
    candidates = projects_by_name.get(project_name, [])
    if not candidates:
        return _result(item, "unresolved", "project_not_found")
    if len(candidates) > 1:
        return _result(item, "ambiguous", "project_name_ambiguous")
    project = candidates[0]
    company_id = _positive_int(project.get("company_id"))
    project_id = _positive_int(project.get("id"))
    if not company_id or not project_id or company_id not in companies:
        return _result(item, "unresolved", "project_owner_missing")
    return _result(item, "ready", "unique_project_name", company_id, project_id)


def build_report(columns, classified):
    rows = list(classified or [])
    counts = Counter(item["status"] for item in rows)
    ready = [item for item in rows if item["status"] == "ready"]
    review = [item for item in rows if item["status"] in REVIEW_STATUSES]
    columns_ready = OWNER_COLUMNS.issubset(columns)
    return {
        "ok": True,
        "table": "messenger_channels",
        "columns": {"companyId": "company_id" in columns, "projectId": "project_id" in columns},
        "reportConsistent": len(rows) == sum(counts[name] for name in ("stored", "ready", *REVIEW_STATUSES)),
        "readyForMigration": not review,
        "readyForStrictRuntime": columns_ready and not ready and not review,
        "summary": {
            "totalRows": len(rows),
            "storedRows": counts["stored"],
            "legacyRows": len(rows) - counts["stored"],
            "ready": counts["ready"],
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "backfillPreview": [
            {
                "channelId": item["channelId"],
                "channelType": item["channelType"],
                "companyId": item["proposedCompanyId"],
                "projectId": item["proposedProjectId"],
                "reason": item["reason"],
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {
                "channelId": item["channelId"],
                "channelType": item["channelType"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def _validate_manual_channel_ids(channels, manual_owners):
    channel_ids = {_positive_int(row.get("id")) for row in channels or []}
    unknown = sorted(channel_id for channel_id in manual_owners if channel_id not in channel_ids)
    if unknown:
        raise ValueError("manual ownership references unknown channel IDs: " + ", ".join(map(str, unknown)))


def collect_ownership(cur, manual_owners=None):
    manual_owners = manual_owners or {}
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='messenger_channels' AND column_name IN ('company_id','project_id')"
    )
    columns = {str(row.get("column_name") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}
    company_sql = "company_id" if "company_id" in columns else "NULL::INT"
    project_sql = "project_id" if "project_id" in columns else "NULL::INT"
    cur.execute(
        f"SELECT id,channel_type,project_name,{company_sql} AS stored_company_id,"
        f"{project_sql} AS stored_project_id FROM messenger_channels ORDER BY id"
    )
    channels = [dict(row or {}) for row in (cur.fetchall() or [])]
    _validate_manual_channel_ids(channels, manual_owners)
    cur.execute("SELECT id FROM companies ORDER BY id")
    companies = {_positive_int(row.get("id") if isinstance(row, dict) else row[0]) for row in (cur.fetchall() or [])}
    cur.execute("SELECT id,company_id,name FROM projects ORDER BY id")
    projects_by_id = {}
    projects_by_name = defaultdict(list)
    for raw in cur.fetchall() or []:
        project = dict(raw or {})
        project_id = _positive_int(project.get("id"))
        if project_id:
            projects_by_id[project_id] = project
        projects_by_name[str(project.get("name") or "").strip()].append(project)
    return columns, [
        classify_channel(row, projects_by_id, projects_by_name, companies, manual_owners)
        for row in channels
    ]


def _plan_sha256(classified):
    plan = [
        [item["channelId"], item["proposedCompanyId"], item["proposedProjectId"]]
        for item in classified or []
        if item.get("status") == "ready"
    ]
    payload = json.dumps(sorted(plan), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_schema(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '60s'")
    cur.execute("LOCK TABLE companies IN SHARE MODE")
    cur.execute("LOCK TABLE projects IN SHARE MODE")
    cur.execute("LOCK TABLE messenger_channels IN ACCESS EXCLUSIVE MODE")
    cur.execute("ALTER TABLE messenger_channels ADD COLUMN IF NOT EXISTS company_id INT")
    cur.execute("ALTER TABLE messenger_channels ADD COLUMN IF NOT EXISTS project_id INT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messenger_channels_company ON messenger_channels(company_id,id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messenger_channels_company_project ON messenger_channels(company_id,project_id)")
    cur.execute(
        """DO $$ BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_messenger_channels_owner') THEN
                   ALTER TABLE messenger_channels ADD CONSTRAINT ck_messenger_channels_owner
                   CHECK (project_id IS NULL OR company_id IS NOT NULL);
               END IF;
           END $$"""
    )


def _apply_ready(cur, ready):
    updated = 0
    for item in ready:
        cur.execute(
            "UPDATE messenger_channels SET company_id=%s,project_id=%s,updated_at=NOW() "
            "WHERE id=%s AND company_id IS NULL AND project_id IS NULL",
            (item["proposedCompanyId"], item["proposedProjectId"], item["channelId"]),
        )
        updated += cur.rowcount
    return updated


def _base_result(report, mode, classified):
    summary = report["summary"]
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": int(summary["ready"]),
        "reviewCount": sum(int(summary[name]) for name in REVIEW_STATUSES),
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updated": 0,
        "writeConflicts": 0,
        "rolledBack": mode == "dry-run",
        "complete": report["readyForStrictRuntime"],
    }


def run_migration(conn, manual_owners=None, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    manual_owners = manual_owners or {}
    if apply and (not isinstance(expected_ready_count, int) or isinstance(expected_ready_count, bool) or expected_ready_count < 0):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not PLAN_SHA256_RE.fullmatch(expected_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    if not apply:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            columns, classified = collect_ownership(cur, manual_owners)
            result = _base_result(build_report(columns, classified), "dry-run", classified)
            conn.rollback()
            return result
        finally:
            cur.close()

    conn.set_session(isolation_level=psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE, autocommit=False)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        columns, classified = collect_ownership(cur, manual_owners)
        report = build_report(columns, classified)
        result = _base_result(report, "apply", classified)
        if not report["readyForMigration"]:
            raise RuntimeError("Migration is blocked by review rows")
        if result["readyCount"] != expected_ready_count or result["planSha256"] != expected_sha:
            raise RuntimeError("Migration plan changed; rerun dry-run")
        _ensure_schema(cur)
        columns, classified = collect_ownership(cur, manual_owners)
        if _plan_sha256(classified) != expected_sha:
            raise RuntimeError("Migration plan changed after schema lock")
        ready = [item for item in classified if item["status"] == "ready"]
        result["writesAttempted"] = len(ready)
        result["updated"] = _apply_ready(cur, ready)
        result["writeConflicts"] = len(ready) - result["updated"]
        post_columns, post_classified = collect_ownership(cur, manual_owners)
        post_report = build_report(post_columns, post_classified)
        if not post_report["readyForStrictRuntime"] or result["writeConflicts"]:
            raise RuntimeError("Messenger channel ownership post-check failed")
        conn.commit()
        result["complete"] = True
        result["postSummary"] = post_report["summary"]
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _manual_owner_map(values):
    owners = {}
    for value in values or []:
        owner = parse_channel_owner(value)
        channel_id = owner["channelId"]
        if channel_id in owners:
            raise ValueError("duplicate --channel-owner for channel " + str(channel_id))
        owners[channel_id] = owner
    return owners


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded messenger channel ownership migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg)
    parser.add_argument("--channel-owner", action="append", default=[])
    args = parser.parse_args(argv)
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error("--apply requires --confirm " + APPLY_CONFIRMATION)
    try:
        owners = _manual_owner_map(args.channel_owner)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    conn = get_db()
    try:
        result = run_migration(
            conn,
            manual_owners=owners,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
