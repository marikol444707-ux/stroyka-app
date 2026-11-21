"""Selected-company access for the legacy material-alias list.

The company directory remains the editor when it is enabled. This list still
answers only for the selected company, including aliases that name no project.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from ..record_company_scope import read_context, resolve_project_owner, row_value, selected_actor
from .runtime import owned_aliases_enabled


def _require_legacy_alias_mode():
    if owned_aliases_enabled():
        raise HTTPException(503, "Редактор соответствий переводится на справочник компании; старый справочник недоступен")


class MaterialAliasModel(BaseModel):
    projectName: str = ""
    aliasName: str
    canonicalName: str
    canonicalUnit: str = ""
    source: str = "manual"
    active: bool = True


_LEADERSHIP = {"директор", "зам_директора", "главный_инженер", "сметчик", "снабженец", "кладовщик"}


def _material_alias_row(row):
    return {
        "id": row["id"],
        "projectName": row["project_name"] or "",
        "aliasName": row["alias_name"] or "",
        "canonicalName": row["canonical_name"] or "",
        "canonicalUnit": row["canonical_unit"] or "",
        "source": row["source"] or "manual",
        "active": bool(row["active"]),
        "updatedBy": row["updated_by"] or "",
        "updatedAt": str(row["updated_at"]) if row["updated_at"] else "",
        "companyId": row.get("company_id"),
        "projectId": row.get("project_id"),
    }


def register_material_aliases_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    resolve = deps["resolve_work_company_context"]
    actors_for = deps["effective_company_actors"]
    scope_filter = deps["company_id_scope_filter"]
    all_company_data = deps["can_see_all_company_data"]
    user_projects = deps["user_project_names"]
    project_access = deps["require_project_access"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())

    @app.get("/material-aliases")
    def list_material_aliases(
        project_name: str = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*read_roles)),
    ):
        _require_legacy_alias_mode()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(
                resolve, actors_for, cur, current_user, x_company_id, x_company_mode, _LEADERSHIP
            )
            if not actor and not all_leadership:
                return []
            company_sql, company_params = scope_filter(context, "company_id")
            where = ["active=TRUE"]
            params = []
            if project_name:
                if actor:
                    project_access(actor, project_name)
                where.append("(project_name=%s OR COALESCE(project_name,'')='')")
                params.append(project_name)
            else:
                allowed = None if all_leadership or not actor or all_company_data(actor) else user_projects(actor)
                if allowed is not None:
                    if not allowed:
                        where.append("COALESCE(project_name,'')=''")
                    else:
                        where.append("(project_name = ANY(%s) OR COALESCE(project_name,'')='')")
                        params.append(allowed)
            params.extend(company_params)
            cur.execute(
                f"""SELECT *
                    FROM material_aliases
                    WHERE {' AND '.join(where)}{company_sql}
                    ORDER BY COALESCE(project_name,'') DESC, alias_name, id""",
                tuple(params),
            )
            return [_material_alias_row(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/material-aliases")
    def create_material_alias(
        data: MaterialAliasModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*write_roles)),
    ):
        _require_legacy_alias_mode()
        project_name = (data.projectName or "").strip()
        alias_name = (data.aliasName or "").strip()
        canonical_name = (data.canonicalName or "").strip()
        if not alias_name or not canonical_name:
            raise HTTPException(status_code=400, detail="Укажите исходное и сметное название материала")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, current_user, "create", x_company_id, x_company_mode, write_roles
            )
            if project_name:
                project_access(actor, project_name)
                scope, project_id = resolve_project_owner(cur, project_name, company_id)
            else:
                scope, project_id = "company", None
            cur.execute(
                """
                UPDATE material_aliases
                SET active=FALSE, updated_by=%s, updated_at=NOW()
                WHERE active=TRUE AND company_id=%s
                  AND COALESCE(project_name,'')=%s
                  AND LOWER(TRIM(alias_name))=LOWER(TRIM(%s))
                """,
                (actor.get("name", ""), company_id, project_name, alias_name),
            )
            cur.execute(
                """
                INSERT INTO material_aliases (
                    project_name, alias_name, canonical_name, canonical_unit,
                    source, active, updated_by, updated_at, created_at,
                    owner_scope, company_id, project_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW(),%s,%s,%s)
                RETURNING *
                """,
                (project_name, alias_name, canonical_name, (data.canonicalUnit or "").strip(),
                 (data.source or "manual").strip()[:50], bool(data.active), actor.get("name") or "",
                 scope, company_id, project_id),
            )
            row = cur.fetchone()
            conn.commit()
            return _material_alias_row(row)
        finally:
            cur.close()
            conn.close()

    @app.delete("/material-aliases/{id}")
    def delete_material_alias(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*write_roles)),
    ):
        _require_legacy_alias_mode()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, current_user, "delete", x_company_id, x_company_mode, write_roles
            )
            cur.execute(
                "SELECT project_name,company_id FROM material_aliases WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сопоставление материала не найдено")
            project_name = row_value(row, "project_name", 0, "") or ""
            if project_name and not all_company_data(actor):
                project_access(actor, project_name)
            cur.execute(
                "UPDATE material_aliases SET active=FALSE, updated_by=%s, updated_at=NOW() WHERE id=%s AND company_id=%s",
                (actor.get("name", ""), id, company_id),
            )
            conn.commit()
            return {"ok": True}
        finally:
            cur.close()
            conn.close()
