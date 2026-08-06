"""Read-only, fail-closed impact audit for reviewed estimate row transfer."""

import argparse
import json
import math
import re
from collections import Counter, defaultdict

import psycopg2.extras

from backend.features.brigade_lineage.canonical import parse_sections, sections_sha256
from backend.features.brigade_lineage.snapshot_service import (
    LineageResolutionError,
    resolve_snapshot_item,
)
from backend.features.supply_estimate_refresh.service import OPEN_SUPPLY_STATUSES


PREVIEW_LIMIT = 100
REPORT_VERSION = 1
APPROVED_RECONCILIATION_STATUS = "Утверждена"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def parse_reconciliation_id(value):
    if isinstance(value, bool):
        raise ValueError("reconciliation_id_invalid")
    if isinstance(value, int):
        if value > 0:
            return value
        raise ValueError("reconciliation_id_invalid")
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("reconciliation_id_invalid")
    return int(value)


def _non_negative_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result >= 0 else None


def _finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _count(value):
    result = _non_negative_int(value)
    return result if result is not None else 0


def _text(value):
    return str(value or "").strip()


def _work_package(value):
    return _text(value) or "Основная"


def _smeta_type(value):
    return _text(value) or "Заказчик"


def _blocked(source_kind, source_id, reason_code):
    return {
        "sourceKind": source_kind,
        "sourceId": _positive_int(source_id),
        "reasonCode": reason_code,
    }


def _parse_snapshot(value):
    try:
        sections = parse_sections(value)
        digest = sections_sha256(sections)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ):
        return None, None
    return sections, digest


def _row_count(sections):
    return sum(
        len(section.get("items") or [])
        for section in sections or []
        if isinstance(section, dict) and isinstance(section.get("items") or [], list)
    )


def _reconciliation_context(row):
    item = dict(row or {})
    reconciliation_id = _positive_int(item.get("reconciliation_id"))
    if item.get("reconciliation_exists") is not True or not reconciliation_id:
        return None, "reconciliation_not_found"
    if _text(item.get("reconciliation_status")) != APPROVED_RECONCILIATION_STATUS:
        return None, "reconciliation_not_approved"

    company_id = _positive_int(item.get("project_company_id"))
    project_id = _positive_int(item.get("project_id"))
    base_estimate_id = _positive_int(item.get("base_estimate_id"))
    target_estimate_id = _positive_int(item.get("target_estimate_id"))
    if (
        item.get("project_exists") is not True
        or not company_id
        or not project_id
        or not base_estimate_id
        or not target_estimate_id
    ):
        return None, "reconciliation_owner_missing"
    if base_estimate_id == target_estimate_id:
        return None, "reconciliation_estimate_pair_invalid"

    owners = (
        (_positive_int(item.get("base_company_id")), _positive_int(item.get("base_project_id"))),
        (_positive_int(item.get("target_company_id")), _positive_int(item.get("target_project_id"))),
    )
    if any(owner != (company_id, project_id) for owner in owners):
        return None, "reconciliation_owner_mismatch"

    work_package = _work_package(item.get("reconciliation_work_package"))
    if any(
        package != work_package
        for package in (
            _work_package(item.get("base_work_package")),
            _work_package(item.get("target_work_package")),
        )
    ):
        return None, "reconciliation_package_mismatch"
    smeta_type = _smeta_type(item.get("reconciliation_smeta_type"))
    if any(
        estimate_type != smeta_type
        for estimate_type in (
            _smeta_type(item.get("base_smeta_type")),
            _smeta_type(item.get("target_smeta_type")),
        )
    ):
        return None, "reconciliation_estimate_type_mismatch"

    base_sections, base_hash = _parse_snapshot(item.get("base_sections_json"))
    target_sections, target_hash = _parse_snapshot(item.get("target_sections_json"))
    if base_sections is None:
        return None, "base_estimate_content_invalid"
    if target_sections is None:
        return None, "target_estimate_content_invalid"
    return {
        "reconciliationId": reconciliation_id,
        "companyId": company_id,
        "projectId": project_id,
        "workPackage": work_package,
        "smetaType": smeta_type,
        "baseEstimateId": base_estimate_id,
        "targetEstimateId": target_estimate_id,
        "projectName": _text(item.get("project_name")),
        "projectNameOwnerCount": _count(item.get("project_name_owner_count", 1)),
        "baseSections": base_sections,
        "baseSectionsSha256": base_hash,
        "targetSections": target_sections,
        "targetSectionsSha256": target_hash,
    }, None


def _resolve_exact_item(estimate_id, sections, section_index, item_index, item_key):
    try:
        return resolve_snapshot_item(
            estimate_id=estimate_id,
            sections=sections,
            section_index=section_index,
            item_index=item_index,
            expected_item_key=item_key,
        ), None
    except LineageResolutionError as exc:
        return None, exc.code


def _classify_assignment(context, row):
    item = dict(row or {})
    source_id = _positive_int(item.get("contract_item_id"))
    contract_id = _positive_int(item.get("contract_id"))
    if not source_id or not contract_id:
        return None, _blocked("assignment", source_id, "assignment_identity_invalid")
    if _text(item.get("source_type")) != "estimate":
        return None, _blocked("assignment", source_id, "assignment_source_not_exact_estimate")
    if (
        _positive_int(item.get("contract_company_id")),
        _positive_int(item.get("contract_project_id")),
    ) != (context["companyId"], context["projectId"]):
        return None, _blocked("assignment", source_id, "assignment_owner_mismatch")
    if _work_package(item.get("contract_work_package")) != context["workPackage"]:
        return None, _blocked("assignment", source_id, "assignment_package_mismatch")
    if _positive_int(item.get("source_estimate_id")) != context["baseEstimateId"]:
        return None, _blocked("assignment", source_id, "assignment_source_estimate_mismatch")

    version_id = _positive_int(item.get("source_estimate_version_id"))
    section_index = _non_negative_int(item.get("source_section_index"))
    item_index = _non_negative_int(item.get("source_item_index"))
    raw_item_key = item.get("source_item_key")
    item_key = _text(raw_item_key)
    if (
        not version_id
        or section_index is None
        or item_index is None
        or not item_key
        or not isinstance(raw_item_key, str)
        or raw_item_key != item_key
    ):
        return None, _blocked("assignment", source_id, "assignment_source_coordinate_invalid")

    snapshot_sections, actual_hash = _parse_snapshot(item.get("snapshot_sections_json"))
    stored_hash = item.get("snapshot_sections_sha256")
    if snapshot_sections is None:
        return None, _blocked("assignment", source_id, "source_snapshot_content_invalid")
    if (
        not isinstance(stored_hash, str)
        or stored_hash != stored_hash.strip().lower()
        or not _SHA256_RE.fullmatch(stored_hash)
    ):
        return None, _blocked("assignment", source_id, "source_snapshot_hash_invalid")
    if actual_hash != stored_hash:
        return None, _blocked("assignment", source_id, "source_snapshot_hash_mismatch")
    _resolved, resolution_error = _resolve_exact_item(
        context["baseEstimateId"],
        snapshot_sections,
        section_index,
        item_index,
        item_key,
    )
    if resolution_error:
        return None, _blocked("assignment", source_id, "source_" + resolution_error)

    quantity = _finite_number(item.get("assignment_quantity"))
    confirmed = _finite_number(item.get("confirmed_quantity"))
    if quantity is None:
        return None, _blocked("assignment", source_id, "assignment_quantity_non_finite")
    if confirmed is None:
        return None, _blocked("assignment", source_id, "confirmed_quantity_non_finite")
    if quantity < 0:
        return None, _blocked("assignment", source_id, "assignment_quantity_negative")
    if confirmed < 0:
        return None, _blocked("assignment", source_id, "confirmed_quantity_negative")
    if confirmed > quantity:
        return None, _blocked("assignment", source_id, "confirmed_quantity_exceeds_assignment")
    transferable = quantity - confirmed
    if transferable <= 0:
        return None, _blocked("assignment", source_id, "assignment_balance_not_positive")

    return {
        "sourceKind": "assignment",
        "sourceId": source_id,
        "contractId": contract_id,
        "state": "candidate",
        "reasonCode": "exact_source_verified",
        "source": {
            "estimateId": context["baseEstimateId"],
            "estimateVersionId": version_id,
            "sectionIndex": section_index,
            "itemIndex": item_index,
            "itemKey": item_key,
            "sectionsSha256": stored_hash,
        },
        "assignmentQuantity": quantity,
        "confirmedQuantity": confirmed,
        "transferableQuantity": transferable,
        "protectedHistoryCounts": {
            "journalRows": _count(item.get("journal_count")),
            "confirmedJournalRows": _count(item.get("confirmed_journal_count")),
            "hiddenActs": _count(item.get("hidden_act_count")),
            "brigadeActs": _count(item.get("brigade_act_count")),
            "brigadePayments": _count(item.get("brigade_payment_count")),
        },
    }, None


def _parse_items(value):
    if isinstance(value, list):
        return value if all(isinstance(item, dict) for item in value) else None
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        return None
    return parsed


def _canonical_item_key(estimate_id, sections, section_index, item_index):
    try:
        section = sections[section_index]
        row = section["items"][item_index]
    except (IndexError, KeyError, TypeError):
        return None, "source_coordinate_not_found"
    if not isinstance(section, dict) or not isinstance(row, dict):
        return None, "snapshot_content_invalid"
    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        raw = row.get(field)
        if raw in (None, ""):
            continue
        if not isinstance(raw, str) or raw != raw.strip() or len(raw) > 255:
            return None, "source_item_key_noncanonical"
        if raw not in keys:
            keys.append(raw)
    if len(keys) > 1:
        return None, "source_item_key_ambiguous"
    return (keys[0] if keys else "%s:%s:%s" % (estimate_id, section_index, item_index)), None


def _supply_descriptors(context, request, deliveries):
    request_id = _positive_int(request.get("request_id"))
    if not request_id:
        return [], [_blocked("supply", None, "supply_request_identity_invalid")]
    if _positive_int(request.get("request_company_id")) != context["companyId"]:
        return [], [_blocked("supply", request_id, "supply_request_owner_mismatch")]
    if _work_package(request.get("request_work_package")) != context["workPackage"]:
        return [], [_blocked("supply", request_id, "supply_request_package_mismatch")]
    if _text(request.get("request_status")) not in OPEN_SUPPLY_STATUSES:
        return [], [_blocked("supply", request_id, "supply_request_not_open")]
    items = _parse_items(request.get("items_json"))
    if items is None:
        return [], [_blocked("supply", request_id, "supply_items_json_invalid")]

    descriptors = []
    blockers = []
    for request_item_index, request_item in enumerate(items):
        lineage = request_item.get("estimateLineage")
        sources = lineage.get("sources") if isinstance(lineage, dict) else None
        if not isinstance(sources, list):
            continue
        base_sources = [
            source for source in sources
            if isinstance(source, dict)
            and _positive_int(source.get("estimateId")) == context["baseEstimateId"]
        ]
        if not base_sources:
            continue
        if (
            len(sources) != 1
            or len(base_sources) != 1
            or request_item.get("sourceType") != "estimate_material_control"
            or lineage.get("version") != 1
            or lineage.get("validated") is not True
            or base_sources[0].get("validated") is not True
        ):
            blockers.append(_blocked("supply", request_id, "supply_source_ambiguous"))
            continue
        source = base_sources[0]
        section_index = _non_negative_int(source.get("sectionIndex"))
        item_index = _non_negative_int(source.get("itemIndex"))
        if section_index is None or item_index is None:
            blockers.append(_blocked("supply", request_id, "supply_source_coordinate_invalid"))
            continue
        item_key, key_error = _canonical_item_key(
            context["baseEstimateId"],
            context["baseSections"],
            section_index,
            item_index,
        )
        if key_error:
            blockers.append(_blocked("supply", request_id, "supply_" + key_error))
            continue
        resolved, resolution_error = _resolve_exact_item(
            context["baseEstimateId"],
            context["baseSections"],
            section_index,
            item_index,
            item_key,
        )
        if resolution_error:
            blockers.append(_blocked("supply", request_id, "supply_" + resolution_error))
            continue
        material_name = _text(request_item.get("materialName") or request_item.get("name"))
        unit = _text(request_item.get("unit"))
        if (
            not material_name
            or not unit
            or _text(source.get("materialName")) != material_name
            or _text(source.get("unit")) != unit
            or _text(resolved.item.get("name")) != material_name
            or _text(resolved.item.get("unit")) != unit
            or _work_package(request_item.get("workPackage")) != context["workPackage"]
            or _work_package(lineage.get("workPackage")) != context["workPackage"]
        ):
            blockers.append(_blocked("supply", request_id, "supply_source_lineage_drift"))
            continue
        quantity = _finite_number(request_item.get("quantity"))
        if quantity is None:
            blockers.append(_blocked("supply", request_id, "supply_quantity_non_finite"))
            continue
        if quantity <= 0:
            blockers.append(_blocked("supply", request_id, "supply_quantity_not_positive"))
            continue
        descriptors.append({
            "requestId": request_id,
            "requestItemIndex": request_item_index,
            "materialIdentity": (material_name, unit),
            "quantity": quantity,
            "source": {
                "estimateId": context["baseEstimateId"],
                "sectionIndex": section_index,
                "itemIndex": item_index,
                "itemKey": item_key,
            },
        })

    identity_counts = Counter(item["materialIdentity"] for item in descriptors)
    request_deliveries = [
        row for row in deliveries
        if _positive_int(row.get("request_id")) == request_id
    ]
    candidates = []
    for descriptor in descriptors:
        matching_deliveries = [
            row for row in request_deliveries
            if (_text(row.get("material_name")), _text(row.get("unit")))
            == descriptor["materialIdentity"]
        ]
        if identity_counts[descriptor["materialIdentity"]] > 1 and matching_deliveries:
            blockers.append(_blocked("supply", request_id, "supply_delivery_allocation_ambiguous"))
            continue
        received = 0.0
        delivery_invalid = False
        for delivery in matching_deliveries:
            if _positive_int(delivery.get("delivery_company_id")) != context["companyId"]:
                blockers.append(_blocked("supply", request_id, "supply_delivery_owner_mismatch"))
                delivery_invalid = True
                break
            delivery_quantity = _finite_number(delivery.get("received_quantity"))
            if delivery_quantity is None or delivery_quantity < 0:
                blockers.append(_blocked("supply", request_id, "supply_received_quantity_invalid"))
                delivery_invalid = True
                break
            received += delivery_quantity
        if delivery_invalid:
            continue
        if received > descriptor["quantity"]:
            blockers.append(_blocked("supply", request_id, "supply_received_exceeds_requested"))
            continue
        transferable = descriptor["quantity"] - received
        if transferable <= 0:
            blockers.append(_blocked("supply", request_id, "supply_balance_not_positive"))
            continue
        candidates.append({
            "sourceKind": "supply",
            "sourceId": request_id,
            "requestItemIndex": descriptor["requestItemIndex"],
            "state": "needs_review",
            "reasonCode": "supply_source_snapshot_missing",
            "source": descriptor["source"],
            "requestedQuantity": descriptor["quantity"],
            "receivedQuantity": received,
            "transferableQuantity": transferable,
            "protectedHistoryCounts": {
                "deliveries": len(matching_deliveries),
                "offers": _count(request.get("offer_count")),
                "supplierInvoices": _count(request.get("supplier_invoice_count")),
                "warehouseInvoices": _count(request.get("warehouse_invoice_count")),
                "warehouseHistoryRows": _count(request.get("warehouse_history_count")),
                "supplyHistoryRows": _count(request.get("supply_history_count")),
                "claims": _count(request.get("claim_count")),
                "paidInvoices": _count(request.get("paid_invoice_count")),
            },
        })
    return candidates, blockers


def classify_target_mapping(reconciliation, mapping):
    context, reconciliation_error = _reconciliation_context(reconciliation)
    source_kind = _text((mapping or {}).get("sourceKind"))
    source_id = _positive_int((mapping or {}).get("sourceId"))
    if reconciliation_error:
        return {
            "sourceKind": source_kind or "unknown",
            "sourceId": source_id,
            "state": "blocked",
            "reasonCode": reconciliation_error,
        }
    if source_kind not in ("assignment", "supply") or not source_id:
        return {
            "sourceKind": source_kind or "unknown",
            "sourceId": source_id,
            "state": "blocked",
            "reasonCode": "mapping_source_identity_invalid",
        }
    quantity = _finite_number((mapping or {}).get("quantity"))
    if quantity is None or quantity <= 0:
        return {
            "sourceKind": source_kind,
            "sourceId": source_id,
            "state": "blocked",
            "reasonCode": "mapping_quantity_invalid",
        }
    resolved, resolution_error = _resolve_exact_item(
        context["targetEstimateId"],
        context["targetSections"],
        (mapping or {}).get("targetSectionIndex"),
        (mapping or {}).get("targetItemIndex"),
        (mapping or {}).get("targetItemKey"),
    )
    if resolution_error:
        return {
            "sourceKind": source_kind,
            "sourceId": source_id,
            "state": "blocked",
            "reasonCode": "target_" + resolution_error.replace("source_", "", 1),
        }
    return {
        "sourceKind": source_kind,
        "sourceId": source_id,
        "state": "verified",
        "reasonCode": "exact_target_verified",
        "quantity": quantity,
        "target": {
            "estimateId": context["targetEstimateId"],
            "sectionIndex": resolved.source_section_index,
            "itemIndex": resolved.source_item_index,
            "itemKey": resolved.source_item_key,
            "sectionsSha256": context["targetSectionsSha256"],
        },
    }


def build_impact_report(
    reconciliation,
    assignment_rows,
    supply_request_rows,
    delivery_rows,
    mapping_rows=None,
):
    context, reconciliation_error = _reconciliation_context(reconciliation)
    base_report = {
        "reportVersion": REPORT_VERSION,
        "ok": reconciliation_error is None,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForMapping": False,
        "assignmentCandidates": [],
        "supplyCandidates": [],
        "targetMappings": [],
        "needsReview": [],
        "needsReviewTruncated": False,
    }
    if reconciliation_error:
        review = [_blocked(
            "reconciliation",
            (reconciliation or {}).get("reconciliation_id"),
            reconciliation_error,
        )]
        base_report.update({
            "summary": {
                "assignmentCandidates": 0,
                "supplyCandidates": 0,
                "targetMappings": 0,
                "needsReview": 1,
            },
            "reasonCounts": {reconciliation_error: 1},
            "needsReview": review,
        })
        return base_report

    assignment_candidates = []
    blockers = []
    for row in assignment_rows or []:
        candidate, blocker = _classify_assignment(context, row)
        if candidate:
            assignment_candidates.append(candidate)
        if blocker:
            blockers.append(blocker)

    deliveries_by_request = defaultdict(list)
    for delivery in delivery_rows or []:
        deliveries_by_request[_positive_int((delivery or {}).get("request_id"))].append(dict(delivery or {}))
    supply_candidates = []
    if context["projectNameOwnerCount"] != 1:
        blockers.append(_blocked(
            "supply",
            context["projectId"],
            "supply_project_identity_ambiguous",
        ))
    else:
        for request in supply_request_rows or []:
            request_id = _positive_int((request or {}).get("request_id"))
            candidates, request_blockers = _supply_descriptors(
                context,
                dict(request or {}),
                deliveries_by_request.get(request_id, []),
            )
            supply_candidates.extend(candidates)
            blockers.extend(request_blockers)
    blockers.extend(
        _blocked("supply", item["sourceId"], item["reasonCode"])
        for item in supply_candidates
        if item["state"] == "needs_review"
    )

    target_mappings = [
        classify_target_mapping(reconciliation, mapping)
        for mapping in (mapping_rows or [])
    ]
    blockers.extend(
        _blocked(mapping["sourceKind"], mapping["sourceId"], mapping["reasonCode"])
        for mapping in target_mappings
        if mapping["state"] != "verified"
    )
    if not mapping_rows:
        blockers.append(_blocked("mapping", context["reconciliationId"], "exact_target_mapping_required"))

    reason_counts = Counter(item["reasonCode"] for item in blockers)
    preview = blockers[:PREVIEW_LIMIT]
    base_report.update({
        "reconciliation": {
            "reconciliationId": context["reconciliationId"],
            "companyId": context["companyId"],
            "projectId": context["projectId"],
            "baseEstimateId": context["baseEstimateId"],
            "targetEstimateId": context["targetEstimateId"],
        },
        "targetSnapshot": {
            "estimateId": context["targetEstimateId"],
            "sectionsSha256": context["targetSectionsSha256"],
            "rowCount": _row_count(context["targetSections"]),
        },
        "readyForMapping": bool(
            (assignment_candidates or supply_candidates)
            and not blockers
            and target_mappings
            and all(item["state"] == "verified" for item in target_mappings)
        ),
        "assignmentCandidates": assignment_candidates[:PREVIEW_LIMIT],
        "supplyCandidates": supply_candidates[:PREVIEW_LIMIT],
        "targetMappings": target_mappings[:PREVIEW_LIMIT],
        "summary": {
            "assignmentCandidates": len(assignment_candidates),
            "supplyCandidates": len(supply_candidates),
            "targetMappings": len(target_mappings),
            "needsReview": len(blockers),
        },
        "reasonCounts": dict(sorted(reason_counts.items())),
        "needsReview": preview,
        "needsReviewTruncated": len(blockers) > PREVIEW_LIMIT,
        "candidatePreviewTruncated": (
            len(assignment_candidates) > PREVIEW_LIMIT
            or len(supply_candidates) > PREVIEW_LIMIT
            or len(target_mappings) > PREVIEW_LIMIT
        ),
    })
    return base_report


def _load_reconciliation(cur, reconciliation_id):
    cur.execute(
        """SELECT TRUE AS reconciliation_exists,
                  r.id AS reconciliation_id,
                  r.status AS reconciliation_status,
                  COALESCE(NULLIF(r.work_package,''),'Основная')
                      AS reconciliation_work_package,
                  COALESCE(NULLIF(r.smeta_type,''),'Заказчик')
                      AS reconciliation_smeta_type,
                  p.id IS NOT NULL AS project_exists,
                  p.id AS project_id,
                  p.company_id AS project_company_id,
                  p.name AS project_name,
                  (SELECT COUNT(*)
                     FROM public.projects project_name_owner
                    WHERE project_name_owner.company_id=p.company_id
                      AND project_name_owner.name=p.name)
                      AS project_name_owner_count,
                  b.id AS base_estimate_id,
                  b.company_id AS base_company_id,
                  b.project_id AS base_project_id,
                  COALESCE(NULLIF(b.work_package,''),'Основная')
                      AS base_work_package,
                  COALESCE(NULLIF(b.smeta_type,''),'Заказчик') AS base_smeta_type,
                  b.sections_json AS base_sections_json,
                  n.id AS target_estimate_id,
                  n.company_id AS target_company_id,
                  n.project_id AS target_project_id,
                  COALESCE(NULLIF(n.work_package,''),'Основная')
                      AS target_work_package,
                  COALESCE(NULLIF(n.smeta_type,''),'Заказчик') AS target_smeta_type,
                  n.sections_json AS target_sections_json
             FROM public.estimate_reconciliations r
             LEFT JOIN public.estimates b ON b.id=r.base_estimate_id
             LEFT JOIN public.estimates n ON n.id=r.next_estimate_id
             LEFT JOIN public.projects p ON p.id=b.project_id
            WHERE r.id=%s""",
        (reconciliation_id,),
    )
    row = cur.fetchone()
    if not row:
        return {
            "reconciliation_exists": False,
            "reconciliation_id": reconciliation_id,
        }
    return dict(row)


def _load_assignment_rows(cur, base_estimate_id):
    cur.execute(
        """SELECT bci.id AS contract_item_id,
                  bci.contract_id,
                  bc.company_id AS contract_company_id,
                  bc.project_id AS contract_project_id,
                  COALESCE(NULLIF(bci.work_package,''),'Основная')
                      AS contract_work_package,
                  bci.source_type,
                  ev.estimate_id AS source_estimate_id,
                  bci.source_estimate_version_id,
                  bci.source_section_index,
                  bci.source_item_index,
                  bci.source_item_key,
                  ev.sections_json AS snapshot_sections_json,
                  ev.sections_sha256 AS snapshot_sections_sha256,
                  bci.quantity AS assignment_quantity,
                  COALESCE((SELECT SUM(wj.quantity)
                              FROM public.work_journal wj
                             WHERE wj.contract_item_id=bci.id
                               AND wj.status='Подтверждено'),0)
                      AS confirmed_quantity,
                  (SELECT COUNT(*) FROM public.work_journal wj
                    WHERE wj.contract_item_id=bci.id) AS journal_count,
                  (SELECT COUNT(*) FROM public.work_journal wj
                    WHERE wj.contract_item_id=bci.id
                      AND wj.status='Подтверждено') AS confirmed_journal_count,
                  (SELECT COUNT(*)
                     FROM public.hidden_works_acts hwa
                     JOIN public.work_journal wj ON wj.id=hwa.work_journal_id
                    WHERE wj.contract_item_id=bci.id) AS hidden_act_count,
                  (SELECT COUNT(*) FROM public.brigade_acts ba
                    WHERE ba.contract_id=bci.contract_id) AS brigade_act_count,
                  (SELECT COUNT(*) FROM public.brigade_payments bp
                    WHERE bp.contract_id=bci.contract_id) AS brigade_payment_count
             FROM public.brigade_contract_items bci
             JOIN public.brigade_contracts bc ON bc.id=bci.contract_id
             JOIN public.estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
            WHERE ev.estimate_id=%s
            ORDER BY bci.id""",
        (base_estimate_id,),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def _load_supply_request_rows(cur, context):
    if context["projectNameOwnerCount"] != 1 or not context["projectName"]:
        return []
    cur.execute(
        """SELECT sr.id AS request_id,
                  sr.company_id AS request_company_id,
                  sr.status AS request_status,
                  COALESCE(NULLIF(sr.work_package,''),'Основная')
                      AS request_work_package,
                  sr.items_json,
                  (SELECT COUNT(*) FROM public.supplier_offers so
                    WHERE so.request_id=sr.id) AS offer_count,
                  (SELECT COUNT(*) FROM public.supplier_invoices si
                    WHERE si.request_id=sr.id) AS supplier_invoice_count,
                  (SELECT COUNT(*) FROM public.warehouse_invoices wi
                    WHERE wi.supply_request_id=sr.id) AS warehouse_invoice_count,
                  (SELECT COUNT(*)
                     FROM public.warehouse_history wh
                     JOIN public.warehouse_invoices wi
                       ON wi.id=wh.source_invoice_id
                    WHERE wi.supply_request_id=sr.id) AS warehouse_history_count,
                  (SELECT COUNT(*) FROM public.supply_history sh
                    WHERE sh.request_id=sr.id) AS supply_history_count,
                  (SELECT COUNT(*) FROM public.supply_claims sc
                    WHERE sc.request_id=sr.id) AS claim_count,
                  (SELECT COUNT(*) FROM public.supplier_invoices paid
                    WHERE paid.request_id=sr.id
                      AND (paid.paid_at IS NOT NULL
                           OR COALESCE(paid.paid_amount,0)<>0)) AS paid_invoice_count
             FROM public.supply_requests sr
            WHERE sr.company_id=%s
              AND sr.project=%s
              AND COALESCE(NULLIF(sr.work_package,''),'Основная')=%s
            ORDER BY sr.id""",
        (context["companyId"], context["projectName"], context["workPackage"]),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def _load_delivery_rows(cur, request_ids):
    normalized_ids = sorted({
        request_id
        for request_id in (_positive_int(value) for value in request_ids)
        if request_id
    })
    if not normalized_ids:
        return []
    cur.execute(
        """SELECT d.id AS delivery_id,
                  d.request_id,
                  d.company_id AS delivery_company_id,
                  d.material_name,
                  d.unit,
                  d.received_quantity
             FROM public.supply_deliveries d
            WHERE d.request_id=ANY(%s)
            ORDER BY d.request_id,d.id""",
        (normalized_ids,),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def collect_transfer_impact(cur, reconciliation_id):
    reconciliation_id = parse_reconciliation_id(reconciliation_id)
    reconciliation = _load_reconciliation(cur, reconciliation_id)
    context, reconciliation_error = _reconciliation_context(reconciliation)
    if reconciliation_error:
        return build_impact_report(reconciliation, [], [], [])
    assignments = _load_assignment_rows(cur, context["baseEstimateId"])
    requests = _load_supply_request_rows(cur, context)
    deliveries = _load_delivery_rows(
        cur,
        [request.get("request_id") for request in requests],
    )
    return build_impact_report(reconciliation, assignments, requests, deliveries)


def run_impact_audit(get_db, reconciliation_id):
    reconciliation_id = parse_reconciliation_id(reconciliation_id)
    conn = get_db()
    cur = None
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        report = collect_transfer_impact(cur, reconciliation_id)
        conn.rollback()
        report["readOnlyTransaction"] = True
        report["rolledBack"] = True
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate row transfer impact audit",
    )
    parser.add_argument("--reconciliation-id", required=True)
    args = parser.parse_args(argv)
    reconciliation_id = parse_reconciliation_id(args.reconciliation_id)
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_impact_audit(get_db, reconciliation_id)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
