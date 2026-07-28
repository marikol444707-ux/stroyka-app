"""Project stage routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 19):
the /project-stages quartet keeps its URLs, role guards and project
access checks; shared project helpers arrive through deps.
"""

from fastapi import Depends


def register_project_stages_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    project_name_from_payload = deps["project_name_from_payload"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/project-stages")
    def get_project_stages(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(current_user)
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("SELECT id,project_id,project_name,name,status,start_date,end_date,progress,responsible,notes,order_num FROM project_stages WHERE project_name = ANY(%s) ORDER BY order_num,id", (allowed_projects,))
        else:
            cur.execute("SELECT id,project_id,project_name,name,status,start_date,end_date,progress,responsible,notes,order_num FROM project_stages ORDER BY order_num,id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"status":r[4],"startDate":r[5],"endDate":r[6],"progress":r[7],"responsible":r[8],"notes":r[9],"orderNum":r[10]} for r in rows]

    @app.post("/project-stages")
    def create_project_stage(data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        project_name = project_name_from_payload(cur, data)
        require_project_access(_current_user, project_name)
        cur.execute("INSERT INTO project_stages (project_id,project_name,name,status,start_date,end_date,progress,responsible,notes,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectId"),project_name,data.get("name",""),data.get("status","Не начат"),data.get("startDate",""),data.get("endDate",""),int(data.get("progress",0)),data.get("responsible",""),data.get("notes",""),int(data.get("orderNum",0))))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.put("/project-stages/{id}")
    def update_project_stage(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_stages", id, _current_user, "project_name")
        cur.execute("UPDATE project_stages SET name=%s,status=%s,start_date=%s,end_date=%s,progress=%s,responsible=%s,notes=%s WHERE id=%s",
            (data.get("name",""),data.get("status",""),data.get("startDate",""),data.get("endDate",""),int(data.get("progress",0)),data.get("responsible",""),data.get("notes",""),id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}

    @app.delete("/project-stages/{id}")
    def delete_project_stage(id: int, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_stages", id, _current_user, "project_name")
        cur.execute("DELETE FROM project_stages WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
