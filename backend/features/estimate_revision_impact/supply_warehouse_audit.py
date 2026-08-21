"""Read-only collector and operator command for A7.3 supply/warehouse impact."""

import argparse
import json

from backend.features.brigade_lineage.canonical import parse_sections

from .baseline import _collect_baseline_audit, run_baseline_audit
from .contract import (
    EVENT_TYPE,
    MAX_CANONICAL_SOURCE_BYTES,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)
from .supply_warehouse_projection import build_supply_warehouse_projection
from .schema_probe import collect_missing_columns
from .resource_limits import (
    MAX_JSON_QUERY_BYTES,
    MAX_NUMERIC_FIELD_BYTES,
    MAX_TEXT_FIELD_BYTES,
    MAX_TEXT_QUERY_AGGREGATE_BYTES,
    _BOUNDED_ACCEPTED,
    _BOUNDED_CARDINALITY,
    _BOUNDED_EMPTY,
    _BOUNDED_OVERFLOW,
    _VariableByteBudget,
    _VariableByteLimitError,
    _accept_bounded_rows,
)


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

_CONTEXT_FIELD_SPECS = (
    (
        "project_name",
        "field_project_name_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "base_work_package",
        "field_base_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "base_sections_json",
        "field_base_sections_json_bytes",
        "json",
        MAX_CANONICAL_SOURCE_BYTES,
        True,
    ),
)
_REQUEST_FIELD_SPECS = (
    (
        "request_project",
        "field_request_project_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "request_work_package",
        "field_request_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "request_status",
        "field_request_status_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "items_json",
        "field_items_json_bytes",
        "json",
        MAX_SOURCE_JSON_BYTES,
        False,
    ),
)
_DELIVERY_FIELD_SPECS = (
    (
        "delivery_project",
        "field_delivery_project_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "delivery_work_package",
        "field_delivery_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
    (
        "material_name",
        "field_material_name_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "unit",
        "field_unit_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "received_quantity",
        "field_received_quantity_bytes",
        "text",
        MAX_NUMERIC_FIELD_BYTES,
        True,
    ),
)
_ALLOCATION_FIELD_SPECS = (
    (
        "allocation_quantity",
        "field_allocation_quantity_bytes",
        "text",
        MAX_NUMERIC_FIELD_BYTES,
        True,
    ),
)
_WAREHOUSE_INVOICE_FIELD_SPECS = (
    (
        "invoice_project",
        "field_invoice_project_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        True,
    ),
    (
        "items",
        "field_items_bytes",
        "json",
        MAX_SOURCE_JSON_BYTES,
        True,
    ),
)
_HISTORY_FIELD_SPECS = (
    (
        "history_work_package",
        "field_history_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
)
_MOVEMENT_FIELD_SPECS = (
    (
        "movement_work_package",
        "field_movement_work_package_bytes",
        "text",
        MAX_TEXT_FIELD_BYTES,
        False,
    ),
)


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


def _load_context(cur, source, variable_budget):
    cur.execute(
        """SELECT bounded.project_name,bounded.owner_count,
                  bounded.base_work_package,bounded.base_sections_json,
                  bounded.base_sections_bytes,
                  bounded.field_project_name_bytes,
                  bounded.field_base_work_package_bytes,
                  bounded.field_base_sections_json_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT p.id AS project_id,
                        p.name AS emitted_project_name,
                        cardinality(ARRAY(
                          SELECT 1 FROM public.projects same_name
                           WHERE same_name.name=p.name
                           ORDER BY same_name.id
                           LIMIT 2
                        )) AS owner_count,
                        COALESCE(NULLIF(b.work_package,''),'Основная')
                            AS emitted_base_work_package,
                        b.sections_json::text AS emitted_base_sections_json
                   FROM public.projects p
                   JOIN public.estimates b
                     ON b.id=%s AND b.company_id=p.company_id
                    AND b.project_id=p.id
                  WHERE p.id=%s AND p.company_id=%s
                  ORDER BY p.id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_project_name,'UTF8'
                        )),0)::bigint AS field_project_name_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_base_work_package,'UTF8'
                        )),0)::bigint AS field_base_work_package_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_base_sections_json,'UTF8'
                        )),0)::bigint AS field_base_sections_json_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_project_name_bytes) OVER ()
                            AS max_field_project_name_bytes,
                        MAX(field_base_work_package_bytes) OVER ()
                            AS max_field_base_work_package_bytes,
                        MAX(field_base_sections_json_bytes) OVER ()
                            AS max_field_base_sections_json_bytes,
                        COALESCE(SUM(
                            field_base_sections_json_bytes::bigint
                        ) OVER (),0)::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_project_name_bytes::bigint
                            + field_base_work_package_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        (query_json_bytes + query_text_bytes)::bigint
                            AS query_variable_bytes,
                        (
                          max_field_base_sections_json_bytes <= %s
                          AND max_field_project_name_bytes <= %s
                          AND max_field_base_work_package_bytes <= %s
                          AND query_json_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_json_bytes + query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.project_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_project_name ELSE NULL
                      END AS project_name,
                      decided.owner_count,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_base_work_package ELSE NULL
                      END AS base_work_package,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_base_sections_json ELSE NULL
                      END AS base_sections_json,
                      decided.field_base_sections_json_bytes
                          AS base_sections_bytes,
                      decided.field_project_name_bytes,
                      decided.field_base_work_package_bytes,
                      decided.field_base_sections_json_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.project_id""",
        (
            source["baseEstimateId"], source["projectId"],
            source["companyId"], 2,
            MAX_CANONICAL_SOURCE_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            1,
            1,
            1,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    for row in rows:
        if (
            type(row.get("base_sections_bytes")) is not int
            or row.get("base_sections_bytes") < 0
            or row.get("base_sections_bytes")
            != row.get("field_base_sections_json_bytes")
        ):
            raise _VariableByteLimitError(
                "variable byte metadata is invalid"
            )
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=1,
        field_specs=_CONTEXT_FIELD_SPECS,
    )


def _load_requests(cur, context, variable_budget):
    estimate_id_pattern = (
        '"estimateId"[[:space:]]*:[[:space:]]*'
        + str(context["baseEstimateId"])
        + "([^0-9]|$)"
    )
    cur.execute(
        """SELECT bounded.request_id,bounded.request_company_id,
                  bounded.request_project,bounded.request_work_package,
                  bounded.request_status,bounded.items_json,
                  bounded.field_request_project_bytes,
                  bounded.field_request_work_package_bytes,
                  bounded.field_request_status_bytes,
                  bounded.field_items_json_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS request_id,
                        company_id AS request_company_id,
                        project AS emitted_request_project,
                        COALESCE(NULLIF(work_package,''),'Основная')
                            AS emitted_request_work_package,
                        COALESCE(status,'') AS emitted_request_status,
                        items_json AS emitted_items_json
                   FROM public.supply_requests
                  WHERE company_id=%s AND project=%s
                    AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                    AND items_json ~ %s
                  ORDER BY id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_request_project,'UTF8'
                        )),0)::bigint AS field_request_project_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_request_work_package,'UTF8'
                        )),0)::bigint
                            AS field_request_work_package_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_request_status,'UTF8'
                        )),0)::bigint AS field_request_status_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_items_json,'UTF8'
                        )),0)::bigint AS field_items_json_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_request_project_bytes) OVER ()
                            AS max_field_request_project_bytes,
                        MAX(field_request_work_package_bytes) OVER ()
                            AS max_field_request_work_package_bytes,
                        MAX(field_request_status_bytes) OVER ()
                            AS max_field_request_status_bytes,
                        MAX(field_items_json_bytes) OVER ()
                            AS max_field_items_json_bytes,
                        COALESCE(SUM(
                            field_items_json_bytes::bigint
                        ) OVER (),0)::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_request_project_bytes::bigint
                            + field_request_work_package_bytes::bigint
                            + field_request_status_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        (query_json_bytes + query_text_bytes)::bigint
                            AS query_variable_bytes,
                        (
                          max_field_items_json_bytes <= %s
                          AND max_field_request_project_bytes <= %s
                          AND max_field_request_work_package_bytes <= %s
                          AND max_field_request_status_bytes <= %s
                          AND query_json_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_json_bytes + query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.request_id,decided.request_company_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_request_project ELSE NULL
                      END AS request_project,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_request_work_package ELSE NULL
                      END AS request_work_package,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_request_status ELSE NULL
                      END AS request_status,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_items_json ELSE NULL
                      END AS items_json,
                      decided.field_request_project_bytes,
                      decided.field_request_work_package_bytes,
                      decided.field_request_status_bytes,
                      decided.field_items_json_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.request_id""",
        (
            context["companyId"], context["projectName"],
            context["workPackage"], estimate_id_pattern,
            MAX_DOMAIN_ROWS + 1,
            MAX_SOURCE_JSON_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_REQUEST_FIELD_SPECS,
    )


def _load_deliveries(cur, request_ids, variable_budget):
    cur.execute(
        """SELECT bounded.delivery_id,bounded.request_id,
                  bounded.delivery_company_id,bounded.delivery_project,
                  bounded.delivery_work_package,bounded.material_name,
                  bounded.unit,bounded.received_quantity,
                  bounded.field_delivery_project_bytes,
                  bounded.field_delivery_work_package_bytes,
                  bounded.field_material_name_bytes,
                  bounded.field_unit_bytes,
                  bounded.field_received_quantity_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS delivery_id,request_id,
                        company_id AS delivery_company_id,
                        project AS emitted_delivery_project,
                        COALESCE(NULLIF(work_package,''),'Основная')
                            AS emitted_delivery_work_package,
                        material_name AS emitted_material_name,
                        unit AS emitted_unit,
                        received_quantity::text
                            AS emitted_received_quantity
                   FROM public.supply_deliveries
                  WHERE request_id=ANY(%s)
                  ORDER BY request_id,id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_delivery_project,'UTF8'
                        )),0)::bigint AS field_delivery_project_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_delivery_work_package,'UTF8'
                        )),0)::bigint
                            AS field_delivery_work_package_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_material_name,'UTF8'
                        )),0)::bigint AS field_material_name_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_unit,'UTF8'
                        )),0)::bigint AS field_unit_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_received_quantity,'UTF8'
                        )),0)::bigint AS field_received_quantity_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_delivery_project_bytes) OVER ()
                            AS max_field_delivery_project_bytes,
                        MAX(field_delivery_work_package_bytes) OVER ()
                            AS max_field_delivery_work_package_bytes,
                        MAX(field_material_name_bytes) OVER ()
                            AS max_field_material_name_bytes,
                        MAX(field_unit_bytes) OVER ()
                            AS max_field_unit_bytes,
                        MAX(field_received_quantity_bytes) OVER ()
                            AS max_field_received_quantity_bytes,
                        0::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_delivery_project_bytes::bigint
                            + field_delivery_work_package_bytes::bigint
                            + field_material_name_bytes::bigint
                            + field_unit_bytes::bigint
                            + field_received_quantity_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        query_text_bytes::bigint AS query_variable_bytes,
                        (
                          max_field_delivery_project_bytes <= %s
                          AND max_field_delivery_work_package_bytes <= %s
                          AND max_field_material_name_bytes <= %s
                          AND max_field_unit_bytes <= %s
                          AND max_field_received_quantity_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.delivery_id,decided.request_id,
                      decided.delivery_company_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_delivery_project ELSE NULL
                      END AS delivery_project,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_delivery_work_package ELSE NULL
                      END AS delivery_work_package,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_material_name ELSE NULL
                      END AS material_name,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_unit ELSE NULL
                      END AS unit,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_received_quantity ELSE NULL
                      END AS received_quantity,
                      decided.field_delivery_project_bytes,
                      decided.field_delivery_work_package_bytes,
                      decided.field_material_name_bytes,
                      decided.field_unit_bytes,
                      decided.field_received_quantity_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.request_id,bounded.delivery_id""",
        (
            request_ids,
            MAX_DOMAIN_ROWS + 1,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_NUMERIC_FIELD_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_DELIVERY_FIELD_SPECS,
    )


def _load_allocations(cur, request_ids, variable_budget):
    cur.execute(
        """SELECT bounded.allocation_id,bounded.request_id,
                  bounded.request_item_index,bounded.allocation_company_id,
                  bounded.source_estimate_id,bounded.source_section_index,
                  bounded.source_item_index,bounded.allocation_quantity,
                  bounded.field_allocation_quantity_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS allocation_id,request_id,request_item_index,
                        company_id AS allocation_company_id,
                        source_estimate_id,source_section_index,
                        source_item_index,allocation_quantity::text
                            AS emitted_allocation_quantity
                   FROM public.estimate_row_supply_allocations
                  WHERE request_id=ANY(%s)
                  ORDER BY request_id,request_item_index,id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_allocation_quantity,'UTF8'
                        )),0)::bigint AS field_allocation_quantity_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_allocation_quantity_bytes) OVER ()
                            AS max_field_allocation_quantity_bytes,
                        0::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_allocation_quantity_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        query_text_bytes::bigint AS query_variable_bytes,
                        (
                          max_field_allocation_quantity_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.allocation_id,decided.request_id,
                      decided.request_item_index,
                      decided.allocation_company_id,
                      decided.source_estimate_id,
                      decided.source_section_index,
                      decided.source_item_index,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_allocation_quantity ELSE NULL
                      END AS allocation_quantity,
                      decided.field_allocation_quantity_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.request_id,bounded.request_item_index,
                     bounded.allocation_id""",
        (
            request_ids,
            MAX_DOMAIN_ROWS + 1,
            MAX_NUMERIC_FIELD_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_ALLOCATION_FIELD_SPECS,
    )


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


def _load_warehouse_invoices(cur, request_ids, variable_budget):
    cur.execute(
        """SELECT bounded.warehouse_invoice_id,
                  bounded.invoice_company_id,bounded.supply_request_id,
                  bounded.supply_delivery_id,bounded.supplier_invoice_id,
                  bounded.invoice_project,bounded.items,
                  bounded.field_invoice_project_bytes,
                  bounded.field_items_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS warehouse_invoice_id,
                        company_id AS invoice_company_id,supply_request_id,
                        supply_delivery_id,supplier_invoice_id,
                        project AS emitted_invoice_project,
                        items AS emitted_items
                   FROM public.warehouse_invoices
                  WHERE supply_request_id=ANY(%s)
                  ORDER BY supply_request_id,id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_invoice_project,'UTF8'
                        )),0)::bigint AS field_invoice_project_bytes,
                        COALESCE(octet_length(convert_to(
                            emitted_items,'UTF8'
                        )),0)::bigint AS field_items_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_invoice_project_bytes) OVER ()
                            AS max_field_invoice_project_bytes,
                        MAX(field_items_bytes) OVER ()
                            AS max_field_items_bytes,
                        COALESCE(SUM(
                            field_items_bytes::bigint
                        ) OVER (),0)::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_invoice_project_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        (query_json_bytes + query_text_bytes)::bigint
                            AS query_variable_bytes,
                        (
                          max_field_invoice_project_bytes <= %s
                          AND max_field_items_bytes <= %s
                          AND query_json_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_json_bytes + query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.warehouse_invoice_id,
                      decided.invoice_company_id,
                      decided.supply_request_id,
                      decided.supply_delivery_id,
                      decided.supplier_invoice_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_invoice_project ELSE NULL
                      END AS invoice_project,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_items ELSE NULL
                      END AS items,
                      decided.field_invoice_project_bytes,
                      decided.field_items_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.supply_request_id,
                     bounded.warehouse_invoice_id""",
        (
            request_ids,
            MAX_DOMAIN_ROWS + 1,
            MAX_TEXT_FIELD_BYTES,
            MAX_SOURCE_JSON_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_WAREHOUSE_INVOICE_FIELD_SPECS,
    )


def _load_history(cur, invoice_ids, variable_budget):
    cur.execute(
        """SELECT bounded.history_id,bounded.history_company_id,
                  bounded.history_work_package,bounded.source_invoice_id,
                  bounded.source_invoice_line_index,
                  bounded.field_history_work_package_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS history_id,company_id AS history_company_id,
                        COALESCE(NULLIF(work_package,''),'Основная')
                            AS emitted_history_work_package,
                        source_invoice_id,source_invoice_line_index
                   FROM public.warehouse_history
                  WHERE source_invoice_id=ANY(%s)
                  ORDER BY source_invoice_id,source_invoice_line_index,id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_history_work_package,'UTF8'
                        )),0)::bigint
                            AS field_history_work_package_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_history_work_package_bytes) OVER ()
                            AS max_field_history_work_package_bytes,
                        0::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_history_work_package_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        query_text_bytes::bigint AS query_variable_bytes,
                        (
                          max_field_history_work_package_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.history_id,decided.history_company_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_history_work_package ELSE NULL
                      END AS history_work_package,
                      decided.source_invoice_id,
                      decided.source_invoice_line_index,
                      decided.field_history_work_package_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.source_invoice_id,
                     bounded.source_invoice_line_index,bounded.history_id""",
        (
            invoice_ids,
            MAX_DOMAIN_ROWS + 1,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_HISTORY_FIELD_SPECS,
    )


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


def _load_movements(cur, invoice_ids, variable_budget):
    cur.execute(
        """SELECT bounded.movement_id,bounded.movement_company_id,
                  bounded.movement_work_package,bounded.source_invoice_id,
                  bounded.source_invoice_line_index,
                  bounded.field_movement_work_package_bytes,
                  bounded.query_json_bytes,bounded.query_text_bytes,
                  bounded.query_variable_bytes,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT id AS movement_id,
                        company_id AS movement_company_id,
                        COALESCE(NULLIF(work_package,''),'Основная')
                            AS emitted_movement_work_package,
                        source_invoice_id,source_invoice_line_index
                   FROM public.warehouse_movements
                  WHERE source_invoice_id=ANY(%s)
                  ORDER BY source_invoice_id,source_invoice_line_index,id
                  LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                            emitted_movement_work_package,'UTF8'
                        )),0)::bigint
                            AS field_movement_work_package_bytes
                   FROM limited
               ), totals AS MATERIALIZED (
                 SELECT sized.*,
                        COUNT(*) OVER () AS row_count,
                        MAX(field_movement_work_package_bytes) OVER ()
                            AS max_field_movement_work_package_bytes,
                        0::bigint AS query_json_bytes,
                        COALESCE(SUM(
                            field_movement_work_package_bytes::bigint
                        ) OVER (),0)::bigint AS query_text_bytes
                   FROM sized
               ), gated AS MATERIALIZED (
                 SELECT totals.*,
                        query_text_bytes::bigint AS query_variable_bytes,
                        (
                          max_field_movement_work_package_bytes <= %s
                          AND query_text_bytes <= %s
                          AND query_text_bytes <= %s
                        ) AS bytes_allowed
                   FROM totals
               ), decided AS MATERIALIZED (
                 SELECT gated.*,
                        (gated.row_count <= %s AND gated.bytes_allowed)
                            AS payload_allowed
                   FROM gated
               )
               SELECT decided.movement_id,decided.movement_company_id,
                      CASE WHEN decided.payload_allowed
                           THEN decided.emitted_movement_work_package ELSE NULL
                      END AS movement_work_package,
                      decided.source_invoice_id,
                      decided.source_invoice_line_index,
                      decided.field_movement_work_package_bytes,
                      decided.query_json_bytes,decided.query_text_bytes,
                      decided.query_variable_bytes,
                      (decided.row_count > %s)
                          AS cardinality_limit_exceeded,
                      (decided.row_count <= %s AND NOT decided.bytes_allowed)
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.source_invoice_id,
                     bounded.source_invoice_line_index,bounded.movement_id""",
        (
            invoice_ids,
            MAX_DOMAIN_ROWS + 1,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            variable_budget.remaining_bytes,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return _accept_bounded_rows(
        rows,
        variable_budget,
        scan_limit=MAX_DOMAIN_ROWS,
        field_specs=_MOVEMENT_FIELD_SPECS,
    )


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


def _fixed_request_faults(context, requests):
    faults = []
    for request in requests:
        request_id = _positive_int(request.get("request_id"))
        request_company_id = _positive_int(
            request.get("request_company_id")
        )
        if not request_id or request_company_id != context["companyId"]:
            faults.append(request)
    return faults


def _fixed_prefix_faults(
    rows,
    *,
    row_id_field,
    parent_id_field,
    owner_field,
    parent_ids,
    company_id,
):
    """Classify only the fixed identity/owner prefix of a bounded row."""

    expected_parent_ids = set(parent_ids)
    faults = []
    for row in rows:
        parent_id = _positive_int(row.get(parent_id_field))
        if parent_id not in expected_parent_ids:
            raise _VariableByteLimitError(
                "variable byte metadata is invalid"
            )
        if (
            not _positive_int(row.get(row_id_field))
            or _positive_int(row.get(owner_field)) != company_id
        ):
            faults.append(row)
    return faults


def _bounded_payload_requires_systemic_stop(
    state,
    rows,
    known_fixed_fault,
    *,
    row_id_field,
    parent_id_field,
    owner_field,
    parent_ids,
    company_id,
):
    """Apply cardinality -> fixed prefix -> payload overflow precedence."""

    if state == _BOUNDED_CARDINALITY:
        return True, known_fixed_fault
    if state not in {
        _BOUNDED_EMPTY,
        _BOUNDED_ACCEPTED,
        _BOUNDED_OVERFLOW,
    }:
        raise _VariableByteLimitError(
            "variable byte metadata is invalid"
        )
    faults = _fixed_prefix_faults(
        rows,
        row_id_field=row_id_field,
        parent_id_field=parent_id_field,
        owner_field=owner_field,
        parent_ids=parent_ids,
        company_id=company_id,
    )
    if state == _BOUNDED_OVERFLOW:
        if faults:
            if len(faults) != len(rows):
                raise _VariableByteLimitError(
                    "variable byte metadata is invalid"
                )
            return False, True
        if known_fixed_fault:
            raise _VariableByteLimitError(
                "variable byte metadata is invalid"
            )
        return True, False
    return False, known_fixed_fault or bool(faults)


def _fixed_lot_movement_faults(
    rows,
    *,
    lot_ids,
    movement_ids,
    company_id,
):
    expected_lot_ids = set(lot_ids)
    expected_movement_ids = set(movement_ids)
    faults = []
    for row in rows:
        lot_id = _positive_int(row.get("lot_id"))
        movement_id = _positive_int(row.get("warehouse_movement_id"))
        if (
            lot_id not in expected_lot_ids
            and movement_id not in expected_movement_ids
        ):
            raise _VariableByteLimitError(
                "variable byte metadata is invalid"
            )
        if (
            not _positive_int(row.get("lot_movement_id"))
            or not lot_id
            or not movement_id
            or _positive_int(row.get("lot_movement_company_id"))
            != company_id
        ):
            faults.append(row)
    return faults


def collect_supply_warehouse_impact_audit(cur, source):
    """Collect A7.1 source plus exact request and warehouse lineage."""

    variable_budget = _VariableByteBudget()
    report = _collect_baseline_audit(cur, source, variable_budget)
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
    context_state, stored_context_rows, _context_overflow_fields = (
        _load_context(cur, source_context, variable_budget)
    )
    if context_state == _BOUNDED_OVERFLOW:
        projection = _empty_projection(
            "incomplete", "supply_warehouse_scan_limit_exceeded",
        )
    elif not stored_context_rows or context_state == _BOUNDED_CARDINALITY:
        projection = _empty_projection(
            "review_required", "supply_warehouse_project_identity_invalid",
        )
    else:
        stored_context = stored_context_rows[0]
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
            request_state, requests, _request_overflow_fields = (
                _load_requests(cur, context, variable_budget)
            )
            if request_state == _BOUNDED_CARDINALITY:
                projection = _empty_projection(
                    "incomplete", "supply_request_scan_limit_exceeded",
                )
            elif request_state == _BOUNDED_OVERFLOW:
                fixed_faults = _fixed_request_faults(
                    context,
                    requests,
                )
                if fixed_faults and len(fixed_faults) != len(requests):
                    raise _VariableByteLimitError(
                        "variable byte metadata is invalid"
                    )
                if fixed_faults:
                    projection = build_supply_warehouse_projection(
                        context,
                        requests,
                        [],
                        [],
                        [],
                        [],
                        [],
                        [],
                        [],
                        [],
                    )
                else:
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
                    if _positive_int(row.get("request_id"))
                    and _positive_int(row.get("request_company_id"))
                    == context["companyId"]
                    and _request_mentions_base_estimate(
                        row, context["baseEstimateId"],
                    )
                })
                if not request_ids:
                    projection = build_supply_warehouse_projection(
                        context, requests, [], [], [], [], [], [], [], [],
                    )
                    report["readyForSupplyWarehouseProjection"] = projection["complete"]
                    report["supplyWarehouseImpact"] = projection
                    return report
                known_fixed_fault = bool(
                    _fixed_request_faults(context, requests)
                )
                delivery_state, deliveries, _delivery_overflow_fields = (
                    _load_deliveries(
                        cur,
                        request_ids,
                        variable_budget,
                    )
                )
                stop, known_fixed_fault = (
                    _bounded_payload_requires_systemic_stop(
                        delivery_state,
                        deliveries,
                        known_fixed_fault,
                        row_id_field="delivery_id",
                        parent_id_field="request_id",
                        owner_field="delivery_company_id",
                        parent_ids=request_ids,
                        company_id=context["companyId"],
                    )
                )
                if stop:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                allocation_state, allocations, _allocation_overflow_fields = (
                    _load_allocations(
                        cur,
                        request_ids,
                        variable_budget,
                    )
                )
                stop, known_fixed_fault = (
                    _bounded_payload_requires_systemic_stop(
                        allocation_state,
                        allocations,
                        known_fixed_fault,
                        row_id_field="allocation_id",
                        parent_id_field="request_id",
                        owner_field="allocation_company_id",
                        parent_ids=request_ids,
                        company_id=context["companyId"],
                    )
                )
                if stop:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                supplier_invoices = _load_supplier_invoices(cur, request_ids)
                if len(supplier_invoices) > MAX_DOMAIN_ROWS:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                supplier_faults = _fixed_prefix_faults(
                    supplier_invoices,
                    row_id_field="supplier_invoice_id",
                    parent_id_field="request_id",
                    owner_field="invoice_company_id",
                    parent_ids=request_ids,
                    company_id=context["companyId"],
                )
                known_fixed_fault = (
                    known_fixed_fault or bool(supplier_faults)
                )
                invoice_state, warehouse_invoices, _invoice_overflow_fields = (
                    _load_warehouse_invoices(
                        cur,
                        request_ids,
                        variable_budget,
                    )
                )
                stop, known_fixed_fault = (
                    _bounded_payload_requires_systemic_stop(
                        invoice_state,
                        warehouse_invoices,
                        known_fixed_fault,
                        row_id_field="warehouse_invoice_id",
                        parent_id_field="supply_request_id",
                        owner_field="invoice_company_id",
                        parent_ids=request_ids,
                        company_id=context["companyId"],
                    )
                )
                if stop:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                invoice_ids = sorted({
                    invoice_id for invoice_id in (
                        _positive_int(row.get("warehouse_invoice_id"))
                        for row in warehouse_invoices
                    ) if invoice_id
                })
                history_state, history, _history_overflow_fields = (
                    _load_history(
                        cur,
                        invoice_ids,
                        variable_budget,
                    )
                )
                stop, known_fixed_fault = (
                    _bounded_payload_requires_systemic_stop(
                        history_state,
                        history,
                        known_fixed_fault,
                        row_id_field="history_id",
                        parent_id_field="source_invoice_id",
                        owner_field="history_company_id",
                        parent_ids=invoice_ids,
                        company_id=context["companyId"],
                    )
                )
                if stop:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                lots = _load_lots(cur, invoice_ids)
                if len(lots) > MAX_DOMAIN_ROWS:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                lot_faults = _fixed_prefix_faults(
                    lots,
                    row_id_field="lot_id",
                    parent_id_field="warehouse_invoice_id",
                    owner_field="lot_company_id",
                    parent_ids=invoice_ids,
                    company_id=context["companyId"],
                )
                known_fixed_fault = known_fixed_fault or bool(lot_faults)
                movement_state, movements, _movement_overflow_fields = (
                    _load_movements(
                        cur,
                        invoice_ids,
                        variable_budget,
                    )
                )
                stop, known_fixed_fault = (
                    _bounded_payload_requires_systemic_stop(
                        movement_state,
                        movements,
                        known_fixed_fault,
                        row_id_field="movement_id",
                        parent_id_field="source_invoice_id",
                        owner_field="movement_company_id",
                        parent_ids=invoice_ids,
                        company_id=context["companyId"],
                    )
                )
                if stop:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
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
                if len(lot_movements) > MAX_DOMAIN_ROWS:
                    projection = _empty_projection(
                        "incomplete", "supply_warehouse_scan_limit_exceeded",
                    )
                    report["readyForSupplyWarehouseProjection"] = False
                    report["supplyWarehouseImpact"] = projection
                    return report
                lot_movement_faults = _fixed_lot_movement_faults(
                    lot_movements,
                    lot_ids=lot_ids,
                    movement_ids=movement_ids,
                    company_id=context["companyId"],
                )
                known_fixed_fault = (
                    known_fixed_fault or bool(lot_movement_faults)
                )
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
