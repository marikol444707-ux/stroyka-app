"""Prescription routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 25):
the /prescriptions quartet keeps its URLs, role guards, customer
self-scope rules and soft-delete via status.
"""

from fastapi import Depends, HTTPException


def register_prescriptions_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/prescriptions")
    def get_prescriptions(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(current_user)
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("SELECT id,project_name,number,issued_by,issued_by_role,violation,deadline,responsible,status,photo_url,fix_photo_url,fix_notes FROM prescriptions WHERE project_name = ANY(%s) AND COALESCE(status,'') <> 'Аннулировано' ORDER BY id DESC", (allowed_projects,))
        else:
            cur.execute("SELECT id,project_name,number,issued_by,issued_by_role,violation,deadline,responsible,status,photo_url,fix_photo_url,fix_notes FROM prescriptions WHERE COALESCE(status,'') <> 'Аннулировано' ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1],"number":r[2],"issuedBy":r[3],"issuedByRole":r[4],"violation":r[5],"deadline":r[6],"responsible":r[7],"status":r[8],"photoUrl":r[9],"fixPhotoUrl":r[10],"fixNotes":r[11]} for r in rows]

    @app.post("/prescriptions")
    def create_prescription(data: dict, current_user: dict = Depends(require_roles(*write_roles, "заказчик"))):
        project_name = data.get("projectName", "")
        require_project_access(current_user, project_name)
        issued_by = data.get("issuedBy","")
        issued_by_role = data.get("issuedByRole","")
        if current_user.get("role") == "заказчик":
            issued_by = current_user.get("name") or issued_by
            issued_by_role = "Заказчик"
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO prescriptions (project_name,number,issued_by,issued_by_role,violation,deadline,responsible,status,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (project_name,data.get("number",""),issued_by,issued_by_role,data.get("violation",""),data.get("deadline",""),data.get("responsible",""),data.get("status","Открыто"),data.get("photoUrl","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.put("/prescriptions/{id}")
    def update_prescription(id: int, data: dict, current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "prescriptions", id, current_user, "project_name")
        role = current_user.get("role")
        new_status = data.get("status","")
        if role in (*worker_execution_roles, "кладовщик", "снабженец") and new_status not in ("На проверке", ""):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Можно только отправить предписание на проверку")
        if role == "заказчик":
            cur.execute("SELECT issued_by, issued_by_role FROM prescriptions WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row or (row[0] != current_user.get("name") and row[1] != "Заказчик"):
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к изменению предписания")
        cur.execute("UPDATE prescriptions SET status=%s,fix_photo_url=%s,fix_notes=%s WHERE id=%s",
            (data.get("status",""),data.get("fixPhotoUrl",""),data.get("fixNotes",""),id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}

    @app.delete("/prescriptions/{id}")
    def delete_prescription(id: int, current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "prescriptions", id, current_user, "project_name")
        cur.execute("UPDATE prescriptions SET status='Аннулировано' WHERE id=%s", (id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
