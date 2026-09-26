"""Invite code routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 31):
GET/POST/DELETE /invite-codes and the public
GET /invite-codes/{code}/info keep their URLs, leadership guard,
access-scope preparation and company/platform account resolution.
"""

import json
import uuid

import psycopg2.extras
from fastapi import Depends, HTTPException


def register_invite_codes_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    prepare_user_access_scope = deps["prepare_user_access_scope"]
    resolve_work_company_context = deps.get("resolve_work_company_context")

    @app.get("/invite-codes")
    def get_invite_codes(_current_user: dict = Depends(require_roles(*admin_roles, "system_owner"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM invite_codes ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/invite-codes")
    def create_invite_code(
        data: dict,
        x_company_id: str | None = Header(None),
        x_company_mode: str | None = Header(None),
        _current_user: dict = Depends(require_roles(*admin_roles, "system_owner")),
    ):
        from datetime import datetime, timedelta
        role = data.get('role') or ''
        if not role:
            raise HTTPException(status_code=400, detail="Не указана роль")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        code = str(uuid.uuid4())[:8].upper()
        expires_in_days = int(data.get('expiresInDays') or 14)
        expires_at = datetime.now() + timedelta(days=expires_in_days)
        project_name = (data.get("projectName") or data.get("project_name") or "").strip()
        assigned_projects, assigned_packages = prepare_user_access_scope(
            cur,
            role,
            project_name,
            data.get("assignedProjects") or [],
            data.get("assignedPackages") or [],
        )
        # Resolve authoritative company context from authenticated selected-company resolver.
        # The request body `companyId` is only a claim and must not be relied upon.
        company_id = None
        platform_account_id = None
        if resolve_work_company_context:
            context = resolve_work_company_context(cur, _current_user, None, "company", x_company_id=x_company_id, x_company_mode=x_company_mode)
            # Fail closed when no concrete selected company
            if not context or context.get("mode") != "company" or not context.get("companyId"):
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Выберите конкретную компанию (selected company) перед созданием приглашения")
            company_id = int(context.get("companyId"))
            # derive platform_account_id server-side
            cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
            company_row = cur.fetchone()
            if company_row:
                platform_account_id = company_row.get("platform_account_id")
        else:
            # fallback: try body, but this should not be relied upon
            try:
                company_id = int(data.get("companyId") or data.get("company_id"))
            except Exception:
                company_id = None
            try:
                platform_account_id = int(data.get("platformAccountId") or data.get("platform_account_id"))
            except Exception:
                platform_account_id = None
        cur.execute(
            "INSERT INTO invite_codes (code, role, supplier_id, preset_name, preset_category, created_by, expires_at, project_name, assigned_projects, assigned_packages, company_id, platform_account_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING *",
            (code, role, data.get('supplierId'), data.get('presetName'),
             data.get('presetCategory'), data.get('createdBy'), expires_at, project_name,
             json.dumps(assigned_projects), json.dumps(assigned_packages), company_id, platform_account_id))
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.delete("/invite-codes/{id}")
    def delete_invite_code(id: int, _current_user: dict = Depends(require_roles(*admin_roles, "system_owner"))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM invite_codes WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}

    @app.get("/invite-codes/{code}/info")
    def invite_code_info(code: str):
        """Возвращает данные приглашения для подсветки формы регистрации."""
        from datetime import datetime
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM invite_codes WHERE code=%s", (code.upper().strip(),))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"valid": False, "error": "Код не найден"}
        if row.get('used'):
            return {"valid": False, "error": "Код уже использован"}
        if row.get('expires_at') and row['expires_at'] < datetime.now():
            return {"valid": False, "error": "Срок действия ссылки истёк"}
        return {
            "valid": True,
            "role": row['role'],
            "presetName": row.get('preset_name') or '',
            "presetCategory": row.get('preset_category') or '',
            "supplierId": row.get('supplier_id'),
            "companyId": row.get('company_id'),
            "platformAccountId": row.get('platform_account_id'),
        }
