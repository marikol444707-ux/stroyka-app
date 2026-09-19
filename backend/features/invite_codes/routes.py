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

from .supplier_relationship import create_supplier_invite, directory


def register_invite_codes_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    prepare_user_access_scope = deps["prepare_user_access_scope"]

    @app.get("/invite-codes")
    def get_invite_codes(_current_user: dict = Depends(require_roles(*admin_roles, "system_owner")),
                         x_company_id: str = Header(None, alias='X-Company-Id'),
                         x_company_mode: str = Header(None, alias='X-Company-Mode')):
        # Scoped invitation codes must not be disclosed to another buyer.
        try:
            with directory(deps).transaction(_current_user, (x_company_id, x_company_mode)) as (_cur, company, _actor):
                company_id = company['id']
        except HTTPException:
            company_id = None
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''SELECT i.* FROM invite_codes i LEFT JOIN supplier_invite_companies b ON b.invite_id=i.id
                       WHERE b.invite_id IS NULL OR b.company_id=%s ORDER BY i.id DESC''', (company_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/invite-codes")
    def create_invite_code(data: dict, _current_user: dict = Depends(require_roles(*admin_roles, "system_owner")),
                           x_company_id: str = Header(None, alias='X-Company-Id'),
                           x_company_mode: str = Header(None, alias='X-Company-Mode')):
        from datetime import datetime, timedelta
        role = data.get('role') or ''
        if not role:
            raise HTTPException(status_code=400, detail="Не указана роль")
        if role == 'поставщик':
            return create_supplier_invite(deps, _current_user, data, (x_company_id, x_company_mode))
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
        company_id = data.get("companyId") or data.get("company_id")
        platform_account_id = data.get("platformAccountId") or data.get("platform_account_id")
        try:
            company_id = int(company_id) if company_id not in (None, "") else None
        except Exception:
            company_id = None
        try:
            platform_account_id = int(platform_account_id) if platform_account_id not in (None, "") else None
        except Exception:
            platform_account_id = None
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
    def delete_invite_code(id: int, _current_user: dict = Depends(require_roles(*admin_roles, "system_owner")),
                           x_company_id: str = Header(None, alias='X-Company-Id'),
                           x_company_mode: str = Header(None, alias='X-Company-Mode')):
        conn = get_db()
        try:
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout='15s'")
            # Registration locks invite before company. Keep the same order,
            # including while the scoped authorization transaction is open.
            cur.execute('SELECT id FROM invite_codes WHERE id=%s FOR UPDATE', (id,))
            if not cur.fetchone():
                return {"ok": True}
            cur.execute('SELECT company_id FROM supplier_invite_companies WHERE invite_id=%s', (id,))
            binding = cur.fetchone()
            if binding:
                with directory(deps).transaction(_current_user, (x_company_id, x_company_mode), write=True) as (scoped, company, actor):
                    if company['id'] != binding[0] or actor.get('role') not in admin_roles:
                        raise HTTPException(403, 'Приглашение относится к другой компании')
                    cur.execute('DELETE FROM invite_codes WHERE id=%s', (id,))
                    conn.commit()
            else:
                cur.execute("DELETE FROM invite_codes WHERE id=%s", (id,))
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
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
