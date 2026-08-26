"""Stable identity rules for rejecting duplicate warehouse invoices."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import re
import unicodedata


_DOCUMENT_NUMBER_PREFIX = re.compile(
    r"^(?:(?:товарная|warehouse)\s+)?"
    r"(?:накладная|сч[её]т(?:\s*-\s*фактура)?|упд|invoice)\s*"
    r"(?:№|no\.?|n\.?|#)?\s*",
    re.IGNORECASE,
)
_NUMBER_MARK_PREFIX = re.compile(r"^(?:NO\.?|N\.?|#)\s*", re.IGNORECASE)
_SCAN_DRAFT_NUMBER = re.compile(r"^SCAN\d{8}\d{4}$", re.IGNORECASE)


def normalize_invoice_number(value) -> str:
    """Return a comparison-safe number; generated OCR drafts have no identity."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().upper().replace("Ё", "Е")
    text = _DOCUMENT_NUMBER_PREFIX.sub("", text)
    text = _NUMBER_MARK_PREFIX.sub("", text)
    normalized = "".join(character for character in text if character.isalnum())
    if _SCAN_DRAFT_NUMBER.fullmatch(normalized):
        return ""
    return normalized


def build_invoice_number_lookup_keys(value):
    """Return DB-side punctuation-stripped variants for a normalized number."""
    number_key = normalize_invoice_number(value)
    if not number_key:
        return tuple()
    prefixes = (
        "",
        "N",
        "NO",
        "INVOICE",
        "УПД",
        "СЧЕТ",
        "СЧЕТФАКТУРА",
        "НАКЛАДНАЯ",
        "ТОВАРНАЯНАКЛАДНАЯ",
    )
    return tuple(prefix + number_key for prefix in prefixes)


def normalize_invoice_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return ""
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date().isoformat()
        except ValueError:
            continue
    return text


def _amount_cents(value):
    try:
        amount = Decimal(str(value or "0").replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def match_warehouse_invoice_duplicate(
    *,
    incoming_number,
    incoming_date,
    incoming_total,
    incoming_items_signature,
    candidate_number,
    candidate_date,
    candidate_total,
    candidate_items_signature,
    same_supplier,
):
    """Return the matching rule name when two records are the same document."""
    incoming_number_key = normalize_invoice_number(incoming_number)
    candidate_number_key = normalize_invoice_number(candidate_number)
    incoming_date_key = normalize_invoice_date(incoming_date)
    candidate_date_key = normalize_invoice_date(candidate_date)
    dates_match = bool(
        incoming_date_key
        and candidate_date_key
        and incoming_date_key == candidate_date_key
    )
    incoming_cents = _amount_cents(incoming_total)
    candidate_cents = _amount_cents(candidate_total)
    totals_match = bool(
        incoming_cents is not None
        and candidate_cents is not None
        and incoming_cents == candidate_cents
    )
    incoming_signature = str(incoming_items_signature or "").strip()
    candidate_signature = str(candidate_items_signature or "").strip()
    items_match = bool(
        incoming_signature
        and candidate_signature
        and incoming_signature == candidate_signature
    )

    if incoming_number_key and candidate_number_key:
        if incoming_number_key != candidate_number_key:
            return None
        if dates_match and (same_supplier or (totals_match and items_match)):
            return "number_date"
        if same_supplier and totals_match and items_match:
            return "number_content"
        return None

    if dates_match and same_supplier and totals_match and items_match:
        return "content"
    return None


def build_warehouse_invoice_lock_keys(
    *,
    company_id,
    invoice_number,
    invoice_date,
    total_with_vat,
    items_signature,
):
    """Build stable transaction lock keys shared by concurrent duplicate uploads."""
    company_key = str(int(company_id or 0))
    number_key = normalize_invoice_number(invoice_number)
    date_key = normalize_invoice_date(invoice_date)
    amount_cents = _amount_cents(total_with_vat)
    items_key = str(items_signature or "").strip()
    raw_keys = []
    if number_key:
        raw_keys.append("company=" + company_key + "|number=" + number_key)
    if date_key and amount_cents is not None and items_key:
        raw_keys.append(
            "company=" + company_key
            + "|date=" + date_key
            + "|amount=" + str(amount_cents)
            + "|items=" + items_key
        )
    return tuple(
        sorted(
            "warehouse-invoice-duplicate:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
            for value in raw_keys
        )
    )
