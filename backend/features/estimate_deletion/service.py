import json


DEPENDENCY_CHECKS = (
    ("история версий", "SELECT COUNT(*) FROM estimate_versions WHERE estimate_id=%s"),
    ("сверки смет", "SELECT COUNT(*) FROM estimate_reconciliations WHERE base_estimate_id=%s OR next_estimate_id=%s"),
    ("изменения сметы", "SELECT COUNT(*) FROM unexpected_works WHERE estimate_id=%s OR included_in_estimate_id=%s"),
    ("записи ЖПР", "SELECT COUNT(*) FROM work_journal WHERE estimate_id=%s"),
    ("акты скрытых работ", "SELECT COUNT(*) FROM hidden_works_acts WHERE estimate_id=%s"),
    ("настройки норм", "SELECT COUNT(*) FROM material_norm_overrides WHERE estimate_id=%s"),
    ("переписка по смете", "SELECT COUNT(*) FROM estimate_chat_messages WHERE estimate_id=%s"),
    ("договорные позиции", "SELECT COUNT(*) FROM brigade_contract_items WHERE estimate_item_key LIKE %s"),
)


def _count(row):
    if isinstance(row, dict):
        return int(next(iter(row.values()), 0) or 0)
    return int((row or [0])[0] or 0)


def _contains_estimate_lineage(value, estimate_id):
    if isinstance(value, str):
        try:
            return _contains_estimate_lineage(json.loads(value), estimate_id)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
    if isinstance(value, list):
        return any(_contains_estimate_lineage(item, estimate_id) for item in value)
    if not isinstance(value, dict):
        return False
    for key, item in value.items():
        if key in {"estimateId", "estimate_id"}:
            try:
                if int(item) == int(estimate_id):
                    return True
            except (TypeError, ValueError):
                pass
        if _contains_estimate_lineage(item, estimate_id):
            return True
    return False


def find_estimate_delete_blockers(cur, *, estimate_id, company_id, project_name):
    blockers = []
    for label, query in DEPENDENCY_CHECKS:
        params = (estimate_id, estimate_id) if query.count("%s") == 2 else (
            (str(int(estimate_id)) + ":%",) if "LIKE" in query else (estimate_id,)
        )
        cur.execute(query, params)
        if _count(cur.fetchone()) > 0:
            blockers.append(label)

    cur.execute(
        "SELECT items_json FROM supply_requests WHERE company_id=%s AND project=%s",
        (company_id, project_name),
    )
    if any(_contains_estimate_lineage(row[0] if not isinstance(row, dict) else row.get("items_json"), estimate_id) for row in cur.fetchall()):
        blockers.append("заявки снабжения")
    return blockers
