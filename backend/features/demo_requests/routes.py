"""Demo request routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 4):
GET /demo-requests, public POST /demo-request and
PUT /demo-requests/{id} keep their URLs, role guards and payloads.
Platform audit writing comes from the platform_admin feature.
"""

import psycopg2.extras
from fastapi import Depends, HTTPException

try:
    from backend.features.platform_admin import write_platform_audit
except ModuleNotFoundError:
    from features.platform_admin import write_platform_audit


def register_demo_requests_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    leadership_roles = tuple(deps.get("leadership_roles") or ())

    @app.get("/demo-requests")
    def list_demo_requests(_current_user: dict = Depends(require_roles(*leadership_roles, "system_owner", "platform_admin"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM demo_requests ORDER BY created_at DESC LIMIT 200")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @app.post("/demo-request")
    def create_demo_request(data: dict):
        """Публичный endpoint — приходит с лендинга / формы на сайте."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""INSERT INTO demo_requests (company_name, contact_name, phone, email,
                                                    employees_count, projects_count, comment, source)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.get('companyName'), data.get('contactName'), data.get('phone'),
             data.get('email'), data.get('employeesCount'), data.get('projectsCount'),
             data.get('comment'), data.get('source') or 'landing'))
        new_id = cur.fetchone()['id']
        conn.close()
        return {"id": new_id, "ok": True, "message": "Заявка принята, с вами свяжутся в течение рабочего дня"}

    @app.put("/demo-requests/{id}")
    def update_demo_request(id: int, data: dict, current_user: dict = Depends(require_roles(*leadership_roles, "system_owner", "platform_admin"))):
        from datetime import datetime
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM demo_requests WHERE id=%s", (id,))
        before = cur.fetchone()
        if not before:
            conn.close()
            raise HTTPException(status_code=404, detail="demo request not found")
        sets, vals = [], []
        for k, c in [('status','status'),('notes','notes'),('assignedCompanyId','assigned_company_id')]:
            if k in data:
                sets.append(c + "=%s"); vals.append(data[k])
        if data.get('status') in ('Обработана','Отклонена'):
            sets.append("processed_at=%s"); vals.append(datetime.now())
        if not sets:
            conn.close()
            return {"ok": False}
        vals.append(id)
        cur.execute("UPDATE demo_requests SET " + ", ".join(sets) + " WHERE id=%s", vals)
        cur.execute("SELECT * FROM demo_requests WHERE id=%s", (id,))
        after = cur.fetchone()
        write_platform_audit(cur, current_user, "demo_request_updated", "demo_request", id,
            after.get("company_name"), company_id=after.get("assigned_company_id"),
            details={"request": data, "beforeStatus": before.get("status"), "afterStatus": after.get("status")})
        conn.close()
        return {"ok": True}
