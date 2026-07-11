import json

from fastapi import HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _values(value):
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item or "").strip()})
    if isinstance(value, str):
        try:
            return _values(json.loads(value))
        except Exception:
            return []
    return []


def _company_id(actor):
    return _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))


def _assigned_projects(actor):
    values = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    if legacy_project:
        values.append(legacy_project)
    return sorted(set(values))


def project_visibility_filter(company_actors, full_view_roles, column_prefix="p"):
    """Build a fail-closed project list filter for one or many company memberships."""
    prefix = str(column_prefix or "p").strip()
    if not prefix.replace("_", "").isalnum():
        raise ValueError("Invalid project table alias")
    full_roles = {str(role or "").strip() for role in full_view_roles or [] if str(role or "").strip()}
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _company_id(actor)
        role = str((actor or {}).get("role") or "").strip()
        if not company_id:
            continue
        actor_clauses = [f"{prefix}.company_id=%s"]
        actor_params = [company_id]
        if role not in full_roles:
            projects = _assigned_projects(actor)
            if not projects:
                continue
            actor_clauses.append(f"{prefix}.name = ANY(%s)")
            actor_params.append(projects)
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
    if not clauses:
        return "FALSE", []
    return "(" + " OR ".join(clauses) + ")", params


def require_project_write_actor(company_actors, write_roles):
    """Return the sole selected-company actor allowed to mutate projects."""
    actors = [actor for actor in company_actors or [] if _company_id(actor)]
    if len(actors) != 1:
        raise HTTPException(
            status_code=409,
            detail="Для изменения объекта выберите одну конкретную компанию",
        )
    actor = dict(actors[0])
    allowed_roles = {str(role or "").strip() for role in write_roles or [] if str(role or "").strip()}
    if str(actor.get("role") or "").strip() not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Роль в выбранной компании не позволяет изменять объекты",
        )
    actor["companyId"] = _company_id(actor)
    actor["company_id"] = _company_id(actor)
    return actor


def require_project_row_company(actor, project_company_id):
    """Reject a direct-ID project mutation when the stored owner differs from the actor company."""
    actor_company_id = _company_id(actor)
    stored_company_id = _positive_int(project_company_id)
    if not actor_company_id or not stored_company_id:
        raise HTTPException(status_code=409, detail="Компания объекта не определена")
    if actor_company_id != stored_company_id:
        raise HTTPException(status_code=403, detail="Объект относится к другой компании")
    return stored_company_id


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _project_parent(row):
    if not row:
        return None
    return {
        "id": _positive_int(_row_value(row, "id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "name": str(_row_value(row, "name", 2) or "").strip(),
    }


def resolve_project_parent(cur, actor, *, project_id=None, project_name="", for_update=False):
    """Resolve a child record parent inside one company; names are a legacy fallback only."""
    company_id = _company_id(actor)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания объекта не определена")
    normalized_project_id = _positive_int(project_id)
    normalized_name = str(project_name or "").strip()
    lock_sql = " FOR UPDATE" if for_update else ""

    if normalized_project_id:
        cur.execute(
            "SELECT id,company_id,name FROM projects WHERE id=%s AND company_id=%s" + lock_sql,
            (normalized_project_id, company_id),
        )
        parent = _project_parent(cur.fetchone())
        if not parent:
            raise HTTPException(status_code=404, detail="Объект не найден в выбранной компании")
        if normalized_name and parent["name"] != normalized_name:
            raise HTTPException(status_code=409, detail="projectId и название объекта указывают на разные записи")
        return parent

    if not normalized_name:
        raise HTTPException(status_code=400, detail="Укажите projectId или название объекта")
    cur.execute(
        "SELECT id,company_id,name FROM projects WHERE company_id=%s AND name=%s ORDER BY id" + lock_sql,
        (company_id, normalized_name),
    )
    rows = cur.fetchall() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Объект не найден в выбранной компании")
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail="В выбранной компании найдено несколько объектов с таким названием. Используйте projectId",
        )
    return _project_parent(rows[0])


def require_project_parent_access(cur, actor, project, full_view_roles):
    """Authorize a resolved project without treating an ambiguous name as an ID."""
    actor_company_id = _company_id(actor)
    project_company_id = _positive_int((project or {}).get("companyId") or (project or {}).get("company_id"))
    project_id = _positive_int((project or {}).get("id"))
    project_name = str((project or {}).get("name") or "").strip()
    if not actor_company_id or not project_company_id or actor_company_id != project_company_id:
        raise HTTPException(status_code=403, detail="Объект относится к другой компании")
    if not project_id or not project_name:
        raise HTTPException(status_code=409, detail="Объект не имеет точного идентификатора")

    full_roles = {str(role or "").strip() for role in full_view_roles or [] if str(role or "").strip()}
    if str((actor or {}).get("role") or "").strip() in full_roles:
        return project
    if project_name not in _assigned_projects(actor):
        raise HTTPException(status_code=403, detail="Нет доступа к объекту")

    cur.execute(
        "SELECT id FROM projects WHERE company_id=%s AND name=%s ORDER BY id",
        (project_company_id, project_name),
    )
    project_ids = [
        _positive_int(_row_value(row, "id", 0))
        for row in (cur.fetchall() or [])
    ]
    project_ids = [value for value in project_ids if value]
    if project_id not in project_ids:
        raise HTTPException(status_code=409, detail="Объект изменился во время проверки доступа")
    if len(project_ids) <= 1:
        return project
    raise HTTPException(
        status_code=409,
        detail="Назначение по названию объекта неоднозначно. Ограничьте доступ после миграции projectId членства",
    )


def require_child_project_identity(child, parent, *, child_label="Документ"):
    """Verify a stored child row against an already resolved project parent."""
    child_company_id = _positive_int((child or {}).get("companyId") or (child or {}).get("company_id"))
    child_project_id = _positive_int((child or {}).get("projectId") or (child or {}).get("project_id"))
    child_project_name = str((child or {}).get("projectName") or (child or {}).get("project_name") or "").strip()
    if child_company_id and child_company_id != _positive_int((parent or {}).get("companyId")):
        raise HTTPException(status_code=409, detail=child_label + " относится к другой компании")
    if child_project_id and child_project_id != _positive_int((parent or {}).get("id")):
        raise HTTPException(status_code=409, detail=child_label + " относится к другому объекту")
    if child_project_name and child_project_name != str((parent or {}).get("name") or "").strip():
        raise HTTPException(status_code=409, detail=child_label + " содержит другое название объекта")
    return parent
