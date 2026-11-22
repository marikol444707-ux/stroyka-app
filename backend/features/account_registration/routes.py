"""Routes moved verbatim from backend/main.py."""

import json
from fastapi import APIRouter, HTTPException, Request, Response
import psycopg2
try:
    from backend.auth import _create_auth_session, _generate_totp_secret, _set_auth_session_cookie, _two_factor_setup_response, _user_requires_2fa, hash_password
except ModuleNotFoundError:
    from auth import _create_auth_session, _generate_totp_secret, _set_auth_session_cookie, _two_factor_setup_response, _user_requires_2fa, hash_password

def register_account_registration_module(app, deps):
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    _normalize_supplier_name_key = deps['_normalize_supplier_name_key']
    _remember_supplier_alias = deps['_remember_supplier_alias']
    _supplier_extract_requisites = deps['_supplier_extract_requisites']
    _supplier_find_match = deps['_supplier_find_match']
    get_db = deps['get_db']
    public_user = deps['public_user']
    router = APIRouter()

    @router.post("/register")
    def register(data: dict, response: Response, request: Request):
        from datetime import datetime
        code = (data.get("code") or "").strip()
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        if not code or not name or not email or not password:
            raise HTTPException(status_code=400, detail="Заполните имя, email, пароль и код приглашения")
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM invite_codes WHERE code=%s AND used=FALSE FOR UPDATE", (code,))
        invite = cur.fetchone()
        if not invite:
            conn.close()
            raise HTTPException(status_code=400, detail="Неверный или использованный код")
        role = invite['role']
        # Проверка срока действия
        if invite.get('expires_at') and invite['expires_at'] < datetime.now():
            conn.close()
            raise HTTPException(status_code=400, detail="Код истёк — попросите новую ссылку")
        try:
            from backend.features.supplier_team.invitations import validate_binding
            team_invite = validate_binding(cur, invite, lock=True)
            from backend.features.company_users.access import COMPANY_ROLES, save_membership
            from backend.features.invite_codes.company_membership import registration_scope
            company_id = None
            platform_account_id = None
            project_id = None
            project_name = ''
            assigned_projects = []
            assigned_packages = []
            if role in COMPANY_ROLES:
                company_id, platform_account_id, project_id, project_name, assigned_projects, assigned_packages = registration_scope(cur, invite)
            elif role in ("account_owner", "account_admin"):
                platform_account_id = invite.get('platform_account_id')
                cur.execute('SELECT id FROM platform_accounts WHERE id=%s AND COALESCE(active,TRUE)=TRUE FOR SHARE', (platform_account_id,))
                if not cur.fetchone():
                    raise HTTPException(409, 'Клиентский аккаунт приглашения недоступен')
            elif role != 'поставщик' and role not in PLATFORM_STAFF_ROLES:
                raise HTTPException(403, 'Недопустимая роль приглашения')
            cur.execute("""INSERT INTO users
                              (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,company_id,platform_account_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING *""",
                        (name, email, hash_password(password), role, project_id, project_name,
                         json.dumps(assigned_projects), json.dumps(assigned_packages), company_id, platform_account_id))
            user = cur.fetchone()
            if role in COMPANY_ROLES:
                save_membership(cur, user['id'], company_id, role, assigned_projects, assigned_packages, True, {'is_default':True})
            if team_invite:
                cur.execute("INSERT INTO supplier_team_members(supplier_id,user_id,role) VALUES(%s,%s,'manager')",
                            (team_invite['supplier_id'], user['id']))
            # Company owners and invited team members have separate registration paths.
            if role == 'поставщик' and not team_invite:
                company_name = data.get("companyName") or name
                supplier_id = invite.get('supplier_id')
                supplier_payload = {
                    **(data or {}),
                    "name": company_name,
                    "companyName": company_name,
                    "email": email,
                    "category": invite.get('preset_category') or data.get("category",""),
                    "status": "Активный",
                    "sourceType": "invite_link",
                    "sourceDetail": "Регистрация поставщика по ссылке приглашения",
                }
                from backend.features.supplier_access.legal_identity import canonical_legal
                for key, lengths in (('inn', (10, 12)), ('ogrn', (13, 15))):
                    canonical = canonical_legal(supplier_payload.get(key), lengths)
                    if canonical is None:
                        raise HTTPException(422, 'Некорректные реквизиты поставщика: ' + key)
                    supplier_payload[key] = canonical
                requisites = _supplier_extract_requisites(supplier_payload)
                # Registration identity comes only from its explicit fields, not OCR
                # aliases or legal numbers extracted from names/free text.
                requisites.update({key: supplier_payload[key] for key in ('inn', 'ogrn')})
                requisites.update(name=str(company_name).strip(), nameKey=_normalize_supplier_name_key(company_name))
                from backend.features.invite_codes.supplier_relationship import lock_inviting_company, lock_invited_identity
                lock_inviting_company(cur, invite)
                lock_invited_identity(cur, invite, requisites)
                if not supplier_id:
                    from backend.features.invite_codes.supplier_relationship import matching_invited_card
                    supplier_id = matching_invited_card(cur, invite, requisites, _normalize_supplier_name_key)
                if supplier_id:
                    from backend.features.invite_codes.supplier_relationship import claim_invited_supplier
                    supplier_id = claim_invited_supplier(cur, {**invite, 'supplier_id': supplier_id}, user, requisites)
                else:
                    if _supplier_find_match(cur, supplier_payload):
                        raise HTTPException(409, 'Приглашение не подтверждает право управлять существующей организацией поставщика. Войдите в её кабинет или обратитесь к администратору платформы для проверки привязки')
                    # Создаём новую компанию
                    cur.execute(
                        "INSERT INTO suppliers (name, phone, email, category, specialization, "
                        "inn, kpp, ogrn, legal_address, bank, bik, account, director_name, "
                        "status, rating, user_id, registered_at, source_type, source_detail) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s) RETURNING id",
                        (company_name, data.get("phone",""), email,
                         invite.get('preset_category') or data.get("category",""),
                         data.get("specialization",""),
                         requisites.get("inn"), data.get("kpp"), requisites.get("ogrn"),
                         data.get("legalAddress"), data.get("bank"), data.get("bik"),
                         data.get("account"), data.get("directorName"),
                         'Активный', 5.0, user['id'],
                         "invite_link", "Регистрация поставщика по ссылке приглашения"))
                    new_supplier = cur.fetchone()
                    supplier_id = new_supplier.get("id") if isinstance(new_supplier, dict) else new_supplier[0]
                _remember_supplier_alias(cur, supplier_id, supplier_payload, source="supplier_invite", requisites=requisites)
                from backend.features.invite_codes.supplier_relationship import link_registered_supplier
                link_registered_supplier(cur, invite, supplier_id, user, supplier_payload)
            cur.execute("UPDATE invite_codes SET used=TRUE WHERE code=%s", (code,))
            session_token = None
            if _user_requires_2fa(user):
                secret = user.get("two_factor_secret") or _generate_totp_secret()
                cur.execute(
                    "UPDATE users SET two_factor_secret=%s, two_factor_enabled=FALSE, two_factor_required=TRUE WHERE id=%s",
                    (secret, user["id"]),
                )
                user["two_factor_secret"] = secret
                user["two_factor_enabled"] = False
                user["two_factor_required"] = True
            else:
                session_token = _create_auth_session(cur, user, request, two_factor_passed=False)
            conn.commit()
            conn.close()
            if _user_requires_2fa(user):
                return _two_factor_setup_response(user, user.get("two_factor_secret") or secret)
            if session_token:
                _set_auth_session_cookie(response, session_token)
            return public_user(user, include_token=True, two_factor_passed=False)
        except HTTPException:
            conn.rollback()
            conn.close()
            raise
        except Exception as e:
            conn.rollback()
            conn.close()
            raise HTTPException(status_code=400, detail=str(e))

    app.include_router(router)

