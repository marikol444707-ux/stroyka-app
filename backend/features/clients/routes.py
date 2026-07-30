"""Client directory routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 32):
the /clients quartet keeps its URLs, role guards and the worker
price-hiding rule. The model moved here — sole user.
"""

import psycopg2.extras
from fastapi import Depends
from pydantic import BaseModel


class ClientModel(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    status: str = "Активный"
    notes: str = ""


def register_clients_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    admin_roles = tuple(deps.get("admin_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())

    @app.get("/clients")
    def get_clients(_current_user: dict = Depends(require_roles(*admin_roles, "менеджер_crm"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM clients")
        rows = cur.fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        if _current_user.get("role") in worker_execution_roles:
            for row in result:
                row["price"] = 0
        return result

    @app.post("/clients")
    def create_client(c: ClientModel, _current_user: dict = Depends(require_roles(*admin_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO clients (name,phone,email,status,notes) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                    (c.name,c.phone,c.email,c.status,c.notes))
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.put("/clients/{id}")
    def update_client(id: int, c: ClientModel, _current_user: dict = Depends(require_roles(*admin_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE clients SET name=%s,phone=%s,email=%s,status=%s,notes=%s WHERE id=%s",
                    (c.name,c.phone,c.email,c.status,c.notes,id))
        conn.close()
        return {"ok": True}

    @app.delete("/clients/{id}")
    def delete_client(id: int, _current_user: dict = Depends(require_roles(*admin_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM clients WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}
