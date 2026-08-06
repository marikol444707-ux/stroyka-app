"""Fail-closed E4.3 assignment transfer preparation and transaction helpers."""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..brigade_lineage.canonical import parse_sections, sections_sha256
from ..brigade_lineage.snapshot_service import (
    LineageResolutionError,
    resolve_snapshot_item,
)
from ..brigade_lineage.source_item import estimate_item_unit_price
from .plan import calculate_plan_sha256


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MONEY_QUANTUM = Decimal("0.01")

ASSIGNMENT_ENTRY_SELECT = """SELECT id,plan_id,company_id,project_id,
       source_kind,source_id,source_parent_id,request_item_index,
       source_estimate_id,source_estimate_version_id,source_section_index,
       source_item_index,source_item_key,source_sections_sha256,
       target_estimate_id,target_estimate_version_id,target_section_index,
       target_item_index,target_item_key,target_sections_sha256,
       source_total_quantity,source_protected_quantity,
       source_available_quantity,quantity
  FROM public.estimate_row_transfer_entries"""

ASSIGNMENT_RECEIPT_SELECT = """SELECT id,entry_id,plan_id,company_id,project_id,
       plan_sha256,source_item_id,target_item_id,transfer_quantity,applied_at
  FROM public.estimate_row_assignment_transfers"""


class AssignmentApplyError(ValueError):
    """Bounded error code safe to expose at the API boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def normalize_assignment_apply_payload(data):
    if (
        not isinstance(data, dict)
        or set(data) != {"planSha256"}
        or not isinstance(data.get("planSha256"), str)
        or not _SHA256_RE.fullmatch(data["planSha256"])
    ):
        raise AssignmentApplyError("assignment_apply_payload_invalid")
    return {"planSha256": data["planSha256"]}


def _positive_int(value, code):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise AssignmentApplyError(code)


def _non_negative_int(value, code):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise AssignmentApplyError(code)


def _decimal(value, code, *, minimum=None, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AssignmentApplyError(code) from exc
    if not number.is_finite():
        raise AssignmentApplyError(code)
    if positive and number <= 0:
        raise AssignmentApplyError(code)
    if minimum is not None and number < minimum:
        raise AssignmentApplyError(code)
    return number


def _canonical_text(value, code, *, maximum=255):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise AssignmentApplyError(code)
    return value


def _entry_identity(item):
    return (item.get("sourceKind"), item.get("sourceId"), item.get("requestItemIndex"))


def _plan_context(stored):
    canonical = dict((stored or {}).get("canonicalPlan") or {})
    digest = canonical.get("planSha256")
    if (
        (stored or {}).get("status") != "approved"
        or not isinstance(digest, str)
        or not _SHA256_RE.fullmatch(digest)
        or (stored or {}).get("approvedPlanSha256") != digest
    ):
        raise AssignmentApplyError("assignment_plan_not_approved")
    if canonical.get("planVersion") != 1:
        raise AssignmentApplyError("assignment_plan_integrity_invalid")
    if calculate_plan_sha256(canonical) != digest:
        raise AssignmentApplyError("assignment_plan_integrity_invalid")
    return {
        "plan": canonical,
        "planId": _positive_int((stored or {}).get("id"), "assignment_plan_integrity_invalid"),
        "companyId": _positive_int(canonical.get("companyId"), "assignment_plan_integrity_invalid"),
        "projectId": _positive_int(canonical.get("projectId"), "assignment_plan_integrity_invalid"),
        "reconciliationId": _positive_int(
            canonical.get("reconciliationId"),
            "assignment_plan_integrity_invalid",
        ),
        "workPackage": _canonical_text(
            canonical.get("workPackage"),
            "assignment_plan_integrity_invalid",
            maximum=100,
        ),
        "planSha256": digest,
    }


def _validate_assignment_entry(row, planned, context):
    source = dict(planned.get("source") or {})
    target = dict(planned.get("target") or {})
    expected = {
        "plan_id": context["planId"],
        "company_id": context["companyId"],
        "project_id": context["projectId"],
        "source_kind": "assignment",
        "source_id": planned.get("sourceId"),
        "source_parent_id": planned.get("sourceParentId"),
        "request_item_index": None,
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
        raise AssignmentApplyError("assignment_plan_integrity_invalid")
    quantity_fields = {
        "source_total_quantity": planned.get("sourceTotalQuantity"),
        "source_protected_quantity": planned.get("sourceProtectedQuantity"),
        "source_available_quantity": planned.get("sourceAvailableQuantity"),
        "quantity": planned.get("quantity"),
    }
    for key, value in quantity_fields.items():
        if _decimal((row or {}).get(key), "assignment_plan_integrity_invalid") != _decimal(
            value,
            "assignment_plan_integrity_invalid",
        ):
            raise AssignmentApplyError("assignment_plan_integrity_invalid")
    return _positive_int((row or {}).get("id"), "assignment_plan_integrity_invalid")


def _target_snapshot(plan, row):
    expected = dict(plan.get("targetSnapshot") or {})
    if (
        (row or {}).get("id") != expected.get("estimateVersionId")
        or (row or {}).get("estimate_id") != expected.get("estimateId")
        or (row or {}).get("sections_sha256") != expected.get("sectionsSha256")
    ):
        raise AssignmentApplyError("assignment_target_snapshot_stale")
    try:
        sections = parse_sections((row or {}).get("sections_json"))
        digest = sections_sha256(sections)
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError) as exc:
        raise AssignmentApplyError("assignment_target_snapshot_invalid") from exc
    if digest != expected.get("sectionsSha256"):
        raise AssignmentApplyError("assignment_target_snapshot_stale")
    return sections


def _confirmed_quantities(rows, source_ids):
    confirmed = {source_id: Decimal(0) for source_id in source_ids}
    for row in rows or ():
        source_id = _positive_int(
            (row or {}).get("contract_item_id"),
            "assignment_journal_identity_invalid",
        )
        if source_id not in confirmed:
            raise AssignmentApplyError("assignment_journal_identity_invalid")
        quantity = _decimal(
            (row or {}).get("quantity"),
            "assignment_journal_quantity_invalid",
            minimum=Decimal(0),
        )
        if (row or {}).get("status") == "Подтверждено":
            confirmed[source_id] += quantity
    return confirmed


def _contract_totals(items, contract_ids):
    totals = {contract_id: Decimal(0) for contract_id in contract_ids}
    for item in items or ():
        contract_id = _positive_int(
            (item or {}).get("contract_id"),
            "assignment_contract_item_invalid",
        )
        if contract_id not in totals:
            raise AssignmentApplyError("assignment_contract_item_invalid")
        quantity = _decimal(
            (item or {}).get("quantity"),
            "assignment_contract_total_invalid",
            minimum=Decimal(0),
        )
        price = _decimal(
            (item or {}).get("price_brigade"),
            "assignment_contract_total_invalid",
            minimum=Decimal(0),
        )
        totals[contract_id] += quantity * price
    return totals


def _money(value, code):
    return _decimal(value, code, minimum=Decimal(0)).quantize(
        _MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _target_metadata(plan, sections, planned):
    target = dict(planned.get("target") or {})
    try:
        resolved = resolve_snapshot_item(
            estimate_id=plan.get("targetEstimateId"),
            sections=sections,
            section_index=target.get("sectionIndex"),
            item_index=target.get("itemIndex"),
            expected_item_key=target.get("itemKey"),
        )
    except LineageResolutionError as exc:
        raise AssignmentApplyError("assignment_target_snapshot_invalid") from exc
    price_smeta = _decimal(
        estimate_item_unit_price(resolved.item),
        "assignment_target_price_invalid",
        positive=True,
    ).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return {
        "section": _canonical_text(
            resolved.section.get("name") or "Без раздела",
            "assignment_target_metadata_invalid",
            maximum=2000,
        ),
        "description": _canonical_text(
            resolved.item.get("name"),
            "assignment_target_metadata_invalid",
            maximum=2000,
        ),
        "unit": _canonical_text(
            resolved.item.get("unit") or "шт",
            "assignment_target_metadata_invalid",
            maximum=50,
        ),
        "priceSmeta": price_smeta,
        "sourceEstimateVersionId": _positive_int(
            target.get("estimateVersionId"),
            "assignment_target_snapshot_invalid",
        ),
        "sourceSectionIndex": _non_negative_int(
            target.get("sectionIndex"),
            "assignment_target_snapshot_invalid",
        ),
        "sourceItemIndex": _non_negative_int(
            target.get("itemIndex"),
            "assignment_target_snapshot_invalid",
        ),
        "sourceItemKey": _canonical_text(
            target.get("itemKey"),
            "assignment_target_snapshot_invalid",
        ),
    }


def prepare_assignment_operations(
    *,
    stored,
    assignment_entries,
    contracts,
    contract_items,
    journal_rows,
    target_snapshot,
):
    """Validate locked rows and return exact writes without executing SQL."""

    context = _plan_context(stored)
    plan = context["plan"]
    planned_entries = [
        item for item in (plan.get("entries") or [])
        if item.get("sourceKind") == "assignment"
    ]
    if not planned_entries:
        raise AssignmentApplyError("assignment_entries_required")
    if len(planned_entries) != len(assignment_entries or ()):
        raise AssignmentApplyError("assignment_plan_integrity_invalid")

    planned_by_source = {item.get("sourceId"): item for item in planned_entries}
    if len(planned_by_source) != len(planned_entries):
        raise AssignmentApplyError("assignment_plan_integrity_invalid")
    entry_by_source = {}
    for row in assignment_entries or ():
        source_id = (row or {}).get("source_id")
        planned = planned_by_source.get(source_id)
        if not planned or source_id in entry_by_source:
            raise AssignmentApplyError("assignment_plan_integrity_invalid")
        entry_by_source[source_id] = (
            _validate_assignment_entry(row, planned, context),
            row,
        )

    contract_ids = sorted({item.get("sourceParentId") for item in planned_entries})
    contracts_by_id = {(row or {}).get("id"): row for row in contracts or ()}
    if len(contracts_by_id) != len(contract_ids):
        raise AssignmentApplyError("assignment_contract_owner_mismatch")
    totals = _contract_totals(contract_items, contract_ids)
    for contract_id in contract_ids:
        row = contracts_by_id.get(contract_id)
        if (
            not row
            or row.get("company_id") != context["companyId"]
            or row.get("project_id") != context["projectId"]
            or (row.get("work_package") or "Основная") != context["workPackage"]
        ):
            raise AssignmentApplyError("assignment_contract_owner_mismatch")
        if _money(
            row.get("total_amount"),
            "assignment_contract_total_invalid",
        ) != _money(totals[contract_id], "assignment_contract_total_invalid"):
            raise AssignmentApplyError("assignment_contract_total_stale")

    items_by_id = {(row or {}).get("id"): row for row in contract_items or ()}
    if len(items_by_id) != len(contract_items or ()):
        raise AssignmentApplyError("assignment_contract_item_invalid")
    confirmed = _confirmed_quantities(journal_rows, set(planned_by_source))
    sections = _target_snapshot(plan, target_snapshot)

    operations = []
    target_identities = set()
    for source_id in sorted(planned_by_source):
        planned = planned_by_source[source_id]
        entry_id, _entry_row = entry_by_source[source_id]
        source = dict(planned.get("source") or {})
        source_row = items_by_id.get(source_id)
        contract_id = planned.get("sourceParentId")
        if not source_row or source_row.get("contract_id") != contract_id:
            raise AssignmentApplyError("assignment_source_not_found")
        if (
            source_row.get("source_type") != "estimate"
            or source_row.get("source_estimate_version_id") != source.get("estimateVersionId")
            or source_row.get("source_section_index") != source.get("sectionIndex")
            or source_row.get("source_item_index") != source.get("itemIndex")
            or source_row.get("source_item_key") != source.get("itemKey")
            or source_row.get("estimate_item_key") != source.get("itemKey")
            or (source_row.get("work_package") or "Основная") != context["workPackage"]
        ):
            raise AssignmentApplyError("assignment_source_lineage_stale")

        before = _decimal(
            source_row.get("quantity"),
            "assignment_source_quantity_invalid",
            positive=True,
        )
        protected = confirmed[source_id]
        transfer = _decimal(
            planned.get("quantity"),
            "assignment_transfer_quantity_invalid",
            positive=True,
        )
        expected_total = _decimal(
            planned.get("sourceTotalQuantity"),
            "assignment_plan_integrity_invalid",
        )
        expected_protected = _decimal(
            planned.get("sourceProtectedQuantity"),
            "assignment_plan_integrity_invalid",
        )
        expected_available = _decimal(
            planned.get("sourceAvailableQuantity"),
            "assignment_plan_integrity_invalid",
        )
        if (
            before != expected_total
            or protected != expected_protected
            or before - protected != expected_available
        ):
            raise AssignmentApplyError("assignment_plan_stale")
        after = before - transfer
        if after < protected:
            raise AssignmentApplyError("assignment_confirmed_quantity_protected")

        done = _decimal(
            source_row.get("done_quantity"),
            "assignment_source_progress_invalid",
            minimum=Decimal(0),
        )
        if done > after:
            raise AssignmentApplyError("assignment_source_progress_protected")
        source_price_smeta = _decimal(
            source_row.get("price_smeta"),
            "assignment_source_price_invalid",
            positive=True,
        )
        source_price_brigade = _decimal(
            source_row.get("price_brigade"),
            "assignment_source_price_invalid",
            positive=True,
        )
        source_status = _canonical_text(
            source_row.get("status"),
            "assignment_source_status_invalid",
            maximum=50,
        )
        target = _target_metadata(plan, sections, planned)
        target_identity = (
            contract_id,
            target["sourceEstimateVersionId"],
            target["sourceSectionIndex"],
            target["sourceItemIndex"],
            target["sourceItemKey"],
        )
        if target_identity in target_identities:
            raise AssignmentApplyError("assignment_target_duplicate")
        target_identities.add(target_identity)
        for existing in contract_items or ():
            if (
                existing.get("contract_id") == contract_id
                and existing.get("source_type") == "estimate"
                and existing.get("source_estimate_version_id")
                    == target["sourceEstimateVersionId"]
                and existing.get("source_section_index")
                    == target["sourceSectionIndex"]
                and existing.get("source_item_index") == target["sourceItemIndex"]
                and existing.get("source_item_key") == target["sourceItemKey"]
            ):
                raise AssignmentApplyError("assignment_target_exists")

        target["quantity"] = transfer
        target["priceBrigade"] = source_price_brigade
        target["doneQuantity"] = Decimal(0)
        operations.append({
            "entryId": entry_id,
            "planId": context["planId"],
            "companyId": context["companyId"],
            "projectId": context["projectId"],
            "reconciliationId": context["reconciliationId"],
            "planSha256": context["planSha256"],
            "sourceContractId": contract_id,
            "sourceItemId": source_id,
            "sourceQuantityBefore": before,
            "sourceQuantityAfter": after,
            "sourceDoneQuantity": done,
            "confirmedQuantity": protected,
            "transferQuantity": transfer,
            "sourcePriceSmeta": source_price_smeta,
            "sourcePriceBrigade": source_price_brigade,
            "targetPriceSmeta": target["priceSmeta"],
            "targetPriceBrigade": source_price_brigade,
            "sourceStatus": source_status,
            "source": {
                "sourceEstimateVersionId": source.get("estimateVersionId"),
                "sourceSectionIndex": source.get("sectionIndex"),
                "sourceItemIndex": source.get("itemIndex"),
                "sourceItemKey": source.get("itemKey"),
            },
            "target": target,
            "contractTotalBefore": _money(
                totals[contract_id],
                "assignment_contract_total_invalid",
            ),
        })
    return operations


def _assignment_entries(cur, context):
    cur.execute(
        ASSIGNMENT_ENTRY_SELECT
        + " WHERE plan_id=%s AND company_id=%s AND project_id=%s"
        + " AND source_kind='assignment' ORDER BY source_id FOR SHARE",
        (context["planId"], context["companyId"], context["projectId"]),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def _assignment_receipts(cur, context):
    cur.execute(
        ASSIGNMENT_RECEIPT_SELECT
        + " WHERE plan_id=%s AND company_id=%s AND project_id=%s"
        + " ORDER BY entry_id FOR UPDATE",
        (context["planId"], context["companyId"], context["projectId"]),
    )
    return [dict(row) for row in (cur.fetchall() or [])]


def _quantity_text(value):
    number = _decimal(value, "assignment_receipt_invalid")
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _result_from_receipts(context, assignment_entries, receipts, *, idempotent):
    entry_by_id = {
        _positive_int(row.get("id"), "assignment_plan_integrity_invalid"): row
        for row in assignment_entries
    }
    if len(entry_by_id) != len(assignment_entries) or len(receipts) != len(entry_by_id):
        raise AssignmentApplyError("assignment_apply_partial_state")
    transfers = []
    applied_at = ""
    seen = set()
    for receipt in receipts:
        entry_id = _positive_int(
            receipt.get("entry_id"),
            "assignment_apply_partial_state",
        )
        entry = entry_by_id.get(entry_id)
        if not entry or entry_id in seen:
            raise AssignmentApplyError("assignment_apply_partial_state")
        seen.add(entry_id)
        if (
            receipt.get("plan_id") != context["planId"]
            or receipt.get("company_id") != context["companyId"]
            or receipt.get("project_id") != context["projectId"]
            or receipt.get("plan_sha256") != context["planSha256"]
            or receipt.get("source_item_id") != entry.get("source_id")
            or _decimal(
                receipt.get("transfer_quantity"),
                "assignment_apply_partial_state",
            )
            != _decimal(entry.get("quantity"), "assignment_apply_partial_state")
        ):
            raise AssignmentApplyError("assignment_apply_partial_state")
        target_item_id = _positive_int(
            receipt.get("target_item_id"),
            "assignment_apply_partial_state",
        )
        applied_value = str(receipt.get("applied_at") or "")
        if not applied_value:
            raise AssignmentApplyError("assignment_apply_partial_state")
        applied_at = max(applied_at, applied_value)
        transfers.append({
            "entryId": entry_id,
            "sourceItemId": entry["source_id"],
            "targetItemId": target_item_id,
            "quantity": _quantity_text(receipt["transfer_quantity"]),
        })
    transfers.sort(key=lambda item: item["entryId"])
    return {
        "planId": context["planId"],
        "planSha256": context["planSha256"],
        "state": "assignment_applied",
        "assignmentCount": len(transfers),
        "transfers": transfers,
        "appliedAt": applied_at,
        "idempotent": bool(idempotent),
    }


def _validate_actor(actor, context):
    actor_id = _positive_int((actor or {}).get("id"), "assignment_actor_invalid")
    company_id = (actor or {}).get("companyId") or (actor or {}).get("company_id")
    name = _canonical_text(
        (actor or {}).get("name"),
        "assignment_actor_invalid",
        maximum=2000,
    )
    role = (actor or {}).get("role")
    if company_id != context["companyId"] or role not in ("директор", "зам_директора"):
        raise AssignmentApplyError("assignment_actor_invalid")
    return {"id": actor_id, "name": name, "role": role}


def _locked_context_rows(cur, context, assignment_entries):
    contract_ids = sorted({
        _positive_int(row.get("source_parent_id"), "assignment_plan_integrity_invalid")
        for row in assignment_entries
    })
    source_ids = sorted({
        _positive_int(row.get("source_id"), "assignment_plan_integrity_invalid")
        for row in assignment_entries
    })
    cur.execute(
        """SELECT id,company_id,project_id,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  total_amount
             FROM public.brigade_contracts
            WHERE id=ANY(%s) ORDER BY id FOR UPDATE""",
        (contract_ids,),
    )
    contracts = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute(
        """SELECT id,contract_id,estimate_section,description,work_package,
                  estimate_item_key,unit,quantity,price_smeta,price_brigade,
                  done_quantity,status,source_type,source_estimate_version_id,
                  source_section_index,source_item_index,source_item_key
             FROM public.brigade_contract_items
            WHERE contract_id=ANY(%s) ORDER BY contract_id,id FOR UPDATE""",
        (contract_ids,),
    )
    contract_items = [dict(row) for row in (cur.fetchall() or [])]
    cur.execute(
        """SELECT id,contract_item_id,quantity,status
             FROM public.work_journal
            WHERE contract_item_id=ANY(%s)
            ORDER BY contract_item_id,id FOR UPDATE""",
        (source_ids,),
    )
    journal_rows = [dict(row) for row in (cur.fetchall() or [])]
    target_snapshot = dict(context["plan"].get("targetSnapshot") or {})
    cur.execute(
        """SELECT id,estimate_id,sections_json,sections_sha256
             FROM public.estimate_versions
            WHERE id=%s AND estimate_id=%s FOR SHARE""",
        (
            target_snapshot.get("estimateVersionId"),
            target_snapshot.get("estimateId"),
        ),
    )
    snapshot_row = cur.fetchone()
    if not snapshot_row:
        raise AssignmentApplyError("assignment_target_snapshot_stale")
    return contracts, contract_items, journal_rows, dict(snapshot_row)


def _update_source(cur, operation):
    source = operation["source"]
    cur.execute(
        """UPDATE public.brigade_contract_items
              SET quantity=%s
            WHERE id=%s AND contract_id=%s AND quantity::numeric=%s
              AND source_type='estimate'
              AND source_estimate_version_id=%s
              AND source_section_index=%s AND source_item_index=%s
              AND source_item_key=%s
            RETURNING id,quantity""",
        (
            operation["sourceQuantityAfter"], operation["sourceItemId"],
            operation["sourceContractId"], operation["sourceQuantityBefore"],
            source["sourceEstimateVersionId"], source["sourceSectionIndex"],
            source["sourceItemIndex"], source["sourceItemKey"],
        ),
    )
    updated = cur.fetchone()
    if (
        not updated
        or updated.get("id") != operation["sourceItemId"]
        or _decimal(updated.get("quantity"), "assignment_source_update_conflict")
            != operation["sourceQuantityAfter"]
    ):
        raise AssignmentApplyError("assignment_source_update_conflict")


def _insert_target(cur, operation, work_package):
    target = operation["target"]
    cur.execute(
        """INSERT INTO public.brigade_contract_items
             (contract_id,estimate_section,description,work_package,
              estimate_item_key,unit,quantity,price_smeta,price_brigade,
              done_quantity,status,source_type,source_estimate_version_id,
              source_section_index,source_item_index,source_item_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,'Не начато','estimate',
                   %s,%s,%s,%s)
           RETURNING id,quantity,price_smeta,price_brigade,done_quantity""",
        (
            operation["sourceContractId"], target["section"],
            target["description"], work_package, target["sourceItemKey"],
            target["unit"], target["quantity"], target["priceSmeta"],
            target["priceBrigade"], target["sourceEstimateVersionId"],
            target["sourceSectionIndex"], target["sourceItemIndex"],
            target["sourceItemKey"],
        ),
    )
    inserted = cur.fetchone()
    target_id = _positive_int(
        (inserted or {}).get("id"),
        "assignment_target_insert_failed",
    )
    if (
        _decimal(inserted.get("quantity"), "assignment_target_insert_failed")
            != operation["transferQuantity"]
        or _decimal(inserted.get("price_smeta"), "assignment_target_insert_failed")
            != operation["targetPriceSmeta"]
        or _decimal(inserted.get("price_brigade"), "assignment_target_insert_failed")
            != operation["targetPriceBrigade"]
        or _decimal(inserted.get("done_quantity"), "assignment_target_insert_failed")
            != 0
    ):
        raise AssignmentApplyError("assignment_target_insert_failed")
    operation["targetItemId"] = target_id


def _post_contract_totals(cur, operations, actor_company_id):
    contract_ids = sorted({item["sourceContractId"] for item in operations})
    cur.execute(
        """SELECT contract_id,
                  ROUND(COALESCE(SUM(quantity::numeric*price_brigade),0),2)
                    AS contract_total
             FROM public.brigade_contract_items
            WHERE contract_id=ANY(%s)
            GROUP BY contract_id ORDER BY contract_id""",
        (contract_ids,),
    )
    after_by_contract = {
        row.get("contract_id"): _money(
            row.get("contract_total"),
            "assignment_contract_total_invalid",
        )
        for row in (cur.fetchall() or [])
    }
    before_by_contract = {}
    for operation in operations:
        before_by_contract.setdefault(
            operation["sourceContractId"],
            operation["contractTotalBefore"],
        )
    if set(after_by_contract) != set(before_by_contract):
        raise AssignmentApplyError("assignment_contract_total_changed")
    for contract_id in contract_ids:
        before = before_by_contract[contract_id]
        after = after_by_contract[contract_id]
        if abs(after - before) > _MONEY_QUANTUM:
            raise AssignmentApplyError("assignment_contract_total_changed")
        # Receipts use the rounded exact post-check value; a sub-cent difference
        # is accepted by the business tolerance but never left ambiguous.
        evidence_total = before if after != before else after
        cur.execute(
            """UPDATE public.brigade_contracts
                  SET total_amount=%s
                WHERE id=%s AND company_id=%s
                RETURNING id,total_amount""",
            (evidence_total, contract_id, actor_company_id),
        )
        updated = cur.fetchone()
        if (
            not updated
            or updated.get("id") != contract_id
            or _money(updated.get("total_amount"), "assignment_contract_update_failed")
                != evidence_total
        ):
            raise AssignmentApplyError("assignment_contract_update_failed")
        for operation in operations:
            if operation["sourceContractId"] == contract_id:
                operation["contractTotalAfter"] = evidence_total


def _insert_receipt(cur, operation, actor):
    source = operation["source"]
    target = operation["target"]
    cur.execute(
        """INSERT INTO public.estimate_row_assignment_transfers
             (entry_id,plan_id,company_id,project_id,reconciliation_id,
              plan_sha256,source_contract_id,source_item_id,target_item_id,
              source_estimate_version_id,source_section_index,source_item_index,
              source_item_key,target_estimate_version_id,target_section_index,
              target_item_index,target_item_key,source_quantity_before,
              source_quantity_after,source_done_quantity,confirmed_quantity,
              transfer_quantity,source_price_smeta,source_price_brigade,
              target_price_smeta,target_price_brigade,source_status,
              contract_total_before,contract_total_after,applied_by_user_id,
              applied_by_name,applied_by_role)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id,applied_at""",
        (
            operation["entryId"], operation["planId"], operation["companyId"],
            operation["projectId"], operation["reconciliationId"],
            operation["planSha256"], operation["sourceContractId"],
            operation["sourceItemId"], operation["targetItemId"],
            source["sourceEstimateVersionId"], source["sourceSectionIndex"],
            source["sourceItemIndex"], source["sourceItemKey"],
            target["sourceEstimateVersionId"], target["sourceSectionIndex"],
            target["sourceItemIndex"], target["sourceItemKey"],
            operation["sourceQuantityBefore"], operation["sourceQuantityAfter"],
            operation["sourceDoneQuantity"], operation["confirmedQuantity"],
            operation["transferQuantity"], operation["sourcePriceSmeta"],
            operation["sourcePriceBrigade"], operation["targetPriceSmeta"],
            operation["targetPriceBrigade"], operation["sourceStatus"],
            operation["contractTotalBefore"], operation["contractTotalAfter"],
            actor["id"], actor["name"], actor["role"],
        ),
    )
    inserted = cur.fetchone()
    if not inserted or not _positive_int(
        inserted.get("id"),
        "assignment_receipt_insert_failed",
    ) or not inserted.get("applied_at"):
        raise AssignmentApplyError("assignment_receipt_insert_failed")


def apply_assignment_plan(cur, *, stored, actor):
    """Apply one approved assignment subset; caller owns commit/rollback."""

    context = _plan_context(stored)
    validated_actor = _validate_actor(actor, context)
    assignment_entries = _assignment_entries(cur, context)
    planned_count = sum(
        1 for item in (context["plan"].get("entries") or [])
        if item.get("sourceKind") == "assignment"
    )
    if not planned_count:
        raise AssignmentApplyError("assignment_entries_required")
    if len(assignment_entries) != planned_count:
        raise AssignmentApplyError("assignment_plan_integrity_invalid")
    existing = _assignment_receipts(cur, context)
    if existing:
        return _result_from_receipts(
            context,
            assignment_entries,
            existing,
            idempotent=True,
        )

    contracts, contract_items, journal_rows, target_snapshot = _locked_context_rows(
        cur,
        context,
        assignment_entries,
    )
    operations = prepare_assignment_operations(
        stored=stored,
        assignment_entries=assignment_entries,
        contracts=contracts,
        contract_items=contract_items,
        journal_rows=journal_rows,
        target_snapshot=target_snapshot,
    )
    for operation in operations:
        _update_source(cur, operation)
        _insert_target(cur, operation, context["workPackage"])
    _post_contract_totals(cur, operations, context["companyId"])
    for operation in operations:
        _insert_receipt(cur, operation, validated_actor)
    stored_receipts = _assignment_receipts(cur, context)
    return _result_from_receipts(
        context,
        assignment_entries,
        stored_receipts,
        idempotent=False,
    )
