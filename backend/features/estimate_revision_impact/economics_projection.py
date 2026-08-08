"""Bounded read-only A7.4 projection of the exact E6 budget adjustment."""

import argparse
import json

from backend.features.project_budget_adjustments.plan import (
    BudgetAdjustmentPlanError,
    build_budget_adjustment_plan,
)
from backend.features.project_budget_adjustments.preview import (
    BudgetAdjustmentPreviewError,
)
from backend.features.project_budget_adjustments.preview_service import (
    PUBLIC_PREVIEW_FIELDS,
    build_budget_adjustment_preview,
)

from .baseline import collect_baseline_audit, run_baseline_audit
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)


ECONOMICS_REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "budget"},
    "estimates": {
        "id", "company_id", "project_id", "status", "smeta_type",
        "work_package", "sections_json",
    },
    "estimate_reconciliations": {
        "id", "base_estimate_id", "next_estimate_id", "status",
        "smeta_type", "work_package", "base_total", "next_total",
    },
    "project_budget_adjustments": {"id", "reconciliation_id"},
}

_BUDGET_FIELDS = (
    "projectBudgetBefore",
    "estimateBaseTotal",
    "estimateNextTotal",
    "adjustmentAmount",
    "projectBudgetAfter",
)
_COMPLETE_BLOCKERS = frozenset({
    "budget_adjustment_reconciliation_not_approved",
    "budget_adjustment_already_applied",
})
_KNOWN_PREVIEW_BLOCKERS = frozenset({
    "budget_adjustment_active_revision_conflict",
    "budget_adjustment_after_out_of_range",
    "budget_adjustment_already_applied",
    "budget_adjustment_base_total_invalid",
    "budget_adjustment_context_invalid",
    "budget_adjustment_estimate_content_invalid",
    "budget_adjustment_estimate_content_too_large",
    "budget_adjustment_identity_invalid",
    "budget_adjustment_negative_after",
    "budget_adjustment_next_not_active",
    "budget_adjustment_next_total_invalid",
    "budget_adjustment_not_found",
    "budget_adjustment_owner_mismatch",
    "budget_adjustment_package_mismatch",
    "budget_adjustment_project_budget_invalid",
    "budget_adjustment_reconciliation_not_approved",
    "budget_adjustment_source_drift",
    "budget_adjustment_source_invalid",
    "budget_adjustment_type_not_customer",
    "budget_adjustment_zero_delta",
})


def _positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _base_projection(
    state,
    *,
    schema_ready=True,
    missing_columns=None,
    scan_complete=True,
    complete=False,
    actionable=False,
    authorized=False,
    reason_code=None,
    budget=None,
    plan_sha256=None,
):
    needs_review = []
    reason_counts = {}
    if reason_code:
        needs_review = [{"reasonCode": reason_code}]
        reason_counts = {reason_code: 1}
    return {
        "state": state,
        "schemaReady": bool(schema_ready),
        "missingColumns": list(missing_columns or []),
        "scanComplete": bool(scan_complete),
        "complete": bool(complete),
        "actionable": bool(actionable),
        "authorizationState": "authorized" if authorized else "not_evaluated",
        "summary": {
            "evidenceComplete": 1 if complete else 0,
            "actionablePlans": 1 if actionable else 0,
            "nonActionablePlans": 1 if complete and not actionable else 0,
            "needsReview": len(needs_review),
        },
        "budget": dict(budget or {}),
        "planSha256": plan_sha256,
        "reasonCounts": reason_counts,
        "needsReview": needs_review,
        "needsReviewTruncated": False,
    }


def _valid_context(context):
    if not isinstance(context, dict):
        return False
    required = (
        "companyId", "projectId", "estimateId", "baseEstimateId",
        "reconciliationId",
    )
    ids = {_positive_int(context.get(key)) for key in required}
    return None not in ids and (
        context.get("baseEstimateId") != context.get("estimateId")
    )


def _validated_preview(context, preview):
    if not _valid_context(context) or not isinstance(preview, dict):
        return None
    if set(preview) != set(PUBLIC_PREVIEW_FIELDS):
        return None
    identity = {
        "reconciliationId": context["reconciliationId"],
        "companyId": context["companyId"],
        "projectId": context["projectId"],
        "baseEstimateId": context["baseEstimateId"],
        "nextEstimateId": context["estimateId"],
    }
    if any(preview.get(key) != value for key, value in identity.items()):
        return None
    try:
        exact_plan = build_budget_adjustment_plan({
            **identity,
            "projectBudgetBefore": preview.get("projectBudgetBefore"),
            "estimateBaseTotal": preview.get("estimateBaseTotal"),
            "estimateNextTotal": preview.get("estimateNextTotal"),
        })
    except BudgetAdjustmentPlanError:
        return None
    expected = {key: exact_plan[key] for key in PUBLIC_PREVIEW_FIELDS}
    if preview != expected:
        return None
    return exact_plan


def build_economics_projection(
    context,
    *,
    preview=None,
    blocker=None,
    authorized=False,
):
    """Classify exact E6 evidence without invoking the E6 approval writer."""

    authorized = authorized is True
    if blocker is not None:
        if blocker not in _KNOWN_PREVIEW_BLOCKERS:
            blocker = "economics_preview_error"
        complete = blocker in _COMPLETE_BLOCKERS
        return _base_projection(
            "non_actionable" if complete else "incomplete",
            complete=complete,
            reason_code=blocker,
            authorized=authorized,
        )

    exact_plan = _validated_preview(context, preview)
    if exact_plan is None:
        return _base_projection(
            "incomplete",
            reason_code="economics_preview_contract_invalid",
            authorized=authorized,
        )

    blockers = list(exact_plan["blockers"])
    if blockers:
        return _base_projection(
            "non_actionable",
            complete=True,
            reason_code=blockers[0],
            budget={key: exact_plan[key] for key in _BUDGET_FIELDS},
            plan_sha256=exact_plan["planSha256"],
            authorized=authorized,
        )
    if not authorized:
        return _base_projection(
            "non_actionable",
            complete=True,
            reason_code="budget_adjustment_authorization_required",
            budget={key: exact_plan[key] for key in _BUDGET_FIELDS},
            plan_sha256=exact_plan["planSha256"],
            authorized=False,
        )
    return _base_projection(
        "complete",
        complete=True,
        actionable=True,
        budget={key: exact_plan[key] for key in _BUDGET_FIELDS},
        plan_sha256=exact_plan["planSha256"],
        authorized=True,
    )


def _load_economics_schema(cur):
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(ECONOMICS_REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    return sorted(
        table + "." + column
        for table, columns in ECONOMICS_REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )


def collect_economics_impact_audit(
    cur,
    source,
    *,
    preview_builder=build_budget_adjustment_preview,
):
    """Collect the exact source and E6 plan in one caller-owned snapshot."""

    report = collect_baseline_audit(cur, source)
    if not report.get("readyForDomainScan"):
        report["readyForEconomicsProjection"] = False
        report["economicsImpact"] = _base_projection(
            "not_collected", scan_complete=False,
        )
        return report

    missing = _load_economics_schema(cur)
    if missing:
        projection = _base_projection(
            "incomplete",
            schema_ready=False,
            missing_columns=missing,
            scan_complete=False,
            reason_code="economics_impact_schema_not_ready",
        )
    else:
        context = report["source"]
        try:
            exact_preview = preview_builder(
                cur,
                context["reconciliationId"],
                context["companyId"],
            )
        except BudgetAdjustmentPreviewError as exc:
            projection = build_economics_projection(
                context,
                blocker=exc.code,
                authorized=False,
            )
        else:
            projection = build_economics_projection(
                context,
                preview=exact_preview,
                authorized=False,
            )

    report["readyForEconomicsProjection"] = projection["complete"]
    report["economicsImpact"] = projection
    return report


def run_economics_impact_audit(
    get_db,
    source,
    *,
    preview_builder=build_budget_adjustment_preview,
):
    return run_baseline_audit(
        get_db,
        source,
        collect_data=lambda cur, exact_source: collect_economics_impact_audit(
            cur,
            exact_source,
            preview_builder=preview_builder,
        ),
    )


def _source_from_args(args):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": args.company_id,
        "projectId": args.project_id,
        "estimateId": args.estimate_id,
        "sourceRevision": args.source_revision,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate revision economics impact audit",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    try:
        source = _source_from_args(args)
    except EstimateRevisionImpactContractError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_economics_impact_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForEconomicsProjection") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ECONOMICS_REQUIRED_COLUMNS",
    "build_economics_projection",
    "collect_economics_impact_audit",
    "run_economics_impact_audit",
]
