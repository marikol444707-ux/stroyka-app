"""Material alias routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 16):
GET/POST /material-aliases and DELETE /material-aliases/{id} keep
their URLs, role guards, project access checks and soft-delete
behavior. The model and row/values helpers moved here — the alias
cluster was their only user; project visibility helpers arrive
through deps.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class MaterialAliasModel(BaseModel):
    projectName: str = ""
    aliasName: str
    canonicalName: str
    canonicalUnit: str = ""
    source: str = "manual"
    active: bool = True


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
    }


def _material_alias_values(data: MaterialAliasModel, user_name: str):
    return (
        (data.projectName or "").strip(),
        (data.aliasName or "").strip(),
        (data.canonicalName or "").strip(),
        (data.canonicalUnit or "").strip(),
        (data.source or "manual").strip()[:50],
        bool(data.active),
        user_name or "",
    )


def register_material_aliases_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    require_project_access = deps["require_project_access"]
    visible_project_names = deps["visible_project_names"]

    @app.get("/material-aliases")
    def list_material_aliases(project_name: str = None, current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = ["active=TRUE"]
        params = []
        if project_name:
            require_project_access(current_user, project_name)
            where.append("(project_name=%s OR COALESCE(project_name,'')='')")
            params.append(project_name)
        else:
            allowed = visible_project_names(current_user)
            if allowed is not None:
                if not allowed:
                    where.append("COALESCE(project_name,'')=''")
                else:
                    where.append("(project_name = ANY(%s) OR COALESCE(project_name,'')='')")
                    params.append(allowed)
        cur.execute(f"""SELECT *
                        FROM material_aliases
                        WHERE {' AND '.join(where)}
                        ORDER BY COALESCE(project_name,'') DESC, alias_name, id""", tuple(params))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [_material_alias_row(r) for r in rows]

    @app.post("/material-aliases")
    def create_material_alias(data: MaterialAliasModel, current_user: dict = Depends(require_roles(*write_roles))):
        project_name = (data.projectName or "").strip()
        alias_name = (data.aliasName or "").strip()
        canonical_name = (data.canonicalName or "").strip()
        if not alias_name or not canonical_name:
            raise HTTPException(status_code=400, detail="Укажите исходное и сметное название материала")
        if project_name:
            require_project_access(current_user, project_name)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        vals = _material_alias_values(data, current_user.get("name", ""))
        cur.execute("""
            UPDATE material_aliases
            SET active=FALSE, updated_by=%s, updated_at=NOW()
            WHERE active=TRUE
              AND COALESCE(project_name,'')=%s
              AND LOWER(TRIM(alias_name))=LOWER(TRIM(%s))
        """, (current_user.get("name", ""), project_name, alias_name))
        cur.execute("""
            INSERT INTO material_aliases (
                project_name, alias_name, canonical_name, canonical_unit,
                source, active, updated_by, updated_at, created_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            RETURNING *
        """, vals)
        row = cur.fetchone()
        cur.close(); conn.close()
        return _material_alias_row(row)

    @app.delete("/material-aliases/{id}")
    def delete_material_alias(id: int, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT project_name FROM material_aliases WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Сопоставление материала не найдено")
        project_name = row["project_name"] or ""
        if project_name:
            require_project_access(current_user, project_name)
        cur.execute("UPDATE material_aliases SET active=FALSE, updated_by=%s, updated_at=NOW() WHERE id=%s", (current_user.get("name", ""), id))
        cur.close(); conn.close()
        return {"ok": True}
