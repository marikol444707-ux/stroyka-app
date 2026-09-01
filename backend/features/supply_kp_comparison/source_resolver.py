"""Read-only source resolver for deterministic supply comparison.

The A8.5.2 boundary deliberately stops before ranking or any business action.
It resolves one request, one selected supplier offer/invoice and one protected
file inside an exact company/project scope, then delegates line comparison to
the pure A8.5.1 technical matcher.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Mapping

import psycopg2.extras

from backend.features.document_access.service import (
    require_document_storage_identity,
)
from backend.features.supply_kp_comparison.technical_matcher import (
    compare_required_to_offer,
)


CONTRACT_VERSION = 1
MAX_JSON_BYTES = 512 * 1024
MAX_LINES = 100
MAX_TEXT_BYTES = 4 * 1024
MAX_DECIMAL_DIGITS = 64
MAX_DECIMAL_INTEGER_DIGITS = 24
MAX_DECIMAL_SCALE = 12
SOURCE_KINDS = frozenset(("supplier_offer", "supplier_invoice"))
_INVALID = "supply_technical_source_resolver_invalid"


class SupplyTechnicalSourceResolverError(ValueError):
    """One fixed, non-leaking failure for invalid or cross-scope sources."""

    def __init__(self):
        self.code = _INVALID
        super().__init__(self.code)


def _fail():
    raise SupplyTechnicalSourceResolverError()


def _positive_int(value):
    if type(value) is not int or value <= 0:
        _fail()
    return value


def _mapping(value):
    if not isinstance(value, Mapping):
        _fail()
    return dict(value)


def _text(value, *, max_bytes=MAX_TEXT_BYTES, allow_empty=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        _fail()
    result = value.strip()
    if (not allow_empty and not result) or len(result.encode("utf-8")) > max_bytes:
        _fail()
    return result


def _decimal(value, *, required=False):
    if value in (None, ""):
        if required:
            _fail()
        return None
    if isinstance(value, bool):
        _fail()
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail()
    if not result.is_finite() or (required and result <= 0):
        _fail()
    decimal_tuple = result.as_tuple()
    if (
        len(decimal_tuple.digits) > MAX_DECIMAL_DIGITS
        or result.adjusted() >= MAX_DECIMAL_INTEGER_DIGITS
        or decimal_tuple.exponent < -MAX_DECIMAL_SCALE
    ):
        _fail()
    return result


def _decimal_text(value):
    result = format(value, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result or "0"


def _json_list(value):
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_JSON_BYTES:
            _fail()
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            _fail()
    elif isinstance(value, (list, tuple)):
        try:
            encoded = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        except (TypeError, ValueError):
            _fail()
        if len(encoded) > MAX_JSON_BYTES:
            _fail()
    else:
        _fail()
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= MAX_LINES:
        _fail()
    return [_mapping(item) for item in value]


def _line(item, *, fallback_name="", fallback_quantity=None, fallback_unit="", fallback_package=""):
    name = _text(
        item.get("materialName") or item.get("material_name") or item.get("name") or fallback_name,
    )
    unit = _text(item.get("unit") or fallback_unit, max_bytes=64)
    quantity = _decimal(item.get("quantity", item.get("qty", fallback_quantity)), required=True)
    work_package = _text(
        item.get("workPackage") or item.get("work_package") or fallback_package or "Основная",
        max_bytes=512,
    )
    category = _text(item.get("category") or "", max_bytes=512, allow_empty=True)
    return {
        "name": name,
        "unit": unit,
        "quantity": _decimal_text(quantity),
        "workPackage": work_package,
        "category": category,
    }


def _request_lines(request):
    raw_items = request.get("items_json")
    if raw_items not in (None, "", [], ()):
        items = _json_list(raw_items)
    else:
        items = [{}]
    return [
        _line(
            item,
            fallback_name=request.get("material_name") or "",
            fallback_quantity=request.get("quantity"),
            fallback_unit=request.get("unit") or "",
            fallback_package=request.get("work_package") or "Основная",
        )
        for item in items
    ]


def _offered_lines(source):
    return [_line(item) for item in _json_list(source.get("items_kp_json"))]


def _canonical_sha256(value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_row_identity(row, *, row_id, company_id, request_id=None, project_id=None):
    if _positive_int(row.get("id")) != row_id:
        _fail()
    if _positive_int(row.get("company_id")) != company_id:
        _fail()
    if request_id is not None and _positive_int(row.get("request_id")) != request_id:
        _fail()
    if project_id is not None and _positive_int(row.get("project_id")) != project_id:
        _fail()


def _validate_selector(company_id, project_id, request_id, source_kind, source_id, file_id):
    company_id = _positive_int(company_id)
    project_id = _positive_int(project_id)
    request_id = _positive_int(request_id)
    source_id = _positive_int(source_id)
    file_id = _positive_int(file_id)
    if type(source_kind) is not str or source_kind not in SOURCE_KINDS:
        _fail()
    return company_id, project_id, request_id, source_kind, source_id, file_id


def _protected_file(file_row, source_file_ref, *, company_id, project_id, file_id, s3_prefixes):
    _require_row_identity(
        file_row,
        row_id=file_id,
        company_id=company_id,
        project_id=project_id,
    )
    if _text(file_row.get("deletion_status") or "active", max_bytes=30).lower() != "active":
        _fail()
    context = _text(file_row.get("context") or "general", max_bytes=100)
    file_url = _text(file_row.get("file_url"))
    storage_key = _text(file_row.get("storage_key") or "", allow_empty=True)
    protected_url = "/tenant-files/{}/content".format(file_id)
    if _text(source_file_ref) not in (protected_url, file_url):
        _fail()
    try:
        require_document_storage_identity(
            company_id,
            project_id,
            context,
            file_url,
            storage_key,
            s3_prefix=s3_prefixes,
            expected_s3_urls=(file_url,),
        )
    except Exception:
        _fail()
    original_name = _text(
        file_row.get("original_name") or "",
        max_bytes=1024,
        allow_empty=True,
    )
    content_type = _text(
        file_row.get("content_type") or "",
        max_bytes=255,
        allow_empty=True,
    )
    return {
        "id": file_id,
        "contentUrl": protected_url,
        "context": context,
        "originalName": original_name,
        "contentType": content_type,
    }


def resolve_supply_technical_source_rows(
    rows,
    *,
    company_id,
    project_id,
    request_id,
    source_kind,
    source_id,
    file_id,
    s3_prefixes=("uploads",),
):
    """Validate resolved rows and compare their lines without side effects."""

    company_id, project_id, request_id, source_kind, source_id, file_id = _validate_selector(
        company_id,
        project_id,
        request_id,
        source_kind,
        source_id,
        file_id,
    )
    if isinstance(s3_prefixes, str):
        s3_prefixes = (s3_prefixes,)
    if not isinstance(s3_prefixes, (tuple, list)) or not s3_prefixes:
        _fail()

    resolved = _mapping(rows)
    request = _mapping(resolved.get("request"))
    source = _mapping(resolved.get("source"))
    file_row = _mapping(resolved.get("file"))

    _require_row_identity(
        request,
        row_id=request_id,
        company_id=company_id,
        project_id=project_id,
    )
    project_name = _text(request.get("project"))
    _require_row_identity(
        source,
        row_id=source_id,
        company_id=company_id,
        request_id=request_id,
    )
    if source_kind == "supplier_invoice":
        if _positive_int(source.get("offer_id")) <= 0:
            _fail()
        if _positive_int(source.get("offer_company_id")) != company_id:
            _fail()
        if _positive_int(source.get("offer_request_id")) != request_id:
            _fail()
        if _text(source.get("project_name")) != project_name:
            _fail()

    protected_file = _protected_file(
        file_row,
        source.get("source_file_ref"),
        company_id=company_id,
        project_id=project_id,
        file_id=file_id,
        s3_prefixes=tuple(s3_prefixes),
    )
    requested_lines = _request_lines(request)
    offered_lines = _offered_lines(source)
    if len(requested_lines) != len(offered_lines):
        _fail()

    comparisons = []
    for index, (required, offered) in enumerate(zip(requested_lines, offered_lines), start=1):
        if required["quantity"] != offered["quantity"]:
            _fail()
        required_package = required["workPackage"].casefold()
        offered_package = offered["workPackage"].casefold()
        if required_package != offered_package:
            _fail()
        category = required["category"] or _text(
            request.get("category") or "",
            max_bytes=512,
            allow_empty=True,
        )
        comparison = compare_required_to_offer(
            required["name"],
            offered["name"],
            required_unit=required["unit"],
            offered_unit=offered["unit"],
            category=category,
        )
        comparisons.append(
            {
                "lineNumber": index,
                "required": required,
                "offered": offered,
                "result": comparison.to_dict(),
            }
        )

    hash_payload = {
        "contractVersion": CONTRACT_VERSION,
        "companyId": company_id,
        "projectId": project_id,
        "requestId": request_id,
        "sourceKind": source_kind,
        "sourceId": source_id,
        "fileId": file_id,
        "comparisonHashes": [item["result"]["comparisonSha256"] for item in comparisons],
    }
    return {
        "ok": True,
        "dryRun": True,
        "contractVersion": CONTRACT_VERSION,
        "companyId": company_id,
        "projectId": project_id,
        "requestId": request_id,
        "sourceKind": source_kind,
        "sourceId": source_id,
        "file": protected_file,
        "requestedLineCount": len(requested_lines),
        "offeredLineCount": len(offered_lines),
        "comparisonCount": len(comparisons),
        "comparisons": comparisons,
        "resultSha256": _canonical_sha256(hash_payload),
        "automaticApprovalAllowed": False,
        "writesAttempted": 0,
        "modelCalls": 0,
    }


def load_supply_technical_source_rows(
    cursor,
    *,
    company_id,
    project_id,
    request_id,
    source_kind,
    source_id,
    file_id,
):
    """Load three exact-scope records using SELECT statements only."""

    company_id, project_id, request_id, source_kind, source_id, file_id = _validate_selector(
        company_id,
        project_id,
        request_id,
        source_kind,
        source_id,
        file_id,
    )

    cursor.execute(
        """
        SELECT r.id,r.company_id,p.id AS project_id,r.project,r.material_name,
               r.quantity,r.unit,r.category,COALESCE(r.work_package,'Основная') AS work_package,
               r.items_json
          FROM supply_requests r
          JOIN projects p
            ON p.id=%s AND p.company_id=r.company_id AND p.name=r.project
         WHERE r.id=%s AND r.company_id=%s
           AND COALESCE(p.archived,FALSE)=FALSE
        """,
        (project_id, request_id, company_id),
    )
    request = cursor.fetchone()
    if source_kind == "supplier_offer":
        cursor.execute(
            """
            SELECT o.id,o.company_id,o.request_id,o.pdf_url AS source_file_ref,
                   o.items_kp_json
              FROM supplier_offers o
             WHERE o.id=%s AND o.request_id=%s AND o.company_id=%s
            """,
            (source_id, request_id, company_id),
        )
    elif source_kind == "supplier_invoice":
        cursor.execute(
            """
            SELECT i.id,i.company_id,i.request_id,i.offer_id,i.project_name,
                   COALESCE(NULLIF(i.file_url,''),NULLIF(i.photo_url,'')) AS source_file_ref,
                   o.company_id AS offer_company_id,o.request_id AS offer_request_id,
                   o.items_kp_json
              FROM supplier_invoices i
              JOIN supplier_offers o
                ON o.id=i.offer_id
               AND o.company_id=i.company_id
               AND o.request_id=i.request_id
             WHERE i.id=%s AND i.request_id=%s AND i.company_id=%s
            """,
            (source_id, request_id, company_id),
        )
    else:
        _fail()
    source = cursor.fetchone()
    cursor.execute(
        """
        SELECT id,company_id,project_id,file_url,storage_key,context,
               original_name,content_type,COALESCE(deletion_status,'active') AS deletion_status
          FROM file_ownership
         WHERE id=%s AND company_id=%s AND project_id=%s
        """,
        (file_id, company_id, project_id),
    )
    file_row = cursor.fetchone()
    return {"request": request, "source": source, "file": file_row}


def run_supply_technical_source_resolver(connection, **values):
    """Run A8.5.2 in a read-only repeatable-read transaction and roll it back."""

    connection.set_session(
        readonly=True,
        autocommit=False,
        isolation_level="REPEATABLE READ",
    )
    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    result = None
    try:
        rows = load_supply_technical_source_rows(
            cursor,
            company_id=values.get("company_id"),
            project_id=values.get("project_id"),
            request_id=values.get("request_id"),
            source_kind=values.get("source_kind"),
            source_id=values.get("source_id"),
            file_id=values.get("file_id"),
        )
        result = resolve_supply_technical_source_rows(rows, **values)
    finally:
        try:
            cursor.close()
        finally:
            connection.rollback()
    result["rolledBack"] = True
    return result
