"""Pure text, quantity and delivery-identity policy for A8 RFQ previews."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation


MAX_MATERIAL_TEXT_LENGTH = 200
MAX_UNIT_TEXT_LENGTH = 50
MAX_PACKAGE_TEXT_LENGTH = 100
MAX_QUANTITY_INTEGER_DIGITS = 14


def bounded_text(value, maximum):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if (
        not value
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        return None
    return value


def canonical_package(value):
    if value in (None, ""):
        return "Основная"
    return bounded_text(value, MAX_PACKAGE_TEXT_LENGTH)


def bounded_decimal(value, *, positive=False):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number.as_tuple().exponent < -6:
        return None
    if number <= 0 if positive else number < 0:
        return None
    integer_digits = max(number.adjusted() + 1, 0) if number else 0
    if integer_digits > MAX_QUANTITY_INTEGER_DIGITS:
        return None
    return number


def quantity_text(value):
    return format(value, ".6f")


def has_competing_delivery_identity(items, selected_index, material_name, unit):
    """Detect a sibling that makes request-level delivery attribution unsafe."""

    for item_index, sibling in enumerate(items):
        if item_index == selected_index or not isinstance(sibling, Mapping):
            continue
        names = {
            bounded_text(sibling.get(field), MAX_MATERIAL_TEXT_LENGTH)
            for field in ("materialName", "material_name", "name")
            if sibling.get(field) not in (None, "")
        }
        sibling_unit = bounded_text(sibling.get("unit"), MAX_UNIT_TEXT_LENGTH)
        if material_name in names and sibling_unit in (None, unit):
            return True
    return False


__all__ = [
    "MAX_MATERIAL_TEXT_LENGTH",
    "MAX_UNIT_TEXT_LENGTH",
    "bounded_decimal",
    "bounded_text",
    "canonical_package",
    "has_competing_delivery_identity",
    "quantity_text",
]
