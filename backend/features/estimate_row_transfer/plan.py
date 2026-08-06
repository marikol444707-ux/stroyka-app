"""Pure validation and deterministic E4.2 reviewed-plan construction."""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation


MAX_PLAN_ENTRIES = 100
MAX_QUANTITY_INTEGER_DIGITS = 14
QUANTITY_SCALE = 6
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PlanValidationError(ValueError):
    """Fixed-code validation error safe to map at the API boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _exact_int(value, *, positive):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if positive and value <= 0:
        return None
    if not positive and value < 0:
        return None
    return value


def _canonical_key(value):
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 255:
        return None
    return value


def _canonical_quantity(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not quantity.is_finite() or quantity <= 0:
        return None
    exponent = quantity.as_tuple().exponent
    if exponent < -QUANTITY_SCALE:
        return None
    integer_digits = max(quantity.adjusted() + 1, 0)
    if integer_digits > MAX_QUANTITY_INTEGER_DIGITS:
        return None
    normalized = format(quantity.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _normalize_entry(raw):
    if not isinstance(raw, dict):
        raise PlanValidationError("mapping_invalid")
    source_kind = raw.get("sourceKind")
    if source_kind not in ("assignment", "supply"):
        raise PlanValidationError("mapping_source_kind_invalid")
    common_keys = {
        "sourceKind",
        "sourceId",
        "quantity",
        "targetSectionIndex",
        "targetItemIndex",
        "targetItemKey",
    }
    expected_keys = set(common_keys)
    if source_kind == "supply":
        expected_keys.update(("requestItemIndex", "sourceEstimateVersionId"))
    if set(raw) != expected_keys:
        raise PlanValidationError("mapping_fields_invalid")

    source_id = _exact_int(raw.get("sourceId"), positive=True)
    target_section_index = _exact_int(raw.get("targetSectionIndex"), positive=False)
    target_item_index = _exact_int(raw.get("targetItemIndex"), positive=False)
    target_item_key = _canonical_key(raw.get("targetItemKey"))
    quantity = _canonical_quantity(raw.get("quantity"))
    if source_id is None:
        raise PlanValidationError("mapping_source_identity_invalid")
    if target_section_index is None or target_item_index is None or not target_item_key:
        raise PlanValidationError("mapping_target_coordinate_invalid")
    if quantity is None:
        raise PlanValidationError("mapping_quantity_invalid")

    normalized = {
        "sourceKind": source_kind,
        "sourceId": source_id,
        "quantity": quantity,
        "targetSectionIndex": target_section_index,
        "targetItemIndex": target_item_index,
        "targetItemKey": target_item_key,
    }
    if source_kind == "supply":
        request_item_index = _exact_int(raw.get("requestItemIndex"), positive=False)
        source_version_id = _exact_int(raw.get("sourceEstimateVersionId"), positive=True)
        if request_item_index is None:
            raise PlanValidationError("mapping_request_item_invalid")
        if source_version_id is None:
            raise PlanValidationError("mapping_source_snapshot_invalid")
        normalized["requestItemIndex"] = request_item_index
        normalized["sourceEstimateVersionId"] = source_version_id
    return normalized


def normalize_draft_payload(data):
    if not isinstance(data, dict) or set(data) != {"reconciliationId", "entries"}:
        raise PlanValidationError("draft_fields_invalid")
    reconciliation_id = _exact_int(data.get("reconciliationId"), positive=True)
    if reconciliation_id is None:
        raise PlanValidationError("reconciliation_id_invalid")
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list) or not 1 <= len(raw_entries) <= MAX_PLAN_ENTRIES:
        raise PlanValidationError("mapping_count_invalid")
    entries = [_normalize_entry(item) for item in raw_entries]
    identities = [
        (item["sourceKind"], item["sourceId"], item.get("requestItemIndex"))
        for item in entries
    ]
    if len(set(identities)) != len(identities):
        raise PlanValidationError("mapping_source_duplicate")
    return {"reconciliationId": reconciliation_id, "entries": entries}


def _identity(item):
    return (item.get("sourceKind"), item.get("sourceId"), item.get("requestItemIndex"))


def _canonical_report_quantity(value, code):
    result = _canonical_quantity(value)
    if result is None:
        raise PlanValidationError(code)
    return result


def _canonical_non_negative_quantity(value, code):
    if isinstance(value, bool):
        raise PlanValidationError(code)
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PlanValidationError(code)
    if not quantity.is_finite() or quantity < 0 or quantity.as_tuple().exponent < -QUANTITY_SCALE:
        raise PlanValidationError(code)
    integer_digits = max(quantity.adjusted() + 1, 0) if quantity else 0
    if integer_digits > MAX_QUANTITY_INTEGER_DIGITS:
        raise PlanValidationError(code)
    normalized = format(quantity.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _canonical_plan_sha256(plan):
    payload = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _valid_context(reconciliation, base_snapshot, target_snapshot):
    ids = (
        reconciliation.get("companyId"),
        reconciliation.get("projectId"),
        reconciliation.get("reconciliationId"),
        reconciliation.get("baseEstimateId"),
        reconciliation.get("targetEstimateId"),
    )
    if any(_exact_int(value, positive=True) is None for value in ids):
        return False
    if reconciliation["baseEstimateId"] == reconciliation["targetEstimateId"]:
        return False
    for field in ("workPackage", "smetaType"):
        value = reconciliation.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            return False
    if base_snapshot.get("estimateId") != reconciliation["baseEstimateId"]:
        return False
    if target_snapshot.get("estimateId") != reconciliation["targetEstimateId"]:
        return False
    return all(
        isinstance(snapshot.get("sectionsSha256"), str)
        and _SHA256_RE.fullmatch(snapshot["sectionsSha256"])
        and _exact_int(snapshot.get("rowCount"), positive=False) is not None
        for snapshot in (base_snapshot, target_snapshot)
    )


def _validated_supply_snapshot(entry, candidate, base_snapshot, supply_snapshots):
    key = (entry["sourceId"], entry["requestItemIndex"], entry["sourceEstimateVersionId"])
    snapshot = dict((supply_snapshots or {}).get(key) or {})
    source = dict(candidate.get("source") or {})
    if (
        snapshot.get("estimateVersionId") != entry["sourceEstimateVersionId"]
        or snapshot.get("estimateId") != base_snapshot.get("estimateId")
        or snapshot.get("sectionIndex") != source.get("sectionIndex")
        or snapshot.get("itemIndex") != source.get("itemIndex")
        or snapshot.get("itemKey") != source.get("itemKey")
        or snapshot.get("sectionsSha256") != base_snapshot.get("sectionsSha256")
    ):
        raise PlanValidationError("supply_source_snapshot_invalid")
    return {
        "estimateId": snapshot["estimateId"],
        "estimateVersionId": snapshot["estimateVersionId"],
        "sectionIndex": snapshot["sectionIndex"],
        "itemIndex": snapshot["itemIndex"],
        "itemKey": snapshot["itemKey"],
        "sectionsSha256": snapshot["sectionsSha256"],
    }


def build_reviewed_plan(report, entries, supply_snapshots=None):
    if not isinstance(report, dict) or report.get("ok") is not True:
        raise PlanValidationError("impact_not_ready")
    if report.get("candidatePreviewTruncated") or report.get("needsReviewTruncated"):
        raise PlanValidationError("impact_preview_truncated")
    reconciliation = dict(report.get("reconciliation") or {})
    base_snapshot = dict(report.get("baseSnapshot") or {})
    target_snapshot = dict(report.get("targetSnapshot") or {})
    if not _valid_context(reconciliation, base_snapshot, target_snapshot):
        raise PlanValidationError("impact_context_invalid")

    candidates = {
        _identity(item): item
        for item in [
            *(report.get("assignmentCandidates") or []),
            *(report.get("supplyCandidates") or []),
        ]
    }
    targets = {
        _identity(item): item
        for item in (report.get("targetMappings") or [])
        if item.get("state") == "verified"
    }
    allowed_supply_blockers = {
        (entry["sourceId"], entry["requestItemIndex"])
        for entry in entries
        if entry["sourceKind"] == "supply"
    }
    if int((report.get("reasonCounts") or {}).get("supply_source_snapshot_missing") or 0) != len(
        allowed_supply_blockers
    ):
        raise PlanValidationError("impact_not_ready")
    for blocker in report.get("needsReview") or []:
        if not (
            blocker.get("sourceKind") == "supply"
            and blocker.get("reasonCode") == "supply_source_snapshot_missing"
            and any(source_id == blocker.get("sourceId") for source_id, _ in allowed_supply_blockers)
        ):
            raise PlanValidationError("impact_not_ready")

    planned_entries = []
    for entry in entries:
        identity = _identity(entry)
        candidate = candidates.get(identity)
        target_mapping = targets.get(identity)
        if not candidate:
            raise PlanValidationError("mapping_source_not_candidate")
        if not target_mapping:
            raise PlanValidationError("mapping_target_not_verified")
        quantity = _canonical_report_quantity(entry["quantity"], "mapping_quantity_invalid")
        available = _canonical_report_quantity(
            candidate.get("transferableQuantity"),
            "source_available_quantity_invalid",
        )
        if Decimal(quantity) > Decimal(available):
            raise PlanValidationError("mapping_quantity_exceeds_available")

        if entry["sourceKind"] == "assignment":
            source = dict(candidate.get("source") or {})
            source_parent_id = candidate.get("contractId")
            total = candidate.get("assignmentQuantity")
            protected = candidate.get("confirmedQuantity")
        else:
            source = _validated_supply_snapshot(
                entry,
                candidate,
                base_snapshot,
                supply_snapshots,
            )
            source_parent_id = entry["sourceId"]
            total = candidate.get("requestedQuantity")
            protected = candidate.get("receivedQuantity")

        planned = {
            "sourceKind": entry["sourceKind"],
            "sourceId": entry["sourceId"],
            "sourceParentId": source_parent_id,
            "source": source,
            "target": dict(target_mapping["target"]),
            "sourceTotalQuantity": _canonical_report_quantity(total, "source_total_quantity_invalid"),
            "sourceProtectedQuantity": _canonical_non_negative_quantity(
                protected,
                "source_protected_quantity_invalid",
            ),
            "sourceAvailableQuantity": available,
            "quantity": quantity,
        }
        if entry["sourceKind"] == "supply":
            planned["requestItemIndex"] = entry["requestItemIndex"]
        planned_entries.append(planned)

    planned_entries.sort(key=lambda item: _identity(item))
    plan = {
        "planVersion": 1,
        "companyId": reconciliation.get("companyId"),
        "projectId": reconciliation.get("projectId"),
        "workPackage": reconciliation.get("workPackage"),
        "smetaType": reconciliation.get("smetaType"),
        "reconciliationId": reconciliation.get("reconciliationId"),
        "baseEstimateId": reconciliation.get("baseEstimateId"),
        "targetEstimateId": reconciliation.get("targetEstimateId"),
        "baseSnapshot": base_snapshot,
        "targetSnapshot": target_snapshot,
        "entries": planned_entries,
    }
    plan["planSha256"] = _canonical_plan_sha256(plan)
    return plan
