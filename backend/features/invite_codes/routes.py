"""Invite code routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 31):
GET/POST/DELETE /invite-codes and the public
GET /invite-codes/{code}/info keep their URLs, leadership guard,
access-scope preparation and company/platform account resolution.
"""

import json
import uuid

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def register_invite_codes_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    prepare_user_access_scope = deps["prepare_user_access_scope"]
    resolve_work_company_context = deps["resolve_work_company_context"]

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
        x_company_id: str | None = Header(None, alias="X-Company-Id"),
        x_company_mode: str | None = Header(None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*admin_roles, "system_owner")),
    ):
        from datetime import datetime, timedelta
        role = data.get('role') or ''
        if not role:
            raise HTTPException(status_code=400, detail="Не указана роль")
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            claimed_company_id = data.get("companyId") or data.get("company_id")
            company_context = resolve_work_company_context(
                cur,
                _current_user,
                claimed_company_id,
                "create",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_id = company_context.get("companyId") or company_context.get("company_id")
            effective_role = company_context.get("effectiveRole") or company_context.get("role") or ""
            if company_context.get("mode") != "company" or not company_id:
                raise HTTPException(status_code=403, detail="Выберите конкретную компанию перед созданием приглашения")
            if effective_role not in admin_roles:
                raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет создавать приглашения")
            company_id = int(company_id)
            platform_account_id = (
                company_context.get("platformAccountId")
                or company_context.get("platform_account_id")
            )
            if not platform_account_id:
                cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
                company_row = cur.fetchone()
                if not company_row:
                    raise HTTPException(status_code=403, detail="Выбранная компания недоступна")
                platform_account_id = company_row.get("platform_account_id")

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
            cur.execute(
                "INSERT INTO invite_codes (code, role, supplier_id, preset_name, preset_category, created_by, expires_at, project_name, assigned_projects, assigned_packages, company_id, platform_account_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING *",
                (code, role, data.get('supplierId'), data.get('presetName'),
                 data.get('presetCategory'), data.get('createdBy'), expires_at, project_name,
                 json.dumps(assigned_projects), json.dumps(assigned_packages), company_id, platform_account_id))
            row = cur.fetchone()
            return dict(row)
        finally:
            conn.close()

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
