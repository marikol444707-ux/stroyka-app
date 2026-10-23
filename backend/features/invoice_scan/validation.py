"""Check OCR arithmetic without guessing quantities or removing repeated goods."""
from decimal import Decimal, InvalidOperation
import re


TABLE_INSTRUCTIONS = (
    "Для УПД и счетов-фактур читай заголовки колонок: колонка 2 — код единицы ОКЕИ, "
    "2а — обозначение единицы, 3 — количество, 4 — цена без НДС, 5 — сумма без НДС, "
    "8 — сумма НДС, 9 — сумма строки с НДС. Код ОКЕИ 796 означает шт, 166 — кг, "
    "006 — м; код единицы не является количеством. quantity бери только из колонки количества. "
    "Одинаковые названия в разных строках с разными артикулами сохраняй отдельно. "
    "lineTotalWithVat бери из колонки 9, priceWithVat вычисляй как lineTotalWithVat / quantity, "
    "а не умножением округленной цены без НДС на ставку. Не округляй цену до двух знаков, "
    "если это меняет сумму строки. Сумму всех строк сверяй с итогом документа. "
    "Не подгоняй количество или суммы под итог; неразборчивое значение оставь null. "
)


def number(value):
    if value is None or isinstance(value, bool) or value == "":
        return None
    text = re.sub(r"\s+", "", str(value)).replace("₽", "")
    text = re.sub(r"руб\.?$", "", text, flags=re.I)
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() and abs(result) <= Decimal("1e15") else None


def first(data, *keys):
    for key in keys:
        if data.get(key) not in (None, ""):
            return number(data[key])
    return None


def present(data, *keys):
    return any(data.get(key) not in (None, "") for key in keys)


def validate_invoice_scan(payload):
    """Return current errors; never trust a cached 'valid' flag from the client/model."""
    errors = []
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    rows_total = Decimal(0)
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue  # Existing receipt validation handles empty form placeholders.
        quantity = first(item, "quantity", "qty")
        price = first(item, "priceWithVat", "price_with_vat", "price", "unitPrice", "unit_price")
        total = first(item, "lineTotalWithVat", "line_total_with_vat", "lineTotal", "line_total", "total")
        invalid_total = total is None and present(item, "lineTotalWithVat", "line_total_with_vat", "lineTotal", "line_total", "total")
        if quantity is None or quantity <= 0 or price is None or price < 0 or invalid_total or (total is not None and total < 0):
            errors.append({"code": "invalid_line", "row": index, "message": f"Строка {index}: проверьте количество, цену и сумму."})
            continue
        calculated = quantity * price
        if total is None:
            total = calculated
        # A printed unit price may be rounded. Allow its rounding error, not a
        # percentage of the document total (which would hide large mistakes).
        places = min(4, max(2, -price.as_tuple().exponent))
        tolerance = abs(quantity) * (Decimal(10) ** -places) / 2 + Decimal("0.01")
        if abs(total - calculated) > tolerance:
            errors.append({"code": "line_total_mismatch", "row": index, "message": f"Строка {index}: количество × цена не совпадает с суммой строки."})
        rows_total += total
    declared = first(payload, "totalWithVat", "total_with_vat", "grandTotal", "total")
    if declared is None and present(payload, "totalWithVat", "total_with_vat", "grandTotal", "total") or declared is not None and declared < 0:
        errors.append({"code": "invalid_document_total", "message": "Проверьте итог документа."})
    tolerance = max(Decimal("0.02"), Decimal(len(items)) * Decimal("0.01"))
    if declared is not None and declared > 0 and abs(rows_total - declared) > tolerance:
        errors.append({"code": "document_total_mismatch", "message": "Сумма строк не совпадает с итогом документа. Сверьте количество, цену и НДС с оригиналом."})
    return {"valid": not errors, "errors": errors, "itemsTotal": float(round(rows_total, 2)),
            "documentTotal": float(declared) if declared is not None else None}
