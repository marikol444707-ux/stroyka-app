"""Supply request template routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 15):
GET/POST /supply-request-templates and DELETE
/supply-request-templates/{id} keep their URLs, supply role guard and
payload validation.
"""

from fastapi import Depends, HTTPException


def register_supply_request_templates_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    supply_roles = tuple(deps.get("supply_roles") or ())

    @app.get("/supply-request-templates")
    def get_supply_request_templates(_current_user: dict = Depends(require_roles(*supply_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id,name,category,items_json,created_by,created_by_id,created_at "
                    "FROM supply_request_templates ORDER BY name")
        rows = cur.fetchall()
        cur.close(); conn.close()
        import json as _json
        out = []
        for r in rows:
            try:
                items = _json.loads(r[3]) if r[3] else []
            except Exception:
                items = []
            out.append({"id": r[0], "name": r[1] or "", "category": r[2] or "", "items": items,
                        "createdBy": r[4] or "", "createdById": r[5], "createdAt": str(r[6]) if r[6] else ""})
        return out

    @app.post("/supply-request-templates")
    def create_supply_request_template(data: dict, _current_user: dict = Depends(require_roles(*supply_roles))):
        import json as _json
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Укажите название шаблона")
        items = [it for it in (data.get("items") or [])
                 if (it or {}).get("materialName") and float((it or {}).get("quantity") or 0) > 0]
        if not items:
            raise HTTPException(status_code=400, detail="Шаблон должен содержать хотя бы одну позицию")
        items = [{"materialName": it["materialName"], "quantity": float(it.get("quantity") or 0),
                  "unit": it.get("unit") or "шт",
                  "workPackage": (it.get("workPackage") or it.get("work_package") or "").strip()} for it in items]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO supply_request_templates (name,category,items_json,created_by,created_by_id) "
                    "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (name, data.get("category", ""), _json.dumps(items, ensure_ascii=False),
                     data.get("createdBy", ""), data.get("createdById")))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return {"id": new_id, "ok": True}

    @app.delete("/supply-request-templates/{id}")
    def delete_supply_request_template(id: int, _current_user: dict = Depends(require_roles(*supply_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM supply_request_templates WHERE id=%s", (id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
