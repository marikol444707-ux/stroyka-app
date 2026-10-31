"""Supervisor act routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 26):
the /supervisor-acts quartet keeps its URLs, role guards, project
access checks, auto-numbering and field mapping.
"""

from fastapi import Depends, Request
from ..legacy_project_records.scope import owned_query, require_record


def register_supervisor_acts_module(app, deps):
    scope = deps["record_scope"]
    authenticated = deps["get_current_user"]
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/supervisor-acts")
    def list_supervisor_acts(project_name: str = None, request: Request = None, current_user: dict = Depends(authenticated)):
        cols = "id, project_name, act_number, act_type, description, findings, recommendations, issued_by, issued_by_role, date, photo_url, file_url, status, created_at"
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            query, params = owned_query(scope, actors, read_roles, 'supervisor_acts', ','.join('r.'+c.strip() for c in cols.split(',')), project_name=project_name)
            cur.execute(query + " ORDER BY r.id DESC", params)
            rows = cur.fetchall()
        return [{"id":r[0],"projectName":r[1] or "","actNumber":r[2] or "","actType":r[3] or "",
                 "description":r[4] or "","findings":r[5] or "","recommendations":r[6] or "",
                 "issuedBy":r[7] or "","issuedByRole":r[8] or "",
                 "date":str(r[9]) if r[9] else "","photoUrl":r[10] or "","fileUrl":r[11] or "",
                 "status":r[12] or "Открыт","createdAt":str(r[13])} for r in rows]

    @app.post("/supervisor-acts")
    def create_supervisor_act(data: dict, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], data, write_roles)
            cur.execute("""INSERT INTO supervisor_acts
                           (company_id, project_id, project_name, act_number, act_type, description, findings, recommendations,
                            issued_by, issued_by_role, date, photo_url, file_url, status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (parent["companyId"], parent["id"], parent["name"], data.get("actNumber","") or ("САО-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                         data.get("actType","Осмотр"), data.get("description",""), data.get("findings",""),
                         data.get("recommendations",""),
                         data.get("issuedBy",""), data.get("issuedByRole","Технадзор"),
                         data.get("date") or None, data.get("photoUrl",""), data.get("fileUrl",""),
                         data.get("status","Открыт")))
            row = cur.fetchone()
        return {"id": row[0], "ok": True}

    @app.put("/supervisor-acts/{id}")
    def update_supervisor_act(id: int, data: dict, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_record(cur, scope, actors, write_roles, 'supervisor_acts', id)
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
                return {"ok": True}
            vals.append(id)
            cur.execute("UPDATE supervisor_acts SET " + ", ".join(sets) + " WHERE id=%s", vals)
            return {"ok": True}

    @app.delete("/supervisor-acts/{id}")
    def delete_supervisor_act(id: int, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_record(cur, scope, actors, write_roles, 'supervisor_acts', id)
            cur.execute("DELETE FROM supervisor_acts WHERE id=%s", (id,))
        return {"ok": True}
