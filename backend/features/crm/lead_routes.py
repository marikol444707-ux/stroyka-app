"""CRM lead routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 33):
the /crm-leads quartet keeps its URLs, company-scoped read context
and owner resolution on create. Read restriction comes from this
feature's writer_ownership; company scope filter from
company_context.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.features.crm.writer_ownership import restrict_crm_read_context
    from backend.features.company_context.service import company_id_scope_filter
except ModuleNotFoundError:
    from features.crm.writer_ownership import restrict_crm_read_context
    from features.company_context.service import company_id_scope_filter


def register_crm_leads_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    resolve_crm_create_owner = deps["resolve_crm_create_owner"]

    @app.get("/crm-leads")
    def get_crm_leads(
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*admin_roles, "менеджер_crm")),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_context = restrict_crm_read_context(
                company_context,
                effective_company_actors(current_user, company_context),
                allowed_roles=(*admin_roles, "менеджер_crm"),
            )
            company_sql, company_params = company_id_scope_filter(company_context, "crm_leads.company_id")
            cur.execute("""
                SELECT id,company_id AS "companyId",name,phone,email,source,budget,notes,stage,
                       created_by AS "createdBy",created_at AS "createdAt",project_id AS "projectId",
                       photo_url AS "photoUrl"
                FROM crm_leads
                WHERE TRUE
            """ + company_sql + " ORDER BY id DESC", company_params)
            rows = cur.fetchall()
            return [
                {
                    **dict(row),
                    "name": row.get("name") or "",
                    "phone": row.get("phone") or "",
                    "email": row.get("email") or "",
                    "source": row.get("source") or "",
                    "budget": float(row.get("budget") or 0),
                    "notes": row.get("notes") or "",
                    "stage": row.get("stage") or "Новый",
                    "createdBy": row.get("createdBy") or "",
                    "createdAt": row.get("createdAt") or "",
                    "photoUrl": row.get("photoUrl") or "",
                }
                for row in rows
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/crm-leads")
    def create_crm_lead(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*admin_roles, "менеджер_crm")),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            owner = resolve_crm_create_owner(cur, _current_user, x_company_id, x_company_mode)
            cur.execute("INSERT INTO crm_leads (company_id,name,phone,email,source,budget,notes,stage,created_by,created_at,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (owner["companyId"], data.get("name",""), data.get("phone",""), data.get("email",""), data.get("source",""), data.get("budget") or 0, data.get("notes",""), data.get("stage","Новый"), _current_user.get("name", ""), data.get("createdAt",""), data.get("photoUrl","")))
            created = cur.fetchone()
            new_id = created.get("id") if isinstance(created, dict) else created[0]
            conn.commit()
            return {"ok": True, "id": new_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(error))
        finally:
            cur.close()
            conn.close()

    @app.put("/crm-leads/{id}")
    def update_crm_lead(id: int, data: dict, _current_user: dict = Depends(require_roles(*admin_roles, "менеджер_crm"))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE crm_leads SET name=%s,phone=%s,email=%s,source=%s,budget=%s,notes=%s,stage=%s,photo_url=%s WHERE id=%s",
            (data.get("name",""), data.get("phone",""), data.get("email",""), data.get("source",""), data.get("budget") or 0, data.get("notes",""), data.get("stage","Новый"), data.get("photoUrl",""), id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}

    @app.delete("/crm-leads/{id}")
    def delete_crm_lead(id: int, _current_user: dict = Depends(require_roles(*admin_roles, "менеджер_crm"))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM crm_leads WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
