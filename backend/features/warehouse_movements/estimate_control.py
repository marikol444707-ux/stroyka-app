REVIEW_STATUSES = {
    "no_active_estimate",
    "no_estimate_material",
    "over_estimate_need",
}


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_movement_estimate_control(items: list) -> dict:
    """Build a stable audit snapshot without blocking the stock movement."""
    rows = []
    issues = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        control = item.get("estimateControl") or {}
        check_status = str(control.get("status") or "not_checked").strip()
        if check_status in REVIEW_STATUSES and check_status not in issues:
            issues.append(check_status)
        rows.append({
            "materialName": item.get("materialName") or item.get("name") or "",
            "quantity": _number(item.get("quantity")),
            "unit": item.get("unit") or "",
            "workPackage": control.get("workPackage") or item.get("workPackage") or item.get("work_package") or "Основная",
            "checkStatus": check_status,
            "controlLabel": control.get("controlLabel") or "",
            "controlMessage": control.get("controlMessage") or "",
            "canonicalName": control.get("canonicalName") or "",
            "canonicalUnit": control.get("canonicalUnit") or "",
            "estimateId": control.get("estimateId"),
            "estimateName": control.get("estimateName") or "",
            "plannedQuantity": _number(control.get("plannedQty")),
            "remainingBeforeMovement": _number(control.get("remainingQty")),
            "remainingAfterMovement": _number(control.get("remainingAfterRequest")),
        })

    if not rows:
        status = "not_applicable"
    elif issues:
        status = "review_required"
    else:
        status = "matched"
    return {
        "status": status,
        "needsReview": bool(issues),
        "issues": issues,
        "items": rows,
    }
