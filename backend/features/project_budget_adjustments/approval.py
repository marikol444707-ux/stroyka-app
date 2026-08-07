"""Fail-closed E6 exact-hash budget-adjustment approval kernel."""

import re


PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEADERSHIP_ROLES = {"директор", "зам_директора"}


class BudgetAdjustmentApprovalError(RuntimeError):
    """Fixed-code approval failure safe to map at a later HTTP boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _positive_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _validated_actor(actor, company_id):
    actor = dict(actor or {})
    actor_id = _positive_int(actor.get("id") or actor.get("userId"))
    name = str(actor.get("name") or "").strip()
    role = str(actor.get("role") or "").strip()
    company_claims = [
        actor[key] for key in ("companyId", "company_id") if key in actor
    ]
    company_ids = [_positive_int(value) for value in company_claims]
    if (
        actor_id is None
        or not name
        or len(name) > 255
        or not company_ids
        or any(value is None for value in company_ids)
    ):
        raise BudgetAdjustmentApprovalError("budget_adjustment_actor_invalid")
    if set(company_ids) != {company_id} or role not in LEADERSHIP_ROLES:
        raise BudgetAdjustmentApprovalError("budget_adjustment_role_forbidden")
    return {"id": actor_id, "name": name, "role": role}


def apply_budget_adjustment(
    cur,
    *,
    reconciliation_id,
    company_id,
    expected_plan_sha256,
    actor,
):
    """Apply one exact plan; caller owns the surrounding transaction."""

    reconciliation_id = _positive_int(reconciliation_id)
    company_id = _positive_int(company_id)
    if reconciliation_id is None or company_id is None:
        raise BudgetAdjustmentApprovalError("budget_adjustment_identity_invalid")
    if not isinstance(expected_plan_sha256, str) or not PLAN_SHA256_RE.fullmatch(
        expected_plan_sha256
    ):
        raise BudgetAdjustmentApprovalError("budget_adjustment_plan_hash_invalid")
    _validated_actor(actor, company_id)
    raise BudgetAdjustmentApprovalError("budget_adjustment_not_found")


__all__ = ["BudgetAdjustmentApprovalError", "apply_budget_adjustment"]
