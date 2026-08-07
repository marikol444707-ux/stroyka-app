"""Pure E5 ownership classification for active material-control estimates."""

from collections import Counter, defaultdict


DEFAULT_PREVIEW_LIMIT = 100


def _positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _id_reason(value, prefix):
    if value is None:
        return prefix + "_missing"
    return prefix + "_invalid" if _positive_id(value) is None else None


def _text(value):
    return str(value or "").strip()


def _row_sort_key(row, id_key):
    value = _positive_id((row or {}).get(id_key))
    return (value is None, value or 0)


class _IssueCollector:
    def __init__(self, maximum):
        self.maximum = max(0, int(maximum))
        self.count = 0
        self.preview = []
        self.reason_counts = Counter()

    def add(self, reason_code, **ids):
        self.count += 1
        self.reason_counts[reason_code] += 1
        if len(self.preview) >= self.maximum:
            return
        item = {"reasonCode": reason_code}
        for key in ("companyId", "projectId", "estimateId"):
            value = _positive_id(ids.get(key))
            if value is not None:
                item[key] = value
        estimate_ids = sorted({
            value for value in (ids.get("estimateIds") or [])
            if _positive_id(value) is not None
        })
        if estimate_ids:
            item["estimateIds"] = estimate_ids
        self.preview.append(item)


def build_owner_readiness(
    project_rows,
    estimate_rows,
    *,
    max_issues=DEFAULT_PREVIEW_LIMIT,
    max_collision_preview=DEFAULT_PREVIEW_LIMIT,
):
    """Classify stored owners without exposing names or estimate contents."""

    issues = _IssueCollector(max_issues)
    projects_by_id = {}
    active_projects = []
    for raw in sorted(project_rows or [], key=lambda row: _row_sort_key(row, "project_id")):
        row = dict(raw or {})
        project_id = _positive_id(row.get("project_id"))
        if project_id is not None:
            projects_by_id[project_id] = row
        if bool(row.get("archived")):
            continue
        active_projects.append(row)
        id_issue = _id_reason(row.get("project_id"), "active_project_id")
        if id_issue:
            issues.add(id_issue, projectId=row.get("project_id"))
        company_issue = _id_reason(
            row.get("company_id"), "active_project_company_id"
        )
        if company_issue:
            issues.add(
                company_issue,
                projectId=row.get("project_id"),
                companyId=row.get("company_id"),
            )

    collision_rows = defaultdict(list)
    for row in active_projects:
        project_id = _positive_id(row.get("project_id"))
        company_id = _positive_id(row.get("company_id"))
        project_name = _text(row.get("project_name"))
        if project_id and company_id and project_name:
            collision_rows[project_name].append((project_id, company_id))

    collisions = []
    collision_counts = Counter()
    for members in collision_rows.values():
        if len(members) < 2:
            continue
        project_ids = sorted({project_id for project_id, _company_id in members})
        if len(project_ids) < 2:
            continue
        company_ids = sorted({company_id for _project_id, company_id in members})
        reason = (
            "project_name_cross_company_collision"
            if len(company_ids) > 1
            else "project_name_same_company_ambiguous"
        )
        collision_counts[reason] += 1
        collisions.append({
            "reasonCode": reason,
            "projectIds": project_ids,
            "companyIds": company_ids,
        })
    collisions.sort(key=lambda item: tuple(item["projectIds"]))

    valid_estimates = []
    for raw in sorted(estimate_rows or [], key=lambda row: _row_sort_key(row, "estimate_id")):
        row = dict(raw or {})
        estimate_id = _positive_id(row.get("estimate_id"))
        company_id = _positive_id(row.get("company_id"))
        project_id = _positive_id(row.get("project_id"))
        failed = False
        for value, prefix in (
            (row.get("estimate_id"), "active_estimate_id"),
            (row.get("company_id"), "active_estimate_company_id"),
            (row.get("project_id"), "active_estimate_project_id"),
        ):
            reason = _id_reason(value, prefix)
            if reason:
                issues.add(
                    reason,
                    estimateId=row.get("estimate_id"),
                    companyId=row.get("company_id"),
                    projectId=row.get("project_id"),
                )
                failed = True
        if failed:
            continue

        parent = projects_by_id.get(project_id)
        if parent is None:
            issues.add(
                "active_estimate_project_not_found",
                estimateId=estimate_id,
                companyId=company_id,
                projectId=project_id,
            )
            continue
        if bool(parent.get("archived")):
            issues.add(
                "active_estimate_project_archived",
                estimateId=estimate_id,
                companyId=company_id,
                projectId=project_id,
            )
            continue
        parent_company_id = _positive_id(parent.get("company_id"))
        if parent_company_id is None:
            issues.add(
                "active_estimate_project_company_id_invalid",
                estimateId=estimate_id,
                companyId=company_id,
                projectId=project_id,
            )
            continue
        if parent_company_id != company_id:
            issues.add(
                "active_estimate_company_mismatch",
                estimateId=estimate_id,
                companyId=company_id,
                projectId=project_id,
            )
            continue
        estimate_name = _text(row.get("project_name"))
        if estimate_name and estimate_name != _text(parent.get("project_name")):
            issues.add(
                "active_estimate_project_name_mismatch",
                estimateId=estimate_id,
                companyId=company_id,
                projectId=project_id,
            )
            continue
        valid_estimates.append(row)

    estimate_scopes = defaultdict(list)
    for row in valid_estimates:
        scope = (
            _positive_id(row.get("company_id")),
            _positive_id(row.get("project_id")),
            _text(row.get("estimate_kind")) or "Заказчик",
            _text(row.get("work_package")) or "Основная",
        )
        estimate_scopes[scope].append(_positive_id(row.get("estimate_id")))
    duplicate_groups = 0
    for (company_id, project_id, _kind, _package), estimate_ids in sorted(
        estimate_scopes.items(), key=lambda item: item[0]
    ):
        if len(estimate_ids) < 2:
            continue
        duplicate_groups += 1
        issues.add(
            "active_estimate_scope_ambiguous",
            companyId=company_id,
            projectId=project_id,
            estimateIds=estimate_ids,
        )

    collision_total = len(collisions)
    collision_limit = max(0, int(max_collision_preview))
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "dataReady": issues.count == 0,
        "summary": {
            "projectsTotal": len(project_rows or []),
            "activeProjects": len(active_projects),
            "activeEstimates": len(estimate_rows or []),
            "validActiveEstimates": len(valid_estimates),
            "duplicateActiveScopes": duplicate_groups,
            "nameCollisionGroups": collision_total,
            "crossCompanyNameCollisionGroups": collision_counts[
                "project_name_cross_company_collision"
            ],
            "sameCompanyNameCollisionGroups": collision_counts[
                "project_name_same_company_ambiguous"
            ],
        },
        "issueCount": issues.count,
        "reasonCounts": dict(sorted(issues.reason_counts.items())),
        "issues": issues.preview,
        "issuesTruncated": issues.count > len(issues.preview),
        "nameCollisions": collisions[:collision_limit],
        "nameCollisionsTruncated": collision_total > collision_limit,
    }


__all__ = ["DEFAULT_PREVIEW_LIMIT", "build_owner_readiness"]
