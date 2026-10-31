"""Inspection order routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 27):
the /inspection-orders quartet keeps its URLs, role guards,
auto-numbering, field mapping and soft-delete via status.
"""

from fastapi import Depends, Request
from ..legacy_project_records.scope import owned_query, require_record


def register_inspection_orders_module(app, deps):
    scope = deps["record_scope"]
    authenticated = deps["get_current_user"]
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/inspection-orders")
    def list_inspection_orders(project_name: str = None, request: Request = None, current_user: dict = Depends(authenticated)):
        cols = "id, project_name, order_number, body, inspector, description, recommendations, deadline, status, photo_url, file_url, date, response, response_date, created_at"
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            query, params = owned_query(scope, actors, read_roles, 'inspection_orders', ','.join('r.'+c.strip() for c in cols.split(',')), project_name=project_name)
            cur.execute(query + " AND COALESCE(r.status,'') <> 'Аннулировано' ORDER BY r.id DESC", params)
            rows = cur.fetchall()
        return [{"id":r[0],"projectName":r[1] or "","orderNumber":r[2] or "","body":r[3] or "",
                 "inspector":r[4] or "","description":r[5] or "","recommendations":r[6] or "",
                 "deadline":str(r[7]) if r[7] else "","status":r[8] or "Открыто",
                 "photoUrl":r[9] or "","fileUrl":r[10] or "",
                 "date":str(r[11]) if r[11] else "","response":r[12] or "",
                 "responseDate":str(r[13]) if r[13] else "",
                 "createdAt":str(r[14])} for r in rows]

    @app.post("/inspection-orders")
    def create_inspection_order(data: dict, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], data, write_roles)
            cur.execute("""INSERT INTO inspection_orders
                           (company_id, project_id, project_name, order_number, body, inspector, description, recommendations,
                            deadline, status, photo_url, file_url, date)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (parent["companyId"], parent["id"], parent["name"], data.get("orderNumber","") or ("ГСН-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                         data.get("body","ГСН"), data.get("inspector",""), data.get("description",""),
                         data.get("recommendations",""), data.get("deadline") or None,
                         data.get("status","Открыто"), data.get("photoUrl",""),
                         data.get("fileUrl",""), data.get("date") or None))
            row = cur.fetchone()
        return {"id": row[0], "ok": True}

    @app.put("/inspection-orders/{id}")
    def update_inspection_order(id: int, data: dict, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_record(cur, scope, actors, write_roles, 'inspection_orders', id)
            fields_map = [('status','status'),('response','response'),('responseDate','response_date'),
                          ('recommendations','recommendations'),('photoUrl','photo_url'),('fileUrl','file_url')]
            sets, vals = [], []
            for js_key, db_col in fields_map:
                if js_key in data:
                    sets.append(db_col + "=%s")
                    v = data[js_key]
                    if js_key == 'responseDate' and not v:
                        v = None
                    vals.append(v)
            if not sets:
                return {"ok": True}
            vals.append(id)
            cur.execute("UPDATE inspection_orders SET " + ", ".join(sets) + " WHERE id=%s", vals)
            return {"ok": True}

    @app.delete("/inspection-orders/{id}")
    def delete_inspection_order(id: int, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_record(cur, scope, actors, write_roles, 'inspection_orders', id)
            cur.execute("UPDATE inspection_orders SET status='Аннулировано' WHERE id=%s", (id,))
        return {"ok": True}
