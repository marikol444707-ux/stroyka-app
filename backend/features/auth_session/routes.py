"""Restore the signed-in user from the HttpOnly session cookie.

The browser cannot read that cookie, and the screen used to look only at
localStorage. This read-only check returns the public profile already stored
for the session. It does not accept a bearer token and does not write.
"""

from fastapi import HTTPException, Request

try:
    import psycopg2.extras
except ImportError:  # pragma: no cover - tests can inject a cursor factory
    psycopg2 = None


SESSION_SELECT_SQL = """SELECT u.*, s.two_factor_passed AS auth_session_two_factor_passed
           FROM user_sessions s
           JOIN users u ON u.id=s.user_id
           WHERE s.session_hash=%s
             AND s.revoked_at IS NULL
             AND s.expires_at>NOW()
           LIMIT 1"""

_SECRET_FIELDS = ("password", "two_factor_secret", "authToken", "auth_token")


def register_auth_session_module(app, deps):
    get_db = deps["get_db"]
    cookie_name = deps["session_cookie_name"]
    session_token_hash = deps["session_token_hash"]
    public_user = deps["public_user"]
    user_requires_2fa = deps["user_requires_2fa"]
    enrich_worker_project_links = deps["enrich_worker_project_links"]
    cursor_factory = deps.get("cursor_factory") or psycopg2.extras.RealDictCursor

    @app.get("/auth/session")
    def read_auth_session(request: Request):
        try:
            token = request.cookies.get(cookie_name) if request is not None else ""
        except Exception:
            token = ""
        if not isinstance(token, str) or not token.strip():
            raise HTTPException(status_code=401, detail="Требуется вход в систему")

        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(SESSION_SELECT_SQL, (session_token_hash(token),))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="Сессия недействительна. Войдите заново.")
            if user.get("active") is False:
                raise HTTPException(status_code=403, detail="Аккаунт отключён. Обратитесь к администратору.")
            if user_requires_2fa(user) and not user.get("auth_session_two_factor_passed"):
                raise HTTPException(status_code=401, detail="Требуется подтверждение 2FA")
            for secret_field in _SECRET_FIELDS:
                user.pop(secret_field, None)
            user = enrich_worker_project_links(cur, user) or user
            payload = public_user(
                user,
                include_token=False,
                two_factor_passed=bool(user.get("auth_session_two_factor_passed")),
            )
            if not isinstance(payload, dict):
                raise HTTPException(status_code=401, detail="Сессия недействительна. Войдите заново.")
            for secret_field in _SECRET_FIELDS:
                payload.pop(secret_field, None)
            if not payload.get("id") or not str(payload.get("role") or "").strip():
                raise HTTPException(status_code=401, detail="Сессия недействительна. Войдите заново.")
            return payload
        finally:
            conn.rollback()
            cur.close()
            conn.close()
