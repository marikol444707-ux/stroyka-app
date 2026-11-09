"""Company-owned inspection orders with exact project authorization."""
from fastapi import Depends, Request


def register_inspection_orders_module(app, deps):
    scope = deps["record_scope"]
    authenticated = deps["get_current_user"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())

    @app.get("/inspection-orders")
    def list_inspection_orders(project_name: str = None, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = scope.visible(actors, read_roles)
            if project_name:
                where += ' AND p.name=%s'
                params.append(project_name)
            cur.execute("SELECT r.id, p.name, r.order_number, r.body, r.inspector, r.description, r.recommendations, r.deadline, r.status, r.photo_url, r.file_url, r.date, r.response, r.response_date, r.created_at, r.company_id, r.project_id FROM inspection_orders r "
                        "JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id "
                        "WHERE " + where + " AND COALESCE(r.status,'') <> 'Аннулировано' ORDER BY r.id DESC", params)
            rows = cur.fetchall()
        return [{"id":r[0],"projectName":r[1] or "","orderNumber":r[2] or "","body":r[3] or "",
                 "inspector":r[4] or "","description":r[5] or "","recommendations":r[6] or "",
                 "deadline":str(r[7]) if r[7] else "","status":r[8] or "Открыто",
                 "photoUrl":r[9] or "","fileUrl":r[10] or "",
                 "date":str(r[11]) if r[11] else "","response":r[12] or "",
                 "responseDate":str(r[13]) if r[13] else "",
                 "createdAt":str(r[14]),"companyId":r[15],"projectId":r[16]} for r in rows]

    @app.post("/inspection-orders")
    def create_inspection_order(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, data, write_roles)
            cur.execute("""INSERT INTO inspection_orders
                           (project_name, order_number, body, inspector, description, recommendations,
                            deadline, status, photo_url, file_url, date, company_id, project_id, created_by_user_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (parent["name"], data.get("orderNumber","") or ("ГСН-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                         data.get("body","ГСН"), data.get("inspector",""), data.get("description",""),
                         data.get("recommendations",""), data.get("deadline") or None,
                         data.get("status","Открыто"), data.get("photoUrl",""),
                         data.get("fileUrl",""), data.get("date") or None, parent["companyId"], parent["id"], actor["id"]))
            row = cur.fetchone()
        return {"id": row[0], "ok": True}

    @app.put("/inspection-orders/{id}")
    def update_inspection_order(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], "inspection_orders", id, write_roles)
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
    def delete_inspection_order(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], "inspection_orders", id, write_roles)
            cur.execute("UPDATE inspection_orders SET status='Аннулировано' WHERE id=%s", (id,))
        return {"ok": True}
