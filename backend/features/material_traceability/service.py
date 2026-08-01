"""Server-side validation for a receipt line used as a transfer source."""

import json


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

    try:
        items = json.loads(invoice.get("items") or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        items = []
    if not isinstance(items, list) or invoice_line_index >= len(items):
        raise ValueError("Строка материала в накладной не найдена")

    return {
        "invoiceId": invoice_id,
        "invoiceLineIndex": invoice_line_index,
        "invoiceLineKey": f"warehouse_invoice:{invoice_id}:item:{invoice_line_index}",
        "invoiceNumber": str(invoice.get("number") or "").strip(),
    }
