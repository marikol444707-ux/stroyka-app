"""Routes moved verbatim from backend/main.py."""

import hashlib
import hmac
import json
import os
import secrets
from fastapi import APIRouter, HTTPException
try:
    from backend.auth import _revoke_user_sessions, hash_password
except ModuleNotFoundError:
    from auth import _revoke_user_sessions, hash_password

def register_password_reset_module(app, deps):
    APP_PUBLIC_URL = deps['APP_PUBLIC_URL']
    AUTH_SECRET = deps['AUTH_SECRET']
    SYSTEM_PROJECT_NAME = deps['SYSTEM_PROJECT_NAME']
    _password_reset_dedupe_key = deps['_password_reset_dedupe_key']
    _send_email = deps['_send_email']
    _should_skip_password_reset_email = deps['_should_skip_password_reset_email']
    get_db = deps['get_db']
    log_audit = deps['log_audit']
    router = APIRouter()

    def _password_reset_token_hash(email: str, code: str) -> str:
        normalized_email = (email or "").strip().lower()
        normalized_code = (code or "").strip()
        return hmac.new(
            AUTH_SECRET.encode("utf-8"),
            f"password-reset:{normalized_email}:{normalized_code}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _upsert_password_reset_task(cur, user_id, user_name: str, email: str, code: str, expires, email_sent: bool):
        dedupe_key = _password_reset_dedupe_key(user_id)
        expires_text = expires.strftime("%d.%m.%Y %H:%M")
        title = f"Сброс пароля: {email}"
        code_line = (
            f"Код: {code}\n"
            if code else
            "Код отправлен на email пользователя и не хранится в задаче.\n"
        )
        description = (
            f"Пользователь {user_name or email} запросил восстановление пароля.\n"
            f"Email: {email}\n"
            f"{code_line}"
            f"Действует до: {expires_text}\n\n"
            + (
                "Передайте код пользователю или задайте новый пароль в разделе Пользователи."
                if not email_sent else
                "Письмо отправлено. Задача оставлена как журнал события и контроль поддержки."
            )
        )
        action_payload = json.dumps({
            "type": "password_reset_request",
            "email": email,
            "userId": user_id,
            "dedupeKey": dedupe_key,
        }, ensure_ascii=False)
        cur.execute("""
            SELECT id
            FROM ai_tasks
            WHERE project_name=%s
              AND owner_scope='platform'
              AND company_id IS NULL
              AND project_id IS NULL
              AND dedupe_key=%s
              AND status NOT IN ('Закрыто','Отклонено')
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        """, (SYSTEM_PROJECT_NAME, dedupe_key))
        existing = cur.fetchone()
        if existing:
            task_id = existing[0]
            cur.execute("""
                UPDATE ai_tasks
                SET title=%s,
                    description=%s,
                    assigned_role='директор',
                    assigned_to='',
                    status='Новое',
                    due_date=%s,
                    accepted_by=NULL,
                    accepted_at=NULL,
                    closed_by=NULL,
                    closed_at=NULL,
                    action_label='Открыть пользователей',
                    action_payload=%s,
                    updated_at=NOW()
                WHERE id=%s AND owner_scope='platform' AND company_id IS NULL AND project_id IS NULL
            """, (title, description, expires.date(), action_payload, task_id))
            return task_id
        cur.execute("""
            INSERT INTO ai_tasks (
                owner_scope, company_id, project_id, finding_id, project_name, title, description, assigned_role, assigned_to,
                status, due_date, action_label, action_payload, dedupe_key, created_at, updated_at
            ) VALUES ('platform',NULL,NULL,NULL,%s,%s,%s,'директор','','Новое',%s,'Открыть пользователей',%s,%s,NOW(),NOW())
            RETURNING id
        """, (SYSTEM_PROJECT_NAME, title, description, expires.date(), action_payload, dedupe_key))
        row = cur.fetchone()
        return row[0] if row else None

    def _close_password_reset_task(cur, user_id):
        cur.execute("""
            UPDATE ai_tasks
            SET status='Закрыто',
                closed_by='system',
                closed_at=NOW(),
                updated_at=NOW()
            WHERE project_name=%s
              AND owner_scope='platform'
              AND company_id IS NULL
              AND project_id IS NULL
              AND dedupe_key=%s
              AND status NOT IN ('Закрыто','Отклонено')
        """, (SYSTEM_PROJECT_NAME, _password_reset_dedupe_key(user_id)))

    def _verify_password_reset_token(email: str, code: str, stored: str) -> bool:
        token = (stored or "").strip()
        clean_code = (code or "").strip()
        if not token or not clean_code:
            return False
        # Backward compatibility for reset codes created before hashed storage.
        if token.isdigit() and len(token) == 6:
            return hmac.compare_digest(token, clean_code)
        return hmac.compare_digest(token, _password_reset_token_hash(email, clean_code))

    def _send_password_reset_email(email: str, user_name: str, code: str, expires) -> bool:
        if _should_skip_password_reset_email(email):
            return False
        expires_text = expires.strftime("%d.%m.%Y %H:%M")
        body = (
            f"Здравствуйте, {user_name or 'пользователь'}.\n\n"
            "Для входа в СтройКа был запрошен сброс пароля.\n\n"
            f"Код восстановления: {code}\n"
            f"Действует до: {expires_text}\n\n"
            f"Откройте {APP_PUBLIC_URL} и введите этот код в форме восстановления пароля.\n"
            "Если вы не запрашивали сброс, просто проигнорируйте письмо."
        )
        return _send_email(email, "Код восстановления пароля СтройКа", body)

    @router.post("/password-reset-request")
    def password_reset_request(data: dict):
        """Генерирует 6-значный код для восстановления пароля. Действителен 30 минут."""
        from datetime import datetime as _dt, timedelta as _td
        email = (data.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Введите email")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM users WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            # Не палим существование email для безопасности
            return {"ok": True, "message": "Если такой email зарегистрирован, код восстановления создан"}
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        expires = _dt.now() + _td(minutes=30)
        token_hash = _password_reset_token_hash(email, code)
        cur.execute("UPDATE users SET reset_token=%s, reset_token_expires=%s WHERE id=%s", (token_hash, expires, row[0]))
        email_sent = _send_password_reset_email(email, row[1] or "", code, expires)
        fallback_code = code if not email_sent else ""
        _upsert_password_reset_task(cur, row[0], row[1], email, fallback_code, expires, email_sent)
        conn.commit()
        cur.close(); conn.close()
        if os.getenv("SHOW_RESET_CODE", "").lower() in ("1", "true", "yes"):
            print(f"PASSWORD RESET CODE for {email}: {code} (valid 30 min)")
        log_audit(user_name=row[1] or "—", user_role="—",
                  action="password_reset_request", entity_type="user", entity_id=row[0],
                  description="Запрошен код восстановления пароля" + ("; email отправлен" if email_sent else "; email не отправлен"))
        response = {
            "ok": True,
            "message": "Код восстановления отправлен на email" if email_sent else "Код восстановления создан. Если почта не подключена, его выдаст директор.",
            "emailSent": email_sent,
        }
        if os.getenv("SHOW_RESET_CODE", "").lower() in ("1", "true", "yes"):
            response["_devCode"] = code
        return response

    @router.post("/password-reset")
    def password_reset(data: dict):
        """Меняет пароль по коду восстановления."""
        from datetime import datetime as _dt
        email = (data.get("email") or "").strip().lower()
        code = (data.get("code") or "").strip()
        new_password = (data.get("newPassword") or "").strip()
        if not email or not code or not new_password:
            raise HTTPException(status_code=400, detail="Заполните email, код и новый пароль")
        if len(new_password) < 5:
            raise HTTPException(status_code=400, detail="Пароль должен быть не короче 5 символов")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, reset_token, reset_token_expires FROM users WHERE LOWER(email)=%s", (email,))
        row = cur.fetchone()
        if not row or not row[1] or not _verify_password_reset_token(email, code, row[1]):
            cur.close(); conn.close()
            raise HTTPException(status_code=401, detail="Неверный код или email")
        if row[2] and row[2] < _dt.now():
            cur.close(); conn.close()
            raise HTTPException(status_code=401, detail="Код истёк — запросите новый")
        cur.execute("UPDATE users SET password=%s, reset_token=NULL, reset_token_expires=NULL, failed_login_count=0, locked_until=NULL WHERE id=%s",
                    (hash_password(new_password), row[0]))
        _revoke_user_sessions(cur, row[0])
        _close_password_reset_task(cur, row[0])
        conn.commit()
        cur.close(); conn.close()
        log_audit(user_name="—", user_role="—",
                  action="password_reset", entity_type="user", entity_id=row[0],
                  description="Сброс пароля через код восстановления")
        return {"ok": True, "message": "Пароль изменён, можно входить"}

    app.include_router(router)

