"""Fail-closed E6 exact-hash budget-adjustment approval kernel."""

import re

from .preview import BudgetAdjustmentPreviewError
from .preview_service import build_budget_adjustment_preview


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
    return {
        "id": actor_id,
        "companyId": company_id,
        "name": name,
        "role": role,
    }


def _receipt_result(row, *, idempotent):
    row = dict(row or {})
    fields = {
        "id": "id",
        "companyId": "company_id",
        "projectId": "project_id",
        "reconciliationId": "reconciliation_id",
        "baseEstimateId": "base_estimate_id",
        "nextEstimateId": "next_estimate_id",
        "projectBudgetBefore": "project_budget_before",
        "estimateBaseTotal": "estimate_base_total",
        "estimateNextTotal": "estimate_next_total",
        "adjustmentAmount": "adjustment_amount",
        "projectBudgetAfter": "project_budget_after",
        "planSha256": "plan_sha256",
        "approvedByUserId": "approved_by_user_id",
        "approvedByName": "approved_by_name",
        "approvedByRole": "approved_by_role",
        "approvedAt": "approved_at",
        "createdAt": "created_at",
    }
    result = {public: row.get(stored) for public, stored in fields.items()}
    for key in (
        "projectBudgetBefore", "estimateBaseTotal", "estimateNextTotal",
        "adjustmentAmount", "projectBudgetAfter",
    ):
        result[key] = str(result[key]) if result[key] is not None else None
    result["idempotent"] = bool(idempotent)
    return result


def apply_budget_adjustment(
    cur,
    *,
    reconciliation_id,
    company_id,
    expected_plan_sha256,
    actor,
    lock_source=None,
    authorize_actor=None,
    load_receipt=None,
    build_preview=build_budget_adjustment_preview,
    insert_receipt=None,
    update_budget=None,
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
    validated_actor = _validated_actor(actor, company_id)
    if any(
        boundary is None
        for boundary in (
            lock_source, authorize_actor, load_receipt,
            insert_receipt, update_budget,
        )
    ):
        from .approval_storage import (
            insert_budget_adjustment_receipt,
            load_authorized_budget_actor,
            load_budget_adjustment_receipt,
            lock_budget_adjustment_source,
            update_project_budget,
        )
        lock_source = lock_source or lock_budget_adjustment_source
        authorize_actor = authorize_actor or load_authorized_budget_actor
        load_receipt = load_receipt or load_budget_adjustment_receipt
        insert_receipt = insert_receipt or insert_budget_adjustment_receipt
        update_budget = update_budget or update_project_budget

    source = lock_source(cur, reconciliation_id, company_id)
    if not source:
        raise BudgetAdjustmentApprovalError("budget_adjustment_not_found")
    authorized_actor = authorize_actor(cur, validated_actor, company_id)
    if not authorized_actor:
        raise BudgetAdjustmentApprovalError("budget_adjustment_role_forbidden")
    existing = load_receipt(cur, reconciliation_id, company_id)
    if existing:
        if existing.get("plan_sha256") != expected_plan_sha256:
            raise BudgetAdjustmentApprovalError("budget_adjustment_plan_stale")
        return _receipt_result(existing, idempotent=True)

    try:
        plan = build_preview(
            cur,
            reconciliation_id,
            company_id,
            source_loader=lambda *_args: source,
        )
    except BudgetAdjustmentPreviewError as exc:
        raise BudgetAdjustmentApprovalError(exc.code) from exc
    if plan.get("planSha256") != expected_plan_sha256:
        raise BudgetAdjustmentApprovalError("budget_adjustment_plan_stale")
    if plan.get("readyForApproval") is not True:
        blockers = list(plan.get("blockers") or [])
        raise BudgetAdjustmentApprovalError(
            blockers[0] if blockers else "budget_adjustment_not_ready"
        )

    inserted = insert_receipt(cur, plan, authorized_actor)
    if not inserted:
        raise BudgetAdjustmentApprovalError("budget_adjustment_receipt_insert_failed")
    if update_budget(cur, plan) is not True:
        raise BudgetAdjustmentApprovalError("budget_adjustment_budget_update_conflict")
    return _receipt_result(inserted, idempotent=False)


__all__ = ["BudgetAdjustmentApprovalError", "apply_budget_adjustment"]
