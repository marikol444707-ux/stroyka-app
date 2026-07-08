import psycopg2.extras
from fastapi import Depends

from .service import build_company_context_response


def register_company_context_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    platform_staff_roles = tuple(deps.get("platform_staff_roles") or ())
    client_account_roles = tuple(deps.get("client_account_roles") or ())

    @app.get("/company-context")
    def get_company_context(current_user: dict = Depends(get_current_user)):
        """Доступные компании пользователя. Read-only слой для безопасной SaaS-миграции."""
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

