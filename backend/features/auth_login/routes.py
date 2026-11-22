"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
import psycopg2
try:
    from backend.auth import _create_auth_session, _generate_totp_secret, _set_auth_session_cookie, _two_factor_challenge_response, _two_factor_setup_response, _user_requires_2fa, _verify_signed_flow_token, _verify_totp_code, hash_password, is_legacy_password, verify_password
except ModuleNotFoundError:
    from auth import _create_auth_session, _generate_totp_secret, _set_auth_session_cookie, _two_factor_challenge_response, _two_factor_setup_response, _user_requires_2fa, _verify_signed_flow_token, _verify_totp_code, hash_password, is_legacy_password, verify_password

def register_auth_login_module(app, deps):
    enrich_worker_project_links = deps['enrich_worker_project_links']
    get_db = deps['get_db']
    log_audit = deps['log_audit']
    public_user = deps['public_user']
    router = APIRouter()

    class LoginModel(BaseModel):
        email: str
        password: str

    class TwoFactorVerifyModel(BaseModel):
        challengeToken: str = ""
        code: str = ""

    class TwoFactorSetupConfirmModel(BaseModel):
        setupToken: str = ""
        code: str = ""

    @router.post("/login")
    def login(data: LoginModel, response: Response, request: Request):
        from datetime import datetime as _dt, timedelta as _td
        email = (data.email or "").strip().lower()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Проверяем не заблокирован ли пользователь
        cur.execute("SELECT id, failed_login_count, locked_until FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
        user_check = cur.fetchone()
        if user_check and user_check.get('locked_until'):
            if user_check['locked_until'] > _dt.now():
                mins_left = int((user_check['locked_until'] - _dt.now()).total_seconds() / 60) + 1
                conn.close()
                raise HTTPException(status_code=429, detail="Аккаунт временно заблокирован после 5 неверных попыток. Попробуйте через "+str(mins_left)+" мин.")
            else:
                # Срок блокировки истёк — сбрасываем
                cur.execute("UPDATE users SET failed_login_count=0, locked_until=NULL WHERE id=%s", (user_check['id'],))
                conn.commit()
        # Логинимся: пароль проверяем в Python, чтобы поддержать хеши и старые plaintext-пароли.
        cur.execute("SELECT * FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
        user = cur.fetchone()
        if user and user.get("active") is False:
            conn.close()
            raise HTTPException(status_code=403, detail="Аккаунт отключён. Обратитесь к администратору.")
        if not user or not verify_password(data.password, user.get("password") or ""):
            # Увеличиваем счётчик неудачных попыток
            if user_check:
                new_count = (user_check.get('failed_login_count') or 0) + 1
                if new_count >= 5:
                    lock_until = _dt.now() + _td(minutes=15)
                    cur.execute("UPDATE users SET failed_login_count=%s, locked_until=%s WHERE id=%s", (new_count, lock_until, user_check['id']))
                    conn.commit()
                    conn.close()
                    raise HTTPException(status_code=429, detail="Превышено количество попыток. Аккаунт заблокирован на 15 минут.")
                else:
                    cur.execute("UPDATE users SET failed_login_count=%s WHERE id=%s", (new_count, user_check['id']))
                    conn.commit()
            conn.close()
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
        # Успех — сбрасываем счётчик
        if is_legacy_password(user.get("password") or ""):
            new_hash = hash_password(data.password)
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (new_hash, user['id']))
            user["password"] = new_hash
        if _user_requires_2fa(user):
            user["two_factor_required"] = True
            cur.execute("UPDATE users SET failed_login_count=0, locked_until=NULL, two_factor_required=TRUE WHERE id=%s", (user['id'],))
            if not user.get("two_factor_secret") or not user.get("two_factor_enabled"):
                secret = user.get("two_factor_secret") or _generate_totp_secret()
                cur.execute(
                    "UPDATE users SET two_factor_secret=%s, two_factor_enabled=FALSE, two_factor_required=TRUE WHERE id=%s",
                    (secret, user['id']),
                )
                user["two_factor_secret"] = secret
                user["two_factor_enabled"] = False
                conn.commit()
                conn.close()
                return _two_factor_setup_response(user, secret)
            conn.commit()
            conn.close()
            return _two_factor_challenge_response(user)
        cur.execute("UPDATE users SET failed_login_count=0, locked_until=NULL WHERE id=%s", (user['id'],))
        session_token = _create_auth_session(cur, user, request, two_factor_passed=False)
        conn.commit()
        user = enrich_worker_project_links(cur, user)
        conn.close()
        _set_auth_session_cookie(response, session_token)
        log_audit(user_name=user.get("name",""), user_role=user.get("role",""),
                  action="login", entity_type="user", entity_id=user['id'],
                  description="Успешный вход в систему")
        return public_user(user, include_token=True, two_factor_passed=False)

    @router.post("/login/2fa/verify")
    def verify_login_2fa(data: TwoFactorVerifyModel, response: Response, request: Request):
        payload = _verify_signed_flow_token(data.challengeToken, "2fa_login")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE id=%s", (payload.get("userId"),))
        user = cur.fetchone()
        if not user or user.get("active") is False:
            conn.close()
            raise HTTPException(status_code=401, detail="Пользователь не найден или отключён")
        if not _user_requires_2fa(user) or not user.get("two_factor_enabled") or not user.get("two_factor_secret"):
            conn.close()
            raise HTTPException(status_code=400, detail="2FA для пользователя не настроена")
        if not _verify_totp_code(user.get("two_factor_secret") or "", data.code):
            conn.close()
            raise HTTPException(status_code=401, detail="Неверный код 2FA")
        cur.execute("UPDATE users SET failed_login_count=0, locked_until=NULL WHERE id=%s", (user["id"],))
        session_token = _create_auth_session(cur, user, request, two_factor_passed=True)
        conn.commit()
        user = enrich_worker_project_links(cur, user)
        conn.close()
        _set_auth_session_cookie(response, session_token)
        log_audit(user_name=user.get("name",""), user_role=user.get("role",""),
                  action="login", entity_type="user", entity_id=user['id'],
                  description="Успешный вход в систему с 2FA")
        return public_user(user, include_token=True, two_factor_passed=True)

    @router.post("/login/2fa/setup-confirm")
    def confirm_login_2fa_setup(data: TwoFactorSetupConfirmModel, response: Response, request: Request):
        payload = _verify_signed_flow_token(data.setupToken, "2fa_setup")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE id=%s", (payload.get("userId"),))
        user = cur.fetchone()
        if not user or user.get("active") is False:
            conn.close()
            raise HTTPException(status_code=401, detail="Пользователь не найден или отключён")
        if not _user_requires_2fa(user) or not user.get("two_factor_secret"):
            conn.close()
            raise HTTPException(status_code=400, detail="2FA не требуется или не подготовлена")
        if not _verify_totp_code(user.get("two_factor_secret") or "", data.code):
            conn.close()
            raise HTTPException(status_code=401, detail="Неверный код 2FA")
        cur.execute(
            "UPDATE users SET two_factor_enabled=TRUE, two_factor_required=TRUE, two_factor_confirmed_at=NOW(), failed_login_count=0, locked_until=NULL WHERE id=%s",
            (user["id"],),
        )
        session_token = _create_auth_session(cur, user, request, two_factor_passed=True)
        conn.commit()
        user["two_factor_enabled"] = True
        user["two_factor_required"] = True
        user = enrich_worker_project_links(cur, user)
        conn.close()
        _set_auth_session_cookie(response, session_token)
        log_audit(user_name=user.get("name",""), user_role=user.get("role",""),
                  action="2fa_setup", entity_type="user", entity_id=user['id'],
                  description="Пользователь включил 2FA")
        return public_user(user, include_token=True, two_factor_passed=True)

    app.include_router(router)

