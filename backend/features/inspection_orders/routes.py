"""Inspection order routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 27):
the /inspection-orders quartet keeps its URLs, role guards,
auto-numbering, field mapping and soft-delete via status.
"""

from fastapi import Depends


def register_inspection_orders_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/inspection-orders")
    def list_inspection_orders(project_name: str = None, current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        cols = "id, project_name, order_number, body, inspector, description, recommendations, deadline, status, photo_url, file_url, date, response, response_date, created_at"
        if project_name:
            require_project_access(current_user, project_name)
            cur.execute(f"SELECT {cols} FROM inspection_orders WHERE project_name=%s AND COALESCE(status,'') <> 'Аннулировано' ORDER BY id DESC", (project_name,))
        elif visible_project_names(current_user) is not None:
            allowed_projects = visible_project_names(current_user)
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute(f"SELECT {cols} FROM inspection_orders WHERE project_name = ANY(%s) AND COALESCE(status,'') <> 'Аннулировано' ORDER BY id DESC", (allowed_projects,))
        else:
            cur.execute(f"SELECT {cols} FROM inspection_orders WHERE COALESCE(status,'') <> 'Аннулировано' ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1] or "","orderNumber":r[2] or "","body":r[3] or "",
                 "inspector":r[4] or "","description":r[5] or "","recommendations":r[6] or "",
                 "deadline":str(r[7]) if r[7] else "","status":r[8] or "Открыто",
                 "photoUrl":r[9] or "","fileUrl":r[10] or "",
                 "date":str(r[11]) if r[11] else "","response":r[12] or "",
                 "responseDate":str(r[13]) if r[13] else "",
                 "createdAt":str(r[14])} for r in rows]

    @app.post("/inspection-orders")
    def create_inspection_order(data: dict, current_user: dict = Depends(require_roles(*write_roles))):
        require_project_access(current_user, data.get("projectName", ""))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO inspection_orders
                       (project_name, order_number, body, inspector, description, recommendations,
                        deadline, status, photo_url, file_url, date)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (data.get("projectName",""), data.get("orderNumber","") or ("ГСН-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                     data.get("body","ГСН"), data.get("inspector",""), data.get("description",""),
                     data.get("recommendations",""), data.get("deadline") or None,
                     data.get("status","Открыто"), data.get("photoUrl",""),
                     data.get("fileUrl",""), data.get("date") or None))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id": row[0], "ok": True}

    @app.put("/inspection-orders/{id}")
    def update_inspection_order(id: int, data: dict, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "inspection_orders", id, current_user, "project_name")
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
            cur.close(); conn.close()
            return {"ok": True}
        vals.append(id)
        cur.execute("UPDATE inspection_orders SET " + ", ".join(sets) + " WHERE id=%s", vals)
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}

    @app.delete("/inspection-orders/{id}")
    def delete_inspection_order(id: int, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "inspection_orders", id, current_user, "project_name")
        cur.execute("UPDATE inspection_orders SET status='Аннулировано' WHERE id=%s", (id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
