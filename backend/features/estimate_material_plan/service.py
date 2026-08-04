import re


def is_resource_adjustment(item: dict, *, imported_quantity: float, line_total: float) -> bool:
    raw = str(item.get("itemType") or item.get("type") or item.get("kind") or "").strip().lower()
    source_code = str(item.get("sourceCode") or item.get("obosn") or item.get("code") or "").strip()
    name = " ".join(str(item.get("name") or "").lower().replace("ё", "е").split())
    explicit_adjustment = raw in ("adjustment", "корректировка") or item.get("importKind") == "resource_adjustment"
    source_looks_resource = bool(
        re.match(r"^\d{2,}[-/]\d+", source_code)
        or re.match(r"^\d{3,}$", source_code)
        or re.match(r"^(ТЦ_|ФСБЦ|ФССЦ)", source_code, re.I)
    )
    strong_work = any(marker in name for marker in (
        "монтаж", "установка", "устройство", "демонтаж", "разбор", "прокладка", "ремонт",
    ))
    return (explicit_adjustment or source_looks_resource) and not strong_work and (
        imported_quantity < 0 or line_total < 0
    )


def material_plan_contribution(
    *,
    is_material: bool,
    is_adjustment: bool,
    imported_quantity: float,
    material_sum: float,
    item_sum: float,
    plan_issue: str = "",
):
    """Return quantity, sum and adjustment marker for one estimate resource row."""
    if not is_material and not is_adjustment:
        return None
    if is_adjustment:
        if imported_quantity >= 0:
            return None
        return imported_quantity, item_sum, True
    if imported_quantity <= 0 or plan_issue:
        return None
    return imported_quantity, material_sum if material_sum > 0 else item_sum, False
