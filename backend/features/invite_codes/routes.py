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
    # Optional helpers for resolving the selected-company context server-side.
    resolve_work_company_context = deps.get("resolve_work_company_context")
    effective_company_actors = deps.get("effective_company_actors")

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
        x_company_id: str = None,
        x_company_mode: str = None,
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
        body_company_id = data.get("companyId") or data.get("company_id")
        platform_account_id = data.get("platformAccountId") or data.get("platform_account_id")
        try:
            company_id = int(body_company_id) if body_company_id not in (None, "") else None
        except Exception:
            company_id = None
        try:
            platform_account_id = int(platform_account_id) if platform_account_id not in (None, "") else None
        except Exception:
            platform_account_id = None
        # If server-side company resolver is provided, resolve selected company
        # and verify the current user's active membership+role in that company.
        if resolve_work_company_context:
            context = resolve_work_company_context(
                cur,
                _current_user,
                company_id,
                "create",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            # Must be a concrete selected company (mode == 'company')
            if (context or {}).get("mode") != "company":
                raise HTTPException(status_code=400, detail="Для создания приглашения выберите конкретную компанию")
            # Ensure we can resolve at least one active actor for this company with allowed role
            if not effective_company_actors:
                raise HTTPException(status_code=500, detail="Ошибка конфигурации сервера: missing effective_company_actors")
            actors = effective_company_actors(_current_user, context) or []
            # find matching actor for the selected company
            selected_company_id = int((context.get("companyId") or context.get("company_id") or 0) or 0)
            matches = [a for a in actors if int((a.get("companyId") or a.get("company_id") or 0) or 0) == selected_company_id]
            if len(matches) != 1:
                raise HTTPException(status_code=403, detail="Компания пользователя не определена")
            # override company_id with validated selected company
            company_id = selected_company_id
        if company_id and not platform_account_id:
            cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
            company_row = cur.fetchone()
            if company_row:
                platform_account_id = company_row.get("platform_account_id")
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
