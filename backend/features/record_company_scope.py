"""Selected-company checks for field records.

A write names one company. A read can cover every company where the person
is a leader. A project name is accepted only when that company has exactly
one project with that name.
"""
from fastapi import HTTPException


def row_value(row, key, index=0, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return row[index] if row and len(row) > index else default


def selected_actor(resolve, actors_for, cur, user, action, x_company_id, x_company_mode, allowed_roles):
    context = resolve(
        cur, user, None, action, x_company_id=x_company_id, x_company_mode=x_company_mode
    )
    if context.get("mode") != "company":
        raise HTTPException(status_code=409, detail="Для изменения данных выберите конкретную компанию")
    actors = actors_for(user, context)
    actor = actors[0] if len(actors) == 1 else {}
    if not actor or (actor.get("role") or "") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет выполнить действие")
    company_id = int(context.get("companyId") or 0)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания не определена")
    return context, actor, company_id


def read_context(resolve, actors_for, cur, user, x_company_id, x_company_mode, leadership):
    context = resolve(
        cur, user, None, "read", x_company_id=x_company_id, x_company_mode=x_company_mode
    )
    if not context.get("companyIds"):
        raise HTTPException(status_code=403, detail="Нет доступа к компаниям")
    actors = actors_for(user, context)
    if context.get("mode") == "company":
        if len(actors) != 1:
            raise HTTPException(status_code=403, detail="Нет активной роли в выбранной компании")
        return context, actors[0], False
    if context.get("mode") == "all_companies" and actors and all(
        (actor.get("role") or "") in leadership for actor in actors
    ):
        return context, None, True
    return context, None, False


def resolve_project_owner(cur, project_name, company_id):
    project_name = str(project_name or "").strip()
    if not project_name:
        return "company", None
    cur.execute("SELECT id,company_id FROM projects WHERE name=%s ORDER BY id", (project_name,))
    rows = cur.fetchall() or []
    matching = [row for row in rows if int(row_value(row, "company_id", 1, 0) or 0) == int(company_id)]
    if len(matching) != 1:
        raise HTTPException(status_code=403, detail="Объект не относится к выбранной компании")
    return "project", int(row_value(matching[0], "id", 0, 0))
