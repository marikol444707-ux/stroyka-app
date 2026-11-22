"""Selected-company access for project checklists."""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from ..record_company_scope import read_context, resolve_project_owner, row_value, selected_actor


_LEADERSHIP = {"директор", "зам_директора", "главный_инженер", "сметчик"}


def register_project_checklists_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    resolve = deps["resolve_work_company_context"]
    actors_for = deps["effective_company_actors"]
    scope_filter = deps["company_id_scope_filter"]
    all_company_data = deps["can_see_all_company_data"]
    user_projects = deps["user_project_names"]
    project_name_from_payload = deps["project_name_from_payload"]
    project_access = deps["require_project_access"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())

    def project_limit(actor, all_leadership):
        if all_leadership or not actor or all_company_data(actor):
            return None
        return user_projects(actor)

    @app.get("/project-checklists")
    def get_project_checklists(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*read_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            context, actor, all_leadership = read_context(
                resolve, actors_for, cur, current_user, x_company_id, x_company_mode, _LEADERSHIP
            )
            if not actor and not all_leadership:
                return []
            company_sql, company_params = scope_filter(context, "company_id")
            allowed = project_limit(actor, all_leadership)
            where = "TRUE"
            params = []
            if allowed is not None:
                if not allowed:
                    return []
                where += " AND (owner_scope='company' OR project_name = ANY(%s))"
                params.append(allowed)
            where += company_sql
            params.extend(company_params)
            cur.execute(
                "SELECT id,project_id,project_name,name,template,status,created_by,created_at,company_id "
                "FROM project_checklists WHERE " + where + " ORDER BY id",
                tuple(params),
            )
            rows = cur.fetchall()
            return [{
                "id": row[0], "projectId": row[1], "projectName": row[2], "name": row[3],
                "template": row[4], "status": row[5], "createdBy": row[6], "createdAt": str(row[7]),
                "companyId": row[8],
            } for row in rows]
        finally:
            cur.close()
            conn.close()

    @app.post("/project-checklists")
    def create_project_checklist(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*write_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "create", x_company_id, x_company_mode, write_roles
            )
            project_name = project_name_from_payload(cur, data)
            project_access(actor, project_name)
            scope, project_id = resolve_project_owner(cur, project_name, company_id)
            requested = data.get("projectId") or data.get("project_id")
            if requested not in (None, "", 0) and int(requested) != project_id:
                raise HTTPException(status_code=403, detail="Объект не относится к выбранной компании")
            cur.execute(
                "INSERT INTO project_checklists (project_id,project_name,name,template,status,created_by,created_at,owner_scope,company_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (project_id, project_name, data.get("name", ""), data.get("template", ""), data.get("status", "В работе"),
                 data.get("createdBy", ""), data.get("createdAt", ""), scope, company_id),
            )
            conn.commit()
            row = cur.fetchone()
            return {"id": row_value(row, "id", 0), "ok": True}
        finally:
            cur.close()
            conn.close()

    @app.delete("/project-checklists/{id}")
    def delete_project_checklist(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*write_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "delete", x_company_id, x_company_mode, write_roles
            )
            cur.execute(
                "SELECT project_name FROM project_checklists WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Чек-лист не найден в выбранной компании")
            if not all_company_data(actor):
                project_access(actor, row_value(row, "project_name", 0, "") or "")
            cur.execute(
                "DELETE FROM checklist_items WHERE checklist_id=%s AND company_id=%s",
                (id, company_id),
            )
            cur.execute(
                "DELETE FROM project_checklists WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            conn.commit()
            return {"ok": True}
        finally:
            cur.close()
            conn.close()
