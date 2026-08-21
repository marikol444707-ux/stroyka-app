"""Pure A9.1 readiness contract for exact A7 warehouse review rows."""

import re
from collections import Counter
from collections.abc import Mapping
from types import MappingProxyType

from backend.features.estimate_revision_impact.combined_contract import (
    COMBINED_REPORT_VERSION,
    DOMAIN_ORDER,
    PREVIEW_LIMIT,
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)


WAREHOUSE_ANOMALY_READINESS_VERSION = 1


def _field_set(names):
    return frozenset(names.split())


_REPORT_FIELDS = _field_set(
    "combinedReportVersion ok dryRun writesAttempted source domainOrder "
    "domains complete actionable reasonCounts evidenceSha256 "
    "readOnlyTransaction rolledBack"
)
_SOURCE_FIELDS = _field_set(
    "companyId projectId estimateId sourceRevision reconciliationId "
    "baseEstimateId reconciliationStatus"
)
_DOMAIN_COMMON_FIELDS = _field_set(
    "state schemaReady missingColumns scanComplete complete factsTruncated "
    "reasonCounts needsReview needsReviewTruncated"
)
_SUPPLY_FIELDS = _DOMAIN_COMMON_FIELDS | _field_set(
    "summary openSupply protectedEvidence"
)
_WAREHOUSE_FIELDS = _DOMAIN_COMMON_FIELDS | _field_set(
    "summary protectedEvidence"
)
_SUPPLY_SUMMARY_FIELDS = _field_set(
    "supplyRequestRows supplyItems openSupplyItems protectedSupplyItems "
    "closedSupplyRequests deliveries allocations supplierInvoices needsReview"
)
_WAREHOUSE_SUMMARY_FIELDS = _field_set(
    "warehouseInvoices warehouseHistoryRows receiptLots warehouseMovements "
    "lotMovements needsReview"
)
_SUPPLY_EVIDENCE_FIELDS = _field_set(
    "closedSupplyRequestIds deliveryIds allocationIds supplierInvoiceIds"
)
_WAREHOUSE_EVIDENCE_FIELDS = _field_set(
    "warehouseInvoiceIds warehouseHistoryIds receiptLotIds "
    "warehouseMovementIds lotMovementIds"
)
_OPEN_SUPPLY_FIELDS = _field_set(
    "requestId requestItemIndex sourceEstimateId sourceSectionIndex "
    "sourceItemIndex state"
)
_REVIEW_REQUIRED_FIELDS = _field_set("reasonCode sourceId")
_REVIEW_OPTIONAL_FIELDS = _field_set(
    "sourceKind sectionIndex itemIndex"
)
_DOMAIN_STATES = frozenset({
    "complete",
    "incomplete",
    "review_required",
    "not_collected",
})
_RECONCILIATION_STATES = frozenset({
    "Черновик",
    "На проверке",
    "Утверждена",
    "Отклонена",
})
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_KIND_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,39}$")
_COLUMN_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _candidate(subject_kind, source_kind, recommendation_code):
    return (subject_kind, source_kind, recommendation_code)


_CANDIDATE_RULES = MappingProxyType({
    "warehouse_invoice_request_mismatch": _candidate(
        "warehouseInvoice", "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    "warehouse_invoice_project_mismatch": _candidate(
        "warehouseInvoice", "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    "warehouse_invoice_delivery_mismatch": _candidate(
        "warehouseInvoice", "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    "warehouse_invoice_supplier_invoice_mismatch": _candidate(
        "warehouseInvoice", "warehouseInvoice",
        "review_warehouse_invoice_lineage",
    ),
    "warehouse_invoice_items_invalid": _candidate(
        "warehouseInvoice", "warehouseInvoice",
        "review_warehouse_invoice_items",
    ),
    "warehouse_receipt_invoice_mismatch": _candidate(
        "warehouseHistory", None, "review_warehouse_receipt_lineage",
    ),
    "warehouse_receipt_line_invalid": _candidate(
        "warehouseHistory", None, "review_warehouse_receipt_lineage",
    ),
    "warehouse_receipt_package_mismatch": _candidate(
        "warehouseHistory", None, "review_warehouse_receipt_lineage",
    ),
    "warehouse_receipt_lot_invoice_mismatch": _candidate(
        "receiptLot", None, "review_receipt_lot_lineage",
    ),
    "warehouse_receipt_lot_line_invalid": _candidate(
        "receiptLot", None, "review_receipt_lot_lineage",
    ),
    "warehouse_receipt_lot_project_mismatch": _candidate(
        "receiptLot", None, "review_receipt_lot_lineage",
    ),
    "warehouse_movement_invoice_mismatch": _candidate(
        "warehouseMovement", None, "review_warehouse_movement_lineage",
    ),
    "warehouse_movement_line_invalid": _candidate(
        "warehouseMovement", None, "review_warehouse_movement_lineage",
    ),
    "warehouse_movement_package_mismatch": _candidate(
        "warehouseMovement", None, "review_warehouse_movement_lineage",
    ),
    "warehouse_movement_lot_missing": _candidate(
        "warehouseMovement", "warehouseMovement",
        "review_warehouse_movement_traceability",
    ),
    "warehouse_lot_movement_missing": _candidate(
        "warehouseMovement", "warehouseMovement",
        "review_warehouse_movement_traceability",
    ),
    "warehouse_lot_movement_parent_mismatch": _candidate(
        "lotMovement", "lotMovement", "review_lot_movement_lineage",
    ),
    "warehouse_lot_movement_source_mismatch": _candidate(
        "lotMovement", "lotMovement", "review_lot_movement_lineage",
    ),
})

_SUBJECT_INVALID_RULES = MappingProxyType({
    "warehouse_invoice_identity_invalid": "warehouseInvoice",
    "warehouse_invoice_owner_mismatch": "warehouseInvoice",
    "warehouse_receipt_identity_invalid": None,
    "warehouse_receipt_owner_mismatch": None,
    "warehouse_receipt_lot_identity_invalid": None,
    "warehouse_receipt_lot_owner_mismatch": None,
    "warehouse_movement_identity_invalid": None,
    "warehouse_movement_owner_mismatch": None,
    "warehouse_lot_movement_identity_invalid": "lotMovement",
    "warehouse_lot_movement_owner_mismatch": "lotMovement",
})
_ITEM_LIMIT_RULES = MappingProxyType({
    "warehouse_invoice_items_limit_exceeded": "warehouseInvoice",
})
_SYSTEMIC_REASONS = frozenset({
    "supply_warehouse_impact_schema_not_ready",
    "supply_warehouse_project_identity_invalid",
    "supply_warehouse_scan_limit_exceeded",
    "supply_warehouse_source_snapshot_invalid",
})


class WarehouseAnomalyReadinessError(ValueError):
    """Fixed-code validation error without business content."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _fail(code):
    raise WarehouseAnomalyReadinessError(code)


def _positive_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _non_negative_int(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _strict_mapping(value, fields, code):
    if not isinstance(value, Mapping) or set(value) != set(fields):
        _fail(code)
    return value


def _bounded_ids(value, code):
    if not isinstance(value, list):
        _fail(code)
    if len(value) > PREVIEW_LIMIT:
        _fail("warehouse_anomaly_candidate_limit_exceeded")
    if (
        any(_positive_int(item) is None for item in value)
        or value != sorted(set(value))
    ):
        _fail(code)
    return list(value)


def _reason_counts(value, code):
    if not isinstance(value, Mapping) or len(value) > PREVIEW_LIMIT:
        _fail(code)
    result = {}
    for reason, count in value.items():
        if (
            not isinstance(reason, str)
            or not _CODE_RE.fullmatch(reason)
            or _positive_int(count) is None
        ):
            _fail(code)
        result[reason] = count
    return result


def _missing_columns(value, code):
    if not isinstance(value, list) or len(value) > PREVIEW_LIMIT:
        _fail(code)
    if (
        any(not isinstance(item, str) or not _COLUMN_RE.fullmatch(item)
            for item in value)
        or value != sorted(set(value))
    ):
        _fail(code)
    return list(value)


def _review(value, *, supply):
    code = "warehouse_anomaly_relevant_domain_invalid"
    if not isinstance(value, Mapping):
        _fail(code)
    fields = set(value)
    if (
        not _REVIEW_REQUIRED_FIELDS.issubset(fields)
        or not fields.issubset(
            _REVIEW_REQUIRED_FIELDS | _REVIEW_OPTIONAL_FIELDS
        )
        or (not supply and fields - _REVIEW_REQUIRED_FIELDS not in (
            set(), {"sourceKind"},
        ))
    ):
        _fail(code)
    reason = value.get("reasonCode")
    if not isinstance(reason, str) or not _CODE_RE.fullmatch(reason):
        _fail(code)
    source_id = value.get("sourceId")
    if source_id is not None and _positive_int(source_id) is None:
        _fail(code)
    source_kind = value.get("sourceKind")
    if "sourceKind" in value and (
        not isinstance(source_kind, str) or not _KIND_RE.fullmatch(source_kind)
    ):
        _fail(code)
    for name in ("sectionIndex", "itemIndex"):
        if name in value and _non_negative_int(value[name]) is None:
            _fail(code)
    return dict(value)


def _open_supply(value):
    code = "warehouse_anomaly_relevant_domain_invalid"
    if not isinstance(value, list):
        _fail(code)
    if len(value) > PREVIEW_LIMIT:
        _fail("warehouse_anomaly_candidate_limit_exceeded")
    result = []
    identities = set()
    for raw in value:
        item = _strict_mapping(raw, _OPEN_SUPPLY_FIELDS, code)
        identity = (
            _positive_int(item.get("requestId")),
            _non_negative_int(item.get("requestItemIndex")),
        )
        if (
            None in identity
            or _positive_int(item.get("sourceEstimateId")) is None
            or _non_negative_int(item.get("sourceSectionIndex")) is None
            or _non_negative_int(item.get("sourceItemIndex")) is None
            or item.get("state") != "open_balance"
            or identity in identities
        ):
            _fail(code)
        identities.add(identity)
        result.append(dict(item))
    return result


def _validate_domain_state(domain, missing, reasons, reviews):
    code = "warehouse_anomaly_relevant_domain_invalid"
    state = domain["state"]
    blocking_evidence = bool(
        not domain["schemaReady"]
        or missing
        or not domain["scanComplete"]
        or domain["factsTruncated"]
        or domain["needsReviewTruncated"]
    )
    if state == "complete":
        valid = bool(
            domain["complete"]
            and not blocking_evidence
            and not reasons
            and not reviews
        )
    elif state == "review_required":
        valid = bool(
            not domain["complete"]
            and not blocking_evidence
            and reasons
        )
    elif state == "incomplete":
        valid = bool(not domain["complete"] and blocking_evidence)
    else:
        valid = bool(
            state == "not_collected"
            and not domain["complete"]
            and not domain["scanComplete"]
        )
    if not valid:
        _fail(code)


def _validated_domain(domain, *, supply):
    code = "warehouse_anomaly_relevant_domain_invalid"
    fields = _SUPPLY_FIELDS if supply else _WAREHOUSE_FIELDS
    summary_fields = (
        _SUPPLY_SUMMARY_FIELDS if supply else _WAREHOUSE_SUMMARY_FIELDS
    )
    evidence_fields = (
        _SUPPLY_EVIDENCE_FIELDS if supply else _WAREHOUSE_EVIDENCE_FIELDS
    )
    domain = _strict_mapping(domain, fields, code)
    summary = _strict_mapping(domain.get("summary"), summary_fields, code)
    if (
        domain.get("state") not in _DOMAIN_STATES
        or any(type(domain.get(name)) is not bool for name in (
            "schemaReady", "scanComplete", "complete", "factsTruncated",
            "needsReviewTruncated",
        ))
        or any(_non_negative_int(value) is None for value in summary.values())
    ):
        _fail(code)
    missing = _missing_columns(domain.get("missingColumns"), code)
    reasons = _reason_counts(domain.get("reasonCounts"), code)
    raw_reviews = domain.get("needsReview")
    if not isinstance(raw_reviews, list):
        _fail(code)
    if len(raw_reviews) > PREVIEW_LIMIT:
        _fail("warehouse_anomaly_candidate_limit_exceeded")
    reviews = [_review(item, supply=supply) for item in raw_reviews]
    if summary["needsReview"] != sum(reasons.values()):
        _fail(code)
    visible_reasons = Counter(item["reasonCode"] for item in reviews)
    if domain["needsReviewTruncated"]:
        if (
            not set(visible_reasons).issubset(reasons)
            or any(
                visible_reasons[reason] > count
                for reason, count in reasons.items()
            )
        ):
            _fail(code)
    elif supply and dict(visible_reasons) != reasons:
        _fail(code)

    _validate_domain_state(domain, missing, reasons, reviews)

    evidence = _strict_mapping(
        domain.get("protectedEvidence"), evidence_fields, code,
    )
    evidence = {
        name: _bounded_ids(values, code)
        for name, values in evidence.items()
    }
    if supply:
        visible = _open_supply(domain.get("openSupply"))
        count_pairs = (
            ("openSupplyItems", visible),
            ("closedSupplyRequests", evidence["closedSupplyRequestIds"]),
            ("deliveries", evidence["deliveryIds"]),
            ("allocations", evidence["allocationIds"]),
            ("supplierInvoices", evidence["supplierInvoiceIds"]),
        )
    else:
        count_pairs = (
            ("warehouseInvoices", evidence["warehouseInvoiceIds"]),
            ("warehouseHistoryRows", evidence["warehouseHistoryIds"]),
            ("receiptLots", evidence["receiptLotIds"]),
            ("warehouseMovements", evidence["warehouseMovementIds"]),
            ("lotMovements", evidence["lotMovementIds"]),
        )
    for count_name, values in count_pairs:
        count = summary[count_name]
        if count < len(values) or (
            not domain["factsTruncated"] and count != len(values)
        ):
            _fail(code)

    result = {
        "state": domain["state"],
        "schemaReady": domain["schemaReady"],
        "missingColumns": missing,
        "scanComplete": domain["scanComplete"],
        "complete": domain["complete"],
        "factsTruncated": domain["factsTruncated"],
        "needsReviewTruncated": domain["needsReviewTruncated"],
        "summary": dict(summary),
        "reasonCounts": reasons,
        "needsReview": reviews,
    }
    if supply:
        result["openSupply"] = visible
    return result


def _source(report_source):
    source = _strict_mapping(
        report_source,
        _SOURCE_FIELDS,
        "warehouse_anomaly_source_invalid",
    )
    ids = {
        name: _positive_int(source.get(name))
        for name in (
            "companyId", "projectId", "estimateId", "reconciliationId",
            "baseEstimateId",
        )
    }
    if (
        None in ids.values()
        or ids["baseEstimateId"] == ids["estimateId"]
        or source.get("reconciliationStatus") not in _RECONCILIATION_STATES
    ):
        _fail("warehouse_anomaly_source_invalid")
    try:
        validate_estimate_revision_source({
            "schemaVersion": REPORT_VERSION,
            "eventType": EVENT_TYPE,
            "companyId": ids["companyId"],
            "projectId": ids["projectId"],
            "estimateId": ids["estimateId"],
            "sourceRevision": source.get("sourceRevision"),
        })
    except EstimateRevisionImpactContractError as exc:
        raise WarehouseAnomalyReadinessError(
            "warehouse_anomaly_source_invalid"
        ) from exc
    return {
        "companyId": ids["companyId"],
        "projectId": ids["projectId"],
        "estimateId": ids["estimateId"],
        "sourceRevision": source["sourceRevision"],
        "reconciliationId": ids["reconciliationId"],
        "baseEstimateId": ids["baseEstimateId"],
    }


def _validated_report(report):
    report = _strict_mapping(
        report, _REPORT_FIELDS, "warehouse_anomaly_report_invalid",
    )
    domains = report.get("domains")
    if (
        type(report.get("combinedReportVersion")) is not int
        or report.get("combinedReportVersion") != COMBINED_REPORT_VERSION
        or report.get("ok") is not True
        or report.get("dryRun") is not True
        or _non_negative_int(report.get("writesAttempted")) != 0
        or report.get("readOnlyTransaction") is not True
        or report.get("rolledBack") is not True
        or type(report.get("complete")) is not bool
        or type(report.get("actionable")) is not bool
        or report.get("domainOrder") != list(DOMAIN_ORDER)
        or not isinstance(domains, Mapping)
        or set(domains) != set(DOMAIN_ORDER)
    ):
        _fail("warehouse_anomaly_report_invalid")
    global_reasons = _reason_counts(
        report.get("reasonCounts"), "warehouse_anomaly_report_invalid",
    )
    aggregate = Counter()
    domain_complete = []
    for name in DOMAIN_ORDER:
        domain = domains.get(name)
        if (
            not isinstance(domain, Mapping)
            or type(domain.get("complete")) is not bool
        ):
            _fail("warehouse_anomaly_report_invalid")
        domain_complete.append(domain["complete"])
        reasons = domain.get("reasonCounts")
        if not isinstance(reasons, Mapping):
            _fail("warehouse_anomaly_report_invalid")
        aggregate.update(_reason_counts(
            reasons, "warehouse_anomaly_report_invalid",
        ))
    if dict(sorted(aggregate.items())) != global_reasons:
        _fail("warehouse_anomaly_report_invalid")
    economics = domains["economics"]
    if type(economics.get("actionable")) is not bool:
        _fail("warehouse_anomaly_report_invalid")
    expected_complete = all(domain_complete)
    expected_actionable = bool(
        expected_complete and economics["actionable"]
    )
    if (
        report["complete"] is not expected_complete
        or report["actionable"] is not expected_actionable
    ):
        _fail("warehouse_anomaly_report_invalid")

    public_source = _source(report.get("source"))
    supplied_hash = report.get("evidenceSha256")
    try:
        calculated_hash = calculate_evidence_sha256(report)
    except Exception as exc:
        raise WarehouseAnomalyReadinessError(
            "warehouse_anomaly_evidence_invalid"
        ) from exc
    if (
        not isinstance(supplied_hash, str)
        or not _HASH_RE.fullmatch(supplied_hash)
        or supplied_hash != calculated_hash
    ):
        _fail("warehouse_anomaly_evidence_invalid")
    public_source["impactEvidenceSha256"] = supplied_hash
    return domains, public_source


def _systemic_gap(supply, warehouse):
    present = set(supply["reasonCounts"]) | set(warehouse["reasonCounts"])
    systemic = present & _SYSTEMIC_REASONS
    if not systemic:
        return False
    if len(systemic) != 1:
        _fail("warehouse_anomaly_relevant_domain_invalid")
    reason = next(iter(systemic))
    expected_review = {
        "reasonCode": reason,
        "sourceKind": "supplyWarehouse",
        "sourceId": None,
    }
    if (
        supply["reasonCounts"] != {reason: 1}
        or supply["summary"]["needsReview"] != 1
        or supply["needsReview"] != [expected_review]
        or supply["needsReviewTruncated"] is not False
        or warehouse["reasonCounts"] != {reason: 1}
        or warehouse["summary"]["needsReview"] != 1
        or warehouse["needsReview"] != []
        or warehouse["needsReviewTruncated"] is not False
    ):
        _fail("warehouse_anomaly_relevant_domain_invalid")
    return True


def _validate_warehouse_reason_alignment(warehouse):
    visible = Counter(
        item["reasonCode"] for item in warehouse["needsReview"]
    )
    reasons = warehouse["reasonCounts"]
    if warehouse["needsReviewTruncated"]:
        if (
            not set(visible).issubset(reasons)
            or any(
                visible[reason] > count for reason, count in reasons.items()
            )
        ):
            _fail("warehouse_anomaly_relevant_domain_invalid")
    elif dict(visible) != reasons:
        _fail("warehouse_anomaly_relevant_domain_invalid")


def _supply_ready(supply):
    return bool(
        supply["state"] == "complete"
        and supply["schemaReady"] is True
        and supply["missingColumns"] == []
        and supply["scanComplete"] is True
        and supply["complete"] is True
        and supply["factsTruncated"] is False
        and supply["reasonCounts"] == {}
        and supply["needsReview"] == []
        and supply["needsReviewTruncated"] is False
    )


def _shape_matches(item, expected_source_kind):
    has_kind = "sourceKind" in item
    if expected_source_kind is None:
        if has_kind:
            _fail("warehouse_anomaly_relevant_domain_invalid")
        return True
    if not has_kind:
        _fail("warehouse_anomaly_relevant_domain_invalid")
    return item["sourceKind"] == expected_source_kind


def _warehouse_blockers(warehouse):
    blockers = []
    if not warehouse["schemaReady"] or warehouse["missingColumns"]:
        blockers.append("warehouse_anomaly_schema_not_ready")
    if not warehouse["scanComplete"]:
        blockers.append("warehouse_anomaly_scan_incomplete")
    if warehouse["factsTruncated"]:
        blockers.append("warehouse_anomaly_facts_truncated")
    if warehouse["needsReviewTruncated"]:
        blockers.append("warehouse_anomaly_reviews_truncated")
    return blockers


def _classify(warehouse):
    candidates = []
    blockers = _warehouse_blockers(warehouse)
    candidate_keys = set()
    for item in warehouse["needsReview"]:
        reason = item["reasonCode"]
        if reason in _CANDIDATE_RULES:
            subject_kind, source_kind, recommendation_code = (
                _CANDIDATE_RULES[reason]
            )
            kind_matches = _shape_matches(item, source_kind)
            subject_id = _positive_int(item.get("sourceId"))
            if not kind_matches or subject_id is None:
                blockers.append("warehouse_anomaly_subject_invalid")
                continue
            key = (subject_kind, subject_id, reason)
            if key in candidate_keys:
                blockers.append("warehouse_anomaly_duplicate_candidate")
                continue
            candidate_keys.add(key)
            candidates.append({
                "subjectKind": subject_kind,
                "subjectId": subject_id,
                "anomalyCode": reason,
                "recommendationCode": recommendation_code,
            })
            continue

        if reason in _SUBJECT_INVALID_RULES:
            _shape_matches(item, _SUBJECT_INVALID_RULES[reason])
            blockers.append("warehouse_anomaly_subject_invalid")
            continue

        if reason in _ITEM_LIMIT_RULES:
            kind_matches = _shape_matches(item, _ITEM_LIMIT_RULES[reason])
            if not kind_matches or _positive_int(item.get("sourceId")) is None:
                blockers.append("warehouse_anomaly_subject_invalid")
            else:
                blockers.append(
                    "warehouse_anomaly_source_items_limit_exceeded"
                )
            continue

        blockers.append("warehouse_anomaly_reason_unsupported")

    return sorted(
        candidates,
        key=lambda item: (
            item["subjectKind"], item["subjectId"], item["anomalyCode"],
        ),
    ), blockers


def _result(source, candidates, blockers):
    blockers = sorted(set(blockers))
    if blockers:
        state = "blocked"
        candidates = []
    elif candidates:
        state = "ready"
    else:
        state = "clear"
    classification_complete = not blockers
    ready = state == "ready"
    return {
        "warehouseAnomalyReadinessVersion": (
            WAREHOUSE_ANOMALY_READINESS_VERSION
        ),
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "previewOnly": True,
        "stockMovementAllowed": False,
        "inventoryAdjustmentAllowed": False,
        "applyAllowed": False,
        "state": state,
        "source": source,
        "classificationComplete": classification_complete,
        "readyForRecommendationPreview": ready,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "blockers": blockers,
    }


def build_warehouse_anomaly_readiness(report):
    """Classify exact A7 warehouse review rows without reading or writing."""

    domains, source = _validated_report(report)
    supply = _validated_domain(domains["supply"], supply=True)
    warehouse = _validated_domain(domains["warehouse"], supply=False)
    if any(
        item["sourceEstimateId"] != source["baseEstimateId"]
        for item in supply["openSupply"]
    ):
        _fail("warehouse_anomaly_source_invalid")
    if _systemic_gap(supply, warehouse):
        return _result(
            source, [], ["warehouse_anomaly_systemic_source_incomplete"],
        )
    _validate_warehouse_reason_alignment(warehouse)
    if not _supply_ready(supply):
        return _result(source, [], ["warehouse_anomaly_supply_not_ready"])

    candidates, blockers = _classify(warehouse)
    if not blockers and not candidates and not (
        warehouse["state"] == "complete"
        and warehouse["complete"] is True
    ):
        _fail("warehouse_anomaly_relevant_domain_invalid")
    return _result(source, candidates, blockers)


__all__ = [
    "WAREHOUSE_ANOMALY_READINESS_VERSION",
    "WarehouseAnomalyReadinessError",
    "build_warehouse_anomaly_readiness",
]
