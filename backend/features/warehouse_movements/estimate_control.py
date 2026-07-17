REVIEW_STATUSES = {
    "no_active_estimate",
    "no_estimate_material",
    "over_estimate_need",
}

ISSUE_LABELS = {
    "no_active_estimate": "по объекту нет активной сметы",
    "no_estimate_material": "материал не найден в активной смете",
    "over_estimate_need": "количество превышает оставшуюся сметную потребность",
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


def build_movement_review_task(
    *,
    movement_id: int,
    project_name: str,
    actor_name: str,
    estimate_control: dict,
):
    control = dict(estimate_control or {})
    if not control.get("needsReview"):
        return None
    items = [item for item in (control.get("items") or []) if isinstance(item, dict)]
    item = items[0] if items else {}
    issues = [str(issue) for issue in (control.get("issues") or []) if str(issue) in REVIEW_STATUSES]
    material_name = str(item.get("materialName") or "Материал").strip()
    quantity = _number(item.get("quantity"))
    unit = str(item.get("unit") or "").strip()
    work_package = str(item.get("workPackage") or "Основная").strip()
    marker = "WAREHOUSE_MOVEMENT_ESTIMATE:" + str(int(movement_id))
    reasons = [ISSUE_LABELS[issue] for issue in issues]
    description = [
        "Складское перемещение проведено, но требует сметного разбора.",
        "Объект: " + str(project_name or "") + ".",
        "Материал: " + material_name + f" — {quantity:g} {unit}" + ".",
        "Пакет: " + work_package + ".",
        "Причина: " + ("; ".join(reasons) if reasons else "сметное соответствие требует проверки") + ".",
    ]
    if "no_estimate_material" in issues:
        description.append("Что сделать: сопоставить название или добавить материал в дополнительную/новую смету.")
    elif "no_active_estimate" in issues:
        description.append("Что сделать: загрузить активную смету и повторно сопоставить материал.")
    elif "over_estimate_need" in issues:
        description.append("Что сделать: проверить причину превышения и при необходимости оформить дополнительный объём материала.")
    if actor_name:
        description.append("Перемещение оформил: " + str(actor_name) + ".")
    return {
        "projectName": str(project_name or ""),
        "title": "Разобрать материал перемещения: " + material_name,
        "description": "\n".join(description),
        "assignedRole": "сметчик",
        "assignedTo": "",
        "status": "Новое",
        "actionLabel": "Разобрать перемещение",
        "dedupeKey": marker,
        "actionPayload": {
            "type": "warehouse_movement_estimate_review",
            "marker": marker,
            "dedupeKey": marker,
            "movementId": int(movement_id),
            "projectName": str(project_name or ""),
            "materialName": material_name,
            "quantity": quantity,
            "unit": unit,
            "workPackage": work_package,
            "issues": issues,
            "estimateControl": control,
        },
    }
