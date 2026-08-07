"""Pure deterministic E6 project-budget adjustment plan construction."""

import hashlib
import json
from decimal import Decimal, InvalidOperation

from .audit import MAX_PROJECT_BUDGET, MONEY_QUANTUM

PLAN_VERSION = 1
MAX_MONEY = MAX_PROJECT_BUDGET
SOURCE_FIELDS = {
    "reconciliationId",
    "companyId",
    "projectId",
    "baseEstimateId",
    "nextEstimateId",
    "projectBudgetBefore",
    "estimateBaseTotal",
    "estimateNextTotal",
}


class BudgetAdjustmentPlanError(ValueError):
    """Fixed-code validation error safe to map at the API boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _canonical_money(value, code):
    if value is None or isinstance(value, bool):
        raise BudgetAdjustmentPlanError(code)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise BudgetAdjustmentPlanError(code)
    if (
        not number.is_finite()
        or number < 0
        or number >= MAX_MONEY
        or number != number.quantize(MONEY_QUANTUM)
    ):
        raise BudgetAdjustmentPlanError(code)
    normalized = number.quantize(MONEY_QUANTUM)
    return Decimal("0.00") if normalized == 0 else normalized


def _money_text(value):
    normalized = Decimal("0.00") if value == 0 else value
    return format(normalized, ".2f")


def calculate_plan_sha256(plan):
    canonical = dict(plan or {})
    canonical.pop("planSha256", None)
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_budget_adjustment_plan(source):
    """Validate authoritative evidence and derive an exact immutable plan."""

    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise BudgetAdjustmentPlanError("budget_adjustment_context_invalid")
    ids = {
        key: _positive_id(source.get(key))
        for key in (
            "reconciliationId",
            "companyId",
            "projectId",
            "baseEstimateId",
            "nextEstimateId",
        )
    }
    if any(value is None for value in ids.values()):
        raise BudgetAdjustmentPlanError("budget_adjustment_identity_invalid")
    if ids["baseEstimateId"] == ids["nextEstimateId"]:
        raise BudgetAdjustmentPlanError("budget_adjustment_source_invalid")

    before = _canonical_money(
        source.get("projectBudgetBefore"),
        "budget_adjustment_project_budget_invalid",
    )
    base_total = _canonical_money(
        source.get("estimateBaseTotal"),
        "budget_adjustment_base_total_invalid",
    )
    next_total = _canonical_money(
        source.get("estimateNextTotal"),
        "budget_adjustment_next_total_invalid",
    )
    adjustment = next_total - base_total
    after = before + adjustment
    if after < 0:
        raise BudgetAdjustmentPlanError("budget_adjustment_negative_after")
    if after >= MAX_MONEY:
        raise BudgetAdjustmentPlanError("budget_adjustment_after_out_of_range")

    no_op = adjustment == 0
    plan = {
        "planVersion": PLAN_VERSION,
        **ids,
        "projectBudgetBefore": _money_text(before),
        "estimateBaseTotal": _money_text(base_total),
        "estimateNextTotal": _money_text(next_total),
        "adjustmentAmount": _money_text(adjustment),
        "projectBudgetAfter": _money_text(after),
        "noOp": no_op,
        "readyForApproval": not no_op,
        "blockers": ["budget_adjustment_zero_delta"] if no_op else [],
    }
    plan["planSha256"] = calculate_plan_sha256(plan)
    return plan


__all__ = [
    "BudgetAdjustmentPlanError",
    "MAX_MONEY",
    "MONEY_QUANTUM",
    "PLAN_VERSION",
    "build_budget_adjustment_plan",
    "calculate_plan_sha256",
]
