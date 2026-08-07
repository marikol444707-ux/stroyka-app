"""Pure E6 project-budget and approved-source readiness classification."""

from collections import Counter
from decimal import Decimal, InvalidOperation


DEFAULT_PREVIEW_LIMIT = 100
MAX_PROJECT_BUDGET = Decimal("1000000000000.00")
MONEY_QUANTUM = Decimal("0.01")


def _positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _money(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _project_budget_reason(value):
    if value is None:
        return "project_budget_missing"
    number = _money(value)
    if number is None:
        return "project_budget_non_finite"
    if number < 0:
        return "project_budget_negative"
    if number >= MAX_PROJECT_BUDGET:
        return "project_budget_out_of_range"
    if number != number.quantize(MONEY_QUANTUM):
        return "project_budget_precision_exceeds_scale"
    return None


def _valid_total(value):
    number = _money(value)
    return bool(
        number is not None
        and number >= 0
        and number < MAX_PROJECT_BUDGET
        and number == number.quantize(MONEY_QUANTUM)
    )


def _text(value):
    return str(value or "").strip()


def _package(value):
    return _text(value) or "Основная"


def _kind(value):
    return _text(value) or "Заказчик"


def _row_sort_key(row, key):
    value = _positive_id((row or {}).get(key))
    return (value is None, value or 0)


class _Issues:
    def __init__(self, maximum):
        self.maximum = max(0, int(maximum))
        self.count = 0
        self.reason_counts = Counter()
        self.preview = []

    def add(self, reason_code, row):
        self.count += 1
        self.reason_counts[reason_code] += 1
        if len(self.preview) >= self.maximum:
            return
        item = {"reasonCode": reason_code}
        for source, target in (
            ("company_id", "companyId"),
            ("project_id", "projectId"),
            ("reconciliation_id", "reconciliationId"),
            ("base_estimate_id", "baseEstimateId"),
            ("next_estimate_id", "nextEstimateId"),
        ):
            value = _positive_id((row or {}).get(source))
            if value is not None:
                item[target] = value
        self.preview.append(item)


def _project_reason(row):
    if _positive_id(row.get("project_id")) is None:
        return "project_id_invalid"
    if _positive_id(row.get("company_id")) is None:
        return "project_company_id_invalid"
    return _project_budget_reason(row.get("project_budget"))


def _approved_source_reason(row, valid_projects):
    for key, reason in (
        ("reconciliation_id", "reconciliation_id_invalid"),
        ("base_estimate_id", "reconciliation_base_estimate_id_invalid"),
        ("next_estimate_id", "reconciliation_next_estimate_id_invalid"),
    ):
        if _positive_id(row.get(key)) is None:
            return reason

    company_id = _positive_id(row.get("company_id"))
    project_id = _positive_id(row.get("project_id"))
    owner = (company_id, project_id)
    if (
        company_id is None
        or project_id is None
        or owner not in valid_projects
        or owner != (
            _positive_id(row.get("base_company_id")),
            _positive_id(row.get("base_project_id")),
        )
        or owner != (
            _positive_id(row.get("next_company_id")),
            _positive_id(row.get("next_project_id")),
        )
    ):
        return "reconciliation_owner_mismatch"

    if {
        _kind(row.get("smeta_type")),
        _kind(row.get("base_smeta_type")),
        _kind(row.get("next_smeta_type")),
    } != {"Заказчик"}:
        return "reconciliation_type_not_customer"
    if len({
        _package(row.get("work_package")),
        _package(row.get("base_work_package")),
        _package(row.get("next_work_package")),
    }) != 1:
        return "reconciliation_package_mismatch"
    if _text(row.get("next_status")) != "Активная":
        return "reconciliation_next_not_active"
    if not _valid_total(row.get("base_total")):
        return "reconciliation_base_total_invalid"
    if not _valid_total(row.get("next_total")):
        return "reconciliation_next_total_invalid"
    return None


def build_budget_adjustment_readiness(
    project_rows,
    reconciliation_rows,
    *,
    max_issues=DEFAULT_PREVIEW_LIMIT,
    max_candidates=DEFAULT_PREVIEW_LIMIT,
):
    """Return a bounded ID-only report without reading or mutating a database."""

    projects = [dict(row or {}) for row in (project_rows or [])]
    reconciliations = [dict(row or {}) for row in (reconciliation_rows or [])]
    issues = _Issues(max_issues)
    valid_projects = set()
    budget_issue_count = 0
    for row in sorted(projects, key=lambda item: _row_sort_key(item, "project_id")):
        reason = _project_reason(row)
        if reason:
            issues.add(reason, row)
            budget_issue_count += 1
            continue
        valid_projects.add((row["company_id"], row["project_id"]))

    approved = [
        row for row in reconciliations
        if _text(row.get("status")) == "Утверждена"
    ]
    candidates = []
    source_issue_count = 0
    for row in sorted(
        approved,
        key=lambda item: _row_sort_key(item, "reconciliation_id"),
    ):
        reason = _approved_source_reason(row, valid_projects)
        if reason:
            issues.add(reason, row)
            source_issue_count += 1
            continue
        candidates.append({
            "reconciliationId": row["reconciliation_id"],
            "companyId": row["company_id"],
            "projectId": row["project_id"],
            "baseEstimateId": row["base_estimate_id"],
            "nextEstimateId": row["next_estimate_id"],
        })

    candidate_limit = max(0, int(max_candidates))
    budget_ready = budget_issue_count == 0
    source_ready = source_issue_count == 0
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "dataReady": budget_ready and source_ready,
        "budgetDataReady": budget_ready,
        "approvedSourcesReady": source_ready,
        "summary": {
            "projectsTotal": len(projects),
            "validProjectBudgets": len(valid_projects),
            "reconciliationsTotal": len(reconciliations),
            "approvedReconciliations": len(approved),
            "readyApprovedReconciliations": len(candidates),
        },
        "issueCount": issues.count,
        "reasonCounts": dict(sorted(issues.reason_counts.items())),
        "issues": issues.preview,
        "issuesTruncated": issues.count > len(issues.preview),
        "readyCandidates": candidates[:candidate_limit],
        "readyCandidatesTruncated": len(candidates) > candidate_limit,
    }


__all__ = [
    "DEFAULT_PREVIEW_LIMIT",
    "MAX_PROJECT_BUDGET",
    "MONEY_QUANTUM",
    "build_budget_adjustment_readiness",
]
