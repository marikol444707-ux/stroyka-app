"""Fail-closed construction of one tenant-bound E6 adjustment preview."""

from decimal import Decimal, InvalidOperation

from .audit import MAX_PROJECT_BUDGET, MONEY_QUANTUM
from .plan import BudgetAdjustmentPlanError, build_budget_adjustment_plan
from .preview import BudgetAdjustmentPreviewError, calculate_sections_total
from .preview_storage import load_budget_adjustment_source


PUBLIC_PREVIEW_FIELDS = {
    "reconciliationId", "companyId", "projectId", "baseEstimateId",
    "nextEstimateId", "projectBudgetBefore", "estimateBaseTotal",
    "estimateNextTotal", "adjustmentAmount", "projectBudgetAfter",
    "planSha256", "readyForApproval", "blockers",
}


def _positive_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _text(value):
    return str(value or "").strip()


def _kind(value):
    return _text(value) or "Заказчик"


def _package(value):
    return _text(value) or "Основная"


def _money(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if (
        not number.is_finite()
        or number < 0
        or number >= MAX_PROJECT_BUDGET
        or number != number.quantize(MONEY_QUANTUM)
    ):
        return None
    return Decimal("0.00") if number == 0 else number.quantize(MONEY_QUANTUM)


def _abort(code):
    raise BudgetAdjustmentPreviewError(code)


def _validate_identity(row, reconciliation_id, company_id):
    base_estimate_id = _positive_int(row.get("base_estimate_id"))
    next_estimate_id = _positive_int(row.get("next_estimate_id"))
    project_id = _positive_int(row.get("project_id"))
    owner = (company_id, project_id)
    if (
        _positive_int(row.get("reconciliation_id")) != reconciliation_id
        or _positive_int(row.get("company_id")) != company_id
        or project_id is None
        or base_estimate_id is None
        or next_estimate_id is None
        or base_estimate_id == next_estimate_id
        or _positive_int(row.get("stored_base_estimate_id")) != base_estimate_id
        or _positive_int(row.get("stored_next_estimate_id")) != next_estimate_id
        or owner != (
            _positive_int(row.get("base_company_id")),
            _positive_int(row.get("base_project_id")),
        )
        or owner != (
            _positive_int(row.get("next_company_id")),
            _positive_int(row.get("next_project_id")),
        )
    ):
        _abort("budget_adjustment_owner_mismatch")
    return project_id, base_estimate_id, next_estimate_id


def _validate_source_state(row):
    if _text(row.get("reconciliation_status")) != "Утверждена":
        _abort("budget_adjustment_reconciliation_not_approved")
    if {
        _kind(row.get("reconciliation_type")),
        _kind(row.get("base_type")),
        _kind(row.get("next_type")),
    } != {"Заказчик"}:
        _abort("budget_adjustment_type_not_customer")
    if len({
        _package(row.get("reconciliation_package")),
        _package(row.get("base_package")),
        _package(row.get("next_package")),
    }) != 1:
        _abort("budget_adjustment_package_mismatch")
    if _text(row.get("next_status")) != "Активная":
        _abort("budget_adjustment_next_not_active")
    if _positive_int(row.get("active_scope_count")) != 1:
        _abort("budget_adjustment_active_revision_conflict")
    if row.get("existing_adjustment_id") is not None:
        _abort("budget_adjustment_already_applied")


def _validated_totals(row):
    stored_base = _money(row.get("reconciliation_base_total"))
    stored_next = _money(row.get("reconciliation_next_total"))
    current_base = calculate_sections_total(row.get("base_sections_json"))
    current_next = calculate_sections_total(row.get("next_sections_json"))
    if (
        stored_base is None
        or stored_next is None
        or current_base != stored_base
        or current_next != stored_next
    ):
        _abort("budget_adjustment_source_drift")
    return current_base, current_next


def build_budget_adjustment_preview(
    cur,
    reconciliation_id,
    company_id,
    *,
    source_loader=load_budget_adjustment_source,
):
    """Return only the public exact plan; never insert, update or lock rows."""

    reconciliation_id = _positive_int(reconciliation_id)
    company_id = _positive_int(company_id)
    if not reconciliation_id or not company_id:
        _abort("budget_adjustment_identity_invalid")
    row = source_loader(cur, reconciliation_id, company_id)
    if not row:
        _abort("budget_adjustment_not_found")
    row = dict(row)
    project_id, base_estimate_id, next_estimate_id = _validate_identity(
        row, reconciliation_id, company_id
    )
    _validate_source_state(row)
    base_total, next_total = _validated_totals(row)
    try:
        plan = build_budget_adjustment_plan({
            "reconciliationId": reconciliation_id,
            "companyId": company_id,
            "projectId": project_id,
            "baseEstimateId": base_estimate_id,
            "nextEstimateId": next_estimate_id,
            "projectBudgetBefore": row.get("project_budget"),
            "estimateBaseTotal": base_total,
            "estimateNextTotal": next_total,
        })
    except BudgetAdjustmentPlanError as exc:
        _abort(exc.code)
    return {key: plan[key] for key in PUBLIC_PREVIEW_FIELDS}


__all__ = [
    "PUBLIC_PREVIEW_FIELDS",
    "build_budget_adjustment_preview",
]
