"""Read-only document parties for shipments and receipts from immutable evidence."""

import hashlib
import json

from fastapi import HTTPException

from ..supplier_access.offer_party_snapshot import validate_offer_party_snapshot
from ..supplier_access.rfq_requester_snapshot import validate_rfq_requester_snapshot


def _fail():
    raise HTTPException(409, "Реквизиты поставки требуют сверки")


def _positive(value):
    if type(value) is not int or value <= 0:
        _fail()
    return value


def _text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        _fail()
    return value


def _party(source, identity_key):
    if not isinstance(source, dict):
        _fail()
    identity = _positive(source.get(identity_key))
    return {
        identity_key: identity,
        "fullName": _text(source.get("fullName")),
        "inn": _text(source.get("inn")),
        "kpp": _text(source.get("kpp")),
        "legalAddress": _text(source.get("legalAddress")),
        "phone": _text(source.get("phone")),
        "email": _text(source.get("email")),
    }


def _verified_contract(snapshot, snapshot_hash, contract_version_id, company_id, supplier_id):
    if not isinstance(snapshot, dict) or not isinstance(snapshot_hash, str):
        _fail()
    try:
        encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        _fail()
    if hashlib.sha256(encoded.encode()).hexdigest() != snapshot_hash:
        _fail()
    buyer = _party(snapshot.get("buyer"), "companyId")
    supplier = _party(snapshot.get("supplier"), "supplierId")
    if buyer["companyId"] != company_id or supplier["supplierId"] != supplier_id:
        _fail()
    return buyer, supplier, {
        "versionId": _positive(contract_version_id),
        "number": _text(snapshot.get("number")),
        "date": _text(snapshot.get("date")),
        "snapshotHash": snapshot_hash,
    }


def delivery_document_projection(
    *, delivery_id, request_id, offer_id, company_id, supplier_id, project_name,
    requester_snapshot, offer_snapshot, contract_version_id,
    source_supplier_invoice_id, contract_snapshot, contract_snapshot_hash,
    contract_company_id=None, contract_offer_id=None,
    source_invoice_company_id=None, source_invoice_supplier_id=None,
    source_invoice_request_id=None, source_invoice_offer_id=None,
    source_invoice_contract_version_id=None,
    **_ignored,
):
    """Build a safe passport without reading mutable company or supplier profiles."""
    ids = tuple(_positive(value) for value in (delivery_id, request_id, offer_id, company_id, supplier_id))
    delivery_id, request_id, offer_id, company_id, supplier_id = ids
    if not requester_snapshot or not offer_snapshot:
        return {
            "version": 1, "deliveryId": delivery_id, "requestId": request_id,
            "offerId": offer_id, "companyId": company_id, "supplierId": supplier_id,
            "reviewRequired": True,
            "reviewReason": "Историческая поставка без сохранённых реквизитов",
        }
    try:
        requester = validate_rfq_requester_snapshot(
            requester_snapshot, request_id=request_id, company_id=company_id,
            project_name=_text(project_name),
        )
        offer = validate_offer_party_snapshot(
            offer_snapshot, offer_id=offer_id, request_id=request_id,
            company_id=company_id, supplier_id=supplier_id,
        )
    except (ValueError, AttributeError, TypeError):
        _fail()

    contract = None
    if contract_version_id is not None or source_supplier_invoice_id is not None:
        if contract_version_id is None or source_supplier_invoice_id is None:
            _fail()
        if _positive(contract_company_id) != company_id or _positive(contract_offer_id) != offer_id:
            _fail()
        if (
            _positive(source_invoice_company_id) != company_id
            or _positive(source_invoice_supplier_id) != supplier_id
            or _positive(source_invoice_request_id) != request_id
            or _positive(source_invoice_offer_id) != offer_id
            or _positive(source_invoice_contract_version_id) != contract_version_id
        ):
            _fail()
        buyer, supplier, contract = _verified_contract(
            contract_snapshot, contract_snapshot_hash, contract_version_id,
            company_id, supplier_id,
        )
        source_invoice_id = _positive(source_supplier_invoice_id)
    else:
        if contract_snapshot is not None or contract_snapshot_hash is not None:
            _fail()
        buyer = _party({**offer["buyer"], "companyId": company_id}, "companyId")
        supplier = _party({**offer["supplier"], "supplierId": supplier_id}, "supplierId")
        source_invoice_id = None

    return {
        "version": 1,
        "deliveryId": delivery_id,
        "requestId": request_id,
        "offerId": offer_id,
        "companyId": company_id,
        "supplierId": supplier_id,
        "buyer": buyer,
        "supplier": supplier,
        "consignee": {
            "companyName": requester["companyName"],
            "projectName": requester["projectName"],
            "deliveryAddress": requester["deliveryAddress"],
            "contactName": requester["contactName"],
            "contactEmail": requester["contactEmail"],
            "contactPhone": requester["contactPhone"],
        },
        "supplierContact": offer["supplierContact"],
        "contract": contract,
        "sourceInvoiceId": source_invoice_id,
        "reviewRequired": False,
    }


def _review_projection(row, reason):
    return {
        "version": 1, "deliveryId": row["delivery_id"], "requestId": row["request_id"],
        "offerId": row["offer_id"], "companyId": row["company_id"],
        "supplierId": row["supplier_id"], "reviewRequired": True,
        "reviewReason": reason,
    }


def load_delivery_document_projections(cursor, delivery_ids, *, strict=True):
    ids = sorted({_positive(value) for value in delivery_ids if value is not None})
    if not ids:
        return {}
    cursor.execute(
        """SELECT d.id AS delivery_id,d.request_id,d.offer_id,d.company_id,d.supplier_id,d.project,
                  (to_jsonb(d)->>'contract_version_id')::bigint AS contract_version_id,
                  (to_jsonb(d)->>'source_supplier_invoice_id')::bigint AS source_supplier_invoice_id,
                  r.requester_snapshot_json,o.party_snapshot_json
             FROM supply_deliveries d
        LEFT JOIN supply_requests r ON r.id=d.request_id AND r.company_id=d.company_id
        LEFT JOIN supplier_offers o ON o.id=d.offer_id AND o.request_id=d.request_id
                                    AND o.company_id=d.company_id AND o.supplier_id=d.supplier_id
            WHERE d.id=ANY(%s)""",
        (ids,),
    )
    rows = list(cursor.fetchall() or [])
    if len(rows) != len(ids):
        _fail()
    contract_ids = sorted({row["contract_version_id"] for row in rows if row["contract_version_id"] is not None})
    contracts = {}
    if contract_ids:
        cursor.execute(
            """SELECT id,company_id,offer_id,snapshot_json,snapshot_hash
                 FROM supplier_contract_versions
                WHERE id=ANY(%s)""",
            (contract_ids,),
        )
        contracts = {row["id"]: row for row in (cursor.fetchall() or [])}
    invoice_ids = sorted({row["source_supplier_invoice_id"] for row in rows if row["source_supplier_invoice_id"] is not None})
    invoices = {}
    if invoice_ids:
        cursor.execute(
            """SELECT id,company_id,supplier_id,request_id,offer_id,
                      (to_jsonb(si)->>'contract_version_id')::bigint AS contract_version_id
                 FROM supplier_invoices si
                WHERE id=ANY(%s)""",
            (invoice_ids,),
        )
        invoices = {row["id"]: row for row in (cursor.fetchall() or [])}
    result = {}
    for row in rows:
        contract = contracts.get(row["contract_version_id"])
        invoice = invoices.get(row["source_supplier_invoice_id"])
        try:
            result[row["delivery_id"]] = delivery_document_projection(
                delivery_id=row["delivery_id"], request_id=row["request_id"],
                offer_id=row["offer_id"], company_id=row["company_id"],
                supplier_id=row["supplier_id"], project_name=row["project"],
                requester_snapshot=row["requester_snapshot_json"],
                offer_snapshot=row["party_snapshot_json"],
                contract_version_id=row["contract_version_id"],
                source_supplier_invoice_id=row["source_supplier_invoice_id"],
                contract_snapshot=(contract or {}).get("snapshot_json"),
                contract_snapshot_hash=(contract or {}).get("snapshot_hash"),
                contract_company_id=(contract or {}).get("company_id"),
                contract_offer_id=(contract or {}).get("offer_id"),
                source_invoice_company_id=(invoice or {}).get("company_id"),
                source_invoice_supplier_id=(invoice or {}).get("supplier_id"),
                source_invoice_request_id=(invoice or {}).get("request_id"),
                source_invoice_offer_id=(invoice or {}).get("offer_id"),
                source_invoice_contract_version_id=(invoice or {}).get("contract_version_id"),
            )
        except HTTPException:
            if strict:
                raise
            result[row["delivery_id"]] = _review_projection(
                row, "Связи документов поставки требуют сверки",
            )
    return result


def enrich_delivery_documents(cursor, rows, *, strict=False):
    documents = load_delivery_document_projections(
        cursor, [row.get("id") for row in rows], strict=strict,
    )
    for row in rows:
        row["documentParties"] = documents.get(row.get("id"))
    return rows
