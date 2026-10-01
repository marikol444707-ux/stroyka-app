"""Dry-run-first project identity backfill for legacy supply requests."""

import argparse
import hashlib
import json
import re

import psycopg2.extensions
import psycopg2.extras


APPLY_CONFIRMATION = "APPLY_SUPPLY_REQUEST_PROJECT_IDS"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _name(value):
    return str(value or "").strip()


def _item(row, status, reason, project_id=None):
    return {
        "requestId": _positive_int((row or {}).get("id")),
        "companyId": _positive_int((row or {}).get("company_id")),
        "projectId": _positive_int(project_id),
        "status": status,
        "reason": reason,
    }


def classify_rows(rows):
    projects_by_id = {
        _positive_int(row.get("id")): dict(row)
        for row in rows.get("projects", [])
        if _positive_int(row.get("id"))
    }
    projects_by_key = {}
    for project in rows.get("projects", []):
        key = (_positive_int(project.get("company_id")), _name(project.get("name")))
        projects_by_key.setdefault(key, []).append(dict(project))

    result = []
    for row in rows.get("supply_requests", []):
        row = dict(row or {})
        company_id = _positive_int(row.get("company_id"))
        project_id = _positive_int(row.get("project_id"))
        project_name = _name(row.get("project"))
        if not company_id:
            result.append(_item(row, "unresolved", "company_missing"))
            continue
        if project_name == "Основной склад":
            result.append(_item(
                row,
                "verified" if project_id is None else "mismatched",
                "main_warehouse_company_scope" if project_id is None else "warehouse_has_project_id",
                project_id,
            ))
            continue
        if not project_name:
            result.append(_item(row, "unresolved", "project_name_missing", project_id))
            continue
        if project_id:
            project = projects_by_id.get(project_id)
            if not project:
                result.append(_item(row, "unresolved", "stored_project_not_found", project_id))
            elif _positive_int(project.get("company_id")) != company_id:
                result.append(_item(row, "mismatched", "stored_project_company_mismatch", project_id))
            elif _name(project.get("name")) != project_name:
                result.append(_item(row, "mismatched", "stored_project_name_mismatch", project_id))
            else:
                result.append(_item(row, "verified", "stored_project_identity", project_id))
            continue
        candidates = projects_by_key.get((company_id, project_name), [])
        if not candidates:
            result.append(_item(row, "unresolved", "project_not_found"))
        elif len(candidates) > 1:
            result.append(_item(row, "ambiguous", "project_name_ambiguous"))
        else:
            result.append(_item(row, "ready", "exact_company_project_name", candidates[0].get("id")))
    return result


def _plan_sha256(ready):
    payload = sorted([
        [item["requestId"], item["companyId"], item["projectId"]]
        for item in ready
    ])
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_report(rows):
    classified = classify_rows(rows)
    ready = [item for item in classified if item["status"] == "ready"]
    review = [item for item in classified if item["status"] in {"unresolved", "ambiguous", "mismatched"}]
    verified = [item for item in classified if item["status"] == "verified"]
    return {
        "ok": True,
        "dryRun": True,
        "totalRows": len(classified),
        "verifiedCount": len(verified),
        "readyCount": len(ready),
        "reviewCount": len(review),
        "readyForStrictRuntime": not ready and not review,
        "planSha256": _plan_sha256(ready),
        "backfillPreview": ready[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "previewTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "writesAttempted": 0,
        "updatedRows": 0,
        "rolledBack": False,
        "complete": False,
    }


def load_rows(cur):
    cur.execute("SELECT id,company_id,name FROM projects ORDER BY id")
    projects = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,company_id,project,project_id FROM supply_requests ORDER BY id")
    requests = [dict(row or {}) for row in (cur.fetchall() or [])]
    return {"projects": projects, "supply_requests": requests}


def run_backfill(conn, *, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    if apply and (isinstance(expected_ready_count, bool) or not isinstance(expected_ready_count, int) or expected_ready_count < 0):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not SHA_RE.fullmatch(expected_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    session = {"readonly": not apply, "autocommit": False}
    if apply:
        session["isolation_level"] = psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE
    conn.set_session(**session)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if apply:
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("LOCK TABLE projects IN SHARE MODE")
            cur.execute("LOCK TABLE supply_requests IN SHARE ROW EXCLUSIVE MODE")
        source_rows = load_rows(cur)
        report = build_report(source_rows)
        report["dryRun"] = not apply
        if not apply:
            conn.rollback()
            report["rolledBack"] = True
            return report
        if report["readyCount"] != expected_ready_count or report["planSha256"] != expected_sha:
            raise RuntimeError("Backfill plan changed; rerun dry-run")
        ready = [item for item in classify_rows(source_rows) if item["status"] == "ready"]
        report["writesAttempted"] = len(ready)
        if ready:
            cur.execute(
                "UPDATE supply_requests AS request SET project_id=plan.project_id "
                "FROM UNNEST(%s::INT[],%s::INT[],%s::INT[]) AS plan(id,company_id,project_id) "
                "WHERE request.id=plan.id AND request.company_id=plan.company_id "
                "AND request.project_id IS NULL",
                (
                    [item["requestId"] for item in ready],
                    [item["companyId"] for item in ready],
                    [item["projectId"] for item in ready],
                ),
            )
            report["updatedRows"] = int(cur.rowcount or 0)
        if report["updatedRows"] != len(ready):
            raise RuntimeError("Backfill write conflict")
        post = build_report(load_rows(cur))
        if post["readyCount"]:
            raise RuntimeError("Backfill post-check still has ready rows")
        conn.commit()
        report["complete"] = True
        report["postcheck"] = {
            "verifiedCount": post["verifiedCount"],
            "reviewCount": post["reviewCount"],
            "readyForStrictRuntime": post["readyForStrictRuntime"],
        }
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Supply request project-id backfill")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=int)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error("--apply requires --confirm " + APPLY_CONFIRMATION)
    if args.apply and (args.expected_ready_count is None or not SHA_RE.fullmatch(str(args.expected_plan_sha256 or ""))):
        parser.error("--apply requires exact count and SHA from dry-run")
    from backend.db import get_db
    conn = get_db()
    try:
        result = run_backfill(
            conn,
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
