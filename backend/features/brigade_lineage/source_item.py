"""Canonical estimate-row policy shared by brigade assignment routes."""

import math


def number(value):
    try:
        result = float(str(value if value is not None else 0).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def is_estimate_work_item(item):
    item = item or {}
    raw_type = str(item.get("itemType") or item.get("type") or item.get("kind") or "work").lower()
    excluded = (
        "material", "материал", "equipment", "оборуд", "delivery", "доставка",
        "other", "прочее", "note", "adjustment",
    )
    if any(token in raw_type for token in excluded):
        return False
    return not (number(item.get("priceMaterial")) > 0 and number(item.get("priceWork")) <= 0)


def _item_total(item):
    for field in (
        "totalWork", "lineTotal", "currentTotal", "total", "baseTotal",
        "estimatedCost", "workTotal", "workSum", "amount", "sum",
    ):
        total = number((item or {}).get(field))
        if abs(total) > 0:
            return total
    return 0.0


def estimate_item_unit_price(item):
    for field in (
        "customerPricePerUnit",
        "priceWork",
        "priceSmeta",
        "price",
        "baseUnitPrice",
    ):
        value = number((item or {}).get(field))
        if value > 0:
            return value
    quantity = number((item or {}).get("quantity"))
    total = _item_total(item)
    return round(total / quantity, 6) if quantity > 0 and total > 0 else 0.0
