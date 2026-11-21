"""Selected-company access for checklist items."""

from typing import Optional

from fastapi import Depends, Header, HTTPException

from ..record_company_scope import row_value, selected_actor


def register_checklist_items_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    resolve = deps["resolve_work_company_context"]
    actors_for = deps["effective_company_actors"]
    project_access = deps["require_project_access"]
    all_company_data = deps["can_see_all_company_data"]
    read_roles = tuple(deps.get("project_document_roles") or ())
    write_roles = tuple(deps.get("project_write_roles") or ())
    check_roles = tuple(deps.get("check_roles") or (*write_roles, "технадзор", "стройконтроль"))

    def parent_checklist(cur, checklist_id, company_id):
        cur.execute(
            "SELECT id,project_name,owner_scope,company_id,project_id FROM project_checklists "
            "WHERE id=%s AND company_id=%s",
            (checklist_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Чек-лист не найден в выбранной компании")
        return row

    def require_parent_access(cur, checklist_id, actor, company_id):
        row = parent_checklist(cur, checklist_id, company_id)
        if not all_company_data(actor):
            project_access(actor, row_value(row, "project_name", 1, "") or "")
        return row

    @app.get("/checklist-items/{checklist_id}")
    def get_checklist_items(
        checklist_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*read_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "read", x_company_id, x_company_mode, read_roles
            )
            require_parent_access(cur, checklist_id, actor, company_id)
            cur.execute(
                "SELECT id,checklist_id,name,checked,checked_by,checked_at,order_num "
                "FROM checklist_items WHERE checklist_id=%s AND company_id=%s ORDER BY order_num,id",
                (checklist_id, company_id),
            )
            rows = cur.fetchall()
            return [{
                "id": row[0], "checklistId": row[1], "name": row[2], "checked": row[3],
                "checkedBy": row[4], "checkedAt": row[5], "orderNum": row[6],
            } for row in rows]
        finally:
            cur.close()
            conn.close()

    @app.post("/checklist-items")
    def create_checklist_item(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*write_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "create", x_company_id, x_company_mode, write_roles
            )
            parent = require_parent_access(cur, int(data.get("checklistId") or 0), actor, company_id)
            cur.execute(
                "INSERT INTO checklist_items (checklist_id,name,checked,checked_by,checked_at,order_num,owner_scope,company_id,project_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (data.get("checklistId"), data.get("name", ""), data.get("checked", False), data.get("checkedBy", ""),
                 data.get("checkedAt", ""), int(data.get("orderNum", 0) or 0),
                 row_value(parent, "owner_scope", 2), company_id, row_value(parent, "project_id", 4)),
            )
            conn.commit()
            row = cur.fetchone()
            return {"id": row_value(row, "id", 0), "ok": True}
        finally:
            cur.close()
            conn.close()

    @app.put("/checklist-items/{id}")
    def update_checklist_item(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*check_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "update", x_company_id, x_company_mode, check_roles
            )
            cur.execute(
                "SELECT checklist_id FROM checklist_items WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Пункт чек-листа не найден в выбранной компании")
            require_parent_access(cur, int(row_value(row, "checklist_id", 0) or 0), actor, company_id)
            cur.execute(
                "UPDATE checklist_items SET checked=%s,checked_by=%s,checked_at=%s WHERE id=%s AND company_id=%s",
                (data.get("checked", False), data.get("checkedBy", ""), data.get("checkedAt", ""), id, company_id),
            )
            conn.commit()
            return {"ok": True}
        finally:
            cur.close()
            conn.close()
