"""Checklist item routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 12):
GET /checklist-items/{checklist_id}, POST /checklist-items and
PUT /checklist-items/{id} keep their URLs, role guards and access
checks; the checklist access helpers stay in main.py and arrive
through deps.
"""

from fastapi import Depends


def register_checklist_items_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    project_document_roles = tuple(deps.get("project_document_roles") or ())
    project_write_roles = tuple(deps.get("project_write_roles") or ())
    require_checklist_access = deps["require_checklist_access"]
    require_checklist_item_access = deps["require_checklist_item_access"]

    @app.get("/checklist-items/{checklist_id}")
    def get_checklist_items(checklist_id: int, _current_user: dict = Depends(require_roles(*project_document_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_checklist_access(cur, checklist_id, _current_user)
        cur.execute("SELECT id,checklist_id,name,checked,checked_by,checked_at,order_num FROM checklist_items WHERE checklist_id=%s ORDER BY order_num,id",(checklist_id,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"checklistId":r[1],"name":r[2],"checked":r[3],"checkedBy":r[4],"checkedAt":r[5],"orderNum":r[6]} for r in rows]

    @app.post("/checklist-items")
    def create_checklist_item(data: dict, _current_user: dict = Depends(require_roles(*project_write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_checklist_access(cur, int(data.get("checklistId") or 0), _current_user)
        cur.execute("INSERT INTO checklist_items (checklist_id,name,checked,checked_by,checked_at,order_num) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("checklistId"),data.get("name",""),data.get("checked",False),data.get("checkedBy",""),data.get("checkedAt",""),int(data.get("orderNum",0))))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.put("/checklist-items/{id}")
    def update_checklist_item(id: int, data: dict, _current_user: dict = Depends(require_roles(*project_write_roles, "технадзор", "стройконтроль"))):
        conn = get_db()
        cur = conn.cursor()
        require_checklist_item_access(cur, id, _current_user)
        cur.execute("UPDATE checklist_items SET checked=%s,checked_by=%s,checked_at=%s WHERE id=%s",
            (data.get("checked",False),data.get("checkedBy",""),data.get("checkedAt",""),id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
