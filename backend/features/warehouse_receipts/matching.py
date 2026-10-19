"""Read-only, conservative matching of an OCR waybill to authorized shipments.

The caller MUST authorize every candidate before calling and supply companyId from
server context, never OCR. document contains documentType (waybill/delivery_note/
upd), waybillNumber, waybillDate, supplierInn, buyerInn and lines with materialName,
unit, quantity. Candidate batches contain id, companyId, supplierId, the waybill
fields, frozen documentParties {buyer: {companyId, inn}, supplier: {inn}} and lines
with id, materialName, unit, shippedQuantity, receivedQuantity, receivedAt, status,
warehouseInvoiceId. This function neither authorizes access nor posts inventory.
Only exact frozen-party headers are eligible for explicit selection. A selected
batch still requires complete line validation and a separate authorized,
transactional receiving operation. Candidate authorization belongs to the caller.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata

from .duplicate_guard import normalize_invoice_date, normalize_invoice_number


_ACCEPTED = {"accepted", "received", "принято"}
_WAYBILLS = {"waybill", "delivery_note", "upd"}


def _text(value):
    if not isinstance(value, str) or len(value) > 1000:
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    raw = str(value)
    return int(raw) if re.fullmatch(r"[1-9][0-9]{0,18}", raw) else None


def _inn(value):
    # No names, numeric coercion, punctuation stripping or fuzzy identity.
    return value.strip() if isinstance(value, str) and re.fullmatch(
        r"(?:[0-9]{10}|[0-9]{12})", value.strip()
    ) else ""


def _date(value):
    if not isinstance(value, (str, date, datetime)):
        return ""
    if isinstance(value, str) and not re.fullmatch(
        r"(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}[./][0-9]{2}[./][0-9]{4})", value.strip()
    ):
        return ""
    normalized = normalize_invoice_date(value)
    try:
        return date.fromisoformat(normalized).isoformat()
    except (ValueError, TypeError):
        return ""


def _quantity(value, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    raw = str(value).strip()
    if len(raw) > 64 or not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,4})?", raw):
        return None
    try:
        result = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return None
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero):
        return None
    return result


def _result(status, *reasons, **values):
    return {"status": status, "reasons": list(reasons), "postingAllowed": False, **values}


def _has_receipt(batch):
    lines = batch.get('lines')
    if not isinstance(lines, list) or not lines:
        return True
    for line in lines:
        if not isinstance(line, dict):
            return True
        received = _quantity(line.get('receivedQuantity', 0), allow_zero=True)
        if (received is None or received > 0 or line.get('receivedAt')
                or line.get('warehouseInvoiceId') is not None
                or _text(line.get('status')) in _ACCEPTED | {'проблема'}):
            return True
    return False


def _lines(values, quantity_key, *, candidate=False):
    if not isinstance(values, list) or not values or len(values) > 1000:
        return None, "invalid_lines"
    indexed = {}
    ids = set()
    for index, line in enumerate(values):
        if not isinstance(line, dict):
            return None, "invalid_line"
        key = (_text(line.get("materialName")), _text(line.get("unit")))
        quantity = _quantity(line.get(quantity_key))
        if not all(key) or quantity is None:
            return None, "invalid_line_identity_or_quantity"
        if key in indexed:
            return None, "duplicate_line_identity"
        if candidate:
            line_id = _id(line.get("id"))
            if line_id is None or line_id in ids:
                return None, "invalid_or_duplicate_line_id"
            ids.add(line_id)
        indexed[key] = (index, quantity, line)
    return indexed, None


def resolve_document_match(document, candidates, *, selected_batch_id=None,
                           explicit_selection_confirmed=False, source_supplier_invoice_id=None):
    """Return status match/ambiguous/no_match/review, reasons and proven IDs.

    receiptState on match is unreceived, partial or existing. Ambiguous headers
    are never disambiguated with OCR line guesses. An explicit selection only
    narrows exact legal/header candidates; it cannot override identity or lines.
    Foreign company batches are ignored without returning IDs.
    """
    if not isinstance(document, dict) or not isinstance(candidates, (list, tuple)):
        return _result("review", "invalid_input")
    company_id = _id(document.get("companyId"))
    if company_id is None:
        return _result("review", "missing_company_scope")
    if _text(document.get("documentType")) not in _WAYBILLS:
        return _result("review", "document_type_requires_review")
    supplier_inn, buyer_inn = _inn(document.get("supplierInn")), _inn(document.get("buyerInn"))
    if not supplier_inn or not buyer_inn:
        return _result("review", "missing_legal_identity")
    raw_number = document.get("waybillNumber")
    number = normalize_invoice_number(raw_number) if isinstance(raw_number, str) else ""
    day = _date(document.get("waybillDate"))
    if not number or not day:
        return _result("review", "invalid_waybill_identity")
    incoming, error = _lines(document.get("lines"), "quantity")
    if error:
        return _result("review", error)
    if selected_batch_id is not None:
        selected_batch_id = _id(selected_batch_id)
        if selected_batch_id is None:
            return _result("review", "invalid_batch_selection")
        if explicit_selection_confirmed is not True:
            return _result("review", "explicit_selection_required")

    matches = []
    incomplete = False
    for batch in candidates:
        if not isinstance(batch, dict):
            incomplete = True
            continue
        batch_company = _id(batch.get("companyId"))
        if batch_company is None:
            incomplete = True
            continue
        if batch_company != company_id:
            continue
        batch_number = batch.get("waybillNumber")
        if not isinstance(batch_number, str) or not _date(batch.get("waybillDate")):
            incomplete = True
            continue
        if normalize_invoice_number(batch_number) != number or _date(batch.get("waybillDate")) != day:
            continue
        parties = batch.get("documentParties")
        buyer = parties.get("buyer") if isinstance(parties, dict) else None
        supplier = parties.get("supplier") if isinstance(parties, dict) else None
        if not isinstance(buyer, dict) or not isinstance(supplier, dict):
            incomplete = True
            continue
        if (not _inn(buyer.get("inn")) or not _inn(supplier.get("inn"))
                or _id(buyer.get("companyId")) != company_id
                or _id(batch.get("id")) is None or _id(batch.get("supplierId")) is None):
            incomplete = True
            continue
        if "supplierId" in supplier and _id(supplier["supplierId"]) != _id(batch["supplierId"]):
            incomplete = True
            continue
        if _inn(buyer["inn"]) == buyer_inn and _inn(supplier["inn"]) == supplier_inn:
            matches.append(batch)
    all_matches = matches
    if source_supplier_invoice_id is not None:
        matches = [batch for batch in matches
                   if _id(batch.get('sourceSupplierInvoiceId')) == source_supplier_invoice_id]
    if selected_batch_id is not None:
        # Never use a direct ID lookup: the ID must survive the same server-side
        # company, legal-party and waybill eligibility checks as every candidate.
        selected = [batch for batch in matches if _id(batch["id"]) == selected_batch_id]
        if len(selected) != 1:
            return _result("review", "selected_batch_not_eligible")
        matches = selected
    elif len(matches) > 1:
        return _result("ambiguous", "multiple_batches",
                       candidateBatchIds=[_id(batch["id"]) for batch in matches])
    if incomplete and selected_batch_id is None:
        return _result("review", "incomplete_candidate_identity")
    if not matches:
        return _result("no_match", "no_exact_legal_waybill_match")
    batch = matches[0]
    if any(other is not batch and _has_receipt(other) for other in all_matches):
        return _result('review', 'another_batch_already_received')
    outgoing, error = _lines(batch.get("lines"), "shippedQuantity", candidate=True)
    if error:
        return _result("review", error)
    if incoming.keys() != outgoing.keys():
        return _result("review", "line_identity_or_unit_mismatch")
    if any(incoming[key][1] != outgoing[key][1] for key in incoming):
        return _result("review", "quantity_mismatch")

    received_count = 0
    accepted_count = 0
    invoice_ids = set()
    line_ids = []
    for key in incoming:
        _, shipped, line = outgoing[key]
        received = _quantity(line.get("receivedQuantity", 0), allow_zero=True)
        if received is None or received > shipped:
            return _result("review", "invalid_received_quantity")
        invoice_id = _id(line.get("warehouseInvoiceId"))
        if line.get("warehouseInvoiceId") is not None and invoice_id is None:
            return _result("review", "invalid_receipt_reference")
        accepted = _text(line.get("status")) in _ACCEPTED
        if received > 0 or line.get("receivedAt") or invoice_id or accepted:
            received_count += 1
        if accepted and received == shipped and invoice_id:
            accepted_count += 1
        if invoice_id:
            invoice_ids.add(invoice_id)
        line_ids.append(_id(line["id"]))
    state = "existing" if accepted_count == len(incoming) else "partial" if received_count else "unreceived"
    return _result(
        "match", "exact_legal_waybill_and_lines", batchId=_id(batch["id"]),
        companyId=company_id, supplierId=_id(batch["supplierId"]), lineIds=line_ids,
        warehouseInvoiceIds=sorted(invoice_ids), receiptState=state,
    )
