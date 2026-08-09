"""Pure A8.1 readiness contract for exact supply recommendation candidates."""

import re
from collections import defaultdict
from collections.abc import Mapping

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


READINESS_VERSION = 1

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
_MATERIAL_FIELDS = _DOMAIN_COMMON_FIELDS | _field_set(
    "summary changedPairs baseOnlyRows targetOnlyRows"
)
_SUPPLY_FIELDS = _DOMAIN_COMMON_FIELDS | _field_set(
    "summary openSupply protectedEvidence"
)
_WAREHOUSE_FIELDS = _DOMAIN_COMMON_FIELDS | _field_set(
    "summary protectedEvidence"
)
_MATERIAL_SUMMARY_FIELDS = _field_set(
    "baseMaterialRows targetMaterialRows pairedRows changedPairs baseOnlyRows "
    "targetOnlyRows needsReview"
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
_PAIR_FIELDS = _field_set(
    "base target matchKind aliasIds changeKinds"
)
_OPEN_SUPPLY_FIELDS = _field_set(
    "requestId requestItemIndex sourceEstimateId sourceSectionIndex "
    "sourceItemIndex state"
)
_MATCH_KINDS = frozenset({"stable_item_key", "confirmed_alias"})
_CHANGE_KINDS = frozenset({
    "quantity_changed",
    "identity_changed",
    "alias_identity_changed",
})
_DOMAIN_STATES = frozenset({
    "complete",
    "incomplete",
    "review_required",
    "not_collected",
    "non_actionable",
})
_RECONCILIATION_STATES = frozenset({
    "Черновик",
    "На проверке",
    "Утверждена",
    "Отклонена",
})
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class SupplyRecommendationReadinessError(ValueError):
    """Fixed-code validation error without business content."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _fail(code):
    raise SupplyRecommendationReadinessError(code)


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


def _bounded_ids(value, code="supply_recommendation_lineage_invalid"):
    if not isinstance(value, list):
        _fail(code)
    if len(value) > PREVIEW_LIMIT:
        _fail("supply_recommendation_candidate_limit_exceeded")
    if (
        any(_positive_int(item) is None for item in value)
        or value != sorted(set(value))
    ):
        _fail(code)
    return list(value)


def _coordinate(value):
    value = _strict_mapping(
        value,
        {"estimateId", "sectionIndex", "itemIndex"},
        "supply_recommendation_lineage_invalid",
    )
    coordinate = {
        "estimateId": _positive_int(value.get("estimateId")),
        "sectionIndex": _non_negative_int(value.get("sectionIndex")),
        "itemIndex": _non_negative_int(value.get("itemIndex")),
    }
    if None in coordinate.values():
        _fail("supply_recommendation_lineage_invalid")
    return coordinate


def _validated_domain(domain, fields, summary_fields, evidence_fields=None):
    code = "supply_recommendation_relevant_domain_invalid"
    domain = _strict_mapping(domain, fields, code)
    summary = _strict_mapping(domain.get("summary"), summary_fields, code)
    missing = domain.get("missingColumns")
    reviews = domain.get("needsReview")
    reasons = domain.get("reasonCounts")
    if (
        type(domain.get("schemaReady")) is not bool
        or type(domain.get("scanComplete")) is not bool
        or type(domain.get("complete")) is not bool
        or type(domain.get("factsTruncated")) is not bool
        or type(domain.get("needsReviewTruncated")) is not bool
        or domain.get("state") not in _DOMAIN_STATES
        or not isinstance(missing, list)
        or len(missing) > PREVIEW_LIMIT
        or not all(isinstance(item, str) for item in missing)
        or not isinstance(reasons, Mapping)
        or len(reasons) > PREVIEW_LIMIT
        or any(
            not isinstance(reason, str)
            or not reason
            or _positive_int(count) is None
            for reason, count in reasons.items()
        )
        or not isinstance(reviews, list)
        or len(reviews) > PREVIEW_LIMIT
        or any(_non_negative_int(value) is None for value in summary.values())
    ):
        _fail(code)
    review_count = summary["needsReview"]
    if (
        review_count != sum(reasons.values())
        or review_count < len(reviews)
        or (
            review_count != len(reviews)
            and domain["needsReviewTruncated"] is False
        )
    ):
        _fail(code)
    evidence = None
    if evidence_fields is not None:
        evidence = _strict_mapping(
            domain.get("protectedEvidence"), evidence_fields, code,
        )
        for values in evidence.values():
            _bounded_ids(values, code)
    return domain, summary, evidence


def _domain_ready(domain):
    return bool(
        domain["state"] == "complete"
        and domain["schemaReady"] is True
        and domain["missingColumns"] == []
        and domain["scanComplete"] is True
        and domain["complete"] is True
        and domain["factsTruncated"] is False
        and domain["reasonCounts"] == {}
        and domain["needsReview"] == []
        and domain["needsReviewTruncated"] is False
    )


def _validate_visible_count(domain, summary, count_name, values):
    count = summary[count_name]
    if count < len(values) or (
        count != len(values) and domain["factsTruncated"] is False
    ):
        _fail("supply_recommendation_relevant_domain_invalid")


def _source(report_source):
    source = _strict_mapping(
        report_source,
        _SOURCE_FIELDS,
        "supply_recommendation_source_invalid",
    )
    ids = {
        name: _positive_int(source.get(name))
        for name in (
            "companyId",
            "projectId",
            "estimateId",
            "reconciliationId",
            "baseEstimateId",
        )
    }
    if (
        None in ids.values()
        or ids["baseEstimateId"] == ids["estimateId"]
        or source.get("reconciliationStatus") not in _RECONCILIATION_STATES
    ):
        _fail("supply_recommendation_source_invalid")
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
        raise SupplyRecommendationReadinessError(
            "supply_recommendation_source_invalid"
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
        report,
        _REPORT_FIELDS,
        "supply_recommendation_report_invalid",
    )
    domains = report.get("domains")
    if (
        report.get("combinedReportVersion") != COMBINED_REPORT_VERSION
        or report.get("ok") is not True
        or report.get("dryRun") is not True
        or report.get("writesAttempted") != 0
        or report.get("readOnlyTransaction") is not True
        or report.get("rolledBack") is not True
        or type(report.get("complete")) is not bool
        or type(report.get("actionable")) is not bool
        or report.get("domainOrder") != list(DOMAIN_ORDER)
        or not isinstance(domains, Mapping)
        or set(domains) != set(DOMAIN_ORDER)
        or not isinstance(report.get("reasonCounts"), Mapping)
    ):
        _fail("supply_recommendation_report_invalid")

    public_source = _source(report.get("source"))
    supplied_hash = report.get("evidenceSha256")
    try:
        calculated_hash = calculate_evidence_sha256(report)
    except Exception as exc:
        raise SupplyRecommendationReadinessError(
            "supply_recommendation_evidence_invalid"
        ) from exc
    if (
        not isinstance(supplied_hash, str)
        or not _HASH_RE.fullmatch(supplied_hash)
        or supplied_hash != calculated_hash
    ):
        _fail("supply_recommendation_evidence_invalid")
    public_source["impactEvidenceSha256"] = supplied_hash
    return domains, public_source


def _pairs(material_domain, source):
    raw_pairs = material_domain.get("changedPairs")
    if not isinstance(raw_pairs, list):
        _fail("supply_recommendation_lineage_invalid")
    if len(raw_pairs) > PREVIEW_LIMIT:
        _fail("supply_recommendation_candidate_limit_exceeded")

    pairs = []
    for raw_pair in raw_pairs:
        pair = _strict_mapping(
            raw_pair,
            _PAIR_FIELDS,
            "supply_recommendation_lineage_invalid",
        )
        base = _coordinate(pair.get("base"))
        target = _coordinate(pair.get("target"))
        change_kinds = pair.get("changeKinds")
        match_kind = pair.get("matchKind")
        alias_ids = _bounded_ids(pair.get("aliasIds"))
        if (
            match_kind not in _MATCH_KINDS
            or not isinstance(change_kinds, list)
            or not change_kinds
            or change_kinds != sorted(set(change_kinds))
            or any(kind not in _CHANGE_KINDS for kind in change_kinds)
            or (match_kind == "confirmed_alias" and not alias_ids)
            or (
                match_kind == "confirmed_alias"
                and "identity_changed" in change_kinds
            )
            or (
                match_kind == "stable_item_key"
                and "alias_identity_changed" in change_kinds
            )
        ):
            _fail("supply_recommendation_lineage_invalid")
        if (
            base["estimateId"] != source["baseEstimateId"]
            or target["estimateId"] != source["estimateId"]
        ):
            _fail("supply_recommendation_source_invalid")
        pairs.append({
            "base": base,
            "target": target,
            "matchKind": match_kind,
            "aliasIds": alias_ids,
        })
    return pairs


def _open_supply(supply_domain, source):
    raw_items = supply_domain.get("openSupply")
    if not isinstance(raw_items, list):
        _fail("supply_recommendation_lineage_invalid")
    if len(raw_items) > PREVIEW_LIMIT:
        _fail("supply_recommendation_candidate_limit_exceeded")

    open_items = []
    request_items = set()
    for raw_item in raw_items:
        item = _strict_mapping(
            raw_item,
            _OPEN_SUPPLY_FIELDS,
            "supply_recommendation_lineage_invalid",
        )
        request_id = _positive_int(item.get("requestId"))
        item_index = _non_negative_int(item.get("requestItemIndex"))
        base = _coordinate({
            "estimateId": item.get("sourceEstimateId"),
            "sectionIndex": item.get("sourceSectionIndex"),
            "itemIndex": item.get("sourceItemIndex"),
        })
        request_item = (request_id, item_index)
        if (
            request_id is None
            or item_index is None
            or item.get("state") != "open_balance"
            or request_item in request_items
        ):
            _fail("supply_recommendation_lineage_invalid")
        if base["estimateId"] != source["baseEstimateId"]:
            _fail("supply_recommendation_source_invalid")
        request_items.add(request_item)
        open_items.append({
            "requestId": request_id,
            "requestItemIndex": item_index,
            "base": base,
        })
    return open_items


def _material_domain(domain, source):
    domain, summary, _evidence = _validated_domain(
        domain,
        _MATERIAL_FIELDS,
        _MATERIAL_SUMMARY_FIELDS,
    )
    pairs = _pairs(domain, source)
    _validate_visible_count(domain, summary, "changedPairs", pairs)
    for rows_name, estimate_name in (
        ("baseOnlyRows", "baseEstimateId"),
        ("targetOnlyRows", "estimateId"),
    ):
        raw_rows = domain[rows_name]
        if not isinstance(raw_rows, list):
            _fail("supply_recommendation_lineage_invalid")
        if len(raw_rows) > PREVIEW_LIMIT:
            _fail("supply_recommendation_candidate_limit_exceeded")
        coordinates = [_coordinate(row) for row in raw_rows]
        if any(
            coordinate["estimateId"] != source[estimate_name]
            for coordinate in coordinates
        ):
            _fail("supply_recommendation_source_invalid")
        _validate_visible_count(domain, summary, rows_name, coordinates)
    return domain, pairs


def _supply_domain(domain, source):
    domain, summary, evidence = _validated_domain(
        domain,
        _SUPPLY_FIELDS,
        _SUPPLY_SUMMARY_FIELDS,
        _SUPPLY_EVIDENCE_FIELDS,
    )
    open_items = _open_supply(domain, source)
    _validate_visible_count(domain, summary, "openSupplyItems", open_items)
    for count_name, evidence_name in (
        ("closedSupplyRequests", "closedSupplyRequestIds"),
        ("deliveries", "deliveryIds"),
        ("allocations", "allocationIds"),
        ("supplierInvoices", "supplierInvoiceIds"),
    ):
        _validate_visible_count(
            domain, summary, count_name, evidence[evidence_name],
        )
    return domain, open_items


def _warehouse_domain(domain):
    domain, summary, evidence = _validated_domain(
        domain,
        _WAREHOUSE_FIELDS,
        _WAREHOUSE_SUMMARY_FIELDS,
        _WAREHOUSE_EVIDENCE_FIELDS,
    )
    for count_name, evidence_name in (
        ("warehouseInvoices", "warehouseInvoiceIds"),
        ("warehouseHistoryRows", "warehouseHistoryIds"),
        ("receiptLots", "receiptLotIds"),
        ("warehouseMovements", "warehouseMovementIds"),
        ("lotMovements", "lotMovementIds"),
    ):
        _validate_visible_count(
            domain, summary, count_name, evidence[evidence_name],
        )
    return domain


def _result(source, candidates, blockers):
    blockers = sorted(set(blockers))
    candidates = [] if blockers else candidates
    return {
        "readinessVersion": READINESS_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": "blocked" if blockers else "ready",
        "source": source,
        "readyForRecommendationPreview": not blockers,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "blockers": blockers,
    }


def build_supply_recommendation_readiness(report):
    """Bind exact open supply rows to exact base-to-target material lineage."""

    domains, source = _validated_report(report)
    material, pairs = _material_domain(domains["materials"], source)
    supply, open_items = _supply_domain(domains["supply"], source)
    warehouse = _warehouse_domain(domains["warehouse"])
    domain_blockers = [
        "supply_recommendation_" + name + "_not_ready"
        for name, domain in (
            ("materials", material),
            ("supply", supply),
            ("warehouse", warehouse),
        )
        if not _domain_ready(domain)
    ]
    if domain_blockers:
        return _result(source, [], domain_blockers)
    if not open_items:
        return _result(source, [], ["supply_recommendation_no_open_supply"])

    pairs_by_base = defaultdict(list)
    for pair in pairs:
        pairs_by_base[tuple(pair["base"].values())].append(pair)

    candidates = []
    blockers = []
    open_by_base = defaultdict(int)
    for item in open_items:
        base_key = tuple(item["base"].values())
        open_by_base[base_key] += 1
        matches = pairs_by_base.get(base_key, [])
        if not matches:
            blockers.append("supply_recommendation_lineage_missing")
            continue
        if len(matches) != 1:
            blockers.append("supply_recommendation_lineage_ambiguous")
            continue
        pair = matches[0]
        candidates.append({
            "requestId": item["requestId"],
            "requestItemIndex": item["requestItemIndex"],
            **pair,
        })
    if any(count > 1 for count in open_by_base.values()):
        blockers.append("supply_recommendation_open_request_ambiguous")

    candidates.sort(key=lambda item: (
        item["requestId"],
        item["requestItemIndex"],
        *item["base"].values(),
        *item["target"].values(),
    ))
    return _result(source, candidates, blockers)


__all__ = [
    "PREVIEW_LIMIT",
    "READINESS_VERSION",
    "SupplyRecommendationReadinessError",
    "build_supply_recommendation_readiness",
]
