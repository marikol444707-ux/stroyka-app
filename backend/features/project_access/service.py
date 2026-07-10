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
