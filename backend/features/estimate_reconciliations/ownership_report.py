"""Read-only ownership diagnostics for estimate reconciliations."""

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


def classify_reconciliation(row):
    item = dict(row or {})
    reconciliation_id = _positive_int(item.get("reconciliation_id"))
    base_id = _positive_int(item.get("base_estimate_id"))
    next_id = _positive_int(item.get("next_estimate_id"))
    base_company = _positive_int(item.get("base_company_id"))
    next_company = _positive_int(item.get("next_company_id"))
    base_project = _positive_int(item.get("base_project_id"))
    next_project = _positive_int(item.get("next_project_id"))
    project_id = _positive_int(item.get("project_id"))
    project_company = _positive_int(item.get("project_company_id"))

    reason = "verified_estimate_pair"
    status = "ready"
    if not base_id or not item.get("base_exists"):
        status, reason = "unresolved", "base_estimate_not_found"
    elif not next_id or not item.get("next_exists"):
        status, reason = "unresolved", "next_estimate_not_found"
    elif not base_company or not base_project:
        status, reason = "unresolved", "base_estimate_owner_missing"
    elif not next_company or not next_project:
        status, reason = "unresolved", "next_estimate_owner_missing"
    elif base_company != next_company or base_project != next_project:
        status, reason = "mismatched", "estimate_owner_mismatch"
    elif not project_id or project_id != base_project or project_company != base_company:
        status, reason = "mismatched", "project_parent_mismatch"
    elif item.get("base_work_package") != item.get("next_work_package"):
        status, reason = "mismatched", "estimate_work_package_mismatch"
    elif item.get("reconciliation_work_package") != item.get("base_work_package"):
        status, reason = "mismatched", "reconciliation_work_package_mismatch"
    elif item.get("base_smeta_type") != item.get("next_smeta_type"):
        status, reason = "mismatched", "estimate_type_mismatch"
    elif item.get("reconciliation_smeta_type") != item.get("base_smeta_type"):
        status, reason = "mismatched", "reconciliation_type_mismatch"
    return {
        "reconciliationId": reconciliation_id,
        "baseEstimateId": base_id,
        "nextEstimateId": next_id,
        "companyId": base_company if status == "ready" else None,
        "projectId": base_project if status == "ready" else None,
        "status": status,
        "reason": reason,
    }


def build_report_from_classified(classified):
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "ready"]
    ready_by_company = Counter(
        str(item["companyId"])
        for item in classified
        if item["status"] == "ready" and item.get("companyId")
    )
    return {
        "ok": True,
        "dryRun": True,
        "table": "estimate_reconciliations",
        "writesAttempted": 0,
        "readyForStrictRuntime": not review,
        "reportConsistent": len(classified) == counts["ready"] + counts["unresolved"] + counts["mismatched"],
        "summary": {
            "totalRows": len(classified),
            "ready": counts["ready"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "needsReview": [
            {
                "reconciliationId": item["reconciliationId"],
                "baseEstimateId": item["baseEstimateId"],
                "nextEstimateId": item["nextEstimateId"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def build_estimate_reconciliation_ownership_report(cur):
    cur.execute(
        """SELECT r.id AS reconciliation_id,
                  r.base_estimate_id,r.next_estimate_id,
                  COALESCE(NULLIF(r.work_package,''),'Основная') AS reconciliation_work_package,
                  COALESCE(r.smeta_type,'Заказчик') AS reconciliation_smeta_type,
                  b.id IS NOT NULL AS base_exists,b.company_id AS base_company_id,
                  b.project_id AS base_project_id,
                  COALESCE(NULLIF(b.work_package,''),'Основная') AS base_work_package,
                  COALESCE(b.smeta_type,'Заказчик') AS base_smeta_type,
                  n.id IS NOT NULL AS next_exists,n.company_id AS next_company_id,
                  n.project_id AS next_project_id,
                  COALESCE(NULLIF(n.work_package,''),'Основная') AS next_work_package,
                  COALESCE(n.smeta_type,'Заказчик') AS next_smeta_type,
                  p.id AS project_id,p.company_id AS project_company_id
             FROM estimate_reconciliations r
             LEFT JOIN estimates b ON b.id=r.base_estimate_id
             LEFT JOIN estimates n ON n.id=r.next_estimate_id
             LEFT JOIN projects p ON p.id=b.project_id
            ORDER BY r.id"""
    )
    classified = [classify_reconciliation(row) for row in (cur.fetchall() or [])]
    return build_report_from_classified(classified)


def run_estimate_reconciliation_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_estimate_reconciliation_ownership_report(cur)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db

    report = run_estimate_reconciliation_ownership_report(get_db)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
