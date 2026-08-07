"""Tenant-bound read projection for immutable E4.4 supply allocations."""

import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from .supply_apply import _canonical_item_snapshot


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except (IndexError, TypeError):
        return None


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _non_negative_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _quantity_text(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number <= 0 or number.as_tuple().exponent < -6:
        return None
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _items(value):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError):
        return None
    return parsed if isinstance(parsed, list) else None


def _public_allocation(row, live_items):
    item_index = _non_negative_int(row.get("request_item_index"))
    quantity = _quantity_text(row.get("allocation_quantity"))
    required_positive_ids = (
        "entry_id", "plan_id", "source_estimate_id",
        "source_estimate_version_id", "target_estimate_id",
        "target_estimate_version_id",
    )
    required_indexes = (
        "source_section_index", "source_item_index",
        "target_section_index", "target_item_index",
    )
    valid_shape = (
        item_index is not None
        and quantity is not None
        and all(_positive_int(row.get(key)) for key in required_positive_ids)
        and all(_non_negative_int(row.get(key)) is not None for key in required_indexes)
        and all(
            isinstance(row.get(key), str) and row.get(key) == row.get(key).strip()
            and bool(row.get(key))
            for key in (
                "source_item_key", "target_item_key", "target_material_name",
                "target_unit", "target_work_package",
            )
        )
    )
    state = "needs_review"
    reason = "allocation_projection_invalid"
    if valid_shape:
        if not isinstance(live_items, list) or item_index >= len(live_items):
            reason = "request_item_snapshot_missing"
        elif not isinstance(live_items[item_index], dict):
            reason = "request_item_snapshot_invalid"
        else:
            try:
                _payload, digest = _canonical_item_snapshot(live_items[item_index])
            except Exception:
                reason = "request_item_snapshot_invalid"
            else:
                if digest == row.get("request_item_sha256"):
                    state = "ready"
                    reason = "exact_request_item_snapshot"
                else:
                    reason = "request_item_snapshot_drift"
    return {
        "entryId": row.get("entry_id"),
        "planId": row.get("plan_id"),
        "requestItemIndex": item_index,
        "state": state,
        "reasonCode": reason,
        "quantity": quantity,
        "sourceEstimateId": row.get("source_estimate_id"),
        "sourceEstimateVersionId": row.get("source_estimate_version_id"),
        "sourceSectionIndex": row.get("source_section_index"),
        "sourceItemIndex": row.get("source_item_index"),
        "sourceItemKey": row.get("source_item_key"),
        "targetEstimateId": row.get("target_estimate_id"),
        "targetEstimateVersionId": row.get("target_estimate_version_id"),
        "targetSectionIndex": row.get("target_section_index"),
        "targetItemIndex": row.get("target_item_index"),
        "targetItemKey": row.get("target_item_key"),
        "targetMaterialName": row.get("target_material_name"),
        "targetUnit": row.get("target_unit"),
        "targetWorkPackage": row.get("target_work_package"),
        "appliedAt": str(row.get("applied_at") or ""),
    }


def attach_supply_allocation_projection(cur, visible_rows):
    """Attach allocations only to request rows already authorized by the caller."""

    rows = [dict(row) for row in (visible_rows or [])]
    for row in rows:
        row["supplyTransferAllocations"] = []
    visible = {
        (_positive_int(row.get("companyId") or row.get("company_id")), _positive_int(row.get("id"))): row
        for row in rows
    }
    visible = {key: row for key, row in visible.items() if all(key)}
    if not visible:
        return rows
    cur.execute(
        "SELECT to_regclass('public.estimate_row_supply_allocations') IS NOT NULL AS ready"
    )
    ready_row = cur.fetchone()
    if not bool(_row_value(ready_row, "ready", 0)):
        return rows
    request_ids = sorted({key[1] for key in visible})
    company_ids = sorted({key[0] for key in visible})
    cur.execute(
        """SELECT entry_id,plan_id,company_id,request_id,request_item_index,
                  request_item_sha256,source_estimate_id,
                  source_estimate_version_id,source_section_index,
                  source_item_index,source_item_key,target_estimate_id,
                  target_estimate_version_id,target_section_index,
                  target_item_index,target_item_key,target_material_name,
                  target_unit,target_work_package,allocation_quantity,applied_at
             FROM public.estimate_row_supply_allocations
            WHERE request_id=ANY(%s) AND company_id=ANY(%s)
            ORDER BY request_id,request_item_index,id""",
        (request_ids, company_ids),
    )
    allocations = defaultdict(list)
    for allocation in cur.fetchall() or []:
        row = dict(allocation)
        key = (_positive_int(row.get("company_id")), _positive_int(row.get("request_id")))
        if key in visible:
            allocations[key].append(row)
    for key, row in visible.items():
        live_items = _items(row.get("itemsJson") or row.get("items_json"))
        row["supplyTransferAllocations"] = [
            _public_allocation(allocation, live_items)
            for allocation in allocations.get(key, [])
        ]
    return rows
