from fastapi import HTTPException


SUPPORTED_LINKED_ENTITY_SQL = {
    "room": "SELECT project AS entity_project_name FROM rooms WHERE id=%s",
    "room_window": "SELECT r.project AS entity_project_name FROM room_windows e JOIN rooms r ON r.id=e.room_id WHERE e.id=%s",
    "room_door": "SELECT r.project AS entity_project_name FROM room_doors e JOIN rooms r ON r.id=e.room_id WHERE e.id=%s",
    "work_journal": "SELECT project AS entity_project_name FROM work_journal WHERE id=%s",
    "material_norm_suggestion": "SELECT project_name AS entity_project_name FROM material_norm_suggestions WHERE id=%s",
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _project(row):
    return {
        "id": _positive_int(_row_value(row, "id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "name": str(_row_value(row, "name", 2) or ""),
    }


def resolve_project_owner(cur, project_name, *, company_id=None, project_id=None, for_update=False):
    requested_name = str(project_name or "")
    normalized_company_id = _positive_int(company_id)
    normalized_project_id = _positive_int(project_id)
    if not requested_name.strip() and not normalized_project_id:
        raise HTTPException(status_code=400, detail="projectName required")
    lock_sql = " FOR UPDATE" if for_update else ""
    if normalized_project_id:
        params = [normalized_project_id]
        where = "id=%s"
        if normalized_company_id:
            where += " AND company_id=%s"
            params.append(normalized_company_id)
        if requested_name.strip():
            where += " AND BTRIM(name)=BTRIM(%s)"
            params.append(requested_name)
        cur.execute("SELECT id,company_id,name FROM projects WHERE " + where + lock_sql, tuple(params))
        rows = cur.fetchall() or []
    elif normalized_company_id:
        cur.execute(
            "SELECT id,company_id,name FROM projects WHERE company_id=%s AND BTRIM(name)=BTRIM(%s) ORDER BY id" + lock_sql,
            (normalized_company_id, requested_name),
        )
        rows = cur.fetchall() or []
    else:
        cur.execute(
            "SELECT id,company_id,name FROM projects WHERE BTRIM(name)=BTRIM(%s) ORDER BY company_id,id" + lock_sql,
            (requested_name,),
        )
        rows = cur.fetchall() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Объект не найден в выбранной компании")
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Название объекта неоднозначно; используйте точный owner")
    project = _project(rows[0])
    if not project["id"] or not project["companyId"] or not project["name"].strip():
        raise HTTPException(status_code=409, detail="Владелец объекта не определён")
    return project


def validate_linked_entity_owner(cur, project, entity_type, entity_id):
    normalized_type = str(entity_type or "").strip()
    normalized_id = str(entity_id or "").strip()
    if not normalized_type and not normalized_id:
        return project
    if not normalized_type or not normalized_id:
        raise HTTPException(status_code=400, detail="Связь находки с сущностью заполнена не полностью")
    sql = SUPPORTED_LINKED_ENTITY_SQL.get(normalized_type)
    if not sql:
        raise HTTPException(status_code=400, detail="Тип связанной сущности находки не поддерживается")
    cur.execute(
        "SELECT entity.entity_project_name,p.id AS project_id,p.company_id "
        "FROM (" + sql + ") entity "
        "JOIN projects p ON BTRIM(p.name)=BTRIM(entity.entity_project_name) "
        "ORDER BY p.company_id,p.id",
        (normalized_id,),
    )
    rows = cur.fetchall() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Связанная сущность находки не найдена")
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Владелец связанной сущности неоднозначен")
    row = rows[0]
    linked_project_id = _positive_int(_row_value(row, "project_id", 1))
    linked_company_id = _positive_int(_row_value(row, "company_id", 2))
    if linked_project_id != _positive_int(project.get("id")) or linked_company_id != _positive_int(project.get("companyId")):
        raise HTTPException(status_code=409, detail="Связанная сущность относится к другому объекту")
    return project


def upsert_finding(cur, finding, current_user, project, *, normalize_assignment, ensure_task):
    payload = dict(finding or {})
    project_name = str(project.get("name") or "")
    validate_linked_entity_owner(cur, project, payload.get("linkedEntityType"), payload.get("linkedEntityId"))
    assignment = normalize_assignment(
        cur,
        project_name,
        payload.get("assignedRole") or "",
        payload.get("assignedTo") or "",
    )
    payload.update({
        "projectName": project_name,
        "assignedRole": assignment.get("assignedRole") or "",
        "assignedTo": assignment.get("assignedTo") or "",
    })
    dedupe_key = payload.get("dedupeKey") or ""
    if dedupe_key:
        cur.execute(
            "SELECT id FROM ai_findings WHERE company_id=%s AND project_id=%s AND dedupe_key=%s "
            "AND status NOT IN ('Закрыто','Отклонено') LIMIT 1",
            (project["companyId"], project["id"], dedupe_key),
        )
        row = cur.fetchone()
        if row:
            finding_id = _positive_int(_row_value(row, "id", 0))
            cur.execute(
                """UPDATE ai_findings
                      SET project_name=%s,finding_type=%s,category=%s,severity=%s,title=%s,description=%s,
                          source=%s,linked_entity_type=%s,linked_entity_id=%s,suggested_action=%s,
                          assigned_role=%s,assigned_to=%s,updated_at=NOW()
                    WHERE id=%s AND company_id=%s AND project_id=%s""",
                (
                    project_name, payload.get("findingType") or "rule", payload.get("category") or "Общее",
                    payload.get("severity") or "Проверить", payload.get("title") or "", payload.get("description") or "",
                    payload.get("source") or "system_rules", payload.get("linkedEntityType") or "",
                    payload.get("linkedEntityId") or "", payload.get("suggestedAction") or "",
                    payload.get("assignedRole") or "", payload.get("assignedTo") or "",
                    finding_id, project["companyId"], project["id"],
                ),
            )
            ensure_task(cur, finding_id, payload, current_user)
            return finding_id, False
    cur.execute(
        """INSERT INTO ai_findings (
               company_id,project_id,project_name,finding_type,category,severity,title,description,source,
               linked_entity_type,linked_entity_id,suggested_action,assigned_role,assigned_to,status,
               dedupe_key,created_by,created_by_id,created_at,updated_at
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
           RETURNING id""",
        (
            project["companyId"], project["id"], project_name, payload.get("findingType") or "rule",
            payload.get("category") or "Общее", payload.get("severity") or "Проверить", payload.get("title") or "",
            payload.get("description") or "", payload.get("source") or "system_rules",
            payload.get("linkedEntityType") or "", payload.get("linkedEntityId") or "",
            payload.get("suggestedAction") or "", payload.get("assignedRole") or "", payload.get("assignedTo") or "",
            payload.get("status") or "Новое", dedupe_key, current_user.get("name") or "", current_user.get("id"),
        ),
    )
    finding_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
    ensure_task(cur, finding_id, payload, current_user)
    return finding_id, True


def close_stale_findings(cur, project, categories, active_keys, actor="ИИ-контроль"):
    if not categories:
        return 0
    cur.execute(
        "SELECT id,dedupe_key FROM ai_findings WHERE company_id=%s AND project_id=%s "
        "AND category = ANY(%s) AND source='system_rules' AND status NOT IN ('Закрыто','Отклонено')",
        (project["companyId"], project["id"], list(categories)),
    )
    stale_ids = [
        _positive_int(_row_value(row, "id", 0))
        for row in (cur.fetchall() or [])
        if str(_row_value(row, "dedupe_key", 1) or "") not in set(active_keys or ())
    ]
    stale_ids = [value for value in stale_ids if value]
    if not stale_ids:
        return 0
    cur.execute(
        "UPDATE ai_findings SET status='Закрыто',updated_at=NOW() "
        "WHERE company_id=%s AND project_id=%s AND id = ANY(%s)",
        (project["companyId"], project["id"], stale_ids),
    )
    cur.execute(
        "UPDATE ai_tasks SET status='Закрыто',closed_by=%s,closed_at=NOW(),updated_at=NOW() "
        "WHERE finding_id = ANY(%s) AND status NOT IN ('Закрыто','Отклонено')",
        (actor, stale_ids),
    )
    return len(stale_ids)
