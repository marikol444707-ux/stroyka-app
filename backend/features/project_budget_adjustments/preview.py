"""Bounded exact-total helpers for the read-only E6 adjustment preview."""

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .audit import MAX_PROJECT_BUDGET, MONEY_QUANTUM


DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_SECTIONS = 5000
DEFAULT_MAX_ITEMS = 50000


class BudgetAdjustmentPreviewError(ValueError):
    """Fixed-code preview error safe to expose at the HTTP boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _abort(code="budget_adjustment_estimate_content_invalid"):
    raise BudgetAdjustmentPreviewError(code)


def _decimal(value):
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, bool):
        _abort()
    if isinstance(value, str):
        value = value.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        if not value:
            return Decimal("0")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _abort()
    if not number.is_finite() or abs(number) >= MAX_PROJECT_BUDGET:
        _abort()
    return number


def _imported_total(item):
    work_total = _decimal(
        item.get("totalWork", item.get("workTotal", item.get("workSum")))
    )
    material_total = _decimal(
        item.get(
            "totalMaterial",
            item.get("materialTotal", item.get("materialSum")),
        )
    )
    if work_total or material_total:
        return work_total + material_total
    for field in (
        "lineTotal", "currentTotal", "total", "amount", "sum",
        "totalSum", "estimatedCost",
    ):
        total = _decimal(item.get(field))
        if total:
            return total
    return None


def _item_total(item):
    if not isinstance(item, dict):
        _abort()
    if item.get("isImported"):
        imported = _imported_total(item)
        if imported is not None:
            return imported
    quantity = _decimal(item.get("quantity"))
    work_price = _decimal(item.get("priceWork"))
    material_price = _decimal(item.get("priceMaterial"))
    total = quantity * (work_price + material_price)
    if not total.is_finite() or abs(total) >= MAX_PROJECT_BUDGET:
        _abort()
    return total


def _sections(raw_sections, max_bytes):
    if isinstance(raw_sections, str):
        if len(raw_sections.encode("utf-8")) > max_bytes:
            _abort("budget_adjustment_estimate_content_too_large")
        try:
            sections = json.loads(raw_sections)
        except (json.JSONDecodeError, RecursionError, UnicodeError):
            _abort()
    else:
        sections = raw_sections
    if not isinstance(sections, list):
        _abort()
    return sections


def calculate_sections_total(
    raw_sections,
    *,
    max_bytes=DEFAULT_MAX_BYTES,
    max_sections=DEFAULT_MAX_SECTIONS,
    max_items=DEFAULT_MAX_ITEMS,
):
    """Recompute one estimate total without returning or mutating its rows."""

    sections = _sections(raw_sections, max(0, int(max_bytes)))
    if len(sections) > max(0, int(max_sections)):
        _abort("budget_adjustment_estimate_content_too_large")
    total = Decimal("0")
    item_count = 0
    for section in sections:
        if not isinstance(section, dict):
            _abort()
        items = section.get("items", [])
        if not isinstance(items, list):
            _abort()
        item_count += len(items)
        if item_count > max(0, int(max_items)):
            _abort("budget_adjustment_estimate_content_too_large")
        for item in items:
            total += _item_total(item)
            if not total.is_finite() or abs(total) >= MAX_PROJECT_BUDGET:
                _abort()
    try:
        rounded = total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        _abort()
    if rounded < 0 or rounded >= MAX_PROJECT_BUDGET:
        _abort()
    return Decimal("0.00") if rounded == 0 else rounded


__all__ = [
    "BudgetAdjustmentPreviewError",
    "calculate_sections_total",
]
