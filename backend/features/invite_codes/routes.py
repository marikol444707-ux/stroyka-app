"""Company-owned invitations and separate supplier relationship invitations."""


import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from .supplier_relationship import create_supplier_invite, directory
from .company_membership import create_company_invite, request_headers
from ..company_users.access import ADMIN_ROLES, COMPANY_ROLES, transaction


def register_invite_codes_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    authenticated = deps.get("authenticated") or require_roles(*admin_roles, "system_owner")

    @app.get("/invite-codes")
    def get_invite_codes(_current_user: dict = Depends(authenticated),
                         x_company_id: str = Header(None, alias='X-Company-Id'),
                         x_company_mode: str = Header(None, alias='X-Company-Mode')):
        with transaction(deps, _current_user, request_headers((x_company_id,x_company_mode))) as (cur, actor, company):
            if actor['role'] not in ADMIN_ROLES:
                raise HTTPException(403, 'Приглашениями управляет руководитель компании')
            cur.execute("SELECT to_regclass('public.supplier_team_invites') AS relation")
            has_team = cur.fetchone()['relation']
            team_filter = ' AND NOT EXISTS(SELECT 1 FROM supplier_team_invites t WHERE t.invite_id=i.id)' if has_team else ''
            cur.execute('''SELECT i.* FROM invite_codes i LEFT JOIN supplier_invite_companies b ON b.invite_id=i.id
                WHERE ((b.invite_id IS NULL AND i.company_id=%s AND i.role=ANY(%s))
                    OR b.company_id=%s)'''+team_filter+' ORDER BY i.id DESC',
                (company,list(COMPANY_ROLES),company))
            return [dict(row) for row in cur.fetchall()]

    @app.post("/invite-codes")
    def create_invite_code(data: dict, _current_user: dict = Depends(authenticated),
                           x_company_id: str = Header(None, alias='X-Company-Id'),
                           x_company_mode: str = Header(None, alias='X-Company-Mode')):
        role = data.get('role') or ''
        if not role:
            raise HTTPException(status_code=400, detail="Не указана роль")
        if role == 'поставщик':
            return create_supplier_invite(deps, _current_user, data, (x_company_id, x_company_mode))
        return create_company_invite(deps, _current_user, data, (x_company_id, x_company_mode))

    @app.delete("/invite-codes/{id}")
    def delete_invite_code(id: int, _current_user: dict = Depends(authenticated),
                           x_company_id: str = Header(None, alias='X-Company-Id'),
                           x_company_mode: str = Header(None, alias='X-Company-Mode')):
        conn = get_db()
        try:
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout='15s'")
            # Registration locks invite before company. Keep the same order,
            # including while the scoped authorization transaction is open.
            cur.execute('SELECT company_id,role FROM invite_codes WHERE id=%s FOR UPDATE', (id,))
            invite = cur.fetchone()
            if not invite:
                return {"ok": True}
            cur.execute("SELECT to_regclass('public.supplier_team_invites')")
            if cur.fetchone()[0]:
                cur.execute('SELECT invite_id FROM supplier_team_invites WHERE invite_id=%s', (id,))
                if cur.fetchone():
                    raise HTTPException(403, 'Управляйте приглашением в кабинете поставщика')
            cur.execute('SELECT company_id FROM supplier_invite_companies WHERE invite_id=%s', (id,))
            binding = cur.fetchone()
            if binding:
                with directory(deps).transaction(_current_user, (x_company_id, x_company_mode), write=True) as (scoped, company, actor):
                    if company['id'] != binding[0] or actor.get('role') not in admin_roles:
                        raise HTTPException(403, 'Приглашение относится к другой компании')
                    cur.execute('DELETE FROM invite_codes WHERE id=%s', (id,))
                    conn.commit()
            else:
                with transaction(deps, _current_user, request_headers((x_company_id,x_company_mode)), True) as (scoped, actor, company):
                    if invite[0] != company or invite[1] not in COMPANY_ROLES:
                        raise HTTPException(403, 'Приглашение относится к другой компании')
                    if actor['role']=='зам_директора' and invite[1] in ('директор','зам_директора'):
                        raise HTTPException(403, 'Приглашениями руководителей управляет директор')
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
        team = None
        try:
            if row and not row.get('used'):
                from ..supplier_team.invitations import validate_binding
                team = validate_binding(cur, row)
        except HTTPException:
            return {"valid": False, "error": "Приглашение больше не действует"}
        finally:
            conn.close()
        if not row:
            return {"valid": False, "error": "Код не найден"}
        if row.get('used'):
            return {"valid": False, "error": "Код уже использован"}
        if row.get('expires_at') and row['expires_at'] < datetime.now():
            return {"valid": False, "error": "Срок действия ссылки истёк"}
        return {
            "valid": True,
            "supplierTeam": bool(team),
            "role": row['role'],
            "presetName": row.get('preset_name') or '',
            "presetCategory": row.get('preset_category') or '',
            "supplierId": row.get('supplier_id'),
            "companyId": row.get('company_id'),
            "platformAccountId": row.get('platform_account_id'),
        }
