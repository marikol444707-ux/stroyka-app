"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
try:
    from backend.auth import AUTH_SESSION_COOKIE_NAME, CSRF_TOKEN_TTL_SECONDS, CookieSessionAuthenticationError, _create_csrf_token, build_cookie_session_authentication
except ModuleNotFoundError:
    from auth import AUTH_SESSION_COOKIE_NAME, CSRF_TOKEN_TTL_SECONDS, CookieSessionAuthenticationError, _create_csrf_token, build_cookie_session_authentication

def register_csrf_token_module(app, deps):
    _current_user_from_session_cookie = deps['_current_user_from_session_cookie']
    router = APIRouter()

    @router.get("/csrf-token")
    def csrf_token(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        try:
            build_cookie_session_authentication(
                request,
                authorization,
                None,
                require_csrf=False,
            )
        except CookieSessionAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=exc.code)
        _current_user_from_session_cookie(request)
        session_token = request.cookies.get(AUTH_SESSION_COOKIE_NAME)
        if not session_token:
            raise HTTPException(status_code=401, detail="Требуется cookie-сессия")
        return {
            "csrfToken": _create_csrf_token(session_token),
            "expiresIn": CSRF_TOKEN_TTL_SECONDS,
        }

    app.include_router(router)

