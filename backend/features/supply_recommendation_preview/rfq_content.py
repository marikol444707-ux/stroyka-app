"""Read-only A8.2 RFQ content preview for one exact A8.1 candidate."""

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

import psycopg2.extras

from backend.features.brigade_lineage.canonical import parse_sections
from backend.features.estimate_revision_impact.contract import (
    EVENT_TYPE,
    MAX_CANONICAL_SOURCE_BYTES,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)
from backend.features.estimate_revision_impact.material_projection import (
    MAX_ALIAS_ROWS,
    MAX_MATERIAL_ROWS,
    build_material_projection,
)
from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    MAX_REQUEST_ITEMS,
    PREVIEW_LIMIT,
    build_supply_warehouse_projection,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    collect_supply_warehouse_impact_audit,
)
from backend.features.estimate_row_transfer.policy import (
    is_explicit_material_item,
)

from .lineage_binding import (
    LINEAGE_AMBIGUOUS,
    LINEAGE_MISSING,
    OPEN_REQUEST_AMBIGUOUS,
    OPEN_SUPPLY_FIELDS,
    bind_open_supply_to_material_pairs,
)
from .rfq_policy import (
    MAX_MATERIAL_TEXT_LENGTH,
    MAX_UNIT_TEXT_LENGTH,
    bounded_decimal as _decimal,
    bounded_text as _text,
    canonical_package as _package,
    has_competing_delivery_identity,
    quantity_text as _quantity_text,
)
from .readiness import (
    SupplyRecommendationReadinessError,
    build_supply_recommendation_readiness,
)


RFQ_CONTENT_VERSION = 1
MAX_CHILD_ROWS = 100
MAX_REQUEST_JSON_BYTES = 1024 * 1024
RFQ_CONTENT_ELIGIBLE_STATUSES = frozenset({
    "Утверждена",
    "КП запрошены",
})
RFQ_CONTENT_REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "name"},
    "estimates": {
        "id", "company_id", "project_id", "work_package", "sections_json",
    },
    "material_aliases": {
        "id", "project_name", "alias_name", "canonical_name",
        "canonical_unit", "active",
    },
    "supply_requests": {
        "id", "company_id", "project", "work_package", "status", "items_json",
    },
    "supply_deliveries": {
        "id", "request_id", "company_id", "project", "work_package",
        "material_name", "unit", "received_quantity",
    },
    "estimate_row_supply_allocations": {
        "id", "request_id", "request_item_index", "company_id",
        "source_estimate_id", "source_section_index", "source_item_index",
        "allocation_quantity",
    },
}


class SupplyRfqContentError(ValueError):
    """Fixed error code safe to expose without database or business text."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


class _PreviewBlock(Exception):
    def __init__(self, state, code):
        self.state = state
        self.code = code
        super().__init__(code)


def _block(state, code):
    raise _PreviewBlock(state, code)


def _positive_int(value):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _non_negative_int(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _canonical_sha256(value):
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError, ValueError, RecursionError, UnicodeError, OverflowError,
    ) as exc:
        raise SupplyRfqContentError("supply_rfq_content_invalid") from exc
    return hashlib.sha256(payload).hexdigest()


def _selection(value):
    if not isinstance(value, Mapping) or set(value) != {
        "requestId", "requestItemIndex",
    }:
        raise SupplyRfqContentError("supply_rfq_selection_invalid")
    request_id = _positive_int(value.get("requestId"))
    item_index = _non_negative_int(value.get("requestItemIndex"))
    if request_id is None or item_index is None:
        raise SupplyRfqContentError("supply_rfq_selection_invalid")
    return {"requestId": request_id, "requestItemIndex": item_index}


def _stored_change_kinds(report, candidate):
    try:
        pairs = report["domains"]["materials"]["changedPairs"]
    except (KeyError, TypeError):
        raise SupplyRfqContentError("supply_rfq_readiness_invalid")
    matches = [
        pair for pair in pairs
        if isinstance(pair, Mapping)
        and pair.get("base") == candidate["base"]
        and pair.get("target") == candidate["target"]
        and pair.get("matchKind") == candidate["matchKind"]
        and pair.get("aliasIds") == candidate["aliasIds"]
    ]
    if len(matches) != 1:
        raise SupplyRfqContentError("supply_rfq_readiness_invalid")
    change_kinds = matches[0].get("changeKinds")
    if not isinstance(change_kinds, list):
        raise SupplyRfqContentError("supply_rfq_readiness_invalid")
    return list(change_kinds)


def _prepare(combined_report, selected):
    selected = _selection(selected)
    try:
        readiness = build_supply_recommendation_readiness(combined_report)
    except SupplyRecommendationReadinessError as exc:
        raise SupplyRfqContentError("supply_rfq_readiness_invalid") from exc
    if not readiness.get("readyForRecommendationPreview"):
        raise SupplyRfqContentError("supply_rfq_readiness_blocked")
    candidates = [
        candidate for candidate in readiness.get("candidates") or []
        if candidate.get("requestId") == selected["requestId"]
        and candidate.get("requestItemIndex") == selected["requestItemIndex"]
    ]
    if len(candidates) != 1:
        raise SupplyRfqContentError("supply_rfq_selection_invalid")
    candidate = {
        "requestId": candidates[0]["requestId"],
        "requestItemIndex": candidates[0]["requestItemIndex"],
        "base": dict(candidates[0]["base"]),
        "target": dict(candidates[0]["target"]),
        "matchKind": candidates[0]["matchKind"],
        "aliasIds": list(candidates[0]["aliasIds"]),
    }
    candidate["changeKinds"] = _stored_change_kinds(
        combined_report, candidate,
    )
    source = dict(readiness["source"])
    expected_reconciliation_status = combined_report["source"][
        "reconciliationStatus"
    ]
    try:
        source_contract = validate_estimate_revision_source({
            "schemaVersion": REPORT_VERSION,
            "eventType": EVENT_TYPE,
            "companyId": source["companyId"],
            "projectId": source["projectId"],
            "estimateId": source["estimateId"],
            "sourceRevision": source["sourceRevision"],
        })
    except (EstimateRevisionImpactContractError, KeyError) as exc:
        raise SupplyRfqContentError("supply_rfq_readiness_invalid") from exc
    return {
        "source": source,
        "sourceContract": source_contract,
        "expectedReconciliationStatus": expected_reconciliation_status,
        "candidate": candidate,
    }


def _result(prepared, state, blockers):
    return {
        "contentVersion": RFQ_CONTENT_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": state,
        "source": dict(prepared["source"]),
        "candidate": _copy_candidate(prepared["candidate"]),
        "readyForRfqDraft": state == "draft_ready",
        "blockers": sorted(set(blockers)),
        "request": None,
        "balance": None,
        "rfqDraft": None,
        "requestItemSha256": None,
        "contentSha256": None,
        "readOnlyTransaction": False,
        "rolledBack": False,
    }


def _copy_candidate(candidate):
    return {
        "requestId": candidate["requestId"],
        "requestItemIndex": candidate["requestItemIndex"],
        "base": dict(candidate["base"]),
        "target": dict(candidate["target"]),
        "matchKind": candidate["matchKind"],
        "aliasIds": list(candidate["aliasIds"]),
        "changeKinds": list(candidate["changeKinds"]),
    }


def calculate_content_sha256(result):
    """Hash only the canonical RFQ content identity, not runner metadata."""

    canonical = {
        "contentVersion": result.get("contentVersion"),
        "source": result.get("source"),
        "candidate": result.get("candidate"),
        "request": result.get("request"),
        "balance": result.get("balance"),
        "rfqDraft": result.get("rfqDraft"),
        "requestItemSha256": result.get("requestItemSha256"),
    }
    return _canonical_sha256(canonical)


def _load_schema(cur):
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(RFQ_CONTENT_REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    return sorted(
        table + "." + column
        for table, columns in RFQ_CONTENT_REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )


def _load_project(cur, source):
    cur.execute(
        """SELECT p.name AS project_name,
                  cardinality(ARRAY(
                    SELECT 1 FROM public.projects same_company
                     WHERE same_company.company_id=p.company_id
                       AND same_company.name=p.name
                     ORDER BY same_company.id
                     LIMIT 2
                  )) AS same_company_owner_count,
                  cardinality(ARRAY(
                    SELECT 1 FROM public.projects same_name
                     WHERE same_name.name=p.name
                     ORDER BY same_name.id
                     LIMIT 2
                  )) AS global_owner_count
             FROM public.projects p
            WHERE p.id=%s AND p.company_id=%s
            ORDER BY p.id
            LIMIT 2""",
        (source["projectId"], source["companyId"]),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_estimates(cur, source):
    cur.execute(
        """SELECT id AS estimate_id,company_id,project_id,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  CASE
                    WHEN octet_length(COALESCE(sections_json::text,'')) <= %s
                    THEN sections_json
                    ELSE NULL
                  END AS sections_json,
                  octet_length(COALESCE(sections_json::text,'')) AS sections_bytes
             FROM public.estimates
            WHERE id=ANY(%s) AND company_id=%s AND project_id=%s
            ORDER BY id
            LIMIT 3""",
        (
            MAX_CANONICAL_SOURCE_BYTES,
            [source["baseEstimateId"], source["estimateId"]],
            source["companyId"],
            source["projectId"],
        ),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_aliases(cur, project_name):
    cur.execute(
        """SELECT id,project_name,alias_name,canonical_name,canonical_unit,active
             FROM public.material_aliases
            WHERE active=TRUE
              AND (project_name=%s OR COALESCE(project_name,'')='')
            ORDER BY COALESCE(project_name,'') DESC,id
            LIMIT %s""",
        (project_name, MAX_ALIAS_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_request(cur, source, candidate):
    cur.execute(
        """SELECT id AS request_id,company_id AS request_company_id,
                  project AS request_project,
                  COALESCE(NULLIF(work_package,''),'Основная')
                      AS request_work_package,
                  COALESCE(status,'') AS request_status,
                  CASE
                    WHEN octet_length(COALESCE(items_json,'')) <= %s
                    THEN items_json
                    ELSE NULL
                  END AS items_json,
                  octet_length(COALESCE(items_json,'')) AS items_bytes
             FROM public.supply_requests
            WHERE id=%s AND company_id=%s
            ORDER BY id
            LIMIT 2""",
        (
            MAX_REQUEST_JSON_BYTES,
            candidate["requestId"],
            source["companyId"],
        ),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_deliveries(cur, request_id):
    cur.execute(
        """SELECT id AS delivery_id,request_id,
                  company_id AS delivery_company_id,
                  project AS delivery_project,
                  COALESCE(NULLIF(work_package,''),'Основная')
                      AS delivery_work_package,
                  material_name,unit,received_quantity
             FROM public.supply_deliveries
            WHERE request_id=%s
            ORDER BY id
            LIMIT %s""",
        (request_id, MAX_CHILD_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_allocations(cur, request_id):
    cur.execute(
        """SELECT id AS allocation_id,request_id,request_item_index,
                  company_id AS allocation_company_id,source_estimate_id,
                  source_section_index,source_item_index,allocation_quantity
             FROM public.estimate_row_supply_allocations
            WHERE request_id=%s
            ORDER BY request_item_index,id
            LIMIT %s""",
        (request_id, MAX_CHILD_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _collect_current_supply_report(cur, prepared):
    report = collect_supply_warehouse_impact_audit(
        cur, prepared["sourceContract"],
    )
    source = prepared["source"]
    current = report.get("source") if isinstance(report, Mapping) else None
    exact_source = (
        isinstance(current, Mapping)
        and all(
            current.get(field) == source[field]
            for field in (
                "companyId", "projectId", "estimateId", "sourceRevision",
                "reconciliationId", "baseEstimateId",
            )
        )
        and current.get("reconciliationStatus")
        == prepared["expectedReconciliationStatus"]
    )
    if (
        not isinstance(report, Mapping)
        or report.get("ok") is not True
        or report.get("dryRun") is not True
        or report.get("writesAttempted") != 0
        or report.get("sourceReady") is not True
        or report.get("readyForDomainScan") is not True
    ):
        _block("incomplete", "supply_rfq_source_not_ready")
    if not exact_source:
        _block("needs_review", "supply_rfq_source_drift")
    return report


def _validated_current_supply_projection(report, candidate, material_pairs):
    projection = (
        report.get("supplyWarehouseImpact")
        if isinstance(report, Mapping) else None
    )
    if not isinstance(projection, Mapping):
        _block("incomplete", "supply_rfq_supply_warehouse_not_ready")
    incomplete = (
        projection.get("state") in {"incomplete", "not_collected"}
        or projection.get("schemaReady") is not True
        or projection.get("scanComplete") is not True
        or projection.get("factsTruncated") is True
        or projection.get("needsReviewTruncated") is True
    )
    if (
        report.get("readyForSupplyWarehouseProjection") is not True
        or projection.get("state") != "complete"
        or projection.get("complete") is not True
        or projection.get("missingColumns") != []
        or projection.get("reasonCounts") != {}
        or projection.get("needsReview") != []
    ):
        _block(
            "incomplete" if incomplete else "needs_review",
            "supply_rfq_supply_warehouse_not_ready",
        )
    summary = projection.get("summary")
    open_supply = projection.get("openSupply")
    if (
        not isinstance(summary, Mapping)
        or not isinstance(open_supply, list)
        or len(open_supply) > PREVIEW_LIMIT
        or summary.get("openSupplyItems") != len(open_supply)
        or summary.get("needsReview") != 0
    ):
        _block("incomplete", "supply_rfq_supply_warehouse_not_ready")

    normalized = []
    request_items = set()
    for row in open_supply:
        if not isinstance(row, Mapping) or set(row) != OPEN_SUPPLY_FIELDS:
            _block("incomplete", "supply_rfq_supply_warehouse_not_ready")
        clean = {
            "requestId": _positive_int(row.get("requestId")),
            "requestItemIndex": _non_negative_int(
                row.get("requestItemIndex"),
            ),
            "sourceEstimateId": _positive_int(
                row.get("sourceEstimateId"),
            ),
            "sourceSectionIndex": _non_negative_int(
                row.get("sourceSectionIndex"),
            ),
            "sourceItemIndex": _non_negative_int(
                row.get("sourceItemIndex"),
            ),
            "state": row.get("state"),
        }
        if None in clean.values() or clean["state"] != "open_balance":
            _block("incomplete", "supply_rfq_supply_warehouse_not_ready")
        request_item = (clean["requestId"], clean["requestItemIndex"])
        if request_item in request_items:
            _block("incomplete", "supply_rfq_supply_warehouse_not_ready")
        request_items.add(request_item)
        normalized.append(clean)

    if not isinstance(material_pairs, list) or len(material_pairs) > PREVIEW_LIMIT:
        _block("incomplete", "supply_rfq_material_not_ready")
    for pair in material_pairs:
        if not isinstance(pair, Mapping):
            _block("incomplete", "supply_rfq_material_not_ready")
        base = pair.get("base")
        target = pair.get("target")
        if not isinstance(base, Mapping) or not isinstance(target, Mapping):
            _block("incomplete", "supply_rfq_material_not_ready")
        base_coordinate = (
            _positive_int(base.get("estimateId")),
            _non_negative_int(base.get("sectionIndex")),
            _non_negative_int(base.get("itemIndex")),
        )
        target_coordinate = (
            _positive_int(target.get("estimateId")),
            _non_negative_int(target.get("sectionIndex")),
            _non_negative_int(target.get("itemIndex")),
        )
        if (
            None in base_coordinate
            or None in target_coordinate
            or base_coordinate[0] != candidate["base"]["estimateId"]
            or target_coordinate[0] != candidate["target"]["estimateId"]
        ):
            _block("needs_review", "supply_rfq_material_lineage_drift")
    _candidates, binding_issues = bind_open_supply_to_material_pairs(
        material_pairs, normalized,
    )
    if OPEN_REQUEST_AMBIGUOUS in binding_issues:
        _block("needs_review", "supply_rfq_open_request_ambiguous")
    if (
        LINEAGE_MISSING in binding_issues
        or LINEAGE_AMBIGUOUS in binding_issues
    ):
        _block("needs_review", "supply_rfq_material_lineage_drift")
    return normalized


def _material_count(stored_sections):
    return sum(
        1
        for section in stored_sections
        if isinstance(section, Mapping)
        for item in (section.get("items") or [])
        if is_explicit_material_item(item)
    )


def _snapshot_item(stored_sections, coordinate):
    try:
        section = stored_sections[coordinate["sectionIndex"]]
        item = section["items"][coordinate["itemIndex"]]
    except (IndexError, KeyError, TypeError):
        return None
    return item if isinstance(item, Mapping) else None


def _current_context(cur, prepared):
    source = prepared["source"]
    projects = _load_project(cur, source)
    if len(projects) != 1:
        _block("needs_review", "supply_rfq_project_identity_invalid")
    project = projects[0]
    project_name = _text(project.get("project_name"), MAX_MATERIAL_TEXT_LENGTH)
    if (
        project_name is None
        or project.get("same_company_owner_count") != 1
        or not isinstance(project.get("global_owner_count"), int)
        or isinstance(project.get("global_owner_count"), bool)
        or project.get("global_owner_count") < 1
    ):
        _block("needs_review", "supply_rfq_project_identity_invalid")

    estimates = _load_estimates(cur, source)
    estimates_by_id = {
        _positive_int(row.get("estimate_id")): row for row in estimates
    }
    base = estimates_by_id.get(source["baseEstimateId"])
    target = estimates_by_id.get(source["estimateId"])
    if len(estimates) != 2 or base is None or target is None:
        _block("needs_review", "supply_rfq_estimate_pair_invalid")
    for row in (base, target):
        if (
            _positive_int(row.get("company_id")) != source["companyId"]
            or _positive_int(row.get("project_id")) != source["projectId"]
            or not isinstance(row.get("sections_bytes"), int)
            or isinstance(row.get("sections_bytes"), bool)
            or row.get("sections_bytes") < 0
            or row.get("sections_bytes") > MAX_CANONICAL_SOURCE_BYTES
            or row.get("sections_json") is None
        ):
            _block("needs_review", "supply_rfq_estimate_pair_invalid")
    work_package = _package(base.get("work_package"))
    if work_package is None or work_package != _package(target.get("work_package")):
        _block("needs_review", "supply_rfq_estimate_pair_invalid")
    try:
        base_sections = parse_sections(base["sections_json"])
        target_sections = parse_sections(target["sections_json"])
    except (
        TypeError, ValueError, json.JSONDecodeError, RecursionError,
        UnicodeError, OverflowError,
    ):
        _block("needs_review", "supply_rfq_estimate_snapshot_invalid")
    if max(_material_count(base_sections), _material_count(target_sections)) > MAX_MATERIAL_ROWS:
        _block("incomplete", "supply_rfq_material_scan_limit_exceeded")

    aliases = _load_aliases(cur, project_name)
    if len(aliases) > MAX_ALIAS_ROWS:
        _block("incomplete", "supply_rfq_alias_scan_limit_exceeded")
    context = {
        "companyId": source["companyId"],
        "projectId": source["projectId"],
        "projectName": project_name,
        "projectNameOwnerCount": project["global_owner_count"],
        "baseEstimateId": source["baseEstimateId"],
        "targetEstimateId": source["estimateId"],
        "workPackage": work_package,
        "baseSections": base_sections,
    }
    projection = build_material_projection(
        context, base_sections, target_sections, aliases,
    )
    if not projection.get("complete"):
        state = "incomplete" if (
            projection.get("state") == "incomplete"
            or projection.get("scanComplete") is not True
            or projection.get("factsTruncated") is True
        ) else "needs_review"
        _block(state, "supply_rfq_material_not_ready")
    material_pairs = projection.get("changedPairs")
    current_pairs = [
        pair for pair in projection.get("changedPairs") or []
        if pair == {
            "base": prepared["candidate"]["base"],
            "target": prepared["candidate"]["target"],
            "matchKind": prepared["candidate"]["matchKind"],
            "aliasIds": prepared["candidate"]["aliasIds"],
            "changeKinds": prepared["candidate"]["changeKinds"],
        }
    ]
    if len(current_pairs) != 1:
        _block("needs_review", "supply_rfq_material_lineage_drift")
    if (
        prepared["candidate"]["matchKind"] == "stable_item_key"
        and "identity_changed" in prepared["candidate"]["changeKinds"]
    ):
        _block("needs_review", "supply_rfq_material_identity_changed")
    target_item = _snapshot_item(target_sections, prepared["candidate"]["target"])
    if not is_explicit_material_item(target_item):
        _block("needs_review", "supply_rfq_target_material_invalid")
    target_name = _text(target_item.get("name"), MAX_MATERIAL_TEXT_LENGTH)
    target_unit = _text(target_item.get("unit"), MAX_UNIT_TEXT_LENGTH)
    if target_name is None or target_unit is None:
        _block("needs_review", "supply_rfq_target_material_invalid")
    return context, target_name, target_unit, material_pairs


def _parse_items(row):
    size = row.get("items_bytes")
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or size < 0
        or size > MAX_REQUEST_JSON_BYTES
        or row.get("items_json") is None
    ):
        _block("incomplete", "supply_rfq_request_snapshot_too_large")
    try:
        items = json.loads(row["items_json"]) if isinstance(
            row["items_json"], str,
        ) else row["items_json"]
    except (
        TypeError, ValueError, json.JSONDecodeError, RecursionError,
        UnicodeError, OverflowError,
    ):
        _block("needs_review", "supply_rfq_request_invalid")
    if not isinstance(items, list) or len(items) > MAX_REQUEST_ITEMS:
        state = "incomplete" if isinstance(items, list) else "needs_review"
        code = (
            "supply_rfq_request_item_scan_limit_exceeded"
            if state == "incomplete" else "supply_rfq_request_invalid"
        )
        _block(state, code)
    return items


def _request_item_details(request, items, context, candidate):
    item_index = candidate["requestItemIndex"]
    if item_index >= len(items) or not isinstance(items[item_index], Mapping):
        _block("needs_review", "supply_rfq_request_invalid")
    item = items[item_index]
    raw_names = [
        _text(item.get(field), MAX_MATERIAL_TEXT_LENGTH)
        for field in ("materialName", "name")
        if item.get(field) not in (None, "")
    ]
    if not raw_names or None in raw_names or len(set(raw_names)) != 1:
        _block("needs_review", "supply_rfq_request_invalid")
    material_name = raw_names[0]
    unit = _text(item.get("unit"), MAX_UNIT_TEXT_LENGTH)
    quantity = _decimal(item.get("quantity"), positive=True)
    lineage = item.get("estimateLineage")
    sources = lineage.get("sources") if isinstance(lineage, Mapping) else None
    if (
        item.get("sourceType") != "estimate_material_control"
        or unit is None
        or quantity is None
        or _package(item.get("workPackage")) != context["workPackage"]
        or not isinstance(lineage, Mapping)
        or lineage.get("version") != 2
        or lineage.get("validated") is not True
        or _positive_int(lineage.get("companyId")) != context["companyId"]
        or _positive_int(lineage.get("projectId")) != context["projectId"]
        or _text(lineage.get("projectName"), MAX_MATERIAL_TEXT_LENGTH)
        != context["projectName"]
        or _package(lineage.get("workPackage")) != context["workPackage"]
        or not isinstance(sources, list)
        or len(sources) != 1
        or not isinstance(sources[0], Mapping)
    ):
        _block("needs_review", "supply_rfq_request_invalid")
    source = sources[0]
    if (
        source.get("validated") is not True
        or _positive_int(source.get("estimateId"))
        != candidate["base"]["estimateId"]
        or _non_negative_int(source.get("sectionIndex"))
        != candidate["base"]["sectionIndex"]
        or _non_negative_int(source.get("itemIndex"))
        != candidate["base"]["itemIndex"]
        or _text(source.get("materialName"), MAX_MATERIAL_TEXT_LENGTH)
        != material_name
        or _text(source.get("unit"), MAX_UNIT_TEXT_LENGTH) != unit
    ):
        _block("needs_review", "supply_rfq_request_invalid")
    base_item = _snapshot_item(context["baseSections"], candidate["base"])
    if (
        not is_explicit_material_item(base_item)
        or _text(base_item.get("name"), MAX_MATERIAL_TEXT_LENGTH) != material_name
        or _text(base_item.get("unit"), MAX_UNIT_TEXT_LENGTH) != unit
    ):
        _block("needs_review", "supply_rfq_request_invalid")
    item_hash = _canonical_sha256(item)
    competing_identity = has_competing_delivery_identity(
        items, item_index, material_name, unit,
    )
    return material_name, unit, quantity, item_hash, competing_identity


def _current_request(cur, prepared, context):
    rows = _load_request(cur, prepared["source"], prepared["candidate"])
    if len(rows) != 1:
        _block("needs_review", "supply_rfq_request_invalid")
    request = rows[0]
    if (
        _positive_int(request.get("request_id"))
        != prepared["candidate"]["requestId"]
        or _positive_int(request.get("request_company_id"))
        != context["companyId"]
        or _text(request.get("request_project"), MAX_MATERIAL_TEXT_LENGTH)
        != context["projectName"]
        or _package(request.get("request_work_package"))
        != context["workPackage"]
    ):
        _block("needs_review", "supply_rfq_request_invalid")
    status = request.get("request_status")
    if status not in RFQ_CONTENT_ELIGIBLE_STATUSES:
        _block("no_action", "supply_rfq_request_status_ineligible")
    items = _parse_items(request)
    details = _request_item_details(
        request, items, context, prepared["candidate"],
    )
    return request, details


def _balance(cur, prepared, context, request, details, canonical_open):
    material_name, unit, requested, item_hash, competing_identity = details
    deliveries = _load_deliveries(cur, prepared["candidate"]["requestId"])
    allocations = _load_allocations(cur, prepared["candidate"]["requestId"])
    if len(deliveries) > MAX_CHILD_ROWS or len(allocations) > MAX_CHILD_ROWS:
        _block("incomplete", "supply_rfq_child_scan_limit_exceeded")
    projection = build_supply_warehouse_projection(
        context,
        [request],
        deliveries,
        allocations,
        [], [], [], [], [], [],
    )
    if not projection.get("complete"):
        state = "incomplete" if (
            projection.get("state") == "incomplete"
            or projection.get("scanComplete") is not True
            or projection.get("factsTruncated") is True
        ) else "needs_review"
        _block(state, "supply_rfq_supply_evidence_invalid")

    matching_deliveries = [
        row
        for row in deliveries
        if _text(row.get("material_name"), MAX_MATERIAL_TEXT_LENGTH)
        == material_name
        and _text(row.get("unit"), MAX_UNIT_TEXT_LENGTH) == unit
    ]
    if competing_identity and matching_deliveries:
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    received_values = [
        _decimal(row.get("received_quantity"))
        for row in matching_deliveries
    ]
    if any(value is None for value in received_values):
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    received = sum(received_values, Decimal(0))
    matching_allocations = [
        row for row in allocations
        if _non_negative_int(row.get("request_item_index"))
        == prepared["candidate"]["requestItemIndex"]
    ]
    allocated_values = [
        _decimal(row.get("allocation_quantity"), positive=True)
        for row in matching_allocations
    ]
    if any(value is None for value in allocated_values):
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    allocated = sum(allocated_values, Decimal(0))
    remaining = requested - received - allocated
    if remaining < 0:
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    if remaining == 0:
        _block("no_action", "supply_rfq_open_balance_zero")
    expected_open = {
        "requestId": prepared["candidate"]["requestId"],
        "requestItemIndex": prepared["candidate"]["requestItemIndex"],
        "sourceEstimateId": prepared["candidate"]["base"]["estimateId"],
        "sourceSectionIndex": prepared["candidate"]["base"]["sectionIndex"],
        "sourceItemIndex": prepared["candidate"]["base"]["itemIndex"],
        "state": "open_balance",
    }
    if sum(row == expected_open for row in canonical_open) != 1:
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    current_open = [
        row for row in projection.get("openSupply") or []
        if row == expected_open
    ]
    if len(current_open) != 1:
        _block("needs_review", "supply_rfq_supply_evidence_invalid")
    return requested, received, allocated, remaining, item_hash


def _collect(cur, prepared):
    try:
        current_supply_report = _collect_current_supply_report(cur, prepared)
        if _load_schema(cur):
            _block("incomplete", "supply_rfq_schema_not_ready")
        context, target_name, target_unit, material_pairs = _current_context(
            cur, prepared,
        )
        request, details = _current_request(cur, prepared, context)
        canonical_open = _validated_current_supply_projection(
            current_supply_report, prepared["candidate"], material_pairs,
        )
        requested, received, allocated, remaining, item_hash = _balance(
            cur, prepared, context, request, details, canonical_open,
        )
    except _PreviewBlock as blocked:
        return _result(prepared, blocked.state, [blocked.code])

    result = _result(prepared, "draft_ready", [])
    result["request"] = {
        "requestId": prepared["candidate"]["requestId"],
        "requestItemIndex": prepared["candidate"]["requestItemIndex"],
        "status": request["request_status"],
    }
    result["balance"] = {
        "requestedQuantity": _quantity_text(requested),
        "receivedQuantity": _quantity_text(received),
        "allocatedQuantity": _quantity_text(allocated),
        "openQuantity": _quantity_text(remaining),
        "unit": target_unit,
    }
    result["rfqDraft"] = {
        "status": "human_supplier_selection_required",
        "sendAllowed": False,
        "supplierIds": [],
        "items": [{
            "materialName": target_name,
            "quantity": _quantity_text(remaining),
            "unit": target_unit,
            "lineage": {
                "requestId": prepared["candidate"]["requestId"],
                "requestItemIndex": prepared["candidate"]["requestItemIndex"],
                "base": dict(prepared["candidate"]["base"]),
                "target": dict(prepared["candidate"]["target"]),
            },
        }],
    }
    result["requestItemSha256"] = item_hash
    result["contentSha256"] = calculate_content_sha256(result)
    return result


def run_supply_rfq_content_preview(get_db, combined_report, selected):
    """Run one exact content preview and always roll its transaction back."""

    prepared = _prepare(combined_report, selected)
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_error = None
    try:
        connection = get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        result = _collect(cur, prepared)
    except BaseException as exc:
        primary_error = exc

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as exc:
            rollback_error = exc

    if cur is not None and hasattr(cur, "close"):
        try:
            cur.close()
        except BaseException as exc:
            cleanup_error = exc
    if connection is not None:
        try:
            connection.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc

    if isinstance(primary_error, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise primary_error
    if rollback_error is not None:
        raise SupplyRfqContentError(
            "supply_rfq_rollback_failed",
        ) from rollback_error
    if isinstance(primary_error, SupplyRfqContentError):
        raise primary_error
    if primary_error is not None:
        raise SupplyRfqContentError("supply_rfq_read_failed") from primary_error
    if cleanup_error is not None:
        raise SupplyRfqContentError(
            "supply_rfq_cleanup_failed",
        ) from cleanup_error
    result["readOnlyTransaction"] = True
    result["rolledBack"] = True
    return result


__all__ = [
    "MAX_CHILD_ROWS",
    "RFQ_CONTENT_ELIGIBLE_STATUSES",
    "RFQ_CONTENT_REQUIRED_COLUMNS",
    "RFQ_CONTENT_VERSION",
    "SupplyRfqContentError",
    "calculate_content_sha256",
    "run_supply_rfq_content_preview",
]
