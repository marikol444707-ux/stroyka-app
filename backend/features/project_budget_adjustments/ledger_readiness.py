"""Bounded, ID-only E6 immutable receipt-ledger readiness audit."""

from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .plan import BudgetAdjustmentPlanError, build_budget_adjustment_plan


MAX_RECEIPT_ROWS = 100000
MAX_ISSUES = 100
LEADERSHIP_ROLES = {"директор", "зам_директора"}

RECEIPT_LEDGER_SELECT = """
    SELECT receipt.id,receipt.company_id,receipt.project_id,
           receipt.reconciliation_id,receipt.base_estimate_id,
           receipt.next_estimate_id,receipt.project_budget_before,
           receipt.estimate_base_total,receipt.estimate_next_total,
           receipt.adjustment_amount,receipt.project_budget_after,
           receipt.plan_sha256,receipt.approved_by_user_id,
           receipt.approved_by_name,receipt.approved_by_role,
           receipt.approved_at,receipt.created_at,
           project.id AS current_project_id,
           project.company_id AS current_project_company_id,
           reconciliation.id AS current_reconciliation_id,
           reconciliation.base_estimate_id AS current_base_estimate_id,
           reconciliation.next_estimate_id AS current_next_estimate_id,
           base_estimate.id AS current_base_id,
           base_estimate.company_id AS current_base_company_id,
           base_estimate.project_id AS current_base_project_id,
           next_estimate.id AS current_next_id,
           next_estimate.company_id AS current_next_company_id,
           next_estimate.project_id AS current_next_project_id,
           approved_user.id AS current_approved_user_id
      FROM public.project_budget_adjustments receipt
      LEFT JOIN public.projects project ON project.id=receipt.project_id
      LEFT JOIN public.estimate_reconciliations reconciliation
        ON reconciliation.id=receipt.reconciliation_id
      LEFT JOIN public.estimates base_estimate
        ON base_estimate.id=receipt.base_estimate_id
      LEFT JOIN public.estimates next_estimate
        ON next_estimate.id=receipt.next_estimate_id
      LEFT JOIN public.users approved_user
        ON approved_user.id=receipt.approved_by_user_id
"""


def _positive_id(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _aware_timestamp(value):
    return bool(
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _exact_money_text(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.quantize(Decimal("0.01")):
        return None
    return format(number, ".2f")


class _IssueCollector:
    def __init__(self, max_issues):
        self.max_issues = max(0, int(max_issues))
        self.count = 0
        self.preview = []
        self.reasons = Counter()

    def add(self, reason_code, row=None):
        self.count += 1
        self.reasons[reason_code] += 1
        if len(self.preview) >= self.max_issues:
            return
        issue = {"reasonCode": reason_code}
        if row is not None:
            issue.update({
                "receiptId": _positive_id(row.get("id")),
                "projectId": _positive_id(row.get("project_id")),
                "reconciliationId": _positive_id(
                    row.get("reconciliation_id")
                ),
            })
        self.preview.append(issue)


def _receipt_plan(row, issues):
    try:
        plan = build_budget_adjustment_plan({
            "reconciliationId": row.get("reconciliation_id"),
            "companyId": row.get("company_id"),
            "projectId": row.get("project_id"),
            "baseEstimateId": row.get("base_estimate_id"),
            "nextEstimateId": row.get("next_estimate_id"),
            "projectBudgetBefore": row.get("project_budget_before"),
            "estimateBaseTotal": row.get("estimate_base_total"),
            "estimateNextTotal": row.get("estimate_next_total"),
        })
    except BudgetAdjustmentPlanError:
        issues.add("budget_adjustment_receipt_plan_invalid", row)
        return None

    if (
        plan.get("readyForApproval") is not True
        or plan.get("noOp") is not False
    ):
        issues.add("budget_adjustment_receipt_plan_invalid", row)
    if (
        _exact_money_text(row.get("adjustment_amount"))
        != plan.get("adjustmentAmount")
        or _exact_money_text(row.get("project_budget_after"))
        != plan.get("projectBudgetAfter")
    ):
        issues.add("budget_adjustment_receipt_equation_mismatch", row)
    if row.get("plan_sha256") != plan.get("planSha256"):
        issues.add("budget_adjustment_receipt_plan_hash_mismatch", row)
    return plan


def _validate_links(row, issues):
    company_id = row.get("company_id")
    project_id = row.get("project_id")
    if row.get("current_project_id") is None:
        issues.add("budget_adjustment_receipt_project_missing", row)
    elif (
        row.get("current_project_id") != project_id
        or row.get("current_project_company_id") != company_id
    ):
        issues.add("budget_adjustment_receipt_project_owner_mismatch", row)

    if row.get("current_reconciliation_id") is None:
        issues.add("budget_adjustment_receipt_reconciliation_missing", row)
    elif (
        row.get("current_reconciliation_id") != row.get("reconciliation_id")
        or row.get("current_base_estimate_id") != row.get("base_estimate_id")
        or row.get("current_next_estimate_id") != row.get("next_estimate_id")
    ):
        issues.add("budget_adjustment_receipt_base_source_mismatch", row)

    if row.get("current_base_id") is None:
        issues.add("budget_adjustment_receipt_base_estimate_missing", row)
    elif (
        row.get("current_base_id") != row.get("base_estimate_id")
        or row.get("current_base_company_id") != company_id
        or row.get("current_base_project_id") != project_id
    ):
        issues.add("budget_adjustment_receipt_base_owner_mismatch", row)

    if row.get("current_next_id") is None:
        issues.add("budget_adjustment_receipt_next_estimate_missing", row)
    elif (
        row.get("current_next_id") != row.get("next_estimate_id")
        or row.get("current_next_company_id") != company_id
        or row.get("current_next_project_id") != project_id
    ):
        issues.add("budget_adjustment_receipt_next_owner_mismatch", row)

    if row.get("current_approved_user_id") != row.get("approved_by_user_id"):
        issues.add("budget_adjustment_receipt_user_missing", row)


def build_receipt_ledger_readiness(rows, *, max_issues=MAX_ISSUES):
    """Validate immutable receipt evidence without returning money or names."""

    normalized = [dict(row or {}) for row in (rows or [])]
    issues = _IssueCollector(max_issues)
    reconciliation_counts = Counter()
    hash_counts = Counter()
    project_ids = set()
    valid_receipts = 0

    for row in normalized:
        before_count = issues.count
        ids = (
            row.get("id"), row.get("company_id"), row.get("project_id"),
            row.get("reconciliation_id"), row.get("base_estimate_id"),
            row.get("next_estimate_id"), row.get("approved_by_user_id"),
        )
        if any(_positive_id(value) is None for value in ids):
            issues.add("budget_adjustment_receipt_identity_invalid", row)
        if row.get("base_estimate_id") == row.get("next_estimate_id"):
            issues.add("budget_adjustment_receipt_identity_invalid", row)

        name = row.get("approved_by_name")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name.strip()) > 255
            or row.get("approved_by_role") not in LEADERSHIP_ROLES
        ):
            issues.add("budget_adjustment_receipt_actor_invalid", row)
        approved_at = row.get("approved_at")
        created_at = row.get("created_at")
        if (
            not _aware_timestamp(approved_at)
            or not _aware_timestamp(created_at)
            or created_at < approved_at
        ):
            issues.add("budget_adjustment_receipt_timestamp_invalid", row)

        _receipt_plan(row, issues)
        _validate_links(row, issues)

        reconciliation_id = _positive_id(row.get("reconciliation_id"))
        if reconciliation_id is not None:
            reconciliation_counts[reconciliation_id] += 1
            if reconciliation_counts[reconciliation_id] > 1:
                issues.add("budget_adjustment_duplicate_reconciliation", row)
        plan_sha256 = row.get("plan_sha256")
        if isinstance(plan_sha256, str):
            hash_counts[plan_sha256] += 1
            if hash_counts[plan_sha256] > 1:
                issues.add("budget_adjustment_duplicate_plan_hash", row)
        project_id = _positive_id(row.get("project_id"))
        if project_id is not None:
            project_ids.add(project_id)
        if issues.count == before_count:
            valid_receipts += 1

    duplicate_reconciliations = sum(
        count - 1 for count in reconciliation_counts.values() if count > 1
    )
    duplicate_hashes = sum(
        count - 1 for count in hash_counts.values() if count > 1
    )
    summary = {
        "receiptsTotal": len(normalized),
        "validReceipts": valid_receipts,
        "projectsWithReceipts": len(project_ids),
        "uniqueReconciliations": len(reconciliation_counts),
        "duplicateReconciliations": duplicate_reconciliations,
        "duplicatePlanHashes": duplicate_hashes,
    }
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "scanComplete": True,
        "ledgerReady": issues.count == 0,
        "validReceipts": valid_receipts,
        "summary": summary,
        "issueCount": issues.count,
        "reasonCounts": dict(sorted(issues.reasons.items())),
        "issues": issues.preview,
        "issuesTruncated": issues.count > len(issues.preview),
    }


def _scan_limit_report():
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "scanComplete": False,
        "ledgerReady": False,
        "validReceipts": 0,
        "summary": {},
        "issueCount": 1,
        "reasonCounts": {
            "budget_adjustment_receipt_scan_limit_exceeded": 1,
        },
        "issues": [{
            "reasonCode": "budget_adjustment_receipt_scan_limit_exceeded",
        }],
        "issuesTruncated": False,
    }


def collect_receipt_ledger_readiness(
    cur,
    *,
    max_receipt_rows=MAX_RECEIPT_ROWS,
):
    """Read one hard-capped metadata/receipt projection and classify it."""

    limit = max(0, int(max_receipt_rows))
    cur.execute(RECEIPT_LEDGER_SELECT + " ORDER BY receipt.id LIMIT %s", (
        limit + 1,
    ))
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    if len(rows) > limit:
        return _scan_limit_report()
    return build_receipt_ledger_readiness(rows)


__all__ = [
    "MAX_ISSUES",
    "MAX_RECEIPT_ROWS",
    "RECEIPT_LEDGER_SELECT",
    "build_receipt_ledger_readiness",
    "collect_receipt_ledger_readiness",
]
