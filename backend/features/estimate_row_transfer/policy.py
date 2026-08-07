"""Shared fail-closed policy for supply balances visible as `requested`."""


ALLOCATABLE_SUPPLY_STATUSES = (
    "Новая",
    "Подтверждена прорабом",
    "Утверждена",
    "КП запрошены",
)

EXPLICIT_MATERIAL_ITEM_TYPES = frozenset((
    "material",
    "materials",
    "материал",
    "материалы",
))


def is_explicit_material_item(item):
    """Return true only for an estimate row explicitly stored as material."""

    if not isinstance(item, dict):
        return False
    raw_type = item.get("itemType") or item.get("type")
    return (
        isinstance(raw_type, str)
        and raw_type.strip().lower() in EXPLICIT_MATERIAL_ITEM_TYPES
    )
