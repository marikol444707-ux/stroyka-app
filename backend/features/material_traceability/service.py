"""Server-side validation for a receipt line used as a transfer source."""

import json


def _invoice_items_as_list(value):
    """Accept legacy TEXT and PostgreSQL JSON/JSONB driver values."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if isinstance(parsed, list):
        return parsed
    return [parsed] if isinstance(parsed, dict) else []


def resolve_invoice_line_source(invoice_id, invoice_line_index, invoice):
    """Return a canonical source reference, or ``None`` when no source was selected."""
    if invoice_id is None and invoice_line_index is None:
        return None
    if invoice_id is None or invoice_line_index is None:
        raise ValueError("Для выдачи из накладной укажите накладную и строку материала")

    try:
        invoice_id = int(invoice_id)
        invoice_line_index = int(invoice_line_index)
    except (TypeError, ValueError):
        raise ValueError("Неверная ссылка на накладную или строку материала")
    if invoice_id <= 0 or invoice_line_index < 0:
        raise ValueError("Неверная ссылка на накладную или строку материала")
    if not invoice:
        raise ValueError("Накладная для выдачи не найдена или аннулирована")

    items = _invoice_items_as_list(invoice.get("items"))
    if not isinstance(items, list) or invoice_line_index >= len(items):
        raise ValueError("Строка материала в накладной не найдена")

    return {
        "invoiceId": invoice_id,
        "invoiceLineIndex": invoice_line_index,
        "invoiceLineKey": f"warehouse_invoice:{invoice_id}:item:{invoice_line_index}",
        "invoiceNumber": str(invoice.get("number") or "").strip(),
    }


def ensure_source_quantity_available(invoice_item, allocated_quantity, requested_quantity):
    try:
        line_quantity = float((invoice_item or {}).get("quantity") or 0)
        allocated_quantity = float(allocated_quantity or 0)
        requested_quantity = float(requested_quantity or 0)
    except (TypeError, ValueError):
        raise ValueError("Не удалось определить доступное количество по строке накладной")
    available_quantity = max(0, line_quantity - allocated_quantity)
    if requested_quantity > available_quantity + 0.000001:
        raise ValueError(str(round(available_quantity, 6)))
    return available_quantity
