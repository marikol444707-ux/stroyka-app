from fastapi import HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def resolve_work_journal_create_scope(
    cur,
    current_user,
    project_name,
    *,
    x_company_id,
    x_company_mode,
    deps,
):
    context = deps["resolve_work_company_context"](
        cur,
        current_user,
        None,
        "create",
        x_company_id=x_company_id,
        x_company_mode=x_company_mode,
    )
    actor = deps["require_project_write_actor"](
        deps["effective_company_actors"](current_user, context),
        deps["journal_write_roles"],
    )
    project = deps["resolve_project_parent"](
        cur,
        actor,
        project_name=str(project_name or "").strip(),
    )
    deps["require_project_parent_access"](
        cur,
        actor,
        project,
        deps["full_view_roles"],
    )
    company_id = _positive_int(project.get("companyId") or project.get("company_id"))
    project_id = _positive_int(project.get("id"))
    canonical_name = str(project.get("name") or "").strip()
    if not company_id or not project_id or not canonical_name:
        raise HTTPException(status_code=409, detail="Объект не имеет точного владельца")
    return actor, {
        "id": project_id,
        "companyId": company_id,
        "name": canonical_name,
    }


def require_work_journal_parent_owner(parent, project, label):
    if (
        _positive_int((parent or {}).get("companyId") or (parent or {}).get("company_id"))
        != _positive_int((project or {}).get("companyId") or (project or {}).get("company_id"))
        or _positive_int((parent or {}).get("projectId") or (parent or {}).get("project_id"))
        != _positive_int((project or {}).get("id"))
    ):
        raise HTTPException(
            status_code=409,
            detail=label + " относится к другой компании или объекту",
        )
