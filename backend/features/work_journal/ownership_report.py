"""Read-only ownership diagnostics for work journal rows."""

import json
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def classify_work_journal(row):
    item = dict(row or {})
    journal_id = _positive_int(item.get("journal_id"))
    stored_company = _positive_int(item.get("stored_company_id"))
    project_count = int(item.get("project_count") or 0)
    project_id = _positive_int(item.get("project_id"))
    project_company = _positive_int(item.get("project_company_id"))

    status, reason = "verified", "stored_company_matches_project"
    if project_count == 0:
        status, reason = "unresolved", "project_not_found"
    elif project_count > 1:
        status, reason = "unresolved", "project_name_ambiguous"
    elif not project_id or not project_company:
        status, reason = "unresolved", "project_owner_missing"
    else:
        parents = (
            ("estimate", item.get("estimate_id"), item.get("estimate_exists"), item.get("estimate_company_id"), item.get("estimate_project_id")),
            ("unexpected_work", item.get("unexpected_work_id"), item.get("unexpected_work_exists"), item.get("unexpected_company_id"), item.get("unexpected_project_id")),
            ("contract_item", item.get("contract_item_id"), item.get("contract_item_exists"), item.get("contract_company_id"), item.get("contract_project_id")),
        )
        for label, parent_id, exists, company_id, parent_project_id in parents:
            if not _positive_int(parent_id):
                continue
            if not exists:
                status, reason = "unresolved", label + "_not_found"
                break
            if not _positive_int(company_id) or not _positive_int(parent_project_id):
                status, reason = "unresolved", label + "_owner_missing"
                break
            if _positive_int(company_id) != project_company or _positive_int(parent_project_id) != project_id:
                status, reason = "mismatched", label + "_owner_mismatch"
                break
        else:
            if not stored_company:
                status, reason = "needs_backfill", "stored_company_missing"
            elif stored_company != project_company:
                status, reason = "needs_backfill", "stored_company_mismatch"

    return {
        "journalId": journal_id,
        "companyId": project_company if status in ("verified", "needs_backfill") else None,
        "projectId": project_id if status in ("verified", "needs_backfill") else None,
        "status": status,
        "reason": reason,
    }


def build_report_from_classified(classified):
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] in ("unresolved", "mismatched")]
    backfill = [item for item in classified if item["status"] == "needs_backfill"]
    return {
        "ok": True,
        "dryRun": True,
        "table": "work_journal",
        "writesAttempted": 0,
        "readyForMigration": not review,
        "readyForStrictRuntime": not review and not backfill,
        "reportConsistent": len(classified) == sum(counts[name] for name in ("verified", "needs_backfill", "unresolved", "mismatched")),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "needsBackfill": counts["needs_backfill"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "backfillPreview": [
            {"journalId": item["journalId"], "companyId": item["companyId"], "projectId": item["projectId"], "reason": item["reason"]}
            for item in backfill[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {"journalId": item["journalId"], "status": item["status"], "reason": item["reason"]}
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(backfill) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def build_work_journal_ownership_report(cur):
    cur.execute(
        """SELECT wj.id AS journal_id,wj.company_id AS stored_company_id,
                  wj.estimate_id,wj.unexpected_work_id,wj.contract_item_id,
                  project_scope.project_count,project_scope.project_id,
                  project_scope.project_company_id,
                  e.id IS NOT NULL AS estimate_exists,e.company_id AS estimate_company_id,
                  e.project_id AS estimate_project_id,
                  uw.id IS NOT NULL AS unexpected_work_exists,
                  uw.company_id AS unexpected_company_id,uw.project_id AS unexpected_project_id,
                  bci.id IS NOT NULL AS contract_item_exists,
                  bc.company_id AS contract_company_id,bc.project_id AS contract_project_id
             FROM work_journal wj
             LEFT JOIN LATERAL (
                 SELECT COUNT(*) AS project_count,MIN(p.id) AS project_id,
                        MIN(p.company_id) AS project_company_id
                   FROM projects p WHERE p.name=wj.project
             ) project_scope ON TRUE
             LEFT JOIN estimates e ON e.id=wj.estimate_id
             LEFT JOIN unexpected_works uw ON uw.id=wj.unexpected_work_id
             LEFT JOIN brigade_contract_items bci ON bci.id=wj.contract_item_id
             LEFT JOIN brigade_contracts bc ON bc.id=bci.contract_id
            ORDER BY wj.id"""
    )
    return build_report_from_classified(
        [classify_work_journal(row) for row in (cur.fetchall() or [])]
    )


def run_work_journal_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_work_journal_ownership_report(cur)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(run_work_journal_ownership_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
