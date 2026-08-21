import inspect
import json
import os
import unittest
from unittest import mock

import psycopg2

import backend.features.estimate_revision_impact.supply_warehouse_audit as supply_audit
import backend.features.estimate_revision_impact.supply_warehouse_projection as supply_projection
from backend.features.estimate_revision_impact.contract import (
    MAX_CANONICAL_SOURCE_BYTES,
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.resource_limits import (
    MAX_COLLECTOR_VARIABLE_BYTES,
    MAX_JSON_QUERY_BYTES,
    MAX_NUMERIC_FIELD_BYTES,
    MAX_TEXT_FIELD_BYTES,
    MAX_TEXT_QUERY_AGGREGATE_BYTES,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    MAX_DOMAIN_ROWS,
    MAX_SOURCE_JSON_BYTES,
    SUPPLY_WAREHOUSE_REQUIRED_COLUMNS,
    collect_supply_warehouse_impact_audit,
    run_supply_warehouse_impact_audit,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row,
    reconciliation_row,
)
from backend.features.estimate_revision_impact.test_supply_warehouse_projection import (
    allocation_row,
    context,
    delivery_row,
    history_row,
    lot_movement_row,
    lot_row,
    movement_row,
    request_item,
    request_row,
    supplier_invoice_row,
    warehouse_invoice_row,
)


def source():
    return build_estimate_revision_source(
        company_id=4,
        project_id=17,
        estimate_id=52,
        version="v2.0",
        sections=[{"name": "Работы", "items": []}],
    )


SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in SUPPLY_WAREHOUSE_REQUIRED_COLUMNS.items()
    for column in columns
)


_CONTEXT_TEXT_FIELDS = ("project_name", "base_work_package")
_REQUEST_TEXT_FIELDS = (
    "request_project",
    "request_work_package",
    "request_status",
)
_REQUEST_VARIABLE_FIELDS = _REQUEST_TEXT_FIELDS + ("items_json",)
_DELIVERY_VARIABLE_FIELDS = (
    "delivery_project",
    "delivery_work_package",
    "material_name",
    "unit",
    "received_quantity",
)
_ALLOCATION_VARIABLE_FIELDS = ("allocation_quantity",)
_INVOICE_VARIABLE_FIELDS = ("invoice_project", "items")
_HISTORY_VARIABLE_FIELDS = ("history_work_package",)
_MOVEMENT_VARIABLE_FIELDS = ("movement_work_package",)

_DELIVERY_FIELD_SPECS = (
    ("delivery_project", "text", MAX_TEXT_FIELD_BYTES),
    ("delivery_work_package", "text", MAX_TEXT_FIELD_BYTES),
    ("material_name", "text", MAX_TEXT_FIELD_BYTES),
    ("unit", "text", MAX_TEXT_FIELD_BYTES),
    ("received_quantity", "text", MAX_NUMERIC_FIELD_BYTES),
)
_ALLOCATION_FIELD_SPECS = (
    ("allocation_quantity", "text", MAX_NUMERIC_FIELD_BYTES),
)
_INVOICE_FIELD_SPECS = (
    ("invoice_project", "text", MAX_TEXT_FIELD_BYTES),
    ("items", "json", MAX_SOURCE_JSON_BYTES),
)
_HISTORY_FIELD_SPECS = (
    ("history_work_package", "text", MAX_TEXT_FIELD_BYTES),
)
_MOVEMENT_FIELD_SPECS = (
    ("movement_work_package", "text", MAX_TEXT_FIELD_BYTES),
)


def _utf8_bytes(value):
    return len(value.encode("utf-8")) if isinstance(value, str) else 0


def _with_field_bytes(row, field_specs):
    result = dict(row)
    for field, _category, _cap in field_specs:
        result["field_" + field + "_bytes"] = _utf8_bytes(
            result.get(field)
        )
    return result


def _bounded_delivery_row(**overrides):
    row = delivery_row(**overrides)
    if row.get("delivery_work_package") in (None, ""):
        row["delivery_work_package"] = "Основная"
    if row.get("received_quantity") is not None:
        row["received_quantity"] = str(row["received_quantity"])
    return _with_field_bytes(row, _DELIVERY_FIELD_SPECS)


def _bounded_allocation_row(**overrides):
    row = allocation_row(**overrides)
    if row.get("allocation_quantity") is not None:
        row["allocation_quantity"] = str(row["allocation_quantity"])
    return _with_field_bytes(row, _ALLOCATION_FIELD_SPECS)


def _bounded_invoice_row(**overrides):
    return _with_field_bytes(
        warehouse_invoice_row(**overrides),
        _INVOICE_FIELD_SPECS,
    )


def _bounded_history_row(**overrides):
    row = history_row(**overrides)
    if row.get("history_work_package") in (None, ""):
        row["history_work_package"] = "Основная"
    return _with_field_bytes(row, _HISTORY_FIELD_SPECS)


def _bounded_movement_row(**overrides):
    row = movement_row(**overrides)
    if row.get("movement_work_package") in (None, ""):
        row["movement_work_package"] = "Основная"
    return _with_field_bytes(row, _MOVEMENT_FIELD_SPECS)


def _bounded_payload_rows(
    *rows,
    field_specs,
    scan_limit=MAX_DOMAIN_ROWS,
    remaining_bytes=MAX_COLLECTOR_VARIABLE_BYTES,
):
    result = [dict(row) for row in rows]
    json_bytes = sum(
        row["field_" + field + "_bytes"]
        for row in result
        for field, category, _cap in field_specs
        if category == "json"
    )
    text_bytes = sum(
        row["field_" + field + "_bytes"]
        for row in result
        for field, category, _cap in field_specs
        if category == "text"
    )
    cardinality_exceeded = len(result) > scan_limit
    bytes_exceeded = (
        any(
            row["field_" + field + "_bytes"] > cap
            for row in result
            for field, _category, cap in field_specs
        )
        or json_bytes > MAX_JSON_QUERY_BYTES
        or text_bytes > MAX_TEXT_QUERY_AGGREGATE_BYTES
        or json_bytes + text_bytes > remaining_bytes
    )
    payload_exceeded = not cardinality_exceeded and bytes_exceeded
    for row in result:
        row.update({
            "query_json_bytes": json_bytes,
            "query_text_bytes": text_bytes,
            "query_variable_bytes": json_bytes + text_bytes,
            "cardinality_limit_exceeded": cardinality_exceeded,
            "payload_limit_exceeded": payload_exceeded,
        })
        if cardinality_exceeded or payload_exceeded:
            for field, _category, _cap in field_specs:
                row[field] = None
    return tuple(result)


def _bounded_delivery_rows(*rows, **limits):
    return _bounded_payload_rows(
        *rows,
        field_specs=_DELIVERY_FIELD_SPECS,
        **limits,
    )


def _bounded_allocation_rows(*rows, **limits):
    return _bounded_payload_rows(
        *rows,
        field_specs=_ALLOCATION_FIELD_SPECS,
        **limits,
    )


def _bounded_invoice_rows(*rows, **limits):
    return _bounded_payload_rows(
        *rows,
        field_specs=_INVOICE_FIELD_SPECS,
        **limits,
    )


def _bounded_history_rows(*rows, **limits):
    return _bounded_payload_rows(
        *rows,
        field_specs=_HISTORY_FIELD_SPECS,
        **limits,
    )


def _bounded_movement_rows(*rows, **limits):
    return _bounded_payload_rows(
        *rows,
        field_specs=_MOVEMENT_FIELD_SPECS,
        **limits,
    )


def _bounded_context_row(**overrides):
    row = {
        "project_name": "Private project",
        "owner_count": 1,
        "base_work_package": "Основная",
        "base_sections_json": json.dumps(context()["baseSections"]),
    }
    row.update(overrides)
    if row.get("base_work_package") in (None, ""):
        row["base_work_package"] = "Основная"
    json_bytes = _utf8_bytes(row.get("base_sections_json"))
    text_sizes = {
        field: _utf8_bytes(row.get(field))
        for field in _CONTEXT_TEXT_FIELDS
    }
    text_bytes = sum(text_sizes.values())
    row.update({
        "base_sections_bytes": json_bytes,
        "field_base_sections_json_bytes": json_bytes,
        "query_json_bytes": json_bytes,
        "query_text_bytes": text_bytes,
        "query_variable_bytes": json_bytes + text_bytes,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    })
    row.update({
        "field_" + field + "_bytes": size
        for field, size in text_sizes.items()
    })
    return row


def _bounded_context_rows(*rows, scan_limit=1):
    result = [dict(row) for row in rows]
    text_byte_keys = tuple(
        "field_" + field + "_bytes"
        for field in _CONTEXT_TEXT_FIELDS
    )
    json_bytes = sum(
        row["field_base_sections_json_bytes"]
        for row in result
    )
    text_bytes = sum(
        row[key]
        for row in result
        for key in text_byte_keys
    )
    cardinality_exceeded = len(result) > scan_limit
    bytes_exceeded = (
        any(
            row["field_base_sections_json_bytes"]
            > MAX_CANONICAL_SOURCE_BYTES
            for row in result
        )
        or any(
            row[key] > MAX_TEXT_FIELD_BYTES
            for row in result
            for key in text_byte_keys
        )
        or json_bytes > MAX_JSON_QUERY_BYTES
        or text_bytes > MAX_TEXT_QUERY_AGGREGATE_BYTES
    )
    payload_exceeded = not cardinality_exceeded and bytes_exceeded
    for row in result:
        row.update({
            "query_json_bytes": json_bytes,
            "query_text_bytes": text_bytes,
            "query_variable_bytes": json_bytes + text_bytes,
            "cardinality_limit_exceeded": cardinality_exceeded,
            "payload_limit_exceeded": payload_exceeded,
        })
        if cardinality_exceeded or payload_exceeded:
            for field in _CONTEXT_TEXT_FIELDS + ("base_sections_json",):
                row[field] = None
    return tuple(result)


def _context_overflow(field):
    row = _bounded_context_row()
    for name in _CONTEXT_TEXT_FIELDS + ("base_sections_json",):
        row[name] = None
    size = (
        MAX_CANONICAL_SOURCE_BYTES + 1
        if field == "base_sections_json"
        else MAX_TEXT_FIELD_BYTES + 1
    )
    row["field_" + field + "_bytes"] = size
    row["base_sections_bytes"] = row["field_base_sections_json_bytes"]
    row["query_json_bytes"] = row["field_base_sections_json_bytes"]
    row["query_text_bytes"] = sum(
        row["field_" + name + "_bytes"]
        for name in _CONTEXT_TEXT_FIELDS
    )
    row["query_variable_bytes"] = (
        row["query_json_bytes"] + row["query_text_bytes"]
    )
    row["payload_limit_exceeded"] = True
    return row


def _bounded_request_row(**overrides):
    row = request_row(**overrides)
    if row.get("request_work_package") in (None, ""):
        row["request_work_package"] = "Основная"
    if row.get("request_status") is None:
        row["request_status"] = ""
    json_bytes = _utf8_bytes(row.get("items_json"))
    text_sizes = {
        field: _utf8_bytes(row.get(field))
        for field in _REQUEST_TEXT_FIELDS
    }
    text_bytes = sum(text_sizes.values())
    row.update({
        "field_items_json_bytes": json_bytes,
        "query_json_bytes": json_bytes,
        "query_text_bytes": text_bytes,
        "query_variable_bytes": json_bytes + text_bytes,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    })
    row.update({
        "field_" + field + "_bytes": size
        for field, size in text_sizes.items()
    })
    return row


def _request_overflow(field):
    row = _bounded_request_row()
    for name in _REQUEST_VARIABLE_FIELDS:
        row[name] = None
    size = (
        MAX_SOURCE_JSON_BYTES + 1
        if field == "items_json"
        else MAX_TEXT_FIELD_BYTES + 1
    )
    row["field_" + field + "_bytes"] = size
    row["query_json_bytes"] = row["field_items_json_bytes"]
    row["query_text_bytes"] = sum(
        row["field_" + name + "_bytes"]
        for name in _REQUEST_TEXT_FIELDS
    )
    row["query_variable_bytes"] = (
        row["query_json_bytes"] + row["query_text_bytes"]
    )
    row["payload_limit_exceeded"] = True
    return row


def _bounded_request_rows(*rows, scan_limit=MAX_DOMAIN_ROWS):
    result = [dict(row) for row in rows]
    text_byte_keys = tuple(
        "field_" + field + "_bytes"
        for field in _REQUEST_TEXT_FIELDS
    )
    json_bytes = sum(row["field_items_json_bytes"] for row in result)
    text_bytes = sum(
        row[key]
        for row in result
        for key in text_byte_keys
    )
    cardinality_exceeded = len(result) > scan_limit
    bytes_exceeded = (
        any(
            row["field_items_json_bytes"] > MAX_SOURCE_JSON_BYTES
            for row in result
        )
        or any(
            row[key] > MAX_TEXT_FIELD_BYTES
            for row in result
            for key in text_byte_keys
        )
        or json_bytes > MAX_JSON_QUERY_BYTES
        or text_bytes > MAX_TEXT_QUERY_AGGREGATE_BYTES
    )
    payload_exceeded = not cardinality_exceeded and bytes_exceeded
    for row in result:
        row.update({
            "query_json_bytes": json_bytes,
            "query_text_bytes": text_bytes,
            "query_variable_bytes": json_bytes + text_bytes,
            "cardinality_limit_exceeded": cardinality_exceeded,
            "payload_limit_exceeded": payload_exceeded,
        })
        if cardinality_exceeded or payload_exceeded:
            for field in _REQUEST_VARIABLE_FIELDS:
                row[field] = None
    return tuple(result)


def _items_json_with_utf8_size(size):
    prefix = '[{"estimateId":51,"padding":"'
    suffix = '"}]'
    padding = size - len((prefix + suffix).encode("utf-8"))
    if padding < 0:
        raise AssertionError("requested JSON fixture size is too small")
    value = prefix + ("a" * padding) + suffix
    if len(value.encode("utf-8")) != size:
        raise AssertionError("JSON fixture byte size mismatch")
    return value


def _assert_query_wide_gate(test, sql, aliases):
    normalized = " ".join(sql.upper().split())
    alias_local = normalized.replace("( ", "(").replace(" )", ")")
    test.assertTrue(normalized.startswith("SELECT "))
    test.assertIn("WITH LIMITED AS MATERIALIZED", normalized)
    test.assertIn("SIZED AS MATERIALIZED", normalized)
    test.assertIn("GATED AS MATERIALIZED", normalized)
    test.assertIn("OCTET_LENGTH(CONVERT_TO(", normalized)
    test.assertIn("'UTF8'", normalized)
    test.assertIn("MAX(", normalized)
    test.assertIn("BYTES_ALLOWED", normalized)
    test.assertIn("PAYLOAD_ALLOWED", normalized)
    test.assertIn("QUERY_JSON_BYTES", normalized)
    test.assertIn("QUERY_TEXT_BYTES", normalized)
    test.assertIn("QUERY_VARIABLE_BYTES", normalized)
    test.assertIn("COUNT(*) OVER ()", normalized)
    test.assertEqual(
        normalized.count(
            "(GATED.ROW_COUNT <= %S AND GATED.BYTES_ALLOWED) "
            "AS PAYLOAD_ALLOWED"
        ),
        1,
    )
    test.assertEqual(
        normalized.count(
            "(DECIDED.ROW_COUNT > %S) AS CARDINALITY_LIMIT_EXCEEDED"
        ),
        1,
    )
    test.assertEqual(
        normalized.count(
            "(DECIDED.ROW_COUNT <= %S AND NOT DECIDED.BYTES_ALLOWED) "
            "AS PAYLOAD_LIMIT_EXCEEDED"
        ),
        1,
    )
    limited_start = normalized.index("WITH LIMITED AS MATERIALIZED")
    sized_start = normalized.index("), SIZED AS MATERIALIZED", limited_start)
    limited_sql = normalized[limited_start:sized_start]
    test.assertIn("ORDER BY", limited_sql)
    test.assertIn("LIMIT %S", limited_sql)
    test.assertLess(
        normalized.rfind("LIMIT %S", limited_start, sized_start),
        normalized.index("COUNT(*) OVER ()"),
    )
    for alias in aliases:
        field_bytes = "FIELD_" + alias.upper() + "_BYTES"
        exact_sizing = (
            "COALESCE(OCTET_LENGTH(CONVERT_TO(EMITTED_"
            + alias.upper()
            + ",'UTF8')),0)::BIGINT AS "
            + field_bytes
        )
        exact_max = (
            "MAX("
            + field_bytes
            + ") OVER () AS MAX_"
            + field_bytes
        )
        exact_cap = "MAX_" + field_bytes + " <= %S"
        test.assertEqual(alias_local.count(exact_sizing), 1)
        test.assertEqual(alias_local.count(exact_max), 1)
        test.assertEqual(alias_local.count(exact_cap), 1)
        exact_gate = (
            "CASE WHEN DECIDED.PAYLOAD_ALLOWED THEN DECIDED.EMITTED_"
            + alias.upper()
            + " ELSE NULL END AS "
            + alias.upper()
        )
        test.assertEqual(normalized.count(exact_gate), 1)
        test.assertEqual(
            normalized.count("EMITTED_" + alias.upper()),
            3,
        )


def _assert_downstream_sql_contract(
    test,
    kind,
    sql,
    params,
    ids,
    remaining_bytes,
):
    normalized = " ".join(sql.upper().split())
    alias_local = normalized.replace("( ", "(").replace(" )", ")")
    contracts = {
        "deliveries": {
            "fields": _DELIVERY_VARIABLE_FIELDS,
            "table": "PUBLIC.SUPPLY_DELIVERIES",
            "top_fields": (
                "DELIVERY_ID", "REQUEST_ID", "DELIVERY_COMPANY_ID",
                "DELIVERY_PROJECT", "DELIVERY_WORK_PACKAGE",
                "MATERIAL_NAME", "UNIT", "RECEIVED_QUANTITY",
                "FIELD_DELIVERY_PROJECT_BYTES",
                "FIELD_DELIVERY_WORK_PACKAGE_BYTES",
                "FIELD_MATERIAL_NAME_BYTES", "FIELD_UNIT_BYTES",
                "FIELD_RECEIVED_QUANTITY_BYTES", "QUERY_JSON_BYTES",
                "QUERY_TEXT_BYTES", "QUERY_VARIABLE_BYTES",
                "CARDINALITY_LIMIT_EXCEEDED", "PAYLOAD_LIMIT_EXCEEDED",
            ),
            "limited": (
                "SELECT ID AS DELIVERY_ID,REQUEST_ID, COMPANY_ID AS "
                "DELIVERY_COMPANY_ID, PROJECT AS EMITTED_DELIVERY_PROJECT, "
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') AS "
                "EMITTED_DELIVERY_WORK_PACKAGE, MATERIAL_NAME AS "
                "EMITTED_MATERIAL_NAME, UNIT AS EMITTED_UNIT, "
                "RECEIVED_QUANTITY::TEXT AS EMITTED_RECEIVED_QUANTITY "
                "FROM PUBLIC.SUPPLY_DELIVERIES WHERE REQUEST_ID=ANY(%S) "
                "ORDER BY REQUEST_ID,ID LIMIT %S"
            ),
            "source": (
                "FROM PUBLIC.SUPPLY_DELIVERIES "
                "WHERE REQUEST_ID=ANY(%S) ORDER BY REQUEST_ID,ID LIMIT %S"
            ),
            "emitted": (
                "PROJECT AS EMITTED_DELIVERY_PROJECT",
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') "
                "AS EMITTED_DELIVERY_WORK_PACKAGE",
                "MATERIAL_NAME AS EMITTED_MATERIAL_NAME",
                "UNIT AS EMITTED_UNIT",
                "RECEIVED_QUANTITY::TEXT AS EMITTED_RECEIVED_QUANTITY",
            ),
            "json_sum": "0::BIGINT AS QUERY_JSON_BYTES",
            "text_sum": (
                "COALESCE(SUM(FIELD_DELIVERY_PROJECT_BYTES::BIGINT + "
                "FIELD_DELIVERY_WORK_PACKAGE_BYTES::BIGINT + "
                "FIELD_MATERIAL_NAME_BYTES::BIGINT + "
                "FIELD_UNIT_BYTES::BIGINT + "
                "FIELD_RECEIVED_QUANTITY_BYTES::BIGINT) OVER (),0)::BIGINT "
                "AS QUERY_TEXT_BYTES"
            ),
            "variable_total": (
                "QUERY_TEXT_BYTES::BIGINT AS QUERY_VARIABLE_BYTES"
            ),
            "cap_order": (
                "MAX_FIELD_DELIVERY_PROJECT_BYTES <= %S AND "
                "MAX_FIELD_DELIVERY_WORK_PACKAGE_BYTES <= %S AND "
                "MAX_FIELD_MATERIAL_NAME_BYTES <= %S AND "
                "MAX_FIELD_UNIT_BYTES <= %S AND "
                "MAX_FIELD_RECEIVED_QUANTITY_BYTES <= %S"
            ),
            "remaining": "QUERY_TEXT_BYTES <= %S",
            "remaining_count": 2,
            "bytes_allowed": (
                "MAX_FIELD_DELIVERY_PROJECT_BYTES <= %S AND "
                "MAX_FIELD_DELIVERY_WORK_PACKAGE_BYTES <= %S AND "
                "MAX_FIELD_MATERIAL_NAME_BYTES <= %S AND "
                "MAX_FIELD_UNIT_BYTES <= %S AND "
                "MAX_FIELD_RECEIVED_QUANTITY_BYTES <= %S AND "
                "QUERY_TEXT_BYTES <= %S AND QUERY_TEXT_BYTES <= %S"
            ),
            "params": (
                ids,
                MAX_DOMAIN_ROWS + 1,
                MAX_TEXT_FIELD_BYTES,
                MAX_TEXT_FIELD_BYTES,
                MAX_TEXT_FIELD_BYTES,
                MAX_TEXT_FIELD_BYTES,
                MAX_NUMERIC_FIELD_BYTES,
                MAX_TEXT_QUERY_AGGREGATE_BYTES,
                remaining_bytes,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
            ),
        },
        "allocations": {
            "fields": _ALLOCATION_VARIABLE_FIELDS,
            "table": "PUBLIC.ESTIMATE_ROW_SUPPLY_ALLOCATIONS",
            "top_fields": (
                "ALLOCATION_ID", "REQUEST_ID", "REQUEST_ITEM_INDEX",
                "ALLOCATION_COMPANY_ID", "SOURCE_ESTIMATE_ID",
                "SOURCE_SECTION_INDEX", "SOURCE_ITEM_INDEX",
                "ALLOCATION_QUANTITY",
                "FIELD_ALLOCATION_QUANTITY_BYTES", "QUERY_JSON_BYTES",
                "QUERY_TEXT_BYTES", "QUERY_VARIABLE_BYTES",
                "CARDINALITY_LIMIT_EXCEEDED", "PAYLOAD_LIMIT_EXCEEDED",
            ),
            "limited": (
                "SELECT ID AS ALLOCATION_ID,REQUEST_ID,REQUEST_ITEM_INDEX, "
                "COMPANY_ID AS ALLOCATION_COMPANY_ID, SOURCE_ESTIMATE_ID,"
                "SOURCE_SECTION_INDEX, SOURCE_ITEM_INDEX,"
                "ALLOCATION_QUANTITY::TEXT AS EMITTED_ALLOCATION_QUANTITY "
                "FROM PUBLIC.ESTIMATE_ROW_SUPPLY_ALLOCATIONS WHERE "
                "REQUEST_ID=ANY(%S) ORDER BY REQUEST_ID,REQUEST_ITEM_INDEX,"
                "ID LIMIT %S"
            ),
            "source": (
                "FROM PUBLIC.ESTIMATE_ROW_SUPPLY_ALLOCATIONS "
                "WHERE REQUEST_ID=ANY(%S) "
                "ORDER BY REQUEST_ID,REQUEST_ITEM_INDEX,ID LIMIT %S"
            ),
            "emitted": (
                "ALLOCATION_QUANTITY::TEXT "
                "AS EMITTED_ALLOCATION_QUANTITY",
            ),
            "json_sum": "0::BIGINT AS QUERY_JSON_BYTES",
            "text_sum": (
                "COALESCE(SUM(FIELD_ALLOCATION_QUANTITY_BYTES::BIGINT) "
                "OVER (),0)::BIGINT AS QUERY_TEXT_BYTES"
            ),
            "variable_total": (
                "QUERY_TEXT_BYTES::BIGINT AS QUERY_VARIABLE_BYTES"
            ),
            "cap_order": "MAX_FIELD_ALLOCATION_QUANTITY_BYTES <= %S",
            "remaining": "QUERY_TEXT_BYTES <= %S",
            "remaining_count": 2,
            "bytes_allowed": (
                "MAX_FIELD_ALLOCATION_QUANTITY_BYTES <= %S AND "
                "QUERY_TEXT_BYTES <= %S AND QUERY_TEXT_BYTES <= %S"
            ),
            "params": (
                ids,
                MAX_DOMAIN_ROWS + 1,
                MAX_NUMERIC_FIELD_BYTES,
                MAX_TEXT_QUERY_AGGREGATE_BYTES,
                remaining_bytes,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
            ),
        },
        "warehouse-invoices": {
            "fields": _INVOICE_VARIABLE_FIELDS,
            "table": "PUBLIC.WAREHOUSE_INVOICES",
            "top_fields": (
                "WAREHOUSE_INVOICE_ID", "INVOICE_COMPANY_ID",
                "SUPPLY_REQUEST_ID", "SUPPLY_DELIVERY_ID",
                "SUPPLIER_INVOICE_ID", "INVOICE_PROJECT", "ITEMS",
                "FIELD_INVOICE_PROJECT_BYTES", "FIELD_ITEMS_BYTES",
                "QUERY_JSON_BYTES", "QUERY_TEXT_BYTES",
                "QUERY_VARIABLE_BYTES", "CARDINALITY_LIMIT_EXCEEDED",
                "PAYLOAD_LIMIT_EXCEEDED",
            ),
            "limited": (
                "SELECT ID AS WAREHOUSE_INVOICE_ID, COMPANY_ID AS "
                "INVOICE_COMPANY_ID,SUPPLY_REQUEST_ID, SUPPLY_DELIVERY_ID,"
                "SUPPLIER_INVOICE_ID, PROJECT AS EMITTED_INVOICE_PROJECT, "
                "ITEMS AS EMITTED_ITEMS FROM PUBLIC.WAREHOUSE_INVOICES "
                "WHERE SUPPLY_REQUEST_ID=ANY(%S) ORDER BY "
                "SUPPLY_REQUEST_ID,ID LIMIT %S"
            ),
            "source": (
                "FROM PUBLIC.WAREHOUSE_INVOICES "
                "WHERE SUPPLY_REQUEST_ID=ANY(%S) "
                "ORDER BY SUPPLY_REQUEST_ID,ID LIMIT %S"
            ),
            "emitted": (
                "PROJECT AS EMITTED_INVOICE_PROJECT",
                "ITEMS AS EMITTED_ITEMS",
            ),
            "json_sum": (
                "COALESCE(SUM(FIELD_ITEMS_BYTES::BIGINT) OVER (),0)::BIGINT "
                "AS QUERY_JSON_BYTES"
            ),
            "text_sum": (
                "COALESCE(SUM(FIELD_INVOICE_PROJECT_BYTES::BIGINT) "
                "OVER (),0)::BIGINT AS QUERY_TEXT_BYTES"
            ),
            "variable_total": (
                "(QUERY_JSON_BYTES + QUERY_TEXT_BYTES)::BIGINT "
                "AS QUERY_VARIABLE_BYTES"
            ),
            "cap_order": (
                "MAX_FIELD_INVOICE_PROJECT_BYTES <= %S AND "
                "MAX_FIELD_ITEMS_BYTES <= %S"
            ),
            "remaining": "QUERY_JSON_BYTES + QUERY_TEXT_BYTES <= %S",
            "remaining_count": 1,
            "bytes_allowed": (
                "MAX_FIELD_INVOICE_PROJECT_BYTES <= %S AND "
                "MAX_FIELD_ITEMS_BYTES <= %S AND "
                "QUERY_JSON_BYTES <= %S AND QUERY_TEXT_BYTES <= %S AND "
                "QUERY_JSON_BYTES + QUERY_TEXT_BYTES <= %S"
            ),
            "params": (
                ids,
                MAX_DOMAIN_ROWS + 1,
                MAX_TEXT_FIELD_BYTES,
                MAX_SOURCE_JSON_BYTES,
                MAX_JSON_QUERY_BYTES,
                MAX_TEXT_QUERY_AGGREGATE_BYTES,
                remaining_bytes,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
            ),
        },
        "history": {
            "fields": _HISTORY_VARIABLE_FIELDS,
            "table": "PUBLIC.WAREHOUSE_HISTORY",
            "top_fields": (
                "HISTORY_ID", "HISTORY_COMPANY_ID",
                "HISTORY_WORK_PACKAGE", "SOURCE_INVOICE_ID",
                "SOURCE_INVOICE_LINE_INDEX",
                "FIELD_HISTORY_WORK_PACKAGE_BYTES", "QUERY_JSON_BYTES",
                "QUERY_TEXT_BYTES", "QUERY_VARIABLE_BYTES",
                "CARDINALITY_LIMIT_EXCEEDED", "PAYLOAD_LIMIT_EXCEEDED",
            ),
            "limited": (
                "SELECT ID AS HISTORY_ID,COMPANY_ID AS HISTORY_COMPANY_ID, "
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') AS "
                "EMITTED_HISTORY_WORK_PACKAGE, SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX FROM PUBLIC.WAREHOUSE_HISTORY "
                "WHERE SOURCE_INVOICE_ID=ANY(%S) ORDER BY SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX,ID LIMIT %S"
            ),
            "source": (
                "FROM PUBLIC.WAREHOUSE_HISTORY "
                "WHERE SOURCE_INVOICE_ID=ANY(%S) ORDER BY SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX,ID LIMIT %S"
            ),
            "emitted": (
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') "
                "AS EMITTED_HISTORY_WORK_PACKAGE",
            ),
            "json_sum": "0::BIGINT AS QUERY_JSON_BYTES",
            "text_sum": (
                "COALESCE(SUM(FIELD_HISTORY_WORK_PACKAGE_BYTES::BIGINT) "
                "OVER (),0)::BIGINT AS QUERY_TEXT_BYTES"
            ),
            "variable_total": (
                "QUERY_TEXT_BYTES::BIGINT AS QUERY_VARIABLE_BYTES"
            ),
            "cap_order": "MAX_FIELD_HISTORY_WORK_PACKAGE_BYTES <= %S",
            "remaining": "QUERY_TEXT_BYTES <= %S",
            "remaining_count": 2,
            "bytes_allowed": (
                "MAX_FIELD_HISTORY_WORK_PACKAGE_BYTES <= %S AND "
                "QUERY_TEXT_BYTES <= %S AND QUERY_TEXT_BYTES <= %S"
            ),
            "params": (
                ids,
                MAX_DOMAIN_ROWS + 1,
                MAX_TEXT_FIELD_BYTES,
                MAX_TEXT_QUERY_AGGREGATE_BYTES,
                remaining_bytes,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
            ),
        },
        "movements": {
            "fields": _MOVEMENT_VARIABLE_FIELDS,
            "table": "PUBLIC.WAREHOUSE_MOVEMENTS",
            "top_fields": (
                "MOVEMENT_ID", "MOVEMENT_COMPANY_ID",
                "MOVEMENT_WORK_PACKAGE", "SOURCE_INVOICE_ID",
                "SOURCE_INVOICE_LINE_INDEX",
                "FIELD_MOVEMENT_WORK_PACKAGE_BYTES", "QUERY_JSON_BYTES",
                "QUERY_TEXT_BYTES", "QUERY_VARIABLE_BYTES",
                "CARDINALITY_LIMIT_EXCEEDED", "PAYLOAD_LIMIT_EXCEEDED",
            ),
            "limited": (
                "SELECT ID AS MOVEMENT_ID, COMPANY_ID AS "
                "MOVEMENT_COMPANY_ID, "
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') AS "
                "EMITTED_MOVEMENT_WORK_PACKAGE, SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX FROM PUBLIC.WAREHOUSE_MOVEMENTS "
                "WHERE SOURCE_INVOICE_ID=ANY(%S) ORDER BY SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX,ID LIMIT %S"
            ),
            "source": (
                "FROM PUBLIC.WAREHOUSE_MOVEMENTS "
                "WHERE SOURCE_INVOICE_ID=ANY(%S) ORDER BY SOURCE_INVOICE_ID,"
                "SOURCE_INVOICE_LINE_INDEX,ID LIMIT %S"
            ),
            "emitted": (
                "COALESCE(NULLIF(WORK_PACKAGE,''),'ОСНОВНАЯ') "
                "AS EMITTED_MOVEMENT_WORK_PACKAGE",
            ),
            "json_sum": "0::BIGINT AS QUERY_JSON_BYTES",
            "text_sum": (
                "COALESCE(SUM(FIELD_MOVEMENT_WORK_PACKAGE_BYTES::BIGINT) "
                "OVER (),0)::BIGINT AS QUERY_TEXT_BYTES"
            ),
            "variable_total": (
                "QUERY_TEXT_BYTES::BIGINT AS QUERY_VARIABLE_BYTES"
            ),
            "cap_order": "MAX_FIELD_MOVEMENT_WORK_PACKAGE_BYTES <= %S",
            "remaining": "QUERY_TEXT_BYTES <= %S",
            "remaining_count": 2,
            "bytes_allowed": (
                "MAX_FIELD_MOVEMENT_WORK_PACKAGE_BYTES <= %S AND "
                "QUERY_TEXT_BYTES <= %S AND QUERY_TEXT_BYTES <= %S"
            ),
            "params": (
                ids,
                MAX_DOMAIN_ROWS + 1,
                MAX_TEXT_FIELD_BYTES,
                MAX_TEXT_QUERY_AGGREGATE_BYTES,
                remaining_bytes,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
                MAX_DOMAIN_ROWS,
            ),
        },
    }
    contract = contracts[kind]
    _assert_query_wide_gate(test, sql, contract["fields"])
    top_end = normalized.index(" FROM ( WITH LIMITED")
    top_fields = tuple(
        item.strip()
        for item in normalized[len("SELECT "):top_end].split(",")
    )
    test.assertEqual(
        top_fields,
        tuple("BOUNDED." + field for field in contract["top_fields"]),
    )
    limited_marker = "WITH LIMITED AS MATERIALIZED ("
    limited_start = normalized.index(limited_marker) + len(limited_marker)
    limited_end = normalized.index(
        "), SIZED AS MATERIALIZED",
        limited_start,
    )
    test.assertEqual(
        normalized[limited_start:limited_end].strip(),
        contract["limited"],
    )
    test.assertEqual(params, contract["params"])
    test.assertEqual(normalized.count(contract["table"]), 1)
    test.assertEqual(normalized.count(contract["source"]), 1)
    for emitted in contract["emitted"]:
        test.assertEqual(normalized.count(emitted), 1)
    test.assertEqual(alias_local.count(contract["json_sum"]), 1)
    test.assertEqual(alias_local.count(contract["text_sum"]), 1)
    test.assertEqual(alias_local.count(contract["variable_total"]), 1)
    test.assertEqual(normalized.count(contract["cap_order"]), 1)
    test.assertEqual(normalized.count(contract["bytes_allowed"]), 1)
    test.assertEqual(
        normalized.count(contract["remaining"]),
        contract["remaining_count"],
    )


def _assert_downstream_loader_signatures(test):
    expected = (
        (supply_audit._load_deliveries, "(cur, request_ids, variable_budget)"),
        (supply_audit._load_allocations, "(cur, request_ids, variable_budget)"),
        (
            supply_audit._load_warehouse_invoices,
            "(cur, request_ids, variable_budget)",
        ),
        (supply_audit._load_history, "(cur, invoice_ids, variable_budget)"),
        (supply_audit._load_movements, "(cur, invoice_ids, variable_budget)"),
    )
    for loader, signature in expected:
        test.assertEqual(str(inspect.signature(loader)), signature)


def _assert_a92_raw_projection_accepts(test, projection):
    from backend.features.warehouse_recommendation_preview.content_contract import (
        _validate_raw_supply_warehouse_projection,
    )

    test.assertIs(
        _validate_raw_supply_warehouse_projection(
            projection,
            base_estimate_id=51,
            allow_not_collected=False,
        ),
        projection,
    )


class SupplyWarehouseProjectionCollectorTests(unittest.TestCase):
    def result_sets(self):
        return (
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
            (_bounded_context_row(),),
            _bounded_request_rows(_bounded_request_row()),
            _bounded_delivery_rows(_bounded_delivery_row()),
            _bounded_allocation_rows(_bounded_allocation_row()),
            (supplier_invoice_row(),),
            _bounded_invoice_rows(_bounded_invoice_row()),
            _bounded_history_rows(_bounded_history_row()),
            (lot_row(),),
            _bounded_movement_rows(_bounded_movement_row()),
            (lot_movement_row(),),
        )

    def test_public_surface_threads_one_budget_without_adding_selects(self):
        cursor = FakeCursor(self.result_sets())

        report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertEqual(
            str(inspect.signature(collect_supply_warehouse_impact_audit)),
            "(cur, source)",
        )
        self.assertEqual(supply_audit.__all__, [
            "MAX_DOMAIN_ROWS",
            "SUPPLY_WAREHOUSE_REQUIRED_COLUMNS",
            "collect_supply_warehouse_impact_audit",
            "run_supply_warehouse_impact_audit",
        ])
        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(len(cursor.calls), 14)
        target = estimate_row()
        reconciliation = reconciliation_row()
        stored_context = _bounded_context_row()
        before_context = (
            MAX_COLLECTOR_VARIABLE_BYTES
            - target["query_variable_bytes"]
            - reconciliation["query_variable_bytes"]
        )
        before_requests = (
            before_context - stored_context["query_variable_bytes"]
        )
        self.assertIn(before_context, cursor.calls[4][1])
        self.assertIn(before_requests, cursor.calls[5][1])
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "field_project_name_bytes",
            "field_items_json_bytes",
            "field_delivery_project_bytes",
            "field_received_quantity_bytes",
            "field_allocation_quantity_bytes",
            "field_invoice_project_bytes",
            "field_items_bytes",
            "field_history_work_package_bytes",
            "field_movement_work_package_bytes",
            "query_json_bytes",
            "query_text_bytes",
            "query_variable_bytes",
            "payload_limit_exceeded",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_private_baseline_context_and_requests_share_one_budget_identity(self):
        cursor = FakeCursor(self.result_sets())
        observed = []
        real_baseline = supply_audit._collect_baseline_audit
        real_context = supply_audit._load_context
        real_requests = supply_audit._load_requests

        def collect_baseline(actual_cursor, actual_source, budget):
            observed.append(budget)
            return real_baseline(actual_cursor, actual_source, budget)

        def load_context(actual_cursor, actual_source, budget):
            observed.append(budget)
            return real_context(actual_cursor, actual_source, budget)

        def load_requests(actual_cursor, actual_context, budget):
            observed.append(budget)
            return real_requests(actual_cursor, actual_context, budget)

        with mock.patch.object(
            supply_audit,
            "_collect_baseline_audit",
            side_effect=collect_baseline,
        ), mock.patch.object(
            supply_audit,
            "_load_context",
            side_effect=load_context,
        ), mock.patch.object(
            supply_audit,
            "_load_requests",
            side_effect=load_requests,
        ):
            report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(len(observed), 3)
        self.assertIs(observed[0], observed[1])
        self.assertIs(observed[1], observed[2])

    def test_context_and_request_sql_use_ordered_query_wide_utf8_gates(self):
        cursor = FakeCursor(self.result_sets())

        report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        context_sql, context_params = cursor.calls[4]
        request_sql, request_params = cursor.calls[5]
        _assert_query_wide_gate(
            self,
            context_sql,
            _CONTEXT_TEXT_FIELDS + ("base_sections_json",),
        )
        _assert_query_wide_gate(
            self,
            request_sql,
            _REQUEST_VARIABLE_FIELDS,
        )
        self.assertEqual(context_sql.upper().count("PUBLIC.ESTIMATES"), 1)
        self.assertEqual(request_sql.upper().count("PUBLIC.SUPPLY_REQUESTS"), 1)
        before_context = (
            MAX_COLLECTOR_VARIABLE_BYTES
            - estimate_row()["query_variable_bytes"]
            - reconciliation_row()["query_variable_bytes"]
        )
        before_requests = (
            before_context - _bounded_context_row()["query_variable_bytes"]
        )
        self.assertEqual(context_params, (
            51,
            17,
            4,
            2,
            MAX_CANONICAL_SOURCE_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            before_context,
            1,
            1,
            1,
        ))
        self.assertEqual(request_params, (
            4,
            "Private project",
            "Основная",
            '"estimateId"[[:space:]]*:[[:space:]]*51([^0-9]|$)',
            MAX_DOMAIN_ROWS + 1,
            MAX_SOURCE_JSON_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_TEXT_FIELD_BYTES,
            MAX_JSON_QUERY_BYTES,
            MAX_TEXT_QUERY_AGGREGATE_BYTES,
            before_requests,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
            MAX_DOMAIN_ROWS,
        ))
        self.assertIn(
            "COALESCE(NULLIF(B.WORK_PACKAGE,''),'Основная')".upper(),
            context_sql.upper(),
        )
        self.assertIn(
            "COALESCE(NULLIF(WORK_PACKAGE,''),'Основная')".upper(),
            request_sql.upper(),
        )
        self.assertIn("COALESCE(STATUS,'')", request_sql.upper())

    def test_sql_gate_assertion_rejects_alias_local_drift(self):
        cursor = FakeCursor(self.result_sets())
        collect_supply_warehouse_impact_audit(cursor, source())
        request_sql = cursor.calls[5][0]
        mutations = (
            request_sql.replace(
                "emitted_request_status,'UTF8'",
                "emitted_request_project,'UTF8'",
                1,
            ),
            request_sql.replace(
                "max_field_request_status_bytes <= %s",
                "max_field_request_project_bytes <= %s",
                1,
            ),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated != request_sql):
                self.assertNotEqual(mutated, request_sql)
                with self.assertRaises(AssertionError):
                    _assert_query_wide_gate(
                        self,
                        mutated,
                        _REQUEST_VARIABLE_FIELDS,
                    )

    def test_context_overflow_maps_systemic_blocker_before_request_scan(self):
        overflow = _context_overflow("project_name")
        expected_text_bytes = sum(
            overflow["field_" + field + "_bytes"]
            for field in _CONTEXT_TEXT_FIELDS
        )
        self.assertEqual(overflow["query_text_bytes"], expected_text_bytes)
        self.assertTrue(overflow["payload_limit_exceeded"])
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
            (overflow,),
        ))

        report = collect_supply_warehouse_impact_audit(cursor, source())

        projection = report["supplyWarehouseImpact"]
        self.assertEqual(projection["state"], "incomplete")
        self.assertEqual(projection["reasonCounts"], {
            "supply_warehouse_scan_limit_exceeded": 1,
        })
        self.assertEqual(len(cursor.calls), 5)

    def test_context_field_boundaries_fallbacks_and_cardinality_are_exact(self):
        source_context = {
            "companyId": 4,
            "projectId": 17,
            "baseEstimateId": 51,
        }
        exact_text = "\u044f" * (MAX_TEXT_FIELD_BYTES // 2)
        exact_values = {
            "project_name": exact_text,
            "base_work_package": exact_text,
            "base_sections_json": _items_json_with_utf8_size(
                MAX_CANONICAL_SOURCE_BYTES
            ),
        }
        for field, value in exact_values.items():
            with self.subTest(boundary="inclusive", field=field):
                row = _bounded_context_row(**{field: value})
                cap = (
                    MAX_CANONICAL_SOURCE_BYTES
                    if field == "base_sections_json"
                    else MAX_TEXT_FIELD_BYTES
                )
                self.assertEqual(row["field_" + field + "_bytes"], cap)
                budget = supply_audit._VariableByteBudget()

                state, clean, overflow_fields = supply_audit._load_context(
                    FakeCursor(((row,),)),
                    source_context,
                    budget,
                )

                self.assertEqual(state, "accepted")
                self.assertEqual(overflow_fields, ())
                self.assertEqual(clean[0][field], value)
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - row["query_variable_bytes"],
                )

        for field in _CONTEXT_TEXT_FIELDS + ("base_sections_json",):
            with self.subTest(boundary="limit+1", field=field):
                row = _context_overflow(field)
                budget = supply_audit._VariableByteBudget()

                state, clean, overflow_fields = supply_audit._load_context(
                    FakeCursor(((row,),)),
                    source_context,
                    budget,
                )

                self.assertEqual(state, "overflow")
                self.assertIn(field, overflow_fields)
                self.assertTrue(all(
                    clean[0][name] is None
                    for name in _CONTEXT_TEXT_FIELDS
                    + ("base_sections_json",)
                ))
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )

        fallback = _bounded_context_row(
            project_name=None,
            base_work_package=None,
            base_sections_json=None,
        )
        self.assertEqual(fallback["base_work_package"], "Основная")
        self.assertEqual(
            fallback["field_base_work_package_bytes"],
            len("Основная".encode("utf-8")),
        )
        self.assertEqual(fallback["field_project_name_bytes"], 0)
        self.assertEqual(fallback["field_base_sections_json_bytes"], 0)
        fallback_budget = supply_audit._VariableByteBudget()
        state, clean, overflow_fields = supply_audit._load_context(
            FakeCursor(((fallback,),)),
            source_context,
            fallback_budget,
        )
        self.assertEqual(state, "accepted")
        self.assertEqual(overflow_fields, ())
        self.assertIsNone(clean[0]["project_name"])
        self.assertEqual(clean[0]["base_work_package"], "Основная")
        self.assertIsNone(clean[0]["base_sections_json"])

        duplicates = _bounded_context_rows(
            _bounded_context_row(),
            _bounded_context_row(project_name="Other project"),
        )
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
            duplicates,
        ))
        report = collect_supply_warehouse_impact_audit(cursor, source())
        self.assertEqual(report["supplyWarehouseImpact"]["reasonCounts"], {
            "supply_warehouse_project_identity_invalid": 1,
        })
        self.assertEqual(len(cursor.calls), 5)

    def test_request_field_boundaries_and_emitted_fallbacks_are_exact(self):
        exact_text = "\u044f" * (MAX_TEXT_FIELD_BYTES // 2)
        exact_values = {
            "request_project": exact_text,
            "request_work_package": exact_text,
            "request_status": exact_text,
            "items_json": _items_json_with_utf8_size(MAX_SOURCE_JSON_BYTES),
        }
        request_context = context()
        for field, value in exact_values.items():
            with self.subTest(boundary="inclusive", field=field):
                row = _bounded_request_row(**{field: value})
                cap = (
                    MAX_SOURCE_JSON_BYTES
                    if field == "items_json"
                    else MAX_TEXT_FIELD_BYTES
                )
                self.assertEqual(row["field_" + field + "_bytes"], cap)
                budget = supply_audit._VariableByteBudget()

                state, clean, overflow_fields = supply_audit._load_requests(
                    FakeCursor(((row,),)),
                    request_context,
                    budget,
                )

                self.assertEqual(state, "accepted")
                self.assertEqual(overflow_fields, ())
                self.assertEqual(clean[0][field], value)
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - row["query_variable_bytes"],
                )

        for field in _REQUEST_VARIABLE_FIELDS:
            with self.subTest(boundary="limit+1", field=field):
                row = _request_overflow(field)
                budget = supply_audit._VariableByteBudget()

                state, clean, overflow_fields = supply_audit._load_requests(
                    FakeCursor(((row,),)),
                    request_context,
                    budget,
                )

                self.assertEqual(state, "overflow")
                self.assertIn(field, overflow_fields)
                self.assertTrue(all(
                    clean[0][name] is None
                    for name in _REQUEST_VARIABLE_FIELDS
                ))
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )

        fallback = _bounded_request_row(
            request_work_package=None,
            request_status=None,
        )
        self.assertEqual(fallback["request_work_package"], "Основная")
        self.assertEqual(fallback["request_status"], "")
        self.assertEqual(
            fallback["field_request_work_package_bytes"],
            len("Основная".encode("utf-8")),
        )
        self.assertEqual(fallback["field_request_status_bytes"], 0)
        fallback_budget = supply_audit._VariableByteBudget()
        state, clean, overflow_fields = supply_audit._load_requests(
            FakeCursor(((fallback,),)),
            request_context,
            fallback_budget,
        )
        self.assertEqual(state, "accepted")
        self.assertEqual(overflow_fields, ())
        self.assertEqual(clean[0]["request_work_package"], "Основная")
        self.assertEqual(clean[0]["request_status"], "")

    def test_request_fixed_identity_and_owner_precede_payload_overflow(self):
        collisions = (
            (
                "identity",
                {"request_id": None},
                "supply_request_identity_invalid",
            ),
            (
                "owner",
                {"request_company_id": 999},
                "supply_request_owner_mismatch",
            ),
        )
        for kind, fixed_overrides, expected_reason in collisions:
            for shape in ("accepted", "overflow-only", "overflow-mixed"):
                with self.subTest(kind=kind, shape=shape):
                    request_overrides = {"request_id": 62}
                    request_overrides.update(fixed_overrides)
                    row = _bounded_request_row(**request_overrides)
                    if shape != "accepted":
                        row["field_request_status_bytes"] = (
                            MAX_TEXT_FIELD_BYTES + 1
                        )
                    rows = [row]
                    if shape == "overflow-mixed":
                        rows.insert(0, _bounded_request_row(request_id=61))
                    gated_rows = _bounded_request_rows(*rows)
                    cursor = FakeCursor((
                        REQUIRED_SCHEMA_ROWS,
                        (estimate_row(),),
                        (reconciliation_row(),),
                        SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
                        (_bounded_context_row(),),
                        gated_rows,
                    ))

                    if shape == "overflow-mixed":
                        with self.assertRaises(
                            supply_audit._VariableByteLimitError
                        ) as caught:
                            collect_supply_warehouse_impact_audit(
                                cursor,
                                source(),
                            )
                        self.assertEqual(caught.exception.args, (
                            "variable byte metadata is invalid",
                        ))
                        self.assertNotIn(
                            expected_reason,
                            str(caught.exception),
                        )
                    else:
                        report = collect_supply_warehouse_impact_audit(
                            cursor,
                            source(),
                        )
                        projection = report["supplyWarehouseImpact"]
                        self.assertEqual(
                            projection["state"],
                            "review_required",
                        )
                        self.assertTrue(projection["scanComplete"])
                        self.assertEqual(
                            projection["summary"]["supplyRequestRows"],
                            1,
                        )
                        self.assertEqual(projection["reasonCounts"], {
                            expected_reason: 1,
                        })
                        self.assertEqual(projection["needsReview"], [{
                            "sourceKind": "supply",
                            "sourceId": None,
                            "reasonCode": expected_reason,
                        }])
                    self.assertEqual(len(cursor.calls), 6)

    def test_request_fixed_faults_precede_lineage_json_parse(self):
        rows = _bounded_request_rows(
            _bounded_request_row(request_id=None),
            _bounded_request_row(
                request_id=62,
                request_company_id=999,
            ),
        )
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
            (_bounded_context_row(),),
            rows,
        ))
        real_mentions = supply_audit._request_mentions_base_estimate
        with mock.patch.object(
            supply_audit,
            "_request_mentions_base_estimate",
            wraps=real_mentions,
        ) as mentions:
            report = collect_supply_warehouse_impact_audit(
                cursor,
                source(),
            )

        mentions.assert_not_called()
        self.assertEqual(
            report["supplyWarehouseImpact"]["reasonCounts"],
            {
                "supply_request_identity_invalid": 1,
                "supply_request_owner_mismatch": 1,
            },
        )
        self.assertEqual(len(cursor.calls), 6)

    def test_request_query_wide_overflow_and_cardinality_stop_dependents(self):
        small = _bounded_request_row(request_id=61)
        oversized = _bounded_request_row(request_id=62)
        oversized["field_request_status_bytes"] = MAX_TEXT_FIELD_BYTES + 1
        mixed_rows = _bounded_request_rows(small, oversized)
        cardinality_rows = []
        for offset in range(MAX_DOMAIN_ROWS + 1):
            row = _bounded_request_row(request_id=1000 + offset)
            if offset == 0:
                row["request_id"] = None
            if offset == MAX_DOMAIN_ROWS:
                row["field_request_status_bytes"] = MAX_TEXT_FIELD_BYTES + 1
            cardinality_rows.append(row)
        cardinality_rows = _bounded_request_rows(
            *cardinality_rows,
            scan_limit=MAX_DOMAIN_ROWS,
        )

        for kind, rows, expected_payload_flag in (
            ("payload", mixed_rows, True),
            ("cardinality", cardinality_rows, False),
        ):
            with self.subTest(kind=kind):
                self.assertTrue(all(
                    row[field] is None
                    for row in rows
                    for field in _REQUEST_VARIABLE_FIELDS
                ))
                self.assertTrue(all(
                    row["payload_limit_exceeded"] is expected_payload_flag
                    for row in rows
                ))
                self.assertEqual(
                    rows[0]["query_variable_bytes"],
                    rows[-1]["query_variable_bytes"],
                )
                cursor = FakeCursor((
                    REQUIRED_SCHEMA_ROWS,
                    (estimate_row(),),
                    (reconciliation_row(),),
                    SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
                    (_bounded_context_row(),),
                    rows,
                ))

                report = collect_supply_warehouse_impact_audit(cursor, source())

                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "incomplete")
                self.assertEqual(projection["reasonCounts"], {
                    "supply_request_scan_limit_exceeded": 1,
                })
                self.assertEqual(len(cursor.calls), 6)

    def test_request_json_aggregate_and_metadata_fail_closed_atomically(self):
        exact_total = MAX_JSON_QUERY_BYTES
        base_size, remainder = divmod(exact_total, MAX_DOMAIN_ROWS)
        exact_rows = _bounded_request_rows(*(
            _bounded_request_row(
                request_id=1000 + index,
                items_json=_items_json_with_utf8_size(
                    base_size + (1 if index < remainder else 0)
                ),
            )
            for index in range(MAX_DOMAIN_ROWS)
        ))
        exact_budget = supply_audit._VariableByteBudget()

        state, clean, overflow_fields = supply_audit._load_requests(
            FakeCursor((exact_rows,)),
            context(),
            exact_budget,
        )

        self.assertEqual(state, "accepted")
        self.assertEqual(len(clean), MAX_DOMAIN_ROWS)
        self.assertEqual(overflow_fields, ())
        self.assertEqual(exact_rows[0]["query_json_bytes"], exact_total)
        self.assertEqual(
            exact_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES
            - exact_rows[0]["query_variable_bytes"],
        )

        overflow_sizes = [
            base_size + (1 if index < remainder else 0)
            for index in range(MAX_DOMAIN_ROWS)
        ]
        overflow_sizes[0] += 1
        overflow_rows = _bounded_request_rows(*(
            _bounded_request_row(
                request_id=2000 + index,
                items_json=_items_json_with_utf8_size(size),
            )
            for index, size in enumerate(overflow_sizes)
        ))
        overflow_budget = supply_audit._VariableByteBudget()

        state, clean, overflow_fields = supply_audit._load_requests(
            FakeCursor((overflow_rows,)),
            context(),
            overflow_budget,
        )

        self.assertEqual(state, "overflow")
        self.assertEqual(overflow_fields, ())
        self.assertTrue(all(
            row[field] is None
            for row in clean
            for field in _REQUEST_VARIABLE_FIELDS
        ))
        self.assertEqual(
            overflow_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES,
        )

        bad_context = _bounded_context_row()
        bad_context["base_sections_bytes"] += 1
        false_flag = _request_overflow("request_status")
        false_flag["payload_limit_exceeded"] = False
        leaked = _request_overflow("request_status")
        leaked["request_project"] = "must-not-leak"
        for kind, loader, row, args in (
            (
                "context-alias",
                supply_audit._load_context,
                bad_context,
                ({
                    "companyId": 4,
                    "projectId": 17,
                    "baseEstimateId": 51,
                },),
            ),
            (
                "request-flag",
                supply_audit._load_requests,
                false_flag,
                (context(),),
            ),
            (
                "request-raw-leak",
                supply_audit._load_requests,
                leaked,
                (context(),),
            ),
        ):
            with self.subTest(kind=kind):
                budget = supply_audit._VariableByteBudget()
                with self.assertRaises(
                    supply_audit._VariableByteLimitError
                ) as caught:
                    loader(FakeCursor(((row,),)), *args, budget)
                self.assertEqual(caught.exception.args, (
                    "variable byte metadata is invalid",
                ))
                self.assertNotIn("must-not-leak", str(caught.exception))
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )

    def test_downstream_sql_gates_use_exact_fields_and_remaining_budget(self):
        result_sets = self.result_sets()
        cursor = FakeCursor(result_sets)

        report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(len(cursor.calls), 14)
        remaining = (
            MAX_COLLECTOR_VARIABLE_BYTES
            - estimate_row()["query_variable_bytes"]
            - reconciliation_row()["query_variable_bytes"]
            - result_sets[4][0]["query_variable_bytes"]
            - result_sets[5][0]["query_variable_bytes"]
        )
        query_specs = (
            (
                6,
                "deliveries",
                _DELIVERY_VARIABLE_FIELDS,
                (MAX_TEXT_FIELD_BYTES, MAX_NUMERIC_FIELD_BYTES),
            ),
            (
                7,
                "allocations",
                _ALLOCATION_VARIABLE_FIELDS,
                (MAX_NUMERIC_FIELD_BYTES,),
            ),
            (
                9,
                "warehouse-invoices",
                _INVOICE_VARIABLE_FIELDS,
                (MAX_TEXT_FIELD_BYTES, MAX_SOURCE_JSON_BYTES),
            ),
            (
                10,
                "history",
                _HISTORY_VARIABLE_FIELDS,
                (MAX_TEXT_FIELD_BYTES,),
            ),
            (
                12,
                "movements",
                _MOVEMENT_VARIABLE_FIELDS,
                (MAX_TEXT_FIELD_BYTES,),
            ),
        )
        for index, kind, fields, field_caps in query_specs:
            with self.subTest(kind=kind):
                sql, params = cursor.calls[index]
                ids = [61] if index in (6, 7, 9) else [101]
                _assert_downstream_sql_contract(
                    self,
                    kind,
                    sql,
                    params,
                    ids,
                    remaining,
                )
                _assert_query_wide_gate(self, sql, fields)
                self.assertIn(remaining, params)
                self.assertIn(MAX_TEXT_QUERY_AGGREGATE_BYTES, params)
                for field_cap in field_caps:
                    self.assertIn(field_cap, params)
                self.assertEqual(
                    sql.upper().count({
                        6: "PUBLIC.SUPPLY_DELIVERIES",
                        7: "PUBLIC.ESTIMATE_ROW_SUPPLY_ALLOCATIONS",
                        9: "PUBLIC.WAREHOUSE_INVOICES",
                        10: "PUBLIC.WAREHOUSE_HISTORY",
                        12: "PUBLIC.WAREHOUSE_MOVEMENTS",
                    }[index]),
                    1,
                )
                remaining -= result_sets[index][0]["query_variable_bytes"]
        delivery_sql = cursor.calls[6][0].upper()
        allocation_sql = cursor.calls[7][0].upper()
        self.assertIn(
            "RECEIVED_QUANTITY::TEXT AS EMITTED_RECEIVED_QUANTITY",
            delivery_sql,
        )
        self.assertIn(
            "ALLOCATION_QUANTITY::TEXT AS EMITTED_ALLOCATION_QUANTITY",
            allocation_sql,
        )

    def test_downstream_sql_contract_rejects_security_drift(self):
        result_sets = self.result_sets()
        cursor = FakeCursor(result_sets)
        collect_supply_warehouse_impact_audit(cursor, source())
        before_delivery = (
            MAX_COLLECTOR_VARIABLE_BYTES
            - estimate_row()["query_variable_bytes"]
            - reconciliation_row()["query_variable_bytes"]
            - result_sets[4][0]["query_variable_bytes"]
            - result_sets[5][0]["query_variable_bytes"]
        )
        before_allocation = (
            before_delivery - result_sets[6][0]["query_variable_bytes"]
        )
        before_invoice = (
            before_allocation - result_sets[7][0]["query_variable_bytes"]
        )
        before_history = (
            before_invoice - result_sets[9][0]["query_variable_bytes"]
        )

        delivery_sql, delivery_params = cursor.calls[6]
        allocation_sql, allocation_params = cursor.calls[7]
        invoice_sql, invoice_params = cursor.calls[9]
        history_sql, history_params = cursor.calls[10]
        swapped_caps = list(delivery_params)
        swapped_caps[2], swapped_caps[6] = (
            swapped_caps[6],
            swapped_caps[2],
        )
        swapped_cap_aliases = delivery_sql.replace(
            "max_field_delivery_project_bytes <= %s",
            "__delivery_cap_swap__",
            1,
        ).replace(
            "max_field_received_quantity_bytes <= %s",
            "max_field_delivery_project_bytes <= %s",
            1,
        ).replace(
            "__delivery_cap_swap__",
            "max_field_received_quantity_bytes <= %s",
            1,
        )
        leaked_invoice_sql = invoice_sql.replace(
            "bounded.field_invoice_project_bytes,",
            "bounded.raw_items,bounded.field_invoice_project_bytes,",
            1,
        ).replace(
            "decided.field_invoice_project_bytes,",
            "decided.emitted_items AS raw_items,"
            "decided.field_invoice_project_bytes,",
            1,
        )
        secret_alias_invoice_sql = invoice_sql.replace(
            "items AS emitted_items",
            "items AS emitted_items,items AS secret_items",
            1,
        ).replace(
            "bounded.field_invoice_project_bytes,",
            "bounded.secret_items,bounded.field_invoice_project_bytes,",
            1,
        ).replace(
            "decided.field_invoice_project_bytes,",
            "decided.secret_items,decided.field_invoice_project_bytes,",
            1,
        )
        rejoined_delivery_sql = delivery_sql.replace(
            "FROM limited",
            "FROM limited JOIN public.supply_deliveries AS leaked ON TRUE",
            1,
        )
        mutations = (
            (
                "omitted-sum-field",
                "deliveries",
                delivery_sql.replace(
                    "+ field_unit_bytes::bigint",
                    "",
                    1,
                ),
                delivery_params,
                [61],
                before_delivery,
            ),
            (
                "removed-remaining-predicate",
                "allocations",
                allocation_sql.replace(
                    "AND query_text_bytes <= %s",
                    "",
                    1,
                ),
                allocation_params,
                [61],
                before_allocation,
            ),
            (
                "removed-package-fallback",
                "history",
                history_sql.replace(
                    "COALESCE(NULLIF(work_package,''),'Основная')",
                    "work_package",
                    1,
                ),
                history_params,
                [101],
                before_history,
            ),
            (
                "broadened-where",
                "warehouse-invoices",
                invoice_sql.replace(
                    "WHERE supply_request_id=ANY(%s)",
                    "WHERE supply_request_id=ANY(%s) OR TRUE",
                    1,
                ),
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "swapped-delivery-caps",
                "deliveries",
                delivery_sql,
                tuple(swapped_caps),
                [61],
                before_delivery,
            ),
            (
                "swapped-delivery-cap-aliases",
                "deliveries",
                swapped_cap_aliases,
                delivery_params,
                [61],
                before_delivery,
            ),
            (
                "raw-items-leak",
                "warehouse-invoices",
                leaked_invoice_sql,
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "removed-cardinality-decision",
                "allocations",
                allocation_sql.replace(
                    "(gated.row_count <= %s AND gated.bytes_allowed)",
                    "(%s IS NOT NULL AND gated.bytes_allowed)",
                    1,
                ),
                allocation_params,
                [61],
                before_allocation,
            ),
            (
                "rejoined-base-table",
                "deliveries",
                rejoined_delivery_sql,
                delivery_params,
                [61],
                before_delivery,
            ),
            (
                "forged-variable-total",
                "warehouse-invoices",
                invoice_sql.replace(
                    "(query_json_bytes + query_text_bytes)::bigint",
                    "0::bigint",
                    1,
                ),
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "removed-json-query-cap",
                "warehouse-invoices",
                invoice_sql.replace(
                    "AND query_json_bytes <= %s",
                    "AND %s >= 0",
                    1,
                ),
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "or-delivery-query-cap",
                "deliveries",
                delivery_sql.replace(
                    "AND query_text_bytes <= %s",
                    "OR query_text_bytes <= %s",
                    1,
                ),
                delivery_params,
                [61],
                before_delivery,
            ),
            (
                "or-invoice-query-cap",
                "warehouse-invoices",
                invoice_sql.replace(
                    "AND query_json_bytes <= %s",
                    "OR query_json_bytes <= %s",
                    1,
                ),
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "new-raw-alias-leak",
                "warehouse-invoices",
                secret_alias_invoice_sql,
                invoice_params,
                [61],
                before_invoice,
            ),
            (
                "fixed-alias-raw-leak",
                "deliveries",
                delivery_sql.replace(
                    "id AS delivery_id",
                    "project AS delivery_id",
                    1,
                ),
                delivery_params,
                [61],
                before_delivery,
            ),
        )
        originals = {
            "omitted-sum-field": delivery_sql,
            "removed-remaining-predicate": allocation_sql,
            "removed-package-fallback": history_sql,
            "broadened-where": invoice_sql,
            "swapped-delivery-cap-aliases": delivery_sql,
            "raw-items-leak": invoice_sql,
            "removed-cardinality-decision": allocation_sql,
            "rejoined-base-table": delivery_sql,
            "forged-variable-total": invoice_sql,
            "removed-json-query-cap": invoice_sql,
            "or-delivery-query-cap": delivery_sql,
            "or-invoice-query-cap": invoice_sql,
            "new-raw-alias-leak": invoice_sql,
            "fixed-alias-raw-leak": delivery_sql,
        }
        for kind, query_kind, sql, params, ids, remaining in mutations:
            with self.subTest(kind=kind):
                if kind in originals:
                    self.assertNotEqual(sql, originals[kind])
                with self.assertRaises(AssertionError):
                    _assert_downstream_sql_contract(
                        self,
                        query_kind,
                        sql,
                        params,
                        ids,
                        remaining,
                    )

    def test_one_budget_identity_reaches_every_payload_loader(self):
        _assert_downstream_loader_signatures(self)
        observed = []

        def observe(real_loader):
            def wrapped(*args):
                observed.append(args[-1])
                return real_loader(*args)
            return wrapped

        patched = (
            "_collect_baseline_audit",
            "_load_context",
            "_load_requests",
            "_load_deliveries",
            "_load_allocations",
            "_load_warehouse_invoices",
            "_load_history",
            "_load_movements",
        )
        patchers = [
            mock.patch.object(
                supply_audit,
                name,
                side_effect=observe(getattr(supply_audit, name)),
            )
            for name in patched
        ]
        for patcher in patchers:
            patcher.start()
        try:
            report = collect_supply_warehouse_impact_audit(
                FakeCursor(self.result_sets()),
                source(),
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(len(observed), len(patched))
        self.assertTrue(all(budget is observed[0] for budget in observed))

    def test_downstream_field_boundaries_and_metadata_are_exact(self):
        _assert_downstream_loader_signatures(self)
        cases = (
            (
                "deliveries",
                supply_audit._load_deliveries,
                ([61],),
                _bounded_delivery_row,
                _bounded_delivery_rows,
                _DELIVERY_FIELD_SPECS,
                _DELIVERY_VARIABLE_FIELDS,
            ),
            (
                "allocations",
                supply_audit._load_allocations,
                ([61],),
                _bounded_allocation_row,
                _bounded_allocation_rows,
                _ALLOCATION_FIELD_SPECS,
                _ALLOCATION_VARIABLE_FIELDS,
            ),
            (
                "warehouse-invoices",
                supply_audit._load_warehouse_invoices,
                ([61],),
                _bounded_invoice_row,
                _bounded_invoice_rows,
                _INVOICE_FIELD_SPECS,
                _INVOICE_VARIABLE_FIELDS,
            ),
            (
                "history",
                supply_audit._load_history,
                ([101],),
                _bounded_history_row,
                _bounded_history_rows,
                _HISTORY_FIELD_SPECS,
                _HISTORY_VARIABLE_FIELDS,
            ),
            (
                "movements",
                supply_audit._load_movements,
                ([101],),
                _bounded_movement_row,
                _bounded_movement_rows,
                _MOVEMENT_FIELD_SPECS,
                _MOVEMENT_VARIABLE_FIELDS,
            ),
        )
        for (
            kind, loader, loader_args, row_builder, rows_builder,
            field_specs, variable_fields,
        ) in cases:
            for field, category, cap in field_specs:
                exact = (
                    _items_json_with_utf8_size(cap)
                    if category == "json"
                    else "1" + ("0" * (cap - 1))
                    if cap == MAX_NUMERIC_FIELD_BYTES
                    else "я" * (cap // 2)
                )
                oversized = (
                    _items_json_with_utf8_size(cap + 1)
                    if category == "json"
                    else "1" + ("0" * cap)
                    if cap == MAX_NUMERIC_FIELD_BYTES
                    else exact + "a"
                )
                with self.subTest(kind=kind, field=field, boundary="inclusive"):
                    rows = rows_builder(row_builder(**{field: exact}))
                    budget = supply_audit._VariableByteBudget()
                    state, clean, overflow_fields = loader(
                        FakeCursor((rows,)),
                        *loader_args,
                        budget,
                    )
                    self.assertEqual(state, "accepted")
                    self.assertEqual(overflow_fields, ())
                    self.assertEqual(clean[0][field], exact)
                    self.assertEqual(
                        budget.remaining_bytes,
                        MAX_COLLECTOR_VARIABLE_BYTES
                        - rows[0]["query_variable_bytes"],
                    )
                    for metadata_key in (
                        "field_" + field + "_bytes",
                        "query_json_bytes",
                        "query_text_bytes",
                        "query_variable_bytes",
                        "cardinality_limit_exceeded",
                        "payload_limit_exceeded",
                    ):
                        self.assertNotIn(metadata_key, clean[0])
                with self.subTest(kind=kind, field=field, boundary="limit+1"):
                    rows = rows_builder(row_builder(**{field: oversized}))
                    budget = supply_audit._VariableByteBudget()
                    state, clean, overflow_fields = loader(
                        FakeCursor((rows,)),
                        *loader_args,
                        budget,
                    )
                    self.assertEqual(state, "overflow")
                    self.assertEqual(overflow_fields, (field,))
                    self.assertTrue(all(
                        clean[0][name] is None for name in variable_fields
                    ))
                    self.assertEqual(
                        budget.remaining_bytes,
                        MAX_COLLECTOR_VARIABLE_BYTES,
                    )

            malformed = list(rows_builder(row_builder()))
            malformed[0]["query_variable_bytes"] += 1
            malformed_budget = supply_audit._VariableByteBudget()
            with self.subTest(kind=kind, metadata="arithmetic"):
                with self.assertRaises(
                    supply_audit._VariableByteLimitError
                ) as caught:
                    loader(
                        FakeCursor((tuple(malformed),)),
                        *loader_args,
                        malformed_budget,
                    )
                self.assertEqual(caught.exception.args, (
                    "variable byte metadata is invalid",
                ))
                self.assertEqual(
                    malformed_budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )

    def test_downstream_true_nulls_are_zero_and_package_fallback_is_16(self):
        fallback_bytes = _utf8_bytes("Основная")
        self.assertEqual(fallback_bytes, 16)
        cases = (
            (
                "deliveries",
                supply_audit._load_deliveries,
                ([61],),
                _bounded_delivery_rows(_bounded_delivery_row(
                    delivery_project=None,
                    delivery_work_package=None,
                    material_name=None,
                    unit=None,
                    received_quantity=None,
                )),
                {
                    "delivery_project": 0,
                    "delivery_work_package": fallback_bytes,
                    "material_name": 0,
                    "unit": 0,
                    "received_quantity": 0,
                },
            ),
            (
                "allocations",
                supply_audit._load_allocations,
                ([61],),
                _bounded_allocation_rows(_bounded_allocation_row(
                    allocation_quantity=None,
                )),
                {"allocation_quantity": 0},
            ),
            (
                "warehouse-invoices",
                supply_audit._load_warehouse_invoices,
                ([61],),
                _bounded_invoice_rows(_bounded_invoice_row(
                    invoice_project=None,
                    items=None,
                )),
                {"invoice_project": 0, "items": 0},
            ),
            (
                "history",
                supply_audit._load_history,
                ([101],),
                _bounded_history_rows(_bounded_history_row(
                    history_work_package=None,
                )),
                {"history_work_package": fallback_bytes},
            ),
            (
                "movements",
                supply_audit._load_movements,
                ([101],),
                _bounded_movement_rows(_bounded_movement_row(
                    movement_work_package=None,
                )),
                {"movement_work_package": fallback_bytes},
            ),
        )
        for kind, loader, loader_args, rows, expected_bytes in cases:
            with self.subTest(kind=kind):
                for field, size in expected_bytes.items():
                    self.assertEqual(rows[0]["field_" + field + "_bytes"], size)
                self.assertEqual(
                    rows[0]["query_variable_bytes"],
                    sum(expected_bytes.values()),
                )
                budget = supply_audit._VariableByteBudget()
                state, clean, overflow_fields = loader(
                    FakeCursor((rows,)),
                    *loader_args,
                    budget,
                )
                self.assertEqual(state, "accepted")
                self.assertEqual(overflow_fields, ())
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - sum(expected_bytes.values()),
                )
                for field in expected_bytes:
                    self.assertNotIn("field_" + field + "_bytes", clean[0])

    def test_downstream_aggregate_and_cumulative_overflow_are_atomic(self):
        _assert_downstream_loader_signatures(self)
        exact_size, exact_remainder = divmod(
            MAX_JSON_QUERY_BYTES,
            MAX_DOMAIN_ROWS,
        )
        exact_rows = _bounded_invoice_rows(*(
            _bounded_invoice_row(
                warehouse_invoice_id=1000 + index,
                items=_items_json_with_utf8_size(
                    exact_size + (1 if index < exact_remainder else 0)
                ),
            )
            for index in range(MAX_DOMAIN_ROWS)
        ))
        exact_budget = supply_audit._VariableByteBudget()
        state, clean, overflow_fields = supply_audit._load_warehouse_invoices(
            FakeCursor((exact_rows,)),
            [61],
            exact_budget,
        )
        self.assertEqual(state, "accepted")
        self.assertEqual(len(clean), MAX_DOMAIN_ROWS)
        self.assertEqual(overflow_fields, ())

        overflow_sizes = [
            exact_size + (1 if index < exact_remainder else 0)
            for index in range(MAX_DOMAIN_ROWS)
        ]
        overflow_sizes[0] += 1
        overflow_rows = _bounded_invoice_rows(*(
            _bounded_invoice_row(
                warehouse_invoice_id=2000 + index,
                items=_items_json_with_utf8_size(size),
            )
            for index, size in enumerate(overflow_sizes)
        ))
        overflow_budget = supply_audit._VariableByteBudget()
        state, clean, overflow_fields = supply_audit._load_warehouse_invoices(
            FakeCursor((overflow_rows,)),
            [61],
            overflow_budget,
        )
        self.assertEqual(state, "overflow")
        self.assertEqual(overflow_fields, ())
        self.assertTrue(all(
            row[field] is None
            for row in clean
            for field in _INVOICE_VARIABLE_FIELDS
        ))
        self.assertEqual(
            overflow_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES,
        )

        delivery = _bounded_delivery_row()
        delivery_bytes = sum(
            delivery["field_" + field + "_bytes"]
            for field in _DELIVERY_VARIABLE_FIELDS
        )
        cumulative_budget = supply_audit._VariableByteBudget()
        cumulative_budget.consume(
            MAX_COLLECTOR_VARIABLE_BYTES - delivery_bytes + 1
        )
        before = cumulative_budget.remaining_bytes
        cumulative_rows = _bounded_delivery_rows(
            delivery,
            remaining_bytes=before,
        )
        state, clean, overflow_fields = supply_audit._load_deliveries(
            FakeCursor((cumulative_rows,)),
            [61],
            cumulative_budget,
        )
        self.assertEqual(state, "overflow")
        self.assertEqual(overflow_fields, ())
        self.assertTrue(all(
            clean[0][field] is None for field in _DELIVERY_VARIABLE_FIELDS
        ))
        self.assertEqual(cumulative_budget.remaining_bytes, before)

    def test_downstream_overflow_stops_at_earliest_query(self):
        overflow_sets = (
            (
                "deliveries",
                6,
                _bounded_delivery_rows(_bounded_delivery_row(
                    delivery_project=("я" * (MAX_TEXT_FIELD_BYTES // 2)) + "a",
                )),
                7,
            ),
            (
                "allocations",
                7,
                _bounded_allocation_rows(_bounded_allocation_row(
                    allocation_quantity="1" + ("0" * MAX_NUMERIC_FIELD_BYTES),
                )),
                8,
            ),
            (
                "warehouse-invoices",
                9,
                _bounded_invoice_rows(_bounded_invoice_row(
                    items=_items_json_with_utf8_size(MAX_SOURCE_JSON_BYTES + 1),
                )),
                10,
            ),
            (
                "history",
                10,
                _bounded_history_rows(_bounded_history_row(
                    history_work_package=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                11,
            ),
            (
                "movements",
                12,
                _bounded_movement_rows(_bounded_movement_row(
                    movement_work_package=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                13,
            ),
        )
        for kind, result_index, rows, expected_calls in overflow_sets:
            with self.subTest(kind=kind):
                result_sets = list(self.result_sets())
                result_sets[result_index] = rows
                cursor = FakeCursor(tuple(result_sets))

                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )

                self.assertEqual(len(cursor.calls), expected_calls)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "incomplete")
                self.assertFalse(projection["scanComplete"])
                self.assertEqual(projection["reasonCounts"], {
                    "supply_warehouse_scan_limit_exceeded": 1,
                })
                _assert_a92_raw_projection_accepts(self, projection)

    def test_fixed_width_cardinality_stops_at_its_query_before_reviews(self):
        cardinality_sets = (
            (
                "supplier-invoices",
                8,
                tuple(
                    supplier_invoice_row(
                        supplier_invoice_id=1000 + index,
                        invoice_company_id=999 if index == 0 else 4,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                9,
            ),
            (
                "receipt-lots",
                11,
                tuple(
                    lot_row(
                        lot_id=2000 + index,
                        lot_company_id=999 if index == 0 else 4,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                12,
            ),
            (
                "lot-movements",
                13,
                tuple(
                    lot_movement_row(
                        lot_movement_id=3000 + index,
                        lot_movement_company_id=999 if index == 0 else 4,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                14,
            ),
        )
        for kind, result_index, rows, expected_calls in cardinality_sets:
            with self.subTest(kind=kind):
                result_sets = list(self.result_sets())
                result_sets[result_index] = rows
                cursor = FakeCursor(tuple(result_sets))

                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )

                self.assertEqual(len(cursor.calls), expected_calls)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "incomplete")
                self.assertFalse(projection["scanComplete"])
                self.assertEqual(projection["reasonCounts"], {
                    "supply_warehouse_scan_limit_exceeded": 1,
                })
                _assert_a92_raw_projection_accepts(self, projection)

    def test_downstream_query_parent_integrity_and_cardinality_precedence(self):
        cases = (
            (
                "deliveries",
                6,
                _bounded_delivery_rows(
                    _bounded_delivery_row(request_id=999)
                ),
                _bounded_delivery_rows(_bounded_delivery_row(
                    request_id=999,
                    delivery_project=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                _bounded_delivery_rows(*(
                    _bounded_delivery_row(
                        delivery_id=6000 + index,
                        request_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                7,
            ),
            (
                "allocations",
                7,
                _bounded_allocation_rows(
                    _bounded_allocation_row(request_id=999)
                ),
                _bounded_allocation_rows(_bounded_allocation_row(
                    request_id=999,
                    allocation_quantity=(
                        "1" + ("0" * MAX_NUMERIC_FIELD_BYTES)
                    ),
                )),
                _bounded_allocation_rows(*(
                    _bounded_allocation_row(
                        allocation_id=7000 + index,
                        request_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                8,
            ),
            (
                "supplier-invoices",
                8,
                (supplier_invoice_row(request_id=999),),
                None,
                tuple(
                    supplier_invoice_row(
                        supplier_invoice_id=8000 + index,
                        request_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                9,
            ),
            (
                "warehouse-invoices",
                9,
                _bounded_invoice_rows(
                    _bounded_invoice_row(supply_request_id=999)
                ),
                _bounded_invoice_rows(_bounded_invoice_row(
                    supply_request_id=999,
                    items=_items_json_with_utf8_size(
                        MAX_SOURCE_JSON_BYTES + 1
                    ),
                )),
                _bounded_invoice_rows(*(
                    _bounded_invoice_row(
                        warehouse_invoice_id=9000 + index,
                        supply_request_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                10,
            ),
            (
                "history",
                10,
                _bounded_history_rows(
                    _bounded_history_row(source_invoice_id=999)
                ),
                _bounded_history_rows(_bounded_history_row(
                    source_invoice_id=999,
                    history_work_package=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                _bounded_history_rows(*(
                    _bounded_history_row(
                        history_id=10000 + index,
                        source_invoice_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                11,
            ),
            (
                "receipt-lots",
                11,
                (lot_row(warehouse_invoice_id=999),),
                None,
                tuple(
                    lot_row(
                        lot_id=11000 + index,
                        warehouse_invoice_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                12,
            ),
            (
                "movements",
                12,
                _bounded_movement_rows(
                    _bounded_movement_row(source_invoice_id=999)
                ),
                _bounded_movement_rows(_bounded_movement_row(
                    source_invoice_id=999,
                    movement_work_package=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                _bounded_movement_rows(*(
                    _bounded_movement_row(
                        movement_id=12000 + index,
                        source_invoice_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                13,
            ),
            (
                "lot-movements",
                13,
                (lot_movement_row(
                    lot_id=998,
                    warehouse_movement_id=999,
                ),),
                None,
                tuple(
                    lot_movement_row(
                        lot_movement_id=13000 + index,
                        lot_id=998,
                        warehouse_movement_id=999,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                ),
                14,
            ),
        )
        for (
            kind, result_index, accepted_rows, overflow_rows,
            cardinality_rows, expected_calls,
        ) in cases:
            invalid_shapes = [("accepted", accepted_rows)]
            if overflow_rows is not None:
                invalid_shapes.append(("overflow", overflow_rows))
            for shape, rows in invalid_shapes:
                with self.subTest(kind=kind, shape=shape):
                    result_sets = list(self.result_sets())
                    result_sets[result_index] = rows
                    cursor = FakeCursor(tuple(result_sets))
                    with self.assertRaises(
                        supply_audit._VariableByteLimitError
                    ) as caught:
                        collect_supply_warehouse_impact_audit(
                            cursor,
                            source(),
                        )
                    self.assertEqual(caught.exception.args, (
                        "variable byte metadata is invalid",
                    ))
                    self.assertEqual(len(cursor.calls), expected_calls)

            with self.subTest(kind=kind, shape="cardinality-first"):
                result_sets = list(self.result_sets())
                result_sets[result_index] = cardinality_rows
                cursor = FakeCursor(tuple(result_sets))
                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )
                self.assertEqual(len(cursor.calls), expected_calls)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["reasonCounts"], {
                    "supply_warehouse_scan_limit_exceeded": 1,
                })
                _assert_a92_raw_projection_accepts(self, projection)

        result_sets = list(self.result_sets())
        result_sets[13] = (lot_movement_row(
            lot_id=121,
            warehouse_movement_id=999,
        ),)
        report = collect_supply_warehouse_impact_audit(
            FakeCursor(tuple(result_sets)),
            source(),
        )
        self.assertEqual(
            report["supplyWarehouseImpact"]["reasonCounts"],
            {
                "warehouse_lot_movement_parent_mismatch": 1,
                "warehouse_lot_movement_missing": 1,
            },
        )

    def test_payload_prefix_faults_precede_overflow_but_never_lie(self):
        collision_specs = (
            (
                "deliveries",
                6,
                _bounded_delivery_row,
                _bounded_delivery_rows,
                _DELIVERY_VARIABLE_FIELDS,
                "delivery_id",
                "delivery_company_id",
                72,
                "received_quantity",
                "1" + ("0" * MAX_NUMERIC_FIELD_BYTES),
                "delivery",
                "supply_delivery_identity_invalid",
                "supply_delivery_owner_mismatch",
                7,
            ),
            (
                "allocations",
                7,
                _bounded_allocation_row,
                _bounded_allocation_rows,
                _ALLOCATION_VARIABLE_FIELDS,
                "allocation_id",
                "allocation_company_id",
                82,
                "allocation_quantity",
                "1" + ("0" * MAX_NUMERIC_FIELD_BYTES),
                "allocation",
                "supply_allocation_identity_invalid",
                "supply_allocation_owner_mismatch",
                8,
            ),
            (
                "warehouse-invoices",
                9,
                _bounded_invoice_row,
                _bounded_invoice_rows,
                _INVOICE_VARIABLE_FIELDS,
                "warehouse_invoice_id",
                "invoice_company_id",
                102,
                "items",
                _items_json_with_utf8_size(MAX_SOURCE_JSON_BYTES + 1),
                "warehouseInvoice",
                "warehouse_invoice_identity_invalid",
                "warehouse_invoice_owner_mismatch",
                10,
            ),
            (
                "history",
                10,
                _bounded_history_row,
                _bounded_history_rows,
                _HISTORY_VARIABLE_FIELDS,
                "history_id",
                "history_company_id",
                112,
                "history_work_package",
                ("я" * (MAX_TEXT_FIELD_BYTES // 2)) + "a",
                "warehouse_receipt",
                "warehouse_receipt_identity_invalid",
                "warehouse_receipt_owner_mismatch",
                11,
            ),
            (
                "movements",
                12,
                _bounded_movement_row,
                _bounded_movement_rows,
                _MOVEMENT_VARIABLE_FIELDS,
                "movement_id",
                "movement_company_id",
                132,
                "movement_work_package",
                ("я" * (MAX_TEXT_FIELD_BYTES // 2)) + "a",
                "warehouse_movement",
                "warehouse_movement_identity_invalid",
                "warehouse_movement_owner_mismatch",
                13,
            ),
        )

        def result_sets_for(kind, result_index, rows):
            result_sets = list(self.result_sets())
            result_sets[result_index] = rows
            if kind == "deliveries":
                result_sets[9] = _bounded_invoice_rows(
                    _bounded_invoice_row(supply_delivery_id=None)
                )
            elif kind == "warehouse-invoices":
                for index in (10, 11, 12, 13):
                    result_sets[index] = ()
            elif kind == "movements":
                result_sets[13] = ()
            return tuple(result_sets)

        for (
            kind, result_index, row_builder, rows_builder,
            variable_fields,
            id_field, owner_field, owner_fault_id, overflow_field,
            overflow_value, source_kind, identity_reason, owner_reason,
            expected_stop,
        ) in collision_specs:
            identity = row_builder(**{id_field: None})
            owner = row_builder(**{
                id_field: owner_fault_id,
                owner_field: 999,
                overflow_field: overflow_value,
            })
            all_fixed_rows = rows_builder(identity, owner)
            self.assertTrue(all(
                row[field] is None
                for row in all_fixed_rows
                for field in variable_fields
            ))
            with self.subTest(kind=kind, shape="all-fixed-overflow"):
                cursor = FakeCursor(result_sets_for(
                    kind,
                    result_index,
                    all_fixed_rows,
                ))
                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )
                self.assertEqual(len(cursor.calls), 14)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "review_required")
                self.assertTrue(projection["scanComplete"])
                self.assertEqual(projection["reasonCounts"], {
                    identity_reason: 1,
                    owner_reason: 1,
                })
                self.assertEqual(projection["needsReview"], [
                    {
                        "sourceKind": source_kind,
                        "sourceId": None,
                        "reasonCode": identity_reason,
                    },
                    {
                        "sourceKind": source_kind,
                        "sourceId": None,
                        "reasonCode": owner_reason,
                    },
                ])
                _assert_a92_raw_projection_accepts(self, projection)

            valid = row_builder()
            mixed_rows = rows_builder(valid, owner)
            self.assertTrue(all(
                row[field] is None
                for row in mixed_rows
                for field in variable_fields
            ))
            with self.subTest(kind=kind, shape="mixed-overflow"):
                cursor = FakeCursor(result_sets_for(
                    kind,
                    result_index,
                    mixed_rows,
                ))
                with self.assertRaises(
                    supply_audit._VariableByteLimitError
                ) as caught:
                    collect_supply_warehouse_impact_audit(cursor, source())
                self.assertEqual(caught.exception.args, (
                    "variable byte metadata is invalid",
                ))
                self.assertNotIn(overflow_value[:16], str(caught.exception))
                self.assertEqual(len(cursor.calls), expected_stop)

            cardinality_rows = []
            for offset in range(MAX_DOMAIN_ROWS + 1):
                overrides = {id_field: 4000 + offset}
                if offset == 0:
                    overrides[owner_field] = 999
                if offset == MAX_DOMAIN_ROWS:
                    overrides[overflow_field] = overflow_value
                cardinality_rows.append(row_builder(**overrides))
            cardinality_rows = rows_builder(*cardinality_rows)
            self.assertTrue(all(
                row[field] is None
                for row in cardinality_rows
                for field in variable_fields
            ))
            with self.subTest(kind=kind, shape="cardinality-first"):
                cursor = FakeCursor(result_sets_for(
                    kind,
                    result_index,
                    cardinality_rows,
                ))
                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )
                self.assertEqual(len(cursor.calls), expected_stop)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "incomplete")
                self.assertFalse(projection["scanComplete"])
                self.assertEqual(projection["reasonCounts"], {
                    "supply_warehouse_scan_limit_exceeded": 1,
                })
                _assert_a92_raw_projection_accepts(self, projection)

    def test_prior_fixed_fault_plus_later_payload_overflow_is_private(self):
        collision_specs = (
            (
                "request-to-delivery",
                5,
                _bounded_request_rows(
                    _bounded_request_row(),
                    _bounded_request_row(
                        request_id=62,
                        request_company_id=999,
                    ),
                ),
                6,
                _bounded_delivery_rows(_bounded_delivery_row(
                    delivery_project=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                _bounded_delivery_rows(*(
                    _bounded_delivery_row(delivery_id=6000 + index)
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                7,
            ),
            (
                "delivery-to-allocation",
                6,
                _bounded_delivery_rows(_bounded_delivery_row(
                    delivery_company_id=999,
                )),
                7,
                _bounded_allocation_rows(_bounded_allocation_row(
                    allocation_quantity=(
                        "1" + ("0" * MAX_NUMERIC_FIELD_BYTES)
                    ),
                )),
                _bounded_allocation_rows(*(
                    _bounded_allocation_row(allocation_id=7000 + index)
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                8,
            ),
            (
                "supplier-to-invoice",
                8,
                (supplier_invoice_row(invoice_company_id=999),),
                9,
                _bounded_invoice_rows(_bounded_invoice_row(
                    items=_items_json_with_utf8_size(
                        MAX_SOURCE_JSON_BYTES + 1
                    ),
                )),
                _bounded_invoice_rows(*(
                    _bounded_invoice_row(
                        warehouse_invoice_id=8000 + index,
                    )
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                10,
            ),
            (
                "lot-to-movement",
                11,
                (lot_row(lot_company_id=999),),
                12,
                _bounded_movement_rows(_bounded_movement_row(
                    movement_work_package=(
                        "я" * (MAX_TEXT_FIELD_BYTES // 2)
                    ) + "a",
                )),
                _bounded_movement_rows(*(
                    _bounded_movement_row(movement_id=9000 + index)
                    for index in range(MAX_DOMAIN_ROWS + 1)
                )),
                13,
            ),
        )
        for (
            kind, prior_index, prior_rows, later_index, overflow_rows,
            cardinality_rows, expected_calls,
        ) in collision_specs:
            with self.subTest(kind=kind, shape="payload-overflow"):
                result_sets = list(self.result_sets())
                result_sets[prior_index] = prior_rows
                result_sets[later_index] = overflow_rows
                cursor = FakeCursor(tuple(result_sets))
                with self.assertRaises(
                    supply_audit._VariableByteLimitError
                ) as caught:
                    collect_supply_warehouse_impact_audit(cursor, source())
                self.assertEqual(caught.exception.args, (
                    "variable byte metadata is invalid",
                ))
                self.assertEqual(len(cursor.calls), expected_calls)

            with self.subTest(kind=kind, shape="cardinality-first"):
                result_sets = list(self.result_sets())
                result_sets[prior_index] = prior_rows
                result_sets[later_index] = cardinality_rows
                cursor = FakeCursor(tuple(result_sets))
                report = collect_supply_warehouse_impact_audit(
                    cursor,
                    source(),
                )
                self.assertEqual(len(cursor.calls), expected_calls)
                projection = report["supplyWarehouseImpact"]
                self.assertEqual(projection["state"], "incomplete")
                self.assertFalse(projection["scanComplete"])
                self.assertEqual(projection["reasonCounts"], {
                    "supply_warehouse_scan_limit_exceeded": 1,
                })
                _assert_a92_raw_projection_accepts(self, projection)

    def test_invoice_items_parse_only_after_prefix_and_bounded_metadata(self):
        invoice_marker = '[{"invoice-prefix-marker":true}]'
        fixed_prefix_rows = (
            _bounded_invoice_row(
                warehouse_invoice_id=None,
                items=invoice_marker,
            ),
            _bounded_invoice_row(
                invoice_company_id=999,
                items=invoice_marker,
            ),
        )
        for kind, invoice in zip(("identity", "owner"), fixed_prefix_rows):
            with self.subTest(kind=kind, shape="accepted-prefix"):
                reviews = []
                with mock.patch.object(
                    supply_projection,
                    "_items",
                    wraps=supply_projection._items,
                ) as parse_items:
                    valid = supply_projection._valid_warehouse_invoices(
                        context(),
                        {},
                        {},
                        {},
                        (invoice,),
                        reviews,
                    )
                self.assertEqual(valid, {})
                self.assertEqual(len(reviews), 1)
                parse_items.assert_not_called()

        def invoice_sets(rows):
            result_sets = list(self.result_sets())
            result_sets[9] = rows
            for index in (10, 11, 12, 13):
                result_sets[index] = ()
            return tuple(result_sets)

        oversized_invoice_items = _items_json_with_utf8_size(
            MAX_SOURCE_JSON_BYTES + 1
        )
        overflow_owner_fault = _bounded_invoice_rows(_bounded_invoice_row(
            invoice_company_id=999,
            items=oversized_invoice_items,
        ))
        valid_overflow = _bounded_invoice_rows(_bounded_invoice_row(
            items=_items_json_with_utf8_size(MAX_SOURCE_JSON_BYTES + 1),
        ))
        cardinality = _bounded_invoice_rows(*(
            _bounded_invoice_row(warehouse_invoice_id=5000 + index)
            for index in range(MAX_DOMAIN_ROWS + 1)
        ))
        malformed = list(_bounded_invoice_rows(_bounded_invoice_row()))
        malformed[0]["query_variable_bytes"] += 1
        cases = (
            (
                "fixed-overflow",
                overflow_owner_fault,
                "report",
                "invoice-absent",
            ),
            ("valid-overflow", valid_overflow, "report", "none"),
            ("cardinality", cardinality, "report", "none"),
            ("malformed", tuple(malformed), "error", "none"),
        )
        for kind, rows, outcome, parse_rule in cases:
            with self.subTest(kind=kind):
                cursor = FakeCursor(invoice_sets(rows))
                with mock.patch.object(
                    supply_projection,
                    "_items",
                    wraps=supply_projection._items,
                ) as parse_items:
                    if outcome == "error":
                        with self.assertRaises(
                            supply_audit._VariableByteLimitError
                        ) as caught:
                            collect_supply_warehouse_impact_audit(
                                cursor,
                                source(),
                            )
                        self.assertEqual(caught.exception.args, (
                            "variable byte metadata is invalid",
                        ))
                    else:
                        report = collect_supply_warehouse_impact_audit(
                            cursor,
                            source(),
                        )
                        _assert_a92_raw_projection_accepts(
                            self,
                            report["supplyWarehouseImpact"],
                        )
                if parse_rule == "none":
                    parse_items.assert_not_called()
                else:
                    parsed_values = tuple(
                        call.args[0] for call in parse_items.call_args_list
                    )
                    self.assertNotIn(None, parsed_values)
                    self.assertNotIn(oversized_invoice_items, parsed_values)

    def test_exact_source_runs_bounded_parameterized_selects_only(self):
        cursor = FakeCursor(self.result_sets())

        report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["supplyWarehouseImpact"]["openSupply"][0]["requestId"], 61)
        self.assertEqual(len(cursor.calls), 14)
        for schema_index, expected_rows in (
            (0, REQUIRED_SCHEMA_ROWS),
            (3, SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS),
        ):
            schema_sql, schema_params = cursor.calls[schema_index]
            self.assertIn("jsonb_to_recordset", schema_sql)
            self.assertIn("pg_catalog.pg_attribute", schema_sql)
            self.assertNotIn("information_schema", schema_sql)
            self.assertIn("LIMIT %s", schema_sql)
            self.assertEqual(schema_params[-1], len(expected_rows) + 1)
        for index, (sql, params) in enumerate(cursor.calls):
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE "):
                self.assertNotIn(mutation, normalized)
            if index >= 5:
                self.assertIn("LIMIT %s", sql)
                self.assertIn(MAX_DOMAIN_ROWS + 1, params)
        request_sql, request_params = cursor.calls[5]
        self.assertIn("items_json ~ %s", request_sql)
        self.assertEqual(
            request_params[3],
            '"estimateId"[[:space:]]*:[[:space:]]*51([^0-9]|$)',
        )
        context_sql, _ = cursor.calls[4]
        self.assertEqual(context_sql.upper().count("LIMIT 2"), 1)
        self.assertIn("ORDER BY P.ID LIMIT %S", context_sql.upper())
        self.assertEqual(context_sql.upper().count("COUNT(*) OVER ()"), 1)

    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        cursor = FakeCursor(self.result_sets())
        connection = FakeConnection(cursor)

        report = run_supply_warehouse_impact_audit(
            lambda: connection, source(),
        )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_operator_command_is_additive_and_not_registered_at_runtime(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["audit:estimate-revision-supply-warehouse-impact"],
            "python3 -m backend.features.estimate_revision_impact."
            "supply_warehouse_audit",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "supply_warehouse_audit",
                (root / relative).read_text(encoding="utf-8"),
            )


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class SupplyWarehouseProjectionPostgresTests(unittest.TestCase):
    TABLES = (
        "supply_requests",
        "supply_deliveries",
        "estimate_row_supply_allocations",
        "supplier_invoices",
        "warehouse_invoices",
        "warehouse_history",
        "warehouse_receipt_lots",
        "warehouse_movements",
        "warehouse_lot_movements",
    )

    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(A7_TEST_DATABASE_URL)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            if not str(cur.fetchone()[0]).startswith("a7_"):
                raise RuntimeError(
                    "A7 integration fixture requires a dedicated a7_* database"
                )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.projects (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    name TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimates (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    version TEXT,
                    sections_json TEXT,
                    status TEXT,
                    is_template BOOLEAN,
                    smeta_type TEXT,
                    work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliations (
                    id INTEGER PRIMARY KEY,
                    base_estimate_id INTEGER,
                    next_estimate_id INTEGER,
                    status TEXT,
                    smeta_type TEXT,
                    work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_requests (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project TEXT,
                    status TEXT,
                    work_package TEXT,
                    items_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_deliveries (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    company_id INTEGER,
                    project TEXT,
                    work_package TEXT,
                    material_name TEXT,
                    unit TEXT,
                    received_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.estimate_row_supply_allocations (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    request_item_index INTEGER,
                    company_id INTEGER,
                    source_estimate_id INTEGER,
                    source_section_index INTEGER,
                    source_item_index INTEGER,
                    allocation_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.supplier_invoices (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    company_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    supply_request_id INTEGER,
                    supply_delivery_id INTEGER,
                    supplier_invoice_id INTEGER,
                    project TEXT,
                    items TEXT
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_history (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    work_package TEXT,
                    source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_receipt_lots (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    warehouse_invoice_id INTEGER,
                    invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_movements (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    work_package TEXT,
                    source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_lot_movements (
                    id INTEGER PRIMARY KEY,
                    lot_id INTEGER,
                    company_id INTEGER,
                    warehouse_movement_id INTEGER
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.warehouse_lot_movements,"
                "public.warehouse_movements,public.warehouse_receipt_lots,"
                "public.warehouse_history,public.warehouse_invoices,"
                "public.supplier_invoices,"
                "public.estimate_row_supply_allocations,"
                "public.supply_deliveries,public.supply_requests,"
                "public.estimate_reconciliations,public.estimates,"
                "public.projects CASCADE"
            )

    def _seed(self):
        base_sections = context()["baseSections"]
        target_sections = [{"name": "Target", "items": []}]
        item = request_item()
        item["estimateLineage"]["projectName"] = "Одинаковый объект"
        foreign_item = request_item()
        foreign_item["estimateLineage"]["projectName"] = "Одинаковый объект"
        foreign_item["estimateLineage"]["companyId"] = 5
        foreign_item["estimateLineage"]["projectId"] = 18
        foreign_item["estimateLineage"]["sources"][0]["estimateId"] = 61
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(17,4,'Одинаковый объект'),(18,5,'Одинаковый объект')"
            )
            cur.execute(
                """INSERT INTO public.estimates
                     (id,company_id,project_id,version,sections_json,status,
                      is_template,smeta_type,work_package)
                   VALUES
                     (51,4,17,'v1.0',%s,'Черновик',FALSE,'Заказчик','Основная'),
                     (52,4,17,'v2.0',%s,'Активная',FALSE,'Заказчик','Основная'),
                     (61,5,18,'v1.0',%s,'Черновик',FALSE,'Заказчик','Основная'),
                     (62,5,18,'v2.0',%s,'Активная',FALSE,'Заказчик','Основная')""",
                tuple(json.dumps(value, ensure_ascii=False) for value in (
                    base_sections, target_sections, base_sections, target_sections,
                )),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,work_package)
                   VALUES (91,51,52,'Черновик','Заказчик','Основная'),
                          (92,61,62,'Черновик','Заказчик','Основная')"""
            )
            cur.execute(
                """INSERT INTO public.supply_requests
                     (id,company_id,project,status,work_package,items_json)
                   VALUES (61,4,'Одинаковый объект','Новая','Основная',%s),
                          (62,5,'Одинаковый объект','Новая','Основная',%s)""",
                (
                    json.dumps([item], ensure_ascii=False),
                    json.dumps([foreign_item], ensure_ascii=False),
                ),
            )
            for company_id, offset, request_id, project_id in (
                (4, 0, 61, 17), (5, 1000, 62, 18),
            ):
                cur.execute(
                    """INSERT INTO public.supply_deliveries
                         (id,request_id,company_id,project,work_package,
                          material_name,unit,received_quantity)
                       VALUES (%s,%s,%s,'Одинаковый объект','Основная',
                               'Private material','кг',3)""",
                    (71 + offset, request_id, company_id),
                )
                cur.execute(
                    """INSERT INTO public.estimate_row_supply_allocations
                         (id,request_id,request_item_index,company_id,
                          source_estimate_id,source_section_index,
                          source_item_index,allocation_quantity)
                       VALUES (%s,%s,0,%s,%s,0,0,2)""",
                    (81 + offset, request_id, company_id, 51 if company_id == 4 else 61),
                )
                cur.execute(
                    "INSERT INTO public.supplier_invoices(id,request_id,company_id) "
                    "VALUES (%s,%s,%s)",
                    (91 + offset, request_id, company_id),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_invoices
                         (id,company_id,supply_request_id,supply_delivery_id,
                          supplier_invoice_id,project,items)
                       VALUES (%s,%s,%s,%s,%s,'Одинаковый объект',%s)""",
                    (
                        101 + offset, company_id, request_id, 71 + offset,
                        91 + offset,
                        json.dumps([{"name": "Private material"}]),
                    ),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_history
                         (id,company_id,work_package,source_invoice_id,
                          source_invoice_line_index)
                       VALUES (%s,%s,'Основная',%s,0)""",
                    (111 + offset, company_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_receipt_lots
                         (id,company_id,project_id,warehouse_invoice_id,
                          invoice_line_index)
                       VALUES (%s,%s,%s,%s,0)""",
                    (121 + offset, company_id, project_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_movements
                         (id,company_id,work_package,source_invoice_id,
                          source_invoice_line_index)
                       VALUES (%s,%s,'Основная',%s,0)""",
                    (131 + offset, company_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_lot_movements
                         (id,lot_id,company_id,warehouse_movement_id)
                       VALUES (%s,%s,%s,%s)""",
                    (141 + offset, 121 + offset, company_id, 131 + offset),
                )
        return build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=target_sections,
        )

    def _snapshot(self):
        result = {}
        with self.admin.cursor() as cur:
            for table in self.TABLES:
                cur.execute(
                    "SELECT row_to_json(t)::text FROM public." + table
                    + " t ORDER BY id"
                )
                result[table] = [row[0] for row in cur.fetchall()]
        return result

    def test_same_name_tenant_isolation_and_protected_rows_unchanged(self):
        exact_source = self._seed()
        before = self._snapshot()

        report = run_supply_warehouse_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL), exact_source,
        )

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(report["supplyWarehouseImpact"]["openSupply"][0]["requestId"], 61)
        self.assertEqual(
            report["supplyWarehouseImpact"]["protectedEvidence"],
            {
                "closedSupplyRequestIds": [],
                "deliveryIds": [71],
                "allocationIds": [81],
                "supplierInvoiceIds": [91],
                "warehouseInvoiceIds": [101],
                "warehouseHistoryIds": [111],
                "receiptLotIds": [121],
                "warehouseMovementIds": [131],
                "lotMovementIds": [141],
            },
        )
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_unrelated_requests_do_not_exhaust_the_exact_lineage_scan(self):
        exact_source = self._seed()
        unrelated_items = json.dumps([{
            "name": "Unrelated material",
            "estimateLineage": {
                "sources": [{"estimateId": 999999}],
            },
        }], ensure_ascii=False)
        with self.admin.cursor() as cur:
            cur.executemany(
                """INSERT INTO public.supply_requests
                     (id,company_id,project,status,work_package,items_json)
                   VALUES (%s,4,'Одинаковый объект','Новая','Основная',%s)""",
                [
                    (request_id, unrelated_items)
                    for request_id in range(1000, 1000 + MAX_DOMAIN_ROWS + 1)
                ],
            )

        report = run_supply_warehouse_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL), exact_source,
        )

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(
            report["supplyWarehouseImpact"]["summary"]["supplyRequestRows"],
            1,
        )



if __name__ == "__main__":
    unittest.main()
