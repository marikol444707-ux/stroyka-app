"""Company list route.

Moved verbatim from backend/main.py. GET /companies keeps its URL,
authentication dependency and response shape.
"""

import psycopg2.extras
from fastapi import APIRouter, Depends


def register_companies_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    router = APIRouter()

    @router.get("/companies")
    def list_companies(_current_user: dict = Depends(get_current_user)):
        """Список компаний-клиентов системы. Сейчас одна (СтройКа).
           В будущем — multi-tenancy: поставщик видит заявки от разных компаний."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, short_name as \"shortName\", inn, logo_url as \"logoUrl\", plan, active FROM companies WHERE active=TRUE ORDER BY id")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    app.include_router(router)
