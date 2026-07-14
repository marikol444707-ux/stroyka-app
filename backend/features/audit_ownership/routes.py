from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.features.audit_ownership.runtime import insert_audit_event
except ModuleNotFoundError:
    from features.audit_ownership.runtime import insert_audit_event


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _allowed_company_ids(actors, allowed_roles):
    roles = {str(role or "").strip() for role in allowed_roles or ()}
    return sorted({
        company_id
        for actor in actors or []
        for company_id in [_positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))]
        if company_id and str((actor or {}).get("role") or "").strip() in roles
    })


def _selected_actor(actors, context):
    if (context or {}).get("mode") != "company":
        raise HTTPException(status_code=400, detail="Для записи действия выберите конкретную компанию")
    company_id = _positive_int((context or {}).get("companyId") or (context or {}).get("company_id"))
    matches = [
        dict(actor or {}) for actor in actors or []
        if _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id")) == company_id
    ]
    if len(matches) != 1 or not company_id:
        raise HTTPException(status_code=403, detail="Компания пользователя не определена")
    matches[0]["companyId"] = company_id
    return matches[0]


def register_audit_log_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    allowed_roles = tuple(deps.get("allowed_roles") or ())

    @app.get("/audit-log")
    def list_audit_log(
        limit: int = 200,
        offset: int = 0,
        search: str = "",
        user_name: str = "",
        user_role: str = "",
        action: str = "",
        entity_type: str = "",
        project_name: str = "",
        date_from: str = "",
        date_to: str = "",
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_ids = _allowed_company_ids(
                effective_company_actors(current_user, context),
                allowed_roles,
            )
            if not company_ids:
                raise HTTPException(status_code=403, detail="Роль не позволяет просматривать журнал действий")

            where = ["owner_scope='company'", "company_id = ANY(%s)"]
            params = [company_ids]

            def add_like(column, value):
                value = str(value or "").strip()
                if value:
                    where.append(f"COALESCE({column}, '') ILIKE %s")
                    params.append("%" + value + "%")

            add_like("user_name", user_name)
            add_like("user_role", user_role)
            add_like("action", action)
            add_like("entity_type", entity_type)
            add_like("project_name", project_name)

            search_value = str(search or "").strip()
            if search_value:
                where.append("""(
                    COALESCE(user_name, '') ILIKE %s OR COALESCE(user_role, '') ILIKE %s OR
                    COALESCE(action, '') ILIKE %s OR COALESCE(entity_type, '') ILIKE %s OR
                    COALESCE(description, '') ILIKE %s OR COALESCE(project_name, '') ILIKE %s
                )""")
                params.extend(["%" + search_value + "%"] * 6)
            if date_from:
                where.append("created_at >= %s")
                params.append(date_from)
            if date_to:
                where.append("created_at < (%s::date + INTERVAL '1 day')")
                params.append(date_to)

            cur.execute(
                """SELECT id,user_id,user_name,user_role,action,entity_type,entity_id,description,
                          project_name,owner_scope,company_id,project_id,created_at
                     FROM audit_log WHERE """ + " AND ".join(where) +
                " ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
                tuple(params + [limit, offset]),
            )
            rows = [dict(row or {}) for row in (cur.fetchall() or [])]
            return [{
                "id": row.get("id"),
                "userId": row.get("user_id"),
                "userName": row.get("user_name") or "",
                "userRole": row.get("user_role") or "",
                "action": row.get("action") or "",
                "entityType": row.get("entity_type") or "",
                "entityId": row.get("entity_id"),
                "description": row.get("description") or "",
                "projectName": row.get("project_name") or "",
                "ownerScope": row.get("owner_scope") or "",
                "companyId": row.get("company_id"),
                "projectId": row.get("project_id"),
                "createdAt": (
                    row.get("created_at").isoformat()
                    if hasattr(row.get("created_at"), "isoformat")
                    else str(row.get("created_at") or "")
                ),
            } for row in rows]
        finally:
            cur.close()
            conn.close()

    @app.post("/audit-log")
    def create_audit_entry(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context = resolve_work_company_context(
                cur,
                current_user,
                data.get("companyId") if "companyId" in data else data.get("company_id"),
                "create",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            actor = _selected_actor(effective_company_actors(current_user, context), context)
            company_id = actor["companyId"]
            project_name = str(data.get("projectName") or "").strip()
            project_id = None
            if project_name:
                cur.execute(
                    "SELECT id,name FROM projects WHERE company_id=%s AND BTRIM(name)=BTRIM(%s) ORDER BY id",
                    (company_id, project_name),
                )
                projects = [dict(row or {}) for row in (cur.fetchall() or [])]
                if len(projects) != 1:
                    raise HTTPException(status_code=409, detail="Объект журнала не найден в выбранной компании")
                project_id = projects[0].get("id")
                project_name = projects[0].get("name") or project_name
            result = insert_audit_event(
                cur,
                user_id=actor.get("id") or current_user.get("id"),
                user_name=actor.get("name") or current_user.get("name") or "",
                user_role=actor.get("role") or "",
                action=data.get("action") or "",
                entity_type=data.get("entityType") or "",
                entity_id=data.get("entityId"),
                description=data.get("description") or "",
                project_name=project_name,
                owner_scope="company",
                company_id=company_id,
                project_id=project_id,
            )
            conn.commit()
            return {"id": result["id"], "ok": True}
        finally:
            cur.close()
            conn.close()
