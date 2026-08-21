"""Pure A7.3 supply balance and explicit warehouse-lineage projection."""

import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from backend.features.brigade_lineage.snapshot_service import (
    LineageResolutionError,
    resolve_snapshot_item,
)
from backend.features.supply_estimate_refresh.service import (
    OPEN_SUPPLY_STATUSES,
)


PREVIEW_LIMIT = 100
MAX_REQUEST_ITEMS = 100
MAX_INVOICE_LINES = 500


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _non_negative_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _package(value):
    return _text(value) or "Основная"


def _decimal(value, *, positive=False):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number.as_tuple().exponent < -6:
        return None
    if number <= 0 if positive else number < 0:
        return None
    return number


def _items(value):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError):
        return None
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        return None
    return parsed


def _review(source_kind, source_id, reason_code, *, expose_id=True):
    return {
        "sourceKind": source_kind,
        "sourceId": _positive_int(source_id) if expose_id else None,
        "reasonCode": reason_code,
    }


def _canonical_item_key(estimate_id, sections, section_index, item_index):
    try:
        section = sections[section_index]
        item = section["items"][item_index]
    except (IndexError, KeyError, TypeError):
        return None, "supply_source_coordinate_not_found"
    if not isinstance(section, dict) or not isinstance(item, dict):
        return None, "supply_source_snapshot_invalid"
    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        raw = item.get(field)
        if raw in (None, ""):
            continue
        if not isinstance(raw, str) or raw != raw.strip() or len(raw) > 255:
            return None, "supply_source_item_key_invalid"
        if raw not in keys:
            keys.append(raw)
    if len(keys) > 1:
        return None, "supply_source_item_key_ambiguous"
    return (keys[0] if keys else f"{estimate_id}:{section_index}:{item_index}"), None


def _request_items(context, request):
    request_id = _positive_int(request.get("request_id"))
    if not request_id:
        return [], [_review("supply", None, "supply_request_identity_invalid")]
    if _positive_int(request.get("request_company_id")) != context["companyId"]:
        return [], [_review(
            "supply", request_id, "supply_request_owner_mismatch", expose_id=False,
        )]
    if _text(request.get("request_project")) != context["projectName"]:
        return [], [_review("supply", request_id, "supply_request_project_mismatch")]
    if _package(request.get("request_work_package")) != context["workPackage"]:
        return [], [_review("supply", request_id, "supply_request_package_mismatch")]
    items = _items(request.get("items_json"))
    if items is None:
        return [], [_review("supply", request_id, "supply_items_json_invalid")]
    if len(items) > MAX_REQUEST_ITEMS:
        return [], [_review(
            "supply", request_id, "supply_request_item_limit_exceeded",
        )]

    descriptors = []
    reviews = []
    for item_index, item in enumerate(items):
        lineage = item.get("estimateLineage")
        sources = lineage.get("sources") if isinstance(lineage, dict) else None
        if item.get("sourceType") != "estimate_material_control":
            continue
        if not isinstance(sources, list):
            reviews.append(_review("supply", request_id, "supply_source_lineage_invalid"))
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
            or lineage.get("version") != 2
            or lineage.get("validated") is not True
            or _positive_int(lineage.get("companyId")) != context["companyId"]
            or _positive_int(lineage.get("projectId")) != context["projectId"]
            or _text(lineage.get("projectName")) != context["projectName"]
            or _package(lineage.get("workPackage")) != context["workPackage"]
        ):
            reviews.append(_review("supply", request_id, "supply_source_lineage_invalid"))
            continue
        source = base_sources[0]
        section_index = _non_negative_int(source.get("sectionIndex"))
        source_item_index = _non_negative_int(source.get("itemIndex"))
        if section_index is None or source_item_index is None:
            reviews.append(_review("supply", request_id, "supply_source_coordinate_invalid"))
            continue
        item_key, key_error = _canonical_item_key(
            context["baseEstimateId"], context["baseSections"],
            section_index, source_item_index,
        )
        if key_error:
            reviews.append(_review("supply", request_id, key_error))
            continue
        try:
            resolved = resolve_snapshot_item(
                estimate_id=context["baseEstimateId"],
                sections=context["baseSections"],
                section_index=section_index,
                item_index=source_item_index,
                expected_item_key=item_key,
            )
        except LineageResolutionError as exc:
            reviews.append(_review(
                "supply", request_id, "supply_" + exc.code,
            ))
            continue
        material_name = _text(item.get("materialName") or item.get("name"))
        unit = _text(item.get("unit"))
        if (
            source.get("validated") is not True
            or not material_name
            or not unit
            or _text(source.get("materialName")) != material_name
            or _text(source.get("unit")) != unit
            or _text(resolved.item.get("name")) != material_name
            or _text(resolved.item.get("unit")) != unit
            or _package(item.get("workPackage")) != context["workPackage"]
        ):
            reviews.append(_review("supply", request_id, "supply_source_lineage_drift"))
            continue
        quantity = _decimal(item.get("quantity"), positive=True)
        if quantity is None:
            reviews.append(_review("supply", request_id, "supply_quantity_invalid"))
            continue
        descriptors.append({
            "requestId": request_id,
            "requestItemIndex": item_index,
            "sourceEstimateId": context["baseEstimateId"],
            "sourceSectionIndex": section_index,
            "sourceItemIndex": source_item_index,
            "identity": (material_name, unit),
            "requested": quantity,
        })
    coordinate_counts = Counter(
        (
            item["sourceEstimateId"], item["sourceSectionIndex"],
            item["sourceItemIndex"],
        )
        for item in descriptors
    )
    for descriptor in descriptors:
        coordinate = (
            descriptor["sourceEstimateId"], descriptor["sourceSectionIndex"],
            descriptor["sourceItemIndex"],
        )
        if coordinate_counts[coordinate] > 1:
            descriptor["invalid"] = True
            reviews.append(_review(
                "supply", request_id, "supply_source_coordinate_duplicate",
            ))
    return descriptors, reviews


def _valid_deliveries(context, requests_by_id, deliveries, reviews):
    result = defaultdict(list)
    ids = []
    for row in deliveries or []:
        row = dict(row or {})
        delivery_id = _positive_int(row.get("delivery_id"))
        request_id = _positive_int(row.get("request_id"))
        owner_exact = _positive_int(row.get("delivery_company_id")) == context["companyId"]
        if not delivery_id or not request_id:
            reviews.append(_review("delivery", delivery_id, "supply_delivery_identity_invalid"))
        elif not owner_exact:
            reviews.append(_review(
                "delivery", delivery_id, "supply_delivery_owner_mismatch", expose_id=False,
            ))
        elif request_id not in requests_by_id:
            reviews.append(_review("delivery", delivery_id, "supply_delivery_request_mismatch"))
        elif (
            _text(row.get("delivery_project")) != context["projectName"]
            or _package(row.get("delivery_work_package")) != context["workPackage"]
        ):
            reviews.append(_review("delivery", delivery_id, "supply_delivery_scope_mismatch"))
        elif _decimal(row.get("received_quantity")) is None:
            reviews.append(_review("delivery", delivery_id, "supply_received_quantity_invalid"))
        else:
            result[request_id].append(row)
            ids.append(delivery_id)
    return result, ids


def _valid_allocations(context, requests_by_id, allocations, reviews):
    result = defaultdict(list)
    ids = []
    for row in allocations or []:
        row = dict(row or {})
        allocation_id = _positive_int(row.get("allocation_id"))
        request_id = _positive_int(row.get("request_id"))
        owner_exact = _positive_int(row.get("allocation_company_id")) == context["companyId"]
        if not allocation_id or not request_id:
            reviews.append(_review("allocation", allocation_id, "supply_allocation_identity_invalid"))
        elif not owner_exact:
            reviews.append(_review(
                "allocation", allocation_id, "supply_allocation_owner_mismatch", expose_id=False,
            ))
        elif request_id not in requests_by_id:
            reviews.append(_review("allocation", allocation_id, "supply_allocation_request_mismatch"))
        elif (
            _positive_int(row.get("source_estimate_id")) != context["baseEstimateId"]
            or _non_negative_int(row.get("source_section_index")) is None
            or _non_negative_int(row.get("source_item_index")) is None
            or _non_negative_int(row.get("request_item_index")) is None
        ):
            reviews.append(_review("allocation", allocation_id, "supply_allocation_lineage_invalid"))
        elif _decimal(row.get("allocation_quantity"), positive=True) is None:
            reviews.append(_review("allocation", allocation_id, "supply_allocation_quantity_invalid"))
        else:
            result[request_id].append(row)
            ids.append(allocation_id)
    return result, ids


def _valid_parent_rows(context, requests_by_id, rows, *, kind, id_field, company_field, reviews):
    valid = {}
    for raw in rows or []:
        row = dict(raw or {})
        row_id = _positive_int(row.get(id_field))
        request_id = _positive_int(row.get("request_id"))
        owner_exact = _positive_int(row.get(company_field)) == context["companyId"]
        if not row_id or not request_id:
            reviews.append(_review(kind, row_id, kind + "_identity_invalid"))
        elif not owner_exact:
            reviews.append(_review(kind, row_id, kind + "_owner_mismatch", expose_id=False))
        elif request_id not in requests_by_id:
            reviews.append(_review(kind, row_id, kind + "_request_mismatch"))
        else:
            valid[row_id] = row
    return valid


def _valid_warehouse_invoices(
    context, requests_by_id, deliveries_by_id, supplier_invoices, rows, reviews,
):
    valid = {}
    for raw in rows or []:
        row = dict(raw or {})
        invoice_id = _positive_int(row.get("warehouse_invoice_id"))
        request_id = _positive_int(row.get("supply_request_id"))
        owner_exact = _positive_int(row.get("invoice_company_id")) == context["companyId"]
        delivery_id = _positive_int(row.get("supply_delivery_id"))
        supplier_invoice_id = _positive_int(row.get("supplier_invoice_id"))
        invoice_items = None
        reason = None
        expose = True
        if not invoice_id or not request_id:
            reason = "warehouse_invoice_identity_invalid"
        elif not owner_exact:
            reason = "warehouse_invoice_owner_mismatch"
            expose = False
        elif request_id not in requests_by_id:
            reason = "warehouse_invoice_request_mismatch"
        elif _text(row.get("invoice_project")) != context["projectName"]:
            reason = "warehouse_invoice_project_mismatch"
        elif delivery_id and delivery_id not in deliveries_by_id:
            reason = "warehouse_invoice_delivery_mismatch"
        elif supplier_invoice_id and supplier_invoice_id not in supplier_invoices:
            reason = "warehouse_invoice_supplier_invoice_mismatch"
        else:
            invoice_items = _items(row.get("items"))
            if invoice_items is None:
                reason = "warehouse_invoice_items_invalid"
            elif len(invoice_items) > MAX_INVOICE_LINES:
                reason = "warehouse_invoice_items_limit_exceeded"
        if reason:
            reviews.append(_review("warehouseInvoice", invoice_id, reason, expose_id=expose))
        else:
            row["parsedItems"] = invoice_items
            valid[invoice_id] = row
    return valid


def _valid_invoice_line_rows(
    context, invoices, rows, *, kind, id_field, company_field,
    invoice_field, line_field, package_field=None, project_field=None, reviews,
):
    valid = {}
    for raw in rows or []:
        row = dict(raw or {})
        row_id = _positive_int(row.get(id_field))
        invoice_id = _positive_int(row.get(invoice_field))
        line_index = _non_negative_int(row.get(line_field))
        owner_exact = _positive_int(row.get(company_field)) == context["companyId"]
        reason = None
        expose = True
        if not row_id or not invoice_id:
            reason = kind + "_identity_invalid"
        elif not owner_exact:
            reason = kind + "_owner_mismatch"
            expose = False
        elif invoice_id not in invoices:
            reason = kind + "_invoice_mismatch"
        elif line_index is None or line_index >= len(invoices[invoice_id]["parsedItems"]):
            reason = kind + "_line_invalid"
        elif package_field and _package(row.get(package_field)) != context["workPackage"]:
            reason = kind + "_package_mismatch"
        elif project_field and _positive_int(row.get(project_field)) != context["projectId"]:
            reason = kind + "_project_mismatch"
        if reason:
            reviews.append(_review(kind, row_id, reason, expose_id=expose))
        else:
            valid[row_id] = row
    return valid


def _valid_lot_movements(context, lots, movements, rows, reviews):
    valid = {}
    for raw in rows or []:
        row = dict(raw or {})
        row_id = _positive_int(row.get("lot_movement_id"))
        lot_id = _positive_int(row.get("lot_id"))
        movement_id = _positive_int(row.get("warehouse_movement_id"))
        owner_exact = _positive_int(row.get("lot_movement_company_id")) == context["companyId"]
        reason = None
        expose = True
        if not row_id or not lot_id or not movement_id:
            reason = "warehouse_lot_movement_identity_invalid"
        elif not owner_exact:
            reason = "warehouse_lot_movement_owner_mismatch"
            expose = False
        elif lot_id not in lots or movement_id not in movements:
            reason = "warehouse_lot_movement_parent_mismatch"
        elif (
            _positive_int(lots[lot_id].get("warehouse_invoice_id")),
            _non_negative_int(lots[lot_id].get("invoice_line_index")),
        ) != (
            _positive_int(movements[movement_id].get("source_invoice_id")),
            _non_negative_int(movements[movement_id].get("source_invoice_line_index")),
        ):
            reason = "warehouse_lot_movement_source_mismatch"
        if reason:
            reviews.append(_review("lotMovement", row_id, reason, expose_id=expose))
        else:
            valid[row_id] = row
    return valid


def build_supply_warehouse_projection(
    context,
    requests,
    deliveries,
    allocations,
    supplier_invoices,
    warehouse_invoices,
    warehouse_history,
    receipt_lots,
    warehouse_movements,
    lot_movements,
    *,
    scan_complete=True,
):
    """Build an ID/count-only impact report from exact saved lineage."""

    reviews = []
    requests_by_id = {}
    descriptors_by_request = defaultdict(list)
    closed_request_ids = set()
    for raw_request in requests or []:
        request = dict(raw_request or {})
        request_id = _positive_int(request.get("request_id"))
        descriptors, request_reviews = _request_items(context, request)
        reviews.extend(request_reviews)
        if request_id and (descriptors or request_reviews) and not any(
            item["reasonCode"] in {
                "supply_request_owner_mismatch", "supply_request_project_mismatch",
                "supply_request_package_mismatch", "supply_items_json_invalid",
            }
            for item in request_reviews
        ):
            requests_by_id[request_id] = request
            descriptors_by_request[request_id].extend(descriptors)
            if _text(request.get("request_status")) not in OPEN_SUPPLY_STATUSES:
                closed_request_ids.add(request_id)

    relevant_request_ids = set(requests_by_id)
    deliveries = [
        row for row in (deliveries or [])
        if _positive_int((row or {}).get("request_id")) in relevant_request_ids
    ]
    allocations = [
        row for row in (allocations or [])
        if _positive_int((row or {}).get("request_id")) in relevant_request_ids
    ]
    supplier_invoices = [
        row for row in (supplier_invoices or [])
        if _positive_int((row or {}).get("request_id")) in relevant_request_ids
    ]
    warehouse_invoices = [
        row for row in (warehouse_invoices or [])
        if _positive_int((row or {}).get("supply_request_id"))
        in relevant_request_ids
    ]
    relevant_invoice_ids = {
        invoice_id for invoice_id in (
            _positive_int((row or {}).get("warehouse_invoice_id"))
            for row in warehouse_invoices
        ) if invoice_id
    }
    warehouse_history = [
        row for row in (warehouse_history or [])
        if _positive_int((row or {}).get("source_invoice_id"))
        in relevant_invoice_ids
    ]
    receipt_lots = [
        row for row in (receipt_lots or [])
        if _positive_int((row or {}).get("warehouse_invoice_id"))
        in relevant_invoice_ids
    ]
    warehouse_movements = [
        row for row in (warehouse_movements or [])
        if _positive_int((row or {}).get("source_invoice_id"))
        in relevant_invoice_ids
    ]
    relevant_lot_ids = {
        lot_id for lot_id in (
            _positive_int((row or {}).get("lot_id")) for row in receipt_lots
        ) if lot_id
    }
    relevant_movement_ids = {
        movement_id for movement_id in (
            _positive_int((row or {}).get("movement_id"))
            for row in warehouse_movements
        ) if movement_id
    }
    lot_movements = [
        row for row in (lot_movements or [])
        if (
            _positive_int((row or {}).get("lot_id")) in relevant_lot_ids
            or _positive_int((row or {}).get("warehouse_movement_id"))
            in relevant_movement_ids
        )
    ]

    deliveries_by_request, delivery_ids = _valid_deliveries(
        context, requests_by_id, deliveries, reviews,
    )
    valid_deliveries = {
        _positive_int(row.get("delivery_id")): row
        for rows in deliveries_by_request.values() for row in rows
    }
    allocations_by_request, allocation_ids = _valid_allocations(
        context, requests_by_id, allocations, reviews,
    )
    valid_supplier_invoices = _valid_parent_rows(
        context, requests_by_id, supplier_invoices,
        kind="supplier_invoice", id_field="supplier_invoice_id",
        company_field="invoice_company_id", reviews=reviews,
    )
    valid_warehouse_invoices = _valid_warehouse_invoices(
        context, requests_by_id, valid_deliveries, valid_supplier_invoices,
        warehouse_invoices, reviews,
    )
    valid_history = _valid_invoice_line_rows(
        context, valid_warehouse_invoices, warehouse_history,
        kind="warehouse_receipt", id_field="history_id",
        company_field="history_company_id", invoice_field="source_invoice_id",
        line_field="source_invoice_line_index",
        package_field="history_work_package", reviews=reviews,
    )
    valid_lots = _valid_invoice_line_rows(
        context, valid_warehouse_invoices, receipt_lots,
        kind="warehouse_receipt_lot", id_field="lot_id",
        company_field="lot_company_id", invoice_field="warehouse_invoice_id",
        line_field="invoice_line_index", project_field="lot_project_id",
        reviews=reviews,
    )
    valid_movements = _valid_invoice_line_rows(
        context, valid_warehouse_invoices, warehouse_movements,
        kind="warehouse_movement", id_field="movement_id",
        company_field="movement_company_id", invoice_field="source_invoice_id",
        line_field="source_invoice_line_index",
        package_field="movement_work_package", reviews=reviews,
    )
    valid_lot_movements = _valid_lot_movements(
        context, valid_lots, valid_movements, lot_movements, reviews,
    )

    lots_by_source = defaultdict(set)
    for lot_id, row in valid_lots.items():
        lots_by_source[(
            _positive_int(row.get("warehouse_invoice_id")),
            _non_negative_int(row.get("invoice_line_index")),
        )].add(lot_id)
    lot_movement_links = {
        (
            _positive_int(row.get("lot_id")),
            _positive_int(row.get("warehouse_movement_id")),
        )
        for row in valid_lot_movements.values()
    }
    for movement in valid_movements.values():
        source = (
            _positive_int(movement.get("source_invoice_id")),
            _non_negative_int(movement.get("source_invoice_line_index")),
        )
        movement_id = _positive_int(movement.get("movement_id"))
        if not lots_by_source[source]:
            reviews.append(_review(
                "warehouseMovement", movement_id,
                "warehouse_movement_lot_missing",
            ))
        elif not any(
            (lot_id, movement_id) in lot_movement_links
            for lot_id in lots_by_source[source]
        ):
            reviews.append(_review(
                "warehouseMovement", movement_id,
                "warehouse_lot_movement_missing",
            ))

    open_supply = []
    protected_supply_items = 0
    for request_id, descriptors in descriptors_by_request.items():
        identities = Counter(
            item["identity"] for item in descriptors
        )
        request_deliveries = deliveries_by_request.get(request_id, [])
        ambiguous_identities = {
            identity for identity, count in identities.items()
            if count > 1 and any(
                (_text(row.get("material_name")), _text(row.get("unit")))
                == identity
                for row in request_deliveries
            )
        }
        if ambiguous_identities:
            reviews.append(_review(
                "supply", request_id,
                "supply_delivery_allocation_ambiguous",
            ))
        for descriptor in descriptors:
            if descriptor.get("invalid"):
                continue
            matching_deliveries = [
                row for row in request_deliveries
                if (_text(row.get("material_name")), _text(row.get("unit")))
                == descriptor["identity"]
            ]
            if descriptor["identity"] in ambiguous_identities:
                continue
            received = sum(
                (_decimal(row.get("received_quantity")) or Decimal(0)
                 for row in matching_deliveries),
                Decimal(0),
            )
            matching_allocations = [
                row for row in allocations_by_request.get(request_id, [])
                if _non_negative_int(row.get("request_item_index"))
                == descriptor["requestItemIndex"]
            ]
            allocation_invalid = any(
                (
                    _positive_int(row.get("source_estimate_id")),
                    _non_negative_int(row.get("source_section_index")),
                    _non_negative_int(row.get("source_item_index")),
                ) != (
                    descriptor["sourceEstimateId"],
                    descriptor["sourceSectionIndex"],
                    descriptor["sourceItemIndex"],
                )
                for row in matching_allocations
            )
            if allocation_invalid:
                reviews.append(_review(
                    "supply", request_id, "supply_allocation_lineage_drift",
                ))
                continue
            allocated = sum(
                (_decimal(row.get("allocation_quantity"), positive=True) or Decimal(0)
                 for row in matching_allocations),
                Decimal(0),
            )
            if received + allocated > descriptor["requested"]:
                reviews.append(_review(
                    "supply", request_id, "supply_protected_exceeds_requested",
                ))
                continue
            if request_id in closed_request_ids:
                protected_supply_items += 1
            elif received + allocated == descriptor["requested"]:
                protected_supply_items += 1
            else:
                open_supply.append({
                    "requestId": request_id,
                    "requestItemIndex": descriptor["requestItemIndex"],
                    "sourceEstimateId": descriptor["sourceEstimateId"],
                    "sourceSectionIndex": descriptor["sourceSectionIndex"],
                    "sourceItemIndex": descriptor["sourceItemIndex"],
                    "state": "open_balance",
                })

    evidence = {
        "closedSupplyRequestIds": sorted(closed_request_ids),
        "deliveryIds": sorted(set(delivery_ids)),
        "allocationIds": sorted(set(allocation_ids)),
        "supplierInvoiceIds": sorted(valid_supplier_invoices),
        "warehouseInvoiceIds": sorted(valid_warehouse_invoices),
        "warehouseHistoryIds": sorted(valid_history),
        "receiptLotIds": sorted(valid_lots),
        "warehouseMovementIds": sorted(valid_movements),
        "lotMovementIds": sorted(valid_lot_movements),
    }
    facts_truncated = len(open_supply) > PREVIEW_LIMIT or any(
        len(ids) > PREVIEW_LIMIT for ids in evidence.values()
    )
    open_supply.sort(key=lambda item: (
        item["requestId"], item["requestItemIndex"],
        item["sourceSectionIndex"], item["sourceItemIndex"],
    ))
    for key in evidence:
        evidence[key] = evidence[key][:PREVIEW_LIMIT]
    reason_counts = Counter(item["reasonCode"] for item in reviews)
    complete = bool(scan_complete) and not reviews and not facts_truncated
    state = "complete" if complete else (
        "incomplete" if not scan_complete or facts_truncated else "review_required"
    )
    return {
        "state": state,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": bool(scan_complete),
        "complete": complete,
        "summary": {
            "supplyRequestRows": len(requests or []),
            "supplyItems": sum(len(rows) for rows in descriptors_by_request.values()),
            "openSupplyItems": len(open_supply),
            "protectedSupplyItems": protected_supply_items,
            "closedSupplyRequests": len(closed_request_ids),
            "deliveries": len(valid_deliveries),
            "allocations": len(allocation_ids),
            "supplierInvoices": len(valid_supplier_invoices),
            "warehouseInvoices": len(valid_warehouse_invoices),
            "warehouseHistoryRows": len(valid_history),
            "receiptLots": len(valid_lots),
            "warehouseMovements": len(valid_movements),
            "lotMovements": len(valid_lot_movements),
            "needsReview": len(reviews),
        },
        "openSupply": open_supply[:PREVIEW_LIMIT],
        "protectedEvidence": evidence,
        "factsTruncated": facts_truncated,
        "reasonCounts": dict(sorted(reason_counts.items())),
        "needsReview": reviews[:PREVIEW_LIMIT],
        "needsReviewTruncated": len(reviews) > PREVIEW_LIMIT,
    }


__all__ = [
    "MAX_INVOICE_LINES",
    "MAX_REQUEST_ITEMS",
    "PREVIEW_LIMIT",
    "build_supply_warehouse_projection",
]
