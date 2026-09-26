"""Invite code routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 31):
GET/POST/DELETE /invite-codes and the public
GET /invite-codes/{code}/info keep their URLs, leadership guard,
access-scope preparation and company/platform account resolution.
"""

import json
import uuid

import psycopg2.extras
from fastapi import Depends, HTTPException, Header


def register_invite_codes_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_user = deps["effective_company_user"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    prepare_user_access_scope = deps["prepare_user_access_scope"]

    @app.get("/invite-codes")
    def get_invite_codes(
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # resolve selected company context (fail closed for non-company/all or missing)
        context = resolve_work_company_context(cur, current_user, None, "read", x_company_id=x_company_id, x_company_mode=x_company_mode)
        if (context or {}).get("mode") != "company":
            raise HTTPException(status_code=409, detail="Для работы с приглашениями выберите одну конкретную компанию")
        actor = effective_company_user(current_user, context)
        role = str(actor.get("role") or "").strip()
        allowed_leadership = set(list(admin_roles) + ["руководитель", "администратор", "директор"])
        if role not in allowed_leadership and role != "system_owner":
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет управлять приглашениями")
        company_id = int((context or {}).get("companyId") or (context or {}).get("company_id"))
        cur.execute("SELECT * FROM invite_codes WHERE company_id=%s ORDER BY id DESC", (company_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/invite-codes")
    def create_invite_code(
        data: dict,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
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
        # authoritative company derived from resolved context
        company_id = int((context or {}).get("companyId") or (context or {}).get("company_id"))
        platform_account_id = None
        # derive authoritative platform_account_id from companies table
        cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
        company_row = cur.fetchone()
        if not company_row:
            raise HTTPException(status_code=409, detail="Компания не найдена")
        platform_account_id = company_row.get("platform_account_id")
        # validate assigned projects belong to the selected company
        for pid in (assigned_projects or []):
            try:
                pid_int = int(pid)
            except Exception:
                raise HTTPException(status_code=400, detail="assignedProjects must contain integers")
            cur.execute("SELECT id,company_id FROM projects WHERE id=%s LIMIT 2", (pid_int,))
            prow = cur.fetchone()
            if not prow:
                raise HTTPException(status_code=404, detail="Проект не найден в выбранной компании")
            if int(prow.get("company_id") or prow.get("company_id") or 0) != company_id:
                raise HTTPException(status_code=409, detail="Проект относится к другой компании")
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
    def delete_invite_code(
        id: int,
        x_company_id: str = Header(default=None, alias="X-Company-Id"),
        x_company_mode: str = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        context = resolve_work_company_context(cur, current_user, None, "delete", x_company_id=x_company_id, x_company_mode=x_company_mode)
        if (context or {}).get("mode") != "company":
            raise HTTPException(status_code=409, detail="Для удаления приглашения выберите одну конкретную компанию")
        actor = effective_company_user(current_user, context)
        role = str(actor.get("role") or "").strip()
        allowed_leadership = set(list(admin_roles) + ["руководитель", "администратор", "директор"])
        if role not in allowed_leadership and role != "system_owner":
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет удалять приглашения")
        # ensure invite belongs to the selected company
        company_id = int((context or {}).get("companyId") or (context or {}).get("company_id"))
        cur.execute("SELECT company_id FROM invite_codes WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Invite not found")
        if int(row.get("company_id") or 0) != company_id:
            conn.close()
            raise HTTPException(status_code=403, detail="Приглашение относится к другой компании")
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
