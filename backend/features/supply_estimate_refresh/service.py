import json


OPEN_SUPPLY_STATUSES = (
    "Новая",
    "Подтверждена прорабом",
    "Утверждена",
    "КП запрошены",
    "В пути",
    "Частично поставлено",
    "Проблема поставки",
    "Утверждено",
)


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    return row[index]


def _items(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def refresh_open_supply_request_controls(
    cur,
    *,
    project_name: str,
    company_id,
    project_id=None,
    attach_control,
):
    project_name = str(project_name or "").strip()
    if not project_name or not company_id:
        return {"scanned": 0, "updated": 0}

    cur.execute(
        """
        SELECT id, items_json
          FROM supply_requests
         WHERE company_id=%s
           AND project=%s
           AND COALESCE(status,'') = ANY(%s)
         ORDER BY id
         FOR UPDATE
        """,
        (int(company_id), project_name, list(OPEN_SUPPLY_STATUSES)),
    )
    rows = cur.fetchall()
    updated = 0
    for row in rows:
        request_id = int(_row_value(row, "id", 0))
        items = _items(_row_value(row, "items_json", 1))
        if not items:
            continue
        refreshed = attach_control(
            cur,
            project_name,
            items,
            exclude_request_id=request_id,
            company_id=int(company_id),
            project_id=project_id,
        )
        cur.execute(
            "UPDATE supply_requests SET items_json=%s WHERE id=%s",
            (json.dumps(refreshed, ensure_ascii=False), request_id),
        )
        updated += 1
    return {"scanned": len(rows), "updated": updated}
