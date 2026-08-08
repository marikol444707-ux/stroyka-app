"""Pure fixed-field A7.4 contract across five impact domains."""

import hashlib
import json
import re
from collections import Counter

from backend.features.project_budget_adjustments.plan import (
    BudgetAdjustmentPlanError,
    build_budget_adjustment_plan,
)

COMBINED_REPORT_VERSION = 1
DOMAIN_ORDER = (
    "assignments",
    "materials",
    "supply",
    "warehouse",
    "economics",
)
PREVIEW_LIMIT = 100

_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MONEY_RE = re.compile(r"^-?(?:0|[1-9][0-9]{0,11})\.[0-9]{2}$")
_STATES = frozenset({
    "complete", "incomplete", "review_required", "not_collected",
    "non_actionable",
})
_HISTORY_NAMES = (
    "workJournal", "confirmedWorkJournal", "hiddenActs", "brigadeActs",
    "brigadePayments", "projectPayments",
)
_ASSIGNMENT_SUMMARY = (
    "assignmentRows", "uncompletedAssignments", "protectedAssignments",
    "needsReview", "workJournalRows", "confirmedWorkJournalRows",
    "hiddenActs", "brigadeActs", "brigadePayments", "projectPayments",
)
_MATERIAL_SUMMARY = (
    "baseMaterialRows", "targetMaterialRows", "pairedRows", "changedPairs",
    "baseOnlyRows", "targetOnlyRows", "needsReview",
)
_SUPPLY_SUMMARY = (
    "supplyRequestRows", "supplyItems", "openSupplyItems",
    "protectedSupplyItems", "closedSupplyRequests", "deliveries",
    "allocations", "supplierInvoices",
)
_WAREHOUSE_SUMMARY = (
    "warehouseInvoices", "warehouseHistoryRows", "receiptLots",
    "warehouseMovements", "lotMovements",
)
_SUPPLY_EVIDENCE = (
    "closedSupplyRequestIds", "deliveryIds", "allocationIds",
    "supplierInvoiceIds",
)
_WAREHOUSE_EVIDENCE = (
    "warehouseInvoiceIds", "warehouseHistoryIds", "receiptLotIds",
    "warehouseMovementIds", "lotMovementIds",
)
_BUDGET_FIELDS = (
    "projectBudgetBefore", "estimateBaseTotal", "estimateNextTotal",
    "adjustmentAmount", "projectBudgetAfter",
)


def _positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _non_negative_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _safe_code(value):
    return value if isinstance(value, str) and _CODE_RE.fullmatch(value) else None


def _ids(values):
    if not isinstance(values, (list, tuple)):
        return [], True
    valid = sorted({
        item_id for item_id in (_positive_int(value) for value in values)
        if item_id is not None
    })
    invalid = len(valid) != len(values)
    return valid[:PREVIEW_LIMIT], invalid or len(valid) > PREVIEW_LIMIT


def _summary(projection, names):
    raw = projection.get("summary")
    raw = raw if isinstance(raw, dict) else {}
    return {name: _non_negative_int(raw.get(name)) for name in names}


def _reason_counts(projection):
    raw = projection.get("reasonCounts")
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for reason, count in raw.items():
        reason = _safe_code(reason)
        count = _non_negative_int(count)
        if reason and count:
            result[reason] = count
    return dict(sorted(result.items()))


def _review(item):
    if not isinstance(item, dict):
        return None
    reason = _safe_code(item.get("reasonCode"))
    if reason is None:
        return None
    result = {"reasonCode": reason}
    source_kind = item.get("sourceKind")
    if (
        isinstance(source_kind, str)
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,39}", source_kind)
    ):
        result["sourceKind"] = source_kind
    source_id = item.get("sourceId")
    if source_id is None or _positive_int(source_id) is not None:
        result["sourceId"] = source_id
    for key in ("sectionIndex", "itemIndex"):
        value = item.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    return result


def _reviews(projection, predicate=None):
    raw = projection.get("needsReview")
    raw = raw if isinstance(raw, list) else []
    result = []
    invalid = False
    for item in raw:
        if predicate is not None and not predicate(item):
            continue
        public = _review(item)
        if public is None:
            invalid = True
            continue
        result.append(public)
    truncated = (
        projection.get("needsReviewTruncated") is True
        or invalid
        or len(result) > PREVIEW_LIMIT
    )
    return result[:PREVIEW_LIMIT], truncated


def _common(projection):
    projection = projection if isinstance(projection, dict) else {}
    state = projection.get("state")
    if state not in _STATES:
        state = "incomplete"
    missing = projection.get("missingColumns")
    missing = missing if isinstance(missing, list) else []
    missing = sorted({
        value for value in missing
        if isinstance(value, str)
        and re.fullmatch(r"[a-z_]+\.[a-z_]+", value)
    })
    return {
        "state": state,
        "schemaReady": projection.get("schemaReady") is True,
        "missingColumns": missing,
        "scanComplete": projection.get("scanComplete") is True,
        "complete": projection.get("complete") is True,
    }


def _coordinate(value):
    if not isinstance(value, dict):
        return None
    estimate_id = _positive_int(value.get("estimateId"))
    section_index = value.get("sectionIndex")
    item_index = value.get("itemIndex")
    if (
        estimate_id is None
        or isinstance(section_index, bool)
        or not isinstance(section_index, int)
        or section_index < 0
        or isinstance(item_index, bool)
        or not isinstance(item_index, int)
        or item_index < 0
    ):
        return None
    return {
        "estimateId": estimate_id,
        "sectionIndex": section_index,
        "itemIndex": item_index,
    }


def _assignment_view(projection):
    projection = projection if isinstance(projection, dict) else {}
    view = _common(projection)
    uncompleted, uncompleted_truncated = _ids(
        projection.get("uncompletedAssignmentIds")
    )
    protected, protected_truncated = _ids(
        projection.get("protectedAssignmentIds")
    )
    history = {}
    history_truncated = False
    raw_history = projection.get("protectedHistory")
    raw_history = raw_history if isinstance(raw_history, dict) else {}
    for name in _HISTORY_NAMES:
        raw = raw_history.get(name)
        raw = raw if isinstance(raw, dict) else {}
        ids, truncated = _ids(raw.get("ids"))
        count = _non_negative_int(raw.get("count"))
        truncated = truncated or raw.get("idsTruncated") is True or count > len(ids)
        history[name] = {
            "count": count,
            "ids": ids,
            "idsTruncated": truncated,
        }
        history_truncated = history_truncated or truncated
    reviews, reviews_truncated = _reviews(projection)
    truncation = (
        uncompleted_truncated or protected_truncated or history_truncated
        or reviews_truncated
    )
    view["complete"] = view["complete"] and not truncation
    if truncation:
        view["state"] = "incomplete"
    view.update({
        "summary": _summary(projection, _ASSIGNMENT_SUMMARY),
        "uncompletedAssignmentIds": uncompleted,
        "protectedAssignmentIds": protected,
        "protectedHistory": history,
        "reasonCounts": _reason_counts(projection),
        "needsReview": reviews,
        "needsReviewTruncated": reviews_truncated,
    })
    return view


def _material_view(projection):
    projection = projection if isinstance(projection, dict) else {}
    view = _common(projection)
    invalid_fact = False
    changed = []
    raw_changed = projection.get("changedPairs")
    raw_changed = raw_changed if isinstance(raw_changed, list) else []
    for item in raw_changed:
        base = _coordinate(item.get("base")) if isinstance(item, dict) else None
        target = _coordinate(item.get("target")) if isinstance(item, dict) else None
        match_kind = item.get("matchKind") if isinstance(item, dict) else None
        if base is None or target is None or match_kind not in {
            "stable_item_key", "confirmed_alias",
        }:
            invalid_fact = True
            continue
        alias_ids, alias_truncated = _ids(item.get("aliasIds"))
        change_kinds = item.get("changeKinds")
        change_kinds = change_kinds if isinstance(change_kinds, list) else []
        change_kinds = sorted({
            value for value in change_kinds
            if value in {
                "quantity_changed", "identity_changed", "alias_identity_changed",
            }
        })
        invalid_fact = invalid_fact or alias_truncated
        changed.append({
            "base": base,
            "target": target,
            "matchKind": match_kind,
            "aliasIds": alias_ids,
            "changeKinds": change_kinds,
        })

    def coordinates(name):
        nonlocal invalid_fact
        raw = projection.get(name)
        raw = raw if isinstance(raw, list) else []
        values = []
        for item in raw:
            public = _coordinate(item)
            if public is None:
                invalid_fact = True
            else:
                values.append(public)
        if len(values) > PREVIEW_LIMIT:
            invalid_fact = True
        return values[:PREVIEW_LIMIT]

    base_only = coordinates("baseOnlyRows")
    target_only = coordinates("targetOnlyRows")
    reviews, reviews_truncated = _reviews(projection)
    facts_truncated = (
        projection.get("factsTruncated") is True
        or invalid_fact
        or len(changed) > PREVIEW_LIMIT
    )
    view["complete"] = (
        view["complete"] and not facts_truncated and not reviews_truncated
    )
    if facts_truncated or reviews_truncated:
        view["state"] = "incomplete"
    view.update({
        "summary": _summary(projection, _MATERIAL_SUMMARY),
        "changedPairs": changed[:PREVIEW_LIMIT],
        "baseOnlyRows": base_only,
        "targetOnlyRows": target_only,
        "factsTruncated": facts_truncated,
        "reasonCounts": _reason_counts(projection),
        "needsReview": reviews,
        "needsReviewTruncated": reviews_truncated,
    })
    return view


def _warehouse_review(item):
    if not isinstance(item, dict):
        return False
    reason = item.get("reasonCode")
    kind = item.get("sourceKind")
    return (
        isinstance(reason, str) and reason.startswith("warehouse_")
    ) or kind in {
        "warehouseInvoice", "warehouseHistory", "receiptLot",
        "warehouseMovement", "lotMovement",
    }


def _split_reason_counts(projection):
    supply = {}
    warehouse = {}
    for reason, count in _reason_counts(projection).items():
        if reason.startswith("warehouse_"):
            warehouse[reason] = count
        elif reason.startswith("supply_warehouse_"):
            supply[reason] = count
            warehouse[reason] = count
        else:
            supply[reason] = count
    return supply, warehouse


def _supply_warehouse_views(projection):
    projection = projection if isinstance(projection, dict) else {}
    common = _common(projection)
    summary = projection.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    evidence = projection.get("protectedEvidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    public_evidence = {}
    evidence_truncation = {}
    for name in _SUPPLY_EVIDENCE + _WAREHOUSE_EVIDENCE:
        ids, invalid = _ids(evidence.get(name))
        public_evidence[name] = ids
        evidence_truncation[name] = invalid

    open_supply = []
    invalid_open = False
    raw_open = projection.get("openSupply")
    raw_open = raw_open if isinstance(raw_open, list) else []
    for item in raw_open:
        if not isinstance(item, dict):
            invalid_open = True
            continue
        public = {
            "requestId": _positive_int(item.get("requestId")),
            "requestItemIndex": item.get("requestItemIndex"),
            "sourceEstimateId": _positive_int(item.get("sourceEstimateId")),
            "sourceSectionIndex": item.get("sourceSectionIndex"),
            "sourceItemIndex": item.get("sourceItemIndex"),
            "state": item.get("state"),
        }
        if (
            None in (public["requestId"], public["sourceEstimateId"])
            or any(
                isinstance(public[key], bool)
                or not isinstance(public[key], int)
                or public[key] < 0
                for key in (
                    "requestItemIndex", "sourceSectionIndex", "sourceItemIndex",
                )
            )
            or public["state"] != "open_balance"
        ):
            invalid_open = True
            continue
        open_supply.append(public)
    if len(open_supply) > PREVIEW_LIMIT:
        invalid_open = True
        open_supply = open_supply[:PREVIEW_LIMIT]

    supply_reviews, supply_review_truncated = _reviews(
        projection, lambda item: not _warehouse_review(item),
    )
    warehouse_reviews, warehouse_review_truncated = _reviews(
        projection, _warehouse_review,
    )
    parent_review_truncated = projection.get("needsReviewTruncated") is True
    supply_review_truncated = supply_review_truncated or parent_review_truncated
    warehouse_review_truncated = warehouse_review_truncated or parent_review_truncated
    supply_reasons, warehouse_reasons = _split_reason_counts(projection)

    supply_summary = {
        name: _non_negative_int(summary.get(name)) for name in _SUPPLY_SUMMARY
    }
    supply_summary["needsReview"] = sum(supply_reasons.values())
    warehouse_summary = {
        name: _non_negative_int(summary.get(name)) for name in _WAREHOUSE_SUMMARY
    }
    warehouse_summary["needsReview"] = sum(warehouse_reasons.values())
    supply_facts_truncated = invalid_open or any(
        evidence_truncation[name] for name in _SUPPLY_EVIDENCE
    ) or supply_summary["openSupplyItems"] > len(open_supply) or any(
        supply_summary[count_name] > len(public_evidence[id_name])
        for count_name, id_name in (
            ("closedSupplyRequests", "closedSupplyRequestIds"),
            ("deliveries", "deliveryIds"),
            ("allocations", "allocationIds"),
            ("supplierInvoices", "supplierInvoiceIds"),
        )
    )
    warehouse_facts_truncated = any(
        evidence_truncation[name] for name in _WAREHOUSE_EVIDENCE
    ) or any(
        warehouse_summary[count_name] > len(public_evidence[id_name])
        for count_name, id_name in (
            ("warehouseInvoices", "warehouseInvoiceIds"),
            ("warehouseHistoryRows", "warehouseHistoryIds"),
            ("receiptLots", "receiptLotIds"),
            ("warehouseMovements", "warehouseMovementIds"),
            ("lotMovements", "lotMovementIds"),
        )
    )

    def domain_view(
        domain_summary,
        names,
        reasons,
        reviews,
        review_truncated,
        facts_truncated,
    ):
        view = dict(common)
        complete = (
            view["schemaReady"] and view["scanComplete"]
            and not reasons and not review_truncated and not facts_truncated
        )
        view["complete"] = complete
        view["state"] = "complete" if complete else (
            "incomplete"
            if not view["schemaReady"] or not view["scanComplete"]
            or review_truncated or facts_truncated
            else "review_required"
        )
        view.update({
            "summary": domain_summary,
            "protectedEvidence": {
                name: public_evidence[name] for name in names
            },
            "factsTruncated": facts_truncated,
            "reasonCounts": reasons,
            "needsReview": reviews,
            "needsReviewTruncated": review_truncated,
        })
        return view

    supply = domain_view(
        supply_summary,
        _SUPPLY_EVIDENCE,
        supply_reasons,
        supply_reviews,
        supply_review_truncated,
        supply_facts_truncated,
    )
    supply["openSupply"] = open_supply
    warehouse = domain_view(
        warehouse_summary,
        _WAREHOUSE_EVIDENCE,
        warehouse_reasons,
        warehouse_reviews,
        warehouse_review_truncated,
        warehouse_facts_truncated,
    )
    return supply, warehouse


def _economics_view(projection, source):
    projection = projection if isinstance(projection, dict) else {}
    view = _common(projection)
    authorization = projection.get("authorizationState")
    if authorization not in {"authorized", "not_evaluated"}:
        authorization = "not_evaluated"
        view["complete"] = False
        view["state"] = "incomplete"
    budget = projection.get("budget")
    budget = budget if isinstance(budget, dict) else {}
    public_budget = {
        name: value for name in _BUDGET_FIELDS
        for value in (budget.get(name),)
        if isinstance(value, str) and _MONEY_RE.fullmatch(value)
    }
    plan_hash = projection.get("planSha256")
    if not isinstance(plan_hash, str) or not _HASH_RE.fullmatch(plan_hash):
        plan_hash = None
    reasons = _reason_counts(projection)
    planless_complete = set(reasons) in ({
        "budget_adjustment_reconciliation_not_approved",
    }, {
        "budget_adjustment_already_applied",
    })
    exact_plan = None
    if len(public_budget) == len(_BUDGET_FIELDS) and plan_hash is not None:
        try:
            exact_plan = build_budget_adjustment_plan({
                "reconciliationId": source.get("reconciliationId"),
                "companyId": source.get("companyId"),
                "projectId": source.get("projectId"),
                "baseEstimateId": source.get("baseEstimateId"),
                "nextEstimateId": source.get("estimateId"),
                "projectBudgetBefore": public_budget.get("projectBudgetBefore"),
                "estimateBaseTotal": public_budget.get("estimateBaseTotal"),
                "estimateNextTotal": public_budget.get("estimateNextTotal"),
            })
        except BudgetAdjustmentPlanError:
            exact_plan = None
    plan_valid = bool(
        exact_plan is not None
        and exact_plan["planSha256"] == plan_hash
        and all(exact_plan[name] == public_budget[name] for name in _BUDGET_FIELDS)
    )
    projection_contract_valid = plan_valid or planless_complete
    if view["complete"] and not projection_contract_valid:
        view["complete"] = False
        view["state"] = "incomplete"
        reasons = {"economics_projection_contract_invalid": 1}
    reviews, reviews_truncated = _reviews(projection)
    actionable = (
        projection.get("actionable") is True
        and view["complete"]
        and authorization == "authorized"
        and len(public_budget) == len(_BUDGET_FIELDS)
        and plan_hash is not None
    )
    view["complete"] = view["complete"] and not reviews_truncated
    if reviews_truncated:
        view["state"] = "incomplete"
    view.update({
        "actionable": actionable,
        "authorizationState": authorization,
        "summary": _summary(projection, (
            "evidenceComplete", "actionablePlans", "nonActionablePlans",
            "needsReview",
        )),
        "budget": public_budget,
        "planSha256": plan_hash,
        "reasonCounts": reasons,
        "needsReview": reviews,
        "needsReviewTruncated": reviews_truncated,
    })
    return view


def _source_view(source):
    source = source if isinstance(source, dict) else {}
    revision = source.get("sourceRevision")
    status = source.get("reconciliationStatus")
    return {
        "companyId": _positive_int(source.get("companyId")),
        "projectId": _positive_int(source.get("projectId")),
        "estimateId": _positive_int(source.get("estimateId")),
        "sourceRevision": (
            revision if isinstance(revision, str) and _REVISION_RE.fullmatch(revision)
            else None
        ),
        "reconciliationId": _positive_int(source.get("reconciliationId")),
        "baseEstimateId": _positive_int(source.get("baseEstimateId")),
        "reconciliationStatus": (
            status if status in {"Черновик", "На проверке", "Утверждена", "Отклонена"}
            else None
        ),
    }


def calculate_evidence_sha256(report):
    canonical = {
        "combinedReportVersion": report["combinedReportVersion"],
        "source": report["source"],
        "domainOrder": report["domainOrder"],
        "domains": report["domains"],
        "complete": report["complete"],
        "actionable": report["actionable"],
        "reasonCounts": report["reasonCounts"],
    }
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _aggregate_reasons(domains):
    counts = Counter()
    for domain in DOMAIN_ORDER:
        counts.update(domains[domain].get("reasonCounts") or {})
    return dict(sorted(counts.items()))


def build_combined_report(
    source,
    *,
    assignment,
    material,
    supply_warehouse,
    economics,
):
    """Compose one fixed-field report without exposing business text."""

    public_source = _source_view(source)
    source_valid = (
        all(public_source.values())
        and public_source["baseEstimateId"] != public_source["estimateId"]
    )
    supply, warehouse = _supply_warehouse_views(supply_warehouse)
    domains = {
        "assignments": _assignment_view(assignment),
        "materials": _material_view(material),
        "supply": supply,
        "warehouse": warehouse,
        "economics": _economics_view(economics, public_source),
    }
    complete = source_valid and all(
        domains[name]["complete"] for name in DOMAIN_ORDER
    )
    actionable = complete and domains["economics"]["actionable"]
    reason_counts = _aggregate_reasons(domains)
    if not source_valid:
        reason_counts["combined_source_contract_invalid"] = 1
        reason_counts = dict(sorted(reason_counts.items()))
    report = {
        "combinedReportVersion": COMBINED_REPORT_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "source": public_source,
        "domainOrder": list(DOMAIN_ORDER),
        "domains": domains,
        "complete": complete,
        "actionable": actionable,
        "reasonCounts": reason_counts,
    }
    report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report
__all__ = [
    "COMBINED_REPORT_VERSION",
    "DOMAIN_ORDER",
    "build_combined_report",
    "calculate_evidence_sha256",
]
