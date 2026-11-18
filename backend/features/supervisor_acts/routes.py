"""Company-owned regulatory records with exact project authorization."""
from fastapi import Depends, Request


def register_supervisor_acts_module(app, deps):
    scope = deps["record_scope"]
    authenticated = deps["get_current_user"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())

    @app.get("/supervisor-acts")
    def list_supervisor_acts(project_name: str = None, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = scope.visible(actors, read_roles)
            if project_name:
                where += ' AND p.name=%s'
                params.append(project_name)
            cur.execute("SELECT r.id, p.name, r.act_number, r.act_type, r.description, r.findings, r.recommendations, r.issued_by, r.issued_by_role, r.date, r.photo_url, r.file_url, r.status, r.created_at, r.company_id, r.project_id FROM supervisor_acts r "
                        "JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id "
                        "WHERE " + where + " ORDER BY r.id DESC", params)
            rows = cur.fetchall()
        return [{"id":r[0],"projectName":r[1] or "","actNumber":r[2] or "","actType":r[3] or "",
                 "description":r[4] or "","findings":r[5] or "","recommendations":r[6] or "",
                 "issuedBy":r[7] or "","issuedByRole":r[8] or "",
                 "date":str(r[9]) if r[9] else "","photoUrl":r[10] or "","fileUrl":r[11] or "",
                 "status":r[12] or "Открыт","createdAt":str(r[13]),"companyId":r[14],"projectId":r[15]} for r in rows]

    @app.post("/supervisor-acts")
    def create_supervisor_act(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, data, write_roles)
            cur.execute("""INSERT INTO supervisor_acts
                           (project_name, act_number, act_type, description, findings, recommendations,
                            issued_by, issued_by_role, date, photo_url, file_url, status, company_id, project_id, created_by_user_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (parent["name"], data.get("actNumber","") or ("САО-"+str(int(__import__("datetime").datetime.now().timestamp()))[-6:]),
                         data.get("actType","Осмотр"), data.get("description",""), data.get("findings",""),
                         data.get("recommendations",""),
                         data.get("issuedBy",""), data.get("issuedByRole","Технадзор"),
                         data.get("date") or None, data.get("photoUrl",""), data.get("fileUrl",""),
                         data.get("status","Открыт"), parent["companyId"], parent["id"], actor["id"]))
            row = cur.fetchone()
        return {"id": row[0], "ok": True}

    @app.put("/supervisor-acts/{id}")
    def update_supervisor_act(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], "supervisor_acts", id, write_roles)
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
    def delete_supervisor_act(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], "supervisor_acts", id, write_roles)
            cur.execute("DELETE FROM supervisor_acts WHERE id=%s", (id,))
        return {"ok": True}
