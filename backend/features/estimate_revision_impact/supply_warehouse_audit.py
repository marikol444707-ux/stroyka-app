"""Read-only collector and operator command for A7.3 supply/warehouse impact."""

import argparse
import json

from backend.features.brigade_lineage.canonical import parse_sections

from .baseline import collect_baseline_audit, run_baseline_audit
from .contract import (
    EVENT_TYPE,
    MAX_CANONICAL_SOURCE_BYTES,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)
from .supply_warehouse_projection import build_supply_warehouse_projection
from .schema_probe import collect_missing_columns


MAX_DOMAIN_ROWS = 100
MAX_SOURCE_JSON_BYTES = 1024 * 1024
SUPPLY_WAREHOUSE_REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "name"},
    "estimates": {"id", "company_id", "project_id", "work_package", "sections_json"},
    "supply_requests": {"id", "company_id", "project", "status", "work_package", "items_json"},
    "supply_deliveries": {
        "id", "request_id", "company_id", "project", "work_package",
        "material_name", "unit", "received_quantity",
    },
    "estimate_row_supply_allocations": {
        "id", "request_id", "request_item_index", "company_id",
        "source_estimate_id", "source_section_index", "source_item_index",
        "allocation_quantity",
    },
    "supplier_invoices": {"id", "request_id", "company_id"},
    "warehouse_invoices": {
        "id", "company_id", "supply_request_id", "supply_delivery_id",
        "supplier_invoice_id", "project", "items",
    },
    "warehouse_history": {
        "id", "company_id", "work_package", "source_invoice_id",
        "source_invoice_line_index",
    },
    "warehouse_receipt_lots": {
        "id", "company_id", "project_id", "warehouse_invoice_id",
        "invoice_line_index",
    },
    "warehouse_movements": {
        "id", "company_id", "work_package", "source_invoice_id",
        "source_invoice_line_index",
    },
    "warehouse_lot_movements": {
        "id", "lot_id", "company_id", "warehouse_movement_id",
    },
}


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _empty_projection(state, reason_code=None, *, schema_ready=True, missing_columns=None):
    reviews = []
    reason_counts = {}
    if reason_code:
        reviews = [{
            "sourceKind": "supplyWarehouse",
            "sourceId": None,
            "reasonCode": reason_code,
        }]
        reason_counts = {reason_code: 1}
    return {
        "state": state,
        "schemaReady": bool(schema_ready),
        "missingColumns": list(missing_columns or []),
        "scanComplete": state not in ("not_collected", "incomplete"),
        "complete": False,
        "summary": {
            "supplyRequestRows": 0,
            "supplyItems": 0,
            "openSupplyItems": 0,
            "protectedSupplyItems": 0,
            "closedSupplyRequests": 0,
            "deliveries": 0,
            "allocations": 0,
            "supplierInvoices": 0,
            "warehouseInvoices": 0,
            "warehouseHistoryRows": 0,
            "receiptLots": 0,
            "warehouseMovements": 0,
            "lotMovements": 0,
            "needsReview": len(reviews),
        },
        "openSupply": [],
        "protectedEvidence": {
            "closedSupplyRequestIds": [],
            "deliveryIds": [],
            "allocationIds": [],
            "supplierInvoiceIds": [],
            "warehouseInvoiceIds": [],
            "warehouseHistoryIds": [],
            "receiptLotIds": [],
            "warehouseMovementIds": [],
            "lotMovementIds": [],
        },
        "factsTruncated": False,
        "reasonCounts": reason_counts,
        "needsReview": reviews,
        "needsReviewTruncated": False,
    }


def _load_schema(cur):
    return collect_missing_columns(cur, SUPPLY_WAREHOUSE_REQUIRED_COLUMNS)


def _load_context(cur, source):
    cur.execute(
        """SELECT p.name AS project_name,
                  cardinality(ARRAY(
                    SELECT 1 FROM public.projects same_name
                     WHERE same_name.name=p.name
                     ORDER BY same_name.id
                     LIMIT 2
                  )) AS owner_count,
                  COALESCE(NULLIF(b.work_package,''),'Основная')
                      AS base_work_package,
                  CASE
                    WHEN octet_length(COALESCE(b.sections_json::text,'')) <= %s
                    THEN b.sections_json
                    ELSE NULL
                  END AS base_sections_json,
                  octet_length(COALESCE(b.sections_json::text,''))
                      AS base_sections_bytes
             FROM public.projects p
             JOIN public.estimates b
               ON b.id=%s AND b.company_id=p.company_id
              AND b.project_id=p.id
            WHERE p.id=%s AND p.company_id=%s
            ORDER BY p.id
            LIMIT 2""",
        (
            MAX_CANONICAL_SOURCE_BYTES,
            source["baseEstimateId"], source["projectId"],
            source["companyId"],
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows[0] if len(rows) == 1 else None


def _load_requests(cur, context):
    estimate_id_pattern = (
        '"estimateId"[[:space:]]*:[[:space:]]*'
        + str(context["baseEstimateId"])
        + "([^0-9]|$)"
    )
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
                  END AS items_json
             FROM public.supply_requests
            WHERE company_id=%s AND project=%s
              AND COALESCE(NULLIF(work_package,''),'Основная')=%s
              AND items_json ~ %s
            ORDER BY id
            LIMIT %s""",
        (
            MAX_SOURCE_JSON_BYTES,
            context["companyId"], context["projectName"],
            context["workPackage"], estimate_id_pattern,
            MAX_DOMAIN_ROWS + 1,
        ),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_deliveries(cur, request_ids):
    cur.execute(
        """SELECT id AS delivery_id,request_id,
                  company_id AS delivery_company_id,
                  project AS delivery_project,
                  COALESCE(NULLIF(work_package,''),'Основная')
                      AS delivery_work_package,
                  material_name,unit,received_quantity
             FROM public.supply_deliveries
            WHERE request_id=ANY(%s)
            ORDER BY request_id,id
            LIMIT %s""",
        (request_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_allocations(cur, request_ids):
    cur.execute(
        """SELECT id AS allocation_id,request_id,request_item_index,
                  company_id AS allocation_company_id,source_estimate_id,
                  source_section_index,source_item_index,allocation_quantity
             FROM public.estimate_row_supply_allocations
            WHERE request_id=ANY(%s)
            ORDER BY request_id,request_item_index,id
            LIMIT %s""",
        (request_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_supplier_invoices(cur, request_ids):
    cur.execute(
        """SELECT id AS supplier_invoice_id,request_id,
                  company_id AS invoice_company_id
             FROM public.supplier_invoices
            WHERE request_id=ANY(%s)
            ORDER BY request_id,id
            LIMIT %s""",
        (request_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_warehouse_invoices(cur, request_ids):
    cur.execute(
        """SELECT id AS warehouse_invoice_id,
                  company_id AS invoice_company_id,supply_request_id,
                  supply_delivery_id,supplier_invoice_id,
                  project AS invoice_project,
                  CASE
                    WHEN octet_length(COALESCE(items,'')) <= %s
                    THEN items
                    ELSE NULL
                  END AS items
             FROM public.warehouse_invoices
            WHERE supply_request_id=ANY(%s)
            ORDER BY supply_request_id,id
            LIMIT %s""",
        (MAX_SOURCE_JSON_BYTES, request_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_history(cur, invoice_ids):
    cur.execute(
        """SELECT id AS history_id,company_id AS history_company_id,
                  COALESCE(NULLIF(work_package,''),'Основная')
                      AS history_work_package,
                  source_invoice_id,source_invoice_line_index
             FROM public.warehouse_history
            WHERE source_invoice_id=ANY(%s)
            ORDER BY source_invoice_id,source_invoice_line_index,id
            LIMIT %s""",
        (invoice_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_lots(cur, invoice_ids):
    cur.execute(
        """SELECT id AS lot_id,company_id AS lot_company_id,
                  project_id AS lot_project_id,warehouse_invoice_id,
                  invoice_line_index
             FROM public.warehouse_receipt_lots
            WHERE warehouse_invoice_id=ANY(%s)
            ORDER BY warehouse_invoice_id,invoice_line_index,id
            LIMIT %s""",
        (invoice_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_movements(cur, invoice_ids):
    cur.execute(
        """SELECT id AS movement_id,company_id AS movement_company_id,
                  COALESCE(NULLIF(work_package,''),'Основная')
                      AS movement_work_package,
                  source_invoice_id,source_invoice_line_index
             FROM public.warehouse_movements
            WHERE source_invoice_id=ANY(%s)
            ORDER BY source_invoice_id,source_invoice_line_index,id
            LIMIT %s""",
        (invoice_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_lot_movements(cur, lot_ids, movement_ids):
    cur.execute(
        """SELECT id AS lot_movement_id,lot_id,
                  company_id AS lot_movement_company_id,warehouse_movement_id
             FROM public.warehouse_lot_movements
            WHERE lot_id=ANY(%s) OR warehouse_movement_id=ANY(%s)
            ORDER BY lot_id,warehouse_movement_id,id
            LIMIT %s""",
        (lot_ids, movement_ids, MAX_DOMAIN_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _too_many(*groups):
    return any(len(group) > MAX_DOMAIN_ROWS for group in groups)


def _request_mentions_base_estimate(request, base_estimate_id):
    value = (request or {}).get("items_json")
    try:
        items = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, RecursionError, UnicodeError, OverflowError):
        return False
    if not isinstance(items, list):
        return False
    return any(
        _positive_int(source.get("estimateId")) == base_estimate_id
        for item in items
        if isinstance(item, dict)
        for lineage in (item.get("estimateLineage"),)
        if isinstance(lineage, dict)
        for sources in (lineage.get("sources"),)
        if isinstance(sources, list)
        for source in sources
        if isinstance(source, dict)
    )


def collect_supply_warehouse_impact_audit(cur, source):
    """Collect A7.1 source plus exact request and warehouse lineage."""

    report = collect_baseline_audit(cur, source)
    if not report.get("readyForDomainScan"):
        report["readyForSupplyWarehouseProjection"] = False
        report["supplyWarehouseImpact"] = _empty_projection("not_collected")
        return report
    missing = _load_schema(cur)
    if missing:
        report["readyForSupplyWarehouseProjection"] = False
        report["supplyWarehouseImpact"] = _empty_projection(
            "incomplete", "supply_warehouse_impact_schema_not_ready",
            schema_ready=False, missing_columns=missing,
        )
        return report

    source_context = report["source"]
    stored_context = _load_context(cur, source_context)
    if stored_context is None:
        projection = _empty_projection(
            "review_required", "supply_warehouse_project_identity_invalid",
        )
    else:
        try:
            base_sections = parse_sections(stored_context.get("base_sections_json"))
        except (
            TypeError, ValueError, json.JSONDecodeError, RecursionError,
            UnicodeError, OverflowError,
        ):
            base_sections = None
        if base_sections is None or not _text(stored_context.get("project_name")):
            projection = _empty_projection(
                "review_required", "supply_warehouse_source_snapshot_invalid",
            )
        else:
            context = {
                "companyId": source_context["companyId"],
                "projectId": source_context["projectId"],
                "projectName": stored_context["project_name"],
                "projectNameOwnerCount": stored_context.get("owner_count"),
                "baseEstimateId": source_context["baseEstimateId"],
                "targetEstimateId": source_context["estimateId"],
                "workPackage": stored_context["base_work_package"],
                "baseSections": base_sections,
            }
            requests = _load_requests(cur, context)
            if len(requests) > MAX_DOMAIN_ROWS:
                projection = _empty_projection(
                    "incomplete", "supply_request_scan_limit_exceeded",
                )
            elif not requests:
                projection = build_supply_warehouse_projection(
                    context, [], [], [], [], [], [], [], [], [],
                )
            else:
                request_ids = sorted({
                    _positive_int(row.get("request_id"))
                    for row in requests
                    if _request_mentions_base_estimate(
                        row, context["baseEstimateId"],
                    ) and _positive_int(row.get("request_id"))
                })
                if not request_ids:
                    projection = build_supply_warehouse_projection(
                        context, requests, [], [], [], [], [], [], [], [],
                    )
                    report["readyForSupplyWarehouseProjection"] = projection["complete"]
                    report["supplyWarehouseImpact"] = projection
                    return report
                deliveries = _load_deliveries(cur, request_ids)
                allocations = _load_allocations(cur, request_ids)
                supplier_invoices = _load_supplier_invoices(cur, request_ids)
                warehouse_invoices = _load_warehouse_invoices(cur, request_ids)
                invoice_ids = sorted({
                    invoice_id for invoice_id in (
                        _positive_int(row.get("warehouse_invoice_id"))
                        for row in warehouse_invoices
                    ) if invoice_id
                })
                history = _load_history(cur, invoice_ids)
                lots = _load_lots(cur, invoice_ids)
                movements = _load_movements(cur, invoice_ids)
                lot_ids = sorted({
                    lot_id for lot_id in (
                        _positive_int(row.get("lot_id")) for row in lots
                    ) if lot_id
                })
                movement_ids = sorted({
                    movement_id for movement_id in (
                        _positive_int(row.get("movement_id")) for row in movements
                    ) if movement_id
                })
                lot_movements = _load_lot_movements(cur, lot_ids, movement_ids)
                if _too_many(
                    deliveries, allocations, supplier_invoices,
                    warehouse_invoices, history, lots, movements, lot_movements,
                ):
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                else:
                    projection = build_supply_warehouse_projection(
                        context, requests, deliveries, allocations,
                        supplier_invoices, warehouse_invoices, history,
                        lots, movements, lot_movements,
                    )
    report["readyForSupplyWarehouseProjection"] = projection["complete"]
    report["supplyWarehouseImpact"] = projection
    return report


def run_supply_warehouse_impact_audit(get_db, source):
    return run_baseline_audit(
        get_db,
        source,
        collect_data=collect_supply_warehouse_impact_audit,
    )


def _source_from_args(args):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": args.company_id,
        "projectId": args.project_id,
        "estimateId": args.estimate_id,
        "sourceRevision": args.source_revision,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate revision supply/warehouse impact audit",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    try:
        source = _source_from_args(args)
    except EstimateRevisionImpactContractError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_supply_warehouse_impact_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForSupplyWarehouseProjection") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_DOMAIN_ROWS",
    "SUPPLY_WAREHOUSE_REQUIRED_COLUMNS",
    "collect_supply_warehouse_impact_audit",
    "run_supply_warehouse_impact_audit",
]
