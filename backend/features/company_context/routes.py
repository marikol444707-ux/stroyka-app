import os
from urllib.parse import urlsplit
import psycopg2.extras
from fastapi import Depends, Request, HTTPException

from .service import build_company_context_response
from .qa_readonly import QAReadOnlyAuthRejected, resolve_qa_identity_read_only
from backend.auth import build_cookie_session_authentication, CookieSessionAuthenticationError


_PRODUCTION_QA_DENYLIST = frozenset({
    "stroyka26.pro", "www.stroyka26.pro",
    "stroyka.pro", "www.stroyka.pro", "147.45.237.127",
})


def qa_readonly_endpoint_enabled() -> bool:
    """Use server-side config, never the untrusted request Host header."""
    if (
        os.getenv("JEV_QA_READONLY_AUTH_ENABLED") != "1"
        or os.getenv("QA_ENVIRONMENT", "").strip().lower() not in {"qa", "test", "staging"}
    ):
        return False
    public = os.getenv("APP_PUBLIC_URL", "").strip()
    permitted = os.getenv("QA_ALLOWED_ORIGIN", "").strip()
    try:
        left, right = urlsplit(public), urlsplit(permitted)
        host = (left.hostname or "").lower().rstrip(".")
        if (
            left.scheme != "https" or right.scheme != "https"
            or not host or host in _PRODUCTION_QA_DENYLIST
            or host.endswith(".stroyka26.pro") or host.endswith(".stroyka.pro")
            or left.username is not None or left.password is not None
            or right.username is not None or right.password is not None
            or left.path not in {"", "/"} or right.path not in {"", "/"}
            or left.query or right.query or left.fragment or right.fragment
            or (left.scheme, host, left.port or 443)
               != (right.scheme, (right.hostname or "").lower().rstrip("."), right.port or 443)
        ):
            return False
    except (ValueError, TypeError):
        return False
    return True


def register_company_context_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    platform_staff_roles = tuple(deps.get("platform_staff_roles") or ())
    client_account_roles = tuple(deps.get("client_account_roles") or ())

    def company_context_payload(current_user: dict):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_company_context_response(
                cur,
                current_user,
                platform_staff_roles=platform_staff_roles,
                client_account_roles=client_account_roles,
            )
        finally:
            cur.close()
            conn.close()

    @app.get("/company-context")
    def get_company_context(current_user: dict = Depends(get_current_user)):
        """Доступные компании пользователя. Read-only слой для безопасной SaaS-миграции."""
        return company_context_payload(current_user)

    @app.get("/users/company-context")
    def get_company_context_proxy_alias(current_user: dict = Depends(get_current_user)):
        """Alias под уже проксируемый nginx prefix /users."""
        return company_context_payload(current_user)

    @app.get("/users/qa-readonly-context")
    def get_qa_readonly_context(request: Request):
        """Opt-in QA-only, cookie-only session projection without DB writes.

        Disabled by default in all environments. The connection is explicitly
        read-only before the first user/session query; do not call the legacy
        get_current_user dependency or write audit/presence records.
        """
        if not qa_readonly_endpoint_enabled():
            raise HTTPException(status_code=404, detail="not found")
        if request.headers.get("authorization") is not None:
            raise HTTPException(status_code=401, detail="QA_READ_ONLY_AUTH_REJECTED")
        try:
            authentication = build_cookie_session_authentication(
                request, authorization=None, require_csrf=False,
            )
        except CookieSessionAuthenticationError:
            raise HTTPException(status_code=401, detail="QA_READ_ONLY_AUTH_REJECTED") from None

        conn = get_db()
        cur = None
        try:
            # get_db() normally enables autocommit. SET TRANSACTION READ ONLY
            # is ineffective outside an explicit transaction in that mode.
            # This is a fresh per-request connection, never a shared pool.
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SET TRANSACTION READ ONLY")
            return resolve_qa_identity_read_only(cur, authentication)
        except QAReadOnlyAuthRejected:
            raise HTTPException(status_code=401, detail="QA_READ_ONLY_AUTH_REJECTED") from None
        finally:
            if cur is not None:
                cur.close()
            conn.rollback()
            conn.close()
