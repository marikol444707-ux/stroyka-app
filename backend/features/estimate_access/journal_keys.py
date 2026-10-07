"""Identifiers shared by the worker's filtered estimate and the full journal."""


def journal_item_keys(estimate_id, section_idx, item_idx, section_name, item_name, item=None):
    item = item or {}
    candidates = [
        item.get("estimateItemKey"),
        item.get("estimate_item_key"),
        item.get("workKey"),
        item.get("work_key"),
        item.get("key"),
        item.get("id"),
        f"{estimate_id}:{section_idx}:{item_idx}",
        f"{section_idx}:{item_idx}",
        f"{section_name or ''}|{item_name or ''}",
    ]
    return list(dict.fromkeys(str(value).strip() for value in candidates if value is not None and str(value).strip()))
