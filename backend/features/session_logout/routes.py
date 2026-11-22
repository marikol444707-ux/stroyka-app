"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from typing import Optional
import psycopg2
try:
    from backend.auth import AUTH_SESSION_COOKIE_NAME, CSRF_LOGOUT_ENFORCED, _clear_auth_session_cookie, _session_token_hash, _valid_csrf_token
except ModuleNotFoundError:
    from auth import AUTH_SESSION_COOKIE_NAME, CSRF_LOGOUT_ENFORCED, _clear_auth_session_cookie, _session_token_hash, _valid_csrf_token

def register_session_logout_module(app, deps):
    get_db = deps['get_db']
    log_audit = deps['log_audit']
    router = APIRouter()

    def require_csrf_for_cookie_mutation(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    ) -> None:
        if not CSRF_LOGOUT_ENFORCED:
            return None
        if authorization and authorization.lower().startswith("bearer "):
            return None
        session_token = request.cookies.get(AUTH_SESSION_COOKIE_NAME)
        if not session_token:
            return None
        if not _valid_csrf_token(x_csrf_token or "", session_token):
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
        return None

    @router.post("/logout")
    def logout(response: Response, request: Request, _csrf: None = Depends(require_csrf_for_cookie_mutation)):
        token = request.cookies.get(AUTH_SESSION_COOKIE_NAME)
        user_id = None
        if token:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """UPDATE user_sessions
                   SET revoked_at=NOW()
                   WHERE session_hash=%s AND revoked_at IS NULL
                   RETURNING user_id""",
                (_session_token_hash(token),),
            )
            row = cur.fetchone()
            user_id = row.get("user_id") if row else None
            conn.commit()
            cur.close(); conn.close()
        _clear_auth_session_cookie(response)
        if user_id:
            log_audit(user_name="—", user_role="—", action="logout", entity_type="user", entity_id=user_id, description="Выход из серверной сессии")
        return {"ok": True}

    app.include_router(router)

