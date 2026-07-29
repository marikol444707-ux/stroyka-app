"""Supervisor act routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 26):
the /supervisor-acts quartet keeps its URLs, role guards, project
access checks, auto-numbering and field mapping.
"""

from fastapi import Depends


def register_supervisor_acts_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/supervisor-acts")
    def list_supervisor_acts(project_name: str = None, current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        cols = "id, project_name, act_number, act_type, description, findings, recommendations, issued_by, issued_by_role, date, photo_url, file_url, status, created_at"
        if project_name:
            require_project_access(current_user, project_name)
            cur.execute(f"SELECT {cols} FROM supervisor_acts WHERE project_name=%s ORDER BY id DESC", (project_name,))
        elif visible_project_names(current_user) is not None:
            allowed_projects = visible_project_names(current_user)
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute(f"SELECT {cols} FROM supervisor_acts WHERE project_name = ANY(%s) ORDER BY id DESC", (allowed_projects,))
        else:
            cur.execute(f"SELECT {cols} FROM supervisor_acts ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1] or "","actNumber":r[2] or "","actType":r[3] or "",
                 "description":r[4] or "","findings":r[5] or "","recommendations":r[6] or "",
                 "issuedBy":r[7] or "","issuedByRole":r[8] or "",
                 "date":str(r[9]) if r[9] else "","photoUrl":r[10] or "","fileUrl":r[11] or "",
                 "status":r[12] or "Открыт","createdAt":str(r[13])} for r in rows]

    @app.post("/supervisor-acts")
    def create_supervisor_act(data: dict, current_user: dict = Depends(require_roles(*write_roles))):
        require_project_access(current_user, data.get("projectName", ""))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO supervisor_acts
                       (project_name, act_number, act_type, description, findings, recommendations,
                        issued_by, issued_by_role, date, photo_url, file_url, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (data.get("projectName",""), data.get("actNumber","") or ("САО-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                     data.get("actType","Осмотр"), data.get("description",""), data.get("findings",""),
                     data.get("recommendations",""),
                     data.get("issuedBy",""), data.get("issuedByRole","Технадзор"),
                     data.get("date") or None, data.get("photoUrl",""), data.get("fileUrl",""),
                     data.get("status","Открыт")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id": row[0], "ok": True}

    @app.put("/supervisor-acts/{id}")
    def update_supervisor_act(id: int, data: dict, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "supervisor_acts", id, current_user, "project_name")
        fields_map = [
            ('actType','act_type'),('description','description'),('findings','findings'),
            ('recommendations','recommendations'),('photoUrl','photo_url'),('fileUrl','file_url'),
            ('status','status'),
        ]
        sets, vals = [], []
        for js_key, db_col in fields_map:
            if js_key in data:
                sets.append(db_col + "=%s")
                vals.append(data[js_key])
        if not sets:
            cur.close(); conn.close()
            return {"ok": True}
        vals.append(id)
        cur.execute("UPDATE supervisor_acts SET " + ", ".join(sets) + " WHERE id=%s", vals)
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}

    @app.delete("/supervisor-acts/{id}")
    def delete_supervisor_act(id: int, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "supervisor_acts", id, current_user, "project_name")
        cur.execute("DELETE FROM supervisor_acts WHERE id=%s", (id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
