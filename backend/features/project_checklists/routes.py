"""Project checklist routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 20):
GET/POST /project-checklists and DELETE /project-checklists/{id}
keep their URLs, role guards, project access checks and the cascade
delete of checklist items.
"""

from fastapi import Depends


def register_project_checklists_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    project_name_from_payload = deps["project_name_from_payload"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/project-checklists")
    def get_project_checklists(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(current_user)
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("SELECT id,project_id,project_name,name,template,status,created_by,created_at FROM project_checklists WHERE project_name = ANY(%s) ORDER BY id", (allowed_projects,))
        else:
            cur.execute("SELECT id,project_id,project_name,name,template,status,created_by,created_at FROM project_checklists ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"template":r[4],"status":r[5],"createdBy":r[6],"createdAt":str(r[7])} for r in rows]

    @app.post("/project-checklists")
    def create_project_checklist(data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        project_name = project_name_from_payload(cur, data)
        require_project_access(_current_user, project_name)
        cur.execute("INSERT INTO project_checklists (project_id,project_name,name,template,status,created_by,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectId"),project_name,data.get("name",""),data.get("template",""),data.get("status","В работе"),data.get("createdBy",""),data.get("createdAt","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.delete("/project-checklists/{id}")
    def delete_project_checklist(id: int, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_checklists", id, _current_user, "project_name")
        cur.execute("DELETE FROM checklist_items WHERE checklist_id=%s",(id,))
        cur.execute("DELETE FROM project_checklists WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
