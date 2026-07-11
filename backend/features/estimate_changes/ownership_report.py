"""Read-only tenant ownership diagnostics for estimate changes."""

import json
from collections import defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _row_value(row, key, index=0):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _project_record(row):
    return {
        "projectId": _positive_int(_row_value(row, "project_id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "projectName": str(_row_value(row, "project_name", 2) or "").strip(),
    }


def _estimate_record(row):
    return {
        "estimateId": _positive_int(_row_value(row, "estimate_id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "projectId": _positive_int(_row_value(row, "project_id", 2)),
        "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
    }


def _ownership_result(row, status, reason, project=None, source=None):
    item = dict(row or {})
    project = project or {}
    return {
        "changeId": _positive_int(item.get("change_id")),
        "estimateId": _positive_int(item.get("estimate_id")),
        "includedEstimateId": _positive_int(item.get("included_estimate_id")),
        "storedProjectId": _positive_int(item.get("project_id")),
        "storedCompanyId": _positive_int(item.get("company_id")),
        "proposedProjectId": _positive_int(project.get("projectId")),
        "proposedCompanyId": _positive_int(project.get("companyId")),
        "source": source,
        "status": status,
        "reason": reason,
    }


def _resolve_estimate_project(estimate_id, estimates_by_id, projects_by_id, projects_by_company_name):
    estimate = estimates_by_id.get(_positive_int(estimate_id))
    if not estimate:
        return None, "unresolved", "estimate_not_found"
    company_id = _positive_int(estimate.get("companyId"))
    if not company_id:
        return None, "unresolved", "estimate_company_missing"
    project_id = _positive_int(estimate.get("projectId"))
    estimate_name = str(estimate.get("projectName") or "").strip()
    if project_id:
        project = projects_by_id.get(project_id)
        if not project:
            return None, "unresolved", "estimate_project_not_found"
        if _positive_int(project.get("companyId")) != company_id:
            return None, "mismatched", "estimate_project_company_mismatch"
        if estimate_name and estimate_name != str(project.get("projectName") or "").strip():
            return None, "mismatched", "estimate_project_name_mismatch"
        return project, None, None
    if not estimate_name:
        return None, "unresolved", "estimate_project_missing"
    candidates = projects_by_company_name.get((company_id, estimate_name), [])
    if not candidates:
        return None, "unresolved", "estimate_project_not_found"
    if len(candidates) > 1:
        return None, "ambiguous", "estimate_project_ambiguous"
    return candidates[0], None, None


def _validate_included_estimate(candidate, included_estimate_id, estimates_by_id, projects_by_id, projects_by_company_name):
    included_id = _positive_int(included_estimate_id)
    if not included_id:
        return None
    included_project, status, reason = _resolve_estimate_project(
        included_id,
        estimates_by_id,
        projects_by_id,
        projects_by_company_name,
    )
    if status:
        return status, "included_" + reason
    if (
        _positive_int(included_project.get("projectId")) != _positive_int(candidate.get("projectId"))
        or _positive_int(included_project.get("companyId")) != _positive_int(candidate.get("companyId"))
    ):
        return "mismatched", "included_estimate_owner_mismatch"
    return None


def _classify_change(row, projects_by_id, projects_by_name, projects_by_company_name, estimates_by_id):
    item = dict(row or {})
    stored_project_id = _positive_int(item.get("project_id"))
    stored_company_id = _positive_int(item.get("company_id"))
    estimate_id = _positive_int(item.get("estimate_id"))
    project_name = str(item.get("project_name") or "").strip()

    if bool(stored_project_id) != bool(stored_company_id):
        return _ownership_result(item, "mismatched", "partial_stored_owner")

    source = None
    candidate = None
    final_status = "ready"
    final_reason = ""
    if stored_project_id and stored_company_id:
        candidate = projects_by_id.get(stored_project_id)
        if not candidate:
            return _ownership_result(item, "unresolved", "stored_project_not_found")
        if _positive_int(candidate.get("companyId")) != stored_company_id:
            return _ownership_result(item, "mismatched", "stored_project_company_mismatch")
        if project_name and project_name != str(candidate.get("projectName") or "").strip():
            return _ownership_result(item, "mismatched", "row_project_name_mismatch", candidate, "stored")
        source = "stored"
        final_status = "stored"
        final_reason = "stored_owner"

    if estimate_id:
        estimate_project, status, reason = _resolve_estimate_project(
            estimate_id,
            estimates_by_id,
            projects_by_id,
            projects_by_company_name,
        )
        if status:
            return _ownership_result(item, status, reason, candidate, source)
        if candidate and (
            _positive_int(candidate.get("projectId")) != _positive_int(estimate_project.get("projectId"))
            or _positive_int(candidate.get("companyId")) != _positive_int(estimate_project.get("companyId"))
        ):
            return _ownership_result(item, "mismatched", "estimate_owner_mismatch", candidate, source)
        candidate = candidate or estimate_project
        source = source or "estimate_id"
        final_reason = final_reason or "estimate_owner"
    elif not candidate:
        if not project_name:
            return _ownership_result(item, "unresolved", "missing_project_identity")
        candidates = projects_by_name.get(project_name, [])
        if not candidates:
            return _ownership_result(item, "unresolved", "project_name_not_found")
        if len(candidates) > 1:
            return _ownership_result(item, "ambiguous", "project_name_ambiguous")
        candidate = candidates[0]
        source = "unique_project_name"
        final_reason = "unique_project_name"

    if project_name and project_name != str(candidate.get("projectName") or "").strip():
        return _ownership_result(item, "mismatched", "row_project_name_mismatch", candidate, source)

    included_error = _validate_included_estimate(
        candidate,
        item.get("included_estimate_id"),
        estimates_by_id,
        projects_by_id,
        projects_by_company_name,
    )
    if included_error:
        status, reason = included_error
        return _ownership_result(item, status, reason, candidate, source)
    return _ownership_result(item, final_status, final_reason, candidate, source)


def collect_estimate_change_ownership(cur):
    cur.execute(
        """SELECT column_name
             FROM information_schema.columns
            WHERE table_schema=current_schema()
              AND table_name='unexpected_works'
            ORDER BY ordinal_position"""
    )
    columns = {
        str(_row_value(row, "column_name", 0) or "").strip()
        for row in (cur.fetchall() or [])
    }
    company_select = "uw.company_id" if "company_id" in columns else "NULL::INT"
    project_select = "uw.project_id" if "project_id" in columns else "NULL::INT"
    estimate_select = "uw.estimate_id" if "estimate_id" in columns else "NULL::INT"
    included_select = (
        "uw.included_in_estimate_id"
        if "included_in_estimate_id" in columns
        else "NULL::INT"
    )
    project_name_select = "uw.project_name" if "project_name" in columns else "NULL::TEXT"
    cur.execute(
        f"""SELECT uw.id AS change_id,
                   {project_name_select} AS project_name,
                   {estimate_select} AS estimate_id,
                   {included_select} AS included_estimate_id,
                   {project_select} AS project_id,
                   {company_select} AS company_id
              FROM unexpected_works uw
             ORDER BY uw.id"""
    )
    change_rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id AS project_id,company_id,name AS project_name FROM projects ORDER BY id")
    projects = [_project_record(row) for row in (cur.fetchall() or [])]
    cur.execute(
        """SELECT id AS estimate_id,company_id,project_id,project_name
             FROM estimates
            ORDER BY id"""
    )
    estimates = [_estimate_record(row) for row in (cur.fetchall() or [])]

    projects_by_id = {
        project["projectId"]: project
        for project in projects
        if project["projectId"]
    }
    projects_by_name = defaultdict(list)
    projects_by_company_name = defaultdict(list)
    for project in projects:
        projects_by_name[project["projectName"]].append(project)
        projects_by_company_name[(project["companyId"], project["projectName"])].append(project)
    estimates_by_id = {
        estimate["estimateId"]: estimate
        for estimate in estimates
        if estimate["estimateId"]
    }

    classified = [
        _classify_change(
            row,
            projects_by_id,
            projects_by_name,
            projects_by_company_name,
            estimates_by_id,
        )
        for row in change_rows
    ]
    return columns, classified


def build_estimate_change_report_from_classified(columns, classified):
    status_counts = {
        status: sum(1 for item in classified if item["status"] == status)
        for status in ("stored", "ready", "ambiguous", "unresolved", "mismatched")
    }
    total_rows = len(classified)
    report_consistent = total_rows == sum(status_counts.values())
    ready_rows = [item for item in classified if item["status"] == "ready"]
    review_rows = [
        item
        for item in classified
        if item["status"] in ("ambiguous", "unresolved", "mismatched")
    ]
    ready_by_company = defaultdict(int)
    for item in ready_rows:
        company_id = _positive_int(item.get("proposedCompanyId"))
        if company_id:
            ready_by_company[str(company_id)] += 1

    def ready_view(item):
        return {
            "changeId": item["changeId"],
            "proposedCompanyId": item["proposedCompanyId"],
            "proposedProjectId": item["proposedProjectId"],
            "source": item["source"],
        }

    def review_view(item):
        return {
            "changeId": item["changeId"],
            "status": item["status"],
            "reason": item["reason"],
            "estimateId": item["estimateId"],
            "includedEstimateId": item["includedEstimateId"],
            "storedCompanyId": item["storedCompanyId"],
            "storedProjectId": item["storedProjectId"],
            "proposedCompanyId": item["proposedCompanyId"],
            "proposedProjectId": item["proposedProjectId"],
        }

    return {
        "ok": True,
        "dryRun": True,
        "table": "unexpected_works",
        "writesAttempted": 0,
        "columns": {
            "companyId": "company_id" in columns,
            "projectId": "project_id" in columns,
        },
        "readyForBackfill": (
            report_consistent
            and not status_counts["ambiguous"]
            and not status_counts["unresolved"]
            and not status_counts["mismatched"]
        ),
        "reportConsistent": report_consistent,
        "summary": {
            "totalRows": total_rows,
            "storedRows": status_counts["stored"],
            "legacyRows": total_rows - status_counts["stored"],
            "ready": status_counts["ready"],
            "ambiguous": status_counts["ambiguous"],
            "unresolved": status_counts["unresolved"],
            "mismatched": status_counts["mismatched"],
        },
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "readyPreview": [ready_view(item) for item in ready_rows[:PREVIEW_LIMIT]],
        "readyPreviewTruncated": len(ready_rows) > PREVIEW_LIMIT,
        "needsReview": [review_view(item) for item in review_rows[:PREVIEW_LIMIT]],
        "reviewListTruncated": len(review_rows) > PREVIEW_LIMIT,
    }


def build_estimate_change_ownership_report(cur):
    columns, classified = collect_estimate_change_ownership(cur)
    return build_estimate_change_report_from_classified(columns, classified)


def run_estimate_change_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_estimate_change_ownership_report(cur)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db

    report = run_estimate_change_ownership_report(get_db)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
