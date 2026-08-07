"""Fail-closed E4.4 supply open-balance allocation ledger."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

import psycopg2.extras

from ..brigade_lineage.canonical import parse_sections, sections_sha256
from ..brigade_lineage.snapshot_service import (
    LineageResolutionError,
    resolve_snapshot_item,
)
from ..supply_estimate_refresh.service import OPEN_SUPPLY_STATUSES
from .plan import calculate_plan_sha256
from .policy import ALLOCATABLE_SUPPLY_STATUSES, is_explicit_material_item


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SUPPLY_ENTRY_SELECT = """SELECT id,plan_id,company_id,project_id,
       source_kind,source_id,source_parent_id,request_item_index,
       source_estimate_id,source_estimate_version_id,source_section_index,
       source_item_index,source_item_key,source_sections_sha256,
       target_estimate_id,target_estimate_version_id,target_section_index,
       target_item_index,target_item_key,target_sections_sha256,
       source_total_quantity,source_protected_quantity,
       source_available_quantity,quantity
  FROM public.estimate_row_transfer_entries"""

SUPPLY_ALLOCATION_SELECT = """SELECT id,entry_id,plan_id,company_id,project_id,
       plan_sha256,request_id,request_item_index,allocation_quantity,applied_at
  FROM public.estimate_row_supply_allocations"""


class SupplyApplyError(ValueError):
    """Bounded error code safe to expose at the API boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def normalize_supply_apply_payload(data):
    if (
        not isinstance(data, dict)
        or set(data) != {"planSha256"}
        or not isinstance(data.get("planSha256"), str)
        or not _SHA256_RE.fullmatch(data["planSha256"])
    ):
        raise SupplyApplyError("supply_apply_payload_invalid")
    return {"planSha256": data["planSha256"]}


def _positive_int(value, code):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise SupplyApplyError(code)


def _non_negative_int(value, code):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise SupplyApplyError(code)


def _decimal(value, code, *, positive=False, minimum=None):
    if isinstance(value, bool):
        raise SupplyApplyError(code)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SupplyApplyError(code) from exc
    if not number.is_finite():
        raise SupplyApplyError(code)
    if positive and number <= 0:
        raise SupplyApplyError(code)
    if minimum is not None and number < minimum:
        raise SupplyApplyError(code)
    if number.as_tuple().exponent < -6:
        raise SupplyApplyError(code)
    return number


def _text(value, code, *, maximum=2000):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise SupplyApplyError(code)
    return value


def _quantity_text(value):
    normalized = format(Decimal(value).normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def canonical_request_item_snapshot(item):
    try:
        payload = json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError) as exc:
        raise SupplyApplyError("supply_request_item_invalid") from exc
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_items(value):
    try:
        items = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError) as exc:
        raise SupplyApplyError("supply_items_json_invalid") from exc
    if not isinstance(items, list) or not items:
        raise SupplyApplyError("supply_items_json_invalid")
    return items


def _plan_context(stored):
    canonical = dict((stored or {}).get("canonicalPlan") or {})
    digest = canonical.get("planSha256")
    if (
        (stored or {}).get("status") != "approved"
        or not isinstance(digest, str)
        or not _SHA256_RE.fullmatch(digest)
        or (stored or {}).get("approvedPlanSha256") != digest
    ):
        raise SupplyApplyError("supply_plan_not_approved")
    if canonical.get("planVersion") != 1 or calculate_plan_sha256(canonical) != digest:
        raise SupplyApplyError("supply_plan_integrity_invalid")
    return {
        "plan": canonical,
        "planId": _positive_int((stored or {}).get("id"), "supply_plan_integrity_invalid"),
        "companyId": _positive_int(canonical.get("companyId"), "supply_plan_integrity_invalid"),
        "projectId": _positive_int(canonical.get("projectId"), "supply_plan_integrity_invalid"),
        "reconciliationId": _positive_int(
            canonical.get("reconciliationId"), "supply_plan_integrity_invalid"
        ),
        "workPackage": _text(
            canonical.get("workPackage"), "supply_plan_integrity_invalid", maximum=100
        ),
        "planSha256": digest,
    }


def _validate_entry(row, planned, context):
    source = dict(planned.get("source") or {})
    target = dict(planned.get("target") or {})
    expected = {
        "plan_id": context["planId"],
        "company_id": context["companyId"],
        "project_id": context["projectId"],
        "source_kind": "supply",
        "source_id": planned.get("sourceId"),
        "source_parent_id": planned.get("sourceId"),
        "request_item_index": planned.get("requestItemIndex"),
        "source_estimate_id": source.get("estimateId"),
        "source_estimate_version_id": source.get("estimateVersionId"),
        "source_section_index": source.get("sectionIndex"),
        "source_item_index": source.get("itemIndex"),
        "source_item_key": source.get("itemKey"),
        "source_sections_sha256": source.get("sectionsSha256"),
        "target_estimate_id": target.get("estimateId"),
        "target_estimate_version_id": target.get("estimateVersionId"),
        "target_section_index": target.get("sectionIndex"),
        "target_item_index": target.get("itemIndex"),
        "target_item_key": target.get("itemKey"),
        "target_sections_sha256": target.get("sectionsSha256"),
    }
    if any((row or {}).get(key) != value for key, value in expected.items()):
        raise SupplyApplyError("supply_plan_integrity_invalid")
    for key, value in (
        ("source_total_quantity", planned.get("sourceTotalQuantity")),
        ("source_protected_quantity", planned.get("sourceProtectedQuantity")),
        ("source_available_quantity", planned.get("sourceAvailableQuantity")),
        ("quantity", planned.get("quantity")),
    ):
        if _decimal((row or {}).get(key), "supply_plan_integrity_invalid") != _decimal(
            value, "supply_plan_integrity_invalid"
        ):
            raise SupplyApplyError("supply_plan_integrity_invalid")
    return _positive_int((row or {}).get("id"), "supply_plan_integrity_invalid")


def _resolved_snapshot(row, expected, *, prefix):
    if (
        (row or {}).get("id") != expected.get("estimateVersionId")
        or (row or {}).get("estimate_id") != expected.get("estimateId")
        or (row or {}).get("sections_sha256") != expected.get("sectionsSha256")
    ):
        raise SupplyApplyError(prefix + "_snapshot_stale")
    try:
        sections = parse_sections((row or {}).get("sections_json"))
        if sections_sha256(sections) != expected.get("sectionsSha256"):
            raise SupplyApplyError(prefix + "_snapshot_stale")
        return resolve_snapshot_item(
            estimate_id=expected.get("estimateId"),
            sections=sections,
            section_index=expected.get("sectionIndex"),
            item_index=expected.get("itemIndex"),
            expected_item_key=expected.get("itemKey"),
        )
    except SupplyApplyError:
        raise
    except (
        LineageResolutionError,
        TypeError,
        ValueError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ) as exc:
        raise SupplyApplyError(prefix + "_snapshot_invalid") from exc


def _request_item(request, planned, context, source_resolved, deliveries):
    if (
        (request or {}).get("company_id") != context["companyId"]
        or (request or {}).get("project_id") != context["projectId"]
    ):
        raise SupplyApplyError("supply_request_owner_mismatch")
    if (request or {}).get("status") not in OPEN_SUPPLY_STATUSES:
        raise SupplyApplyError("supply_request_status_closed")
    if (request or {}).get("status") not in ALLOCATABLE_SUPPLY_STATUSES:
        raise SupplyApplyError("supply_projection_status_unsupported")
    if ((request or {}).get("work_package") or "Основная") != context["workPackage"]:
        raise SupplyApplyError("supply_request_package_mismatch")
    items = _parse_items((request or {}).get("items_json"))
    item_index = _non_negative_int(
        planned.get("requestItemIndex"), "supply_request_item_invalid"
    )
    if item_index >= len(items) or not isinstance(items[item_index], dict):
        raise SupplyApplyError("supply_request_item_invalid")
    item = items[item_index]
    lineage = item.get("estimateLineage")
    sources = lineage.get("sources") if isinstance(lineage, dict) else None
    if (
        item.get("sourceType") != "estimate_material_control"
        or not isinstance(lineage, dict)
        or lineage.get("version") not in (1, 2)
        or (
            lineage.get("version") == 2
            and (
                _positive_int(
                    lineage.get("companyId"), "supply_source_lineage_stale"
                ) != context["companyId"]
                or _positive_int(
                    lineage.get("projectId"), "supply_source_lineage_stale"
                ) != context["projectId"]
            )
        )
        or lineage.get("validated") is not True
        or lineage.get("projectName") != request.get("project")
        or (lineage.get("workPackage") or "Основная") != context["workPackage"]
        or not isinstance(sources, list)
        or len(sources) != 1
        or not isinstance(sources[0], dict)
        or sources[0].get("validated") is not True
    ):
        raise SupplyApplyError("supply_source_lineage_stale")
    source = dict(planned.get("source") or {})
    stored_source = sources[0]
    material_name = _text(
        item.get("materialName") or item.get("name"),
        "supply_material_identity_invalid",
    )
    unit = _text(item.get("unit"), "supply_material_identity_invalid", maximum=50)
    if (
        stored_source.get("estimateId") != source.get("estimateId")
        or stored_source.get("sectionIndex") != source.get("sectionIndex")
        or stored_source.get("itemIndex") != source.get("itemIndex")
        or stored_source.get("materialName") != material_name
        or stored_source.get("unit") != unit
        or source_resolved.item.get("name") != material_name
        or source_resolved.item.get("unit") != unit
        or (item.get("workPackage") or "Основная") != context["workPackage"]
    ):
        raise SupplyApplyError("supply_source_lineage_stale")

    material_identities = Counter()
    source_coordinates = Counter()
    for candidate in items:
        if not isinstance(candidate, dict):
            continue
        candidate_name = candidate.get("materialName") or candidate.get("name")
        candidate_unit = candidate.get("unit")
        material_identities[(candidate_name, candidate_unit)] += 1
        candidate_lineage = candidate.get("estimateLineage")
        candidate_sources = (
            candidate_lineage.get("sources")
            if isinstance(candidate_lineage, dict) else None
        )
        if isinstance(candidate_sources, list):
            for candidate_source in candidate_sources:
                if isinstance(candidate_source, dict):
                    source_coordinates[(
                        candidate_source.get("estimateId"),
                        candidate_source.get("sectionIndex"),
                        candidate_source.get("itemIndex"),
                    )] += 1
    matching_deliveries = [
        row for row in deliveries
        if row.get("material_name") == material_name and row.get("unit") == unit
    ]
    if material_identities[(material_name, unit)] > 1 and matching_deliveries:
        raise SupplyApplyError("supply_delivery_allocation_ambiguous")
    coordinate = (
        source.get("estimateId"), source.get("sectionIndex"), source.get("itemIndex")
    )
    if source_coordinates[coordinate] > 1:
        raise SupplyApplyError("supply_source_coordinate_duplicate")
    received = Decimal(0)
    for delivery in deliveries:
        if delivery.get("company_id") != context["companyId"]:
            raise SupplyApplyError("supply_delivery_owner_mismatch")
        if delivery in matching_deliveries:
            received += _decimal(
                delivery.get("received_quantity"),
                "supply_received_quantity_invalid",
                minimum=Decimal(0),
            )
    requested = _decimal(
        item.get("quantity"), "supply_requested_quantity_invalid", positive=True
    )
    if received > requested:
        raise SupplyApplyError("supply_received_exceeds_requested")
    snapshot_json, snapshot_sha = canonical_request_item_snapshot(item)
    return {
        "snapshot": json.loads(snapshot_json),
        "snapshotSha256": snapshot_sha,
        "requested": requested,
        "received": received,
    }


def prepare_supply_allocations(
    *,
    stored,
    supply_entries,
    requests,
    deliveries,
    prior_allocations,
    source_snapshots,
    target_snapshot,
):
    """Validate locked state and return immutable allocation inserts."""

    context = _plan_context(stored)
    plan = context["plan"]
    planned_entries = [
        entry for entry in (plan.get("entries") or [])
        if entry.get("sourceKind") == "supply"
    ]
    if not planned_entries:
        raise SupplyApplyError("supply_entries_required")
    if len(planned_entries) != len(supply_entries or ()):
        raise SupplyApplyError("supply_plan_integrity_invalid")
    planned_by_identity = {
        (entry.get("sourceId"), entry.get("requestItemIndex")): entry
        for entry in planned_entries
    }
    if len(planned_by_identity) != len(planned_entries):
        raise SupplyApplyError("supply_plan_integrity_invalid")
    entries_by_identity = {}
    for row in supply_entries or ():
        identity = ((row or {}).get("source_id"), (row or {}).get("request_item_index"))
        planned = planned_by_identity.get(identity)
        if not planned or identity in entries_by_identity:
            raise SupplyApplyError("supply_plan_integrity_invalid")
        entries_by_identity[identity] = _validate_entry(row, planned, context)

    requests_by_id = {(row or {}).get("id"): row for row in requests or ()}
    request_ids = {identity[0] for identity in planned_by_identity}
    if len(requests_by_id) != len(requests or ()):
        raise SupplyApplyError("supply_request_project_identity_ambiguous")
    if set(requests_by_id) != request_ids:
        raise SupplyApplyError("supply_request_not_found")
    deliveries_by_request = defaultdict(list)
    for row in deliveries or ():
        request_id = (row or {}).get("request_id")
        if request_id not in request_ids:
            raise SupplyApplyError("supply_delivery_identity_invalid")
        deliveries_by_request[request_id].append(row)
    prior_by_identity = defaultdict(list)
    for row in prior_allocations or ():
        identity = ((row or {}).get("request_id"), (row or {}).get("request_item_index"))
        if identity not in planned_by_identity:
            continue
        if (row or {}).get("company_id") != context["companyId"]:
            raise SupplyApplyError("supply_prior_allocation_owner_mismatch")
        prior_by_identity[identity].append(row)
    snapshots_by_id = {(row or {}).get("id"): row for row in source_snapshots or ()}
    target_expected = dict(plan.get("targetSnapshot") or {})

    operations = []
    for identity in sorted(planned_by_identity):
        planned = planned_by_identity[identity]
        source = dict(planned.get("source") or {})
        target = dict(planned.get("target") or {})
        source_resolved = _resolved_snapshot(
            snapshots_by_id.get(source.get("estimateVersionId")),
            source,
            prefix="supply_source",
        )
        target_resolved = _resolved_snapshot(
            target_snapshot,
            {**target_expected, **target},
            prefix="supply_target",
        )
        if not is_explicit_material_item(target_resolved.item):
            raise SupplyApplyError("supply_target_not_material")
        request_state = _request_item(
            requests_by_id[identity[0]],
            planned,
            context,
            source_resolved,
            deliveries_by_request[identity[0]],
        )
        prior = sum((
            _decimal(
                row.get("allocation_quantity"),
                "supply_prior_allocation_quantity_invalid",
                positive=True,
            )
            for row in prior_by_identity[identity]
        ), Decimal(0))
        requested = request_state["requested"]
        received = request_state["received"]
        remaining_before = requested - received - prior
        transfer = _decimal(
            planned.get("quantity"), "supply_allocation_quantity_invalid", positive=True
        )
        expected_total = _decimal(
            planned.get("sourceTotalQuantity"), "supply_plan_integrity_invalid"
        )
        expected_protected = _decimal(
            planned.get("sourceProtectedQuantity"), "supply_plan_integrity_invalid"
        )
        expected_available = _decimal(
            planned.get("sourceAvailableQuantity"), "supply_plan_integrity_invalid"
        )
        if (
            requested != expected_total
            or received + prior != expected_protected
            or remaining_before != expected_available
        ):
            raise SupplyApplyError("supply_plan_stale")
        if transfer > remaining_before:
            raise SupplyApplyError("supply_allocation_exceeds_remaining")
        target_name = _text(
            target_resolved.item.get("name"), "supply_target_metadata_invalid"
        )
        target_unit = _text(
            target_resolved.item.get("unit") or "шт",
            "supply_target_metadata_invalid",
            maximum=50,
        )
        operations.append({
            "entryId": entries_by_identity[identity],
            "requestId": identity[0],
            "requestItemIndex": identity[1],
            "requestItemSnapshot": request_state["snapshot"],
            "requestItemSha256": request_state["snapshotSha256"],
            "source": source,
            "target": {
                **target,
                "materialName": target_name,
                "unit": target_unit,
                "workPackage": context["workPackage"],
            },
            "requestedQuantity": requested,
            "receivedQuantity": received,
            "previouslyAllocatedQuantity": prior,
            "allocationQuantity": transfer,
            "remainingUnallocatedQuantity": remaining_before - transfer,
        })
    return operations


def _receipt_result(context, receipts, *, idempotent):
    ordered = sorted(receipts, key=lambda row: row.get("entry_id") or 0)
    applied_at = max((str(row.get("applied_at") or "") for row in ordered), default="")
    return {
        "planId": context["planId"],
        "planSha256": context["planSha256"],
        "state": "supply_allocated",
        "supplyCount": len(ordered),
        "allocations": [{
            "entryId": row.get("entry_id"),
            "requestId": row.get("request_id"),
            "requestItemIndex": row.get("request_item_index"),
            "quantity": _quantity_text(row.get("allocation_quantity")),
        } for row in ordered],
        "appliedAt": applied_at,
        "idempotent": idempotent,
    }


def _existing_receipt_result(context, planned_entries, entry_rows, receipts):
    expected = {
        (entry.get("sourceId"), entry.get("requestItemIndex")): entry
        for entry in planned_entries
    }
    expected_entry_ids = {
        (row.get("source_id"), row.get("request_item_index")): row.get("id")
        for row in entry_rows or ()
    }
    if len(receipts or ()) != len(expected):
        raise SupplyApplyError("supply_apply_partial_state")
    seen = set()
    for row in receipts or ():
        identity = (row.get("request_id"), row.get("request_item_index"))
        planned = expected.get(identity)
        if (
            not planned
            or identity in seen
            or row.get("entry_id") != expected_entry_ids.get(identity)
            or row.get("plan_id") != context["planId"]
            or row.get("company_id") != context["companyId"]
            or row.get("project_id") != context["projectId"]
            or row.get("plan_sha256") != context["planSha256"]
            or _decimal(row.get("allocation_quantity"), "supply_apply_partial_state")
                != _decimal(planned.get("quantity"), "supply_apply_partial_state")
        ):
            raise SupplyApplyError("supply_apply_partial_state")
        seen.add(identity)
    return _receipt_result(context, receipts, idempotent=True)


def apply_supply_plan(cur, *, stored, actor):
    """Insert supply ledger receipts only; the caller owns commit/rollback."""

    context = _plan_context(stored)
    planned_entries = [
        entry for entry in (context["plan"].get("entries") or [])
        if entry.get("sourceKind") == "supply"
    ]
    if not planned_entries:
        raise SupplyApplyError("supply_entries_required")
    cur.execute(
        SUPPLY_ENTRY_SELECT + " WHERE plan_id=%s AND source_kind='supply' ORDER BY id FOR UPDATE",
        (context["planId"],),
    )
    entry_rows = cur.fetchall() or []
    cur.execute(
        SUPPLY_ALLOCATION_SELECT + " WHERE plan_id=%s ORDER BY id FOR UPDATE",
        (context["planId"],),
    )
    receipts = cur.fetchall() or []
    if receipts:
        return _existing_receipt_result(
            context, planned_entries, entry_rows, receipts
        )

    request_ids = sorted({entry.get("sourceId") for entry in planned_entries})
    cur.execute(
        """SELECT sr.id,sr.company_id,project_owner.id AS project_id,sr.project,
                  sr.status,COALESCE(NULLIF(sr.work_package,''),'Основная')
                    AS work_package,sr.items_json
             FROM public.supply_requests sr
             LEFT JOIN public.projects project_owner
               ON project_owner.company_id=sr.company_id
              AND project_owner.name=sr.project
            WHERE sr.id=ANY(%s)
            ORDER BY sr.id,project_owner.id
            FOR UPDATE OF sr""",
        (request_ids,),
    )
    requests = cur.fetchall() or []
    cur.execute(
        """SELECT id,request_id,company_id,material_name,unit,received_quantity
             FROM public.supply_deliveries
            WHERE request_id=ANY(%s)
            ORDER BY request_id,id FOR UPDATE""",
        (request_ids,),
    )
    deliveries = cur.fetchall() or []
    cur.execute(
        SUPPLY_ALLOCATION_SELECT
        + " WHERE company_id=%s AND request_id=ANY(%s) ORDER BY request_id,request_item_index,id FOR UPDATE",
        (context["companyId"], request_ids),
    )
    prior_allocations = cur.fetchall() or []
    version_ids = sorted({
        entry.get("source", {}).get("estimateVersionId") for entry in planned_entries
    } | {context["plan"].get("targetSnapshot", {}).get("estimateVersionId")})
    cur.execute(
        """SELECT id,estimate_id,sections_json,sections_sha256
             FROM public.estimate_versions
            WHERE id=ANY(%s) ORDER BY id""",
        (version_ids,),
    )
    snapshots = cur.fetchall() or []
    target_version_id = context["plan"].get("targetSnapshot", {}).get("estimateVersionId")
    target_rows = [row for row in snapshots if row.get("id") == target_version_id]
    operations = prepare_supply_allocations(
        stored=stored,
        supply_entries=entry_rows,
        requests=requests,
        deliveries=deliveries,
        prior_allocations=prior_allocations,
        source_snapshots=[row for row in snapshots if row.get("id") != target_version_id],
        target_snapshot=target_rows[0] if len(target_rows) == 1 else None,
    )

    inserted = []
    for operation in operations:
        source = operation["source"]
        target = operation["target"]
        cur.execute(
            """INSERT INTO public.estimate_row_supply_allocations
                 (entry_id,plan_id,company_id,project_id,reconciliation_id,
                  plan_sha256,request_id,request_item_index,
                  request_item_snapshot,request_item_sha256,
                  source_estimate_id,source_estimate_version_id,
                  source_section_index,source_item_index,source_item_key,
                  source_sections_sha256,target_estimate_id,
                  target_estimate_version_id,target_section_index,
                  target_item_index,target_item_key,target_sections_sha256,
                  target_material_name,target_unit,target_work_package,
                  requested_quantity,received_quantity,
                  previously_allocated_quantity,allocation_quantity,
                  remaining_unallocated_quantity,applied_by_user_id,
                  applied_by_name,applied_by_role)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id,applied_at""",
            (
                operation["entryId"], context["planId"], context["companyId"],
                context["projectId"], context["reconciliationId"],
                context["planSha256"], operation["requestId"],
                operation["requestItemIndex"],
                psycopg2.extras.Json(
                    operation["requestItemSnapshot"],
                    dumps=lambda value: json.dumps(
                        value, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False,
                    ),
                ),
                operation["requestItemSha256"], source["estimateId"],
                source["estimateVersionId"], source["sectionIndex"],
                source["itemIndex"], source["itemKey"], source["sectionsSha256"],
                target["estimateId"], target["estimateVersionId"],
                target["sectionIndex"], target["itemIndex"], target["itemKey"],
                target["sectionsSha256"], target["materialName"], target["unit"],
                target["workPackage"], operation["requestedQuantity"],
                operation["receivedQuantity"],
                operation["previouslyAllocatedQuantity"],
                operation["allocationQuantity"],
                operation["remainingUnallocatedQuantity"], actor["id"],
                str(actor.get("name") or ""), str(actor.get("role") or ""),
            ),
        )
        written = cur.fetchone() or {}
        if not written.get("id") or not written.get("applied_at"):
            raise SupplyApplyError("supply_allocation_insert_failed")
        inserted.append({
            "id": written["id"],
            "entry_id": operation["entryId"],
            "plan_id": context["planId"],
            "company_id": context["companyId"],
            "project_id": context["projectId"],
            "plan_sha256": context["planSha256"],
            "request_id": operation["requestId"],
            "request_item_index": operation["requestItemIndex"],
            "allocation_quantity": operation["allocationQuantity"],
            "applied_at": written["applied_at"],
        })
    return _receipt_result(context, inserted, idempotent=False)
