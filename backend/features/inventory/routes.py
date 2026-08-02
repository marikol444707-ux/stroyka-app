"""Selected-company access for tools and inventory operations."""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _row_value(row, key, index=0, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return row[index] if row and len(row) > index else default


def register_inventory_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    resolve_context = deps["resolve_work_company_context"]
    effective_actors = deps["effective_company_actors"]
    scope_filter = deps["company_id_scope_filter"]
    all_company_data = deps["can_see_all_company_data"]
    project_access = deps["require_project_access"]
    user_projects = deps["user_project_names"]
    warehouse_roles = tuple(deps["warehouse_roles"])
    project_document_roles = tuple(deps["project_document_roles"])
    worker_roles = tuple(deps["worker_execution_roles"])
    tool_model = deps["tool_model"]
    tool_history_model = deps["tool_history_model"]
    inventory_model = deps["inventory_model"]
    inventory_item_model = deps["inventory_item_model"]

    def selected_actor(cur, user, action, x_company_id, x_company_mode, allowed_roles):
        context = resolve_context(
            cur, user, None, action, x_company_id=x_company_id, x_company_mode=x_company_mode
        )
        if context.get("mode") != "company":
            raise HTTPException(status_code=409, detail="Для изменения данных выберите конкретную компанию")
        actors = effective_actors(user, context)
        actor = actors[0] if len(actors) == 1 else {}
        if not actor or (actor.get("role") or "") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет выполнить действие")
        company_id = int(context.get("companyId") or 0)
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания не определена")
        return context, actor, company_id

    def read_context(cur, user, x_company_id, x_company_mode):
        context = resolve_context(
            cur, user, None, "read", x_company_id=x_company_id, x_company_mode=x_company_mode
        )
        if not context.get("companyIds"):
            raise HTTPException(status_code=403, detail="Нет доступа к компаниям")
        actors = effective_actors(user, context)
        if context.get("mode") == "company":
            if len(actors) != 1:
                raise HTTPException(status_code=403, detail="Нет активной роли в выбранной компании")
            return context, actors[0], False
        leadership = {"директор", "зам_директора", "главный_инженер", "кладовщик", "снабженец"}
        if context.get("mode") == "all_companies" and actors and all(
            (actor.get("role") or "") in leadership for actor in actors
        ):
            return context, None, True
        return context, None, False

    def resolve_project_owner(cur, project_name, company_id):
        project_name = str(project_name or "").strip()
        if not project_name:
            return "company", None
        cur.execute("SELECT id,company_id FROM projects WHERE name=%s ORDER BY id", (project_name,))
        rows = cur.fetchall() or []
        matching = [row for row in rows if int(_row_value(row, "company_id", 1, 0) or 0) == company_id]
        if len(matching) != 1:
            raise HTTPException(status_code=403, detail="Объект не относится к выбранной компании")
        return "project", int(_row_value(matching[0], "id", 0, 0))

    def tool_row_for_company(cur, tool_id, company_id):
        cur.execute(
            "SELECT id,project,location,master_id,master_name,owner_scope,company_id,project_id "
            "FROM tools WHERE id=%s AND company_id=%s",
            (tool_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Инструмент не найден в выбранной компании")
        return row

    def require_tool_actor_access(cur, tool_id, actor, company_id):
        row = tool_row_for_company(cur, tool_id, company_id)
        role = actor.get("role") or ""
        if all_company_data(actor) or role in ("кладовщик", "снабженец"):
            return row
        project = str(_row_value(row, "project", 1, "") or "")
        location = str(_row_value(row, "location", 2, "") or "")
        master_id = _row_value(row, "master_id", 3)
        master_name = str(_row_value(row, "master_name", 4, "") or "")
        if role == "прораб":
            allowed = user_projects(actor)
            if not project or project in allowed or location in allowed:
                return row
        if role in worker_roles:
            if str(master_id or "") == str(actor.get("id") or "") or (
                not master_id and master_name == (actor.get("name") or "")
            ):
                return row
        raise HTTPException(status_code=403, detail="Нет доступа к инструменту")

    def inventory_row_for_company(cur, inventory_id, company_id):
        cur.execute(
            "SELECT id,project,owner_scope,company_id,project_id FROM inventory "
            "WHERE id=%s AND company_id=%s", (inventory_id, company_id)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Инвентаризация не найдена в выбранной компании")
        return row

    def require_inventory_actor_access(cur, inventory_id, actor, company_id):
        row = inventory_row_for_company(cur, inventory_id, company_id)
        role = actor.get("role") or ""
        if all_company_data(actor) or role in ("кладовщик", "снабженец"):
            return row
        project_access(actor, str(_row_value(row, "project", 1, "") or ""))
        return row

    @app.get("/tools")
    def get_tools(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(cur, current_user, x_company_id, x_company_mode)
            company_sql, params = scope_filter(context, "company_id")
            if not actor and not all_leadership: return []
            actor = actor or current_user
            role = actor.get("role") or ""
            base = "SELECT id,name,inventory_number as \"inventoryNumber\",cost,status,location,project,master_id as \"masterId\",master_name as \"masterName\",issue_type as \"issueType\",photo_url as \"photoUrl\",notes FROM tools WHERE TRUE" + company_sql
            if role == "прораб":
                allowed = user_projects(actor)
                base += " AND (owner_scope='company' OR project = ANY(%s) OR location = ANY(%s))"
                params.extend([allowed, allowed])
            elif role in worker_roles:
                base += " AND (COALESCE(master_id,0)=%s OR (COALESCE(master_id,0)=0 AND master_name=%s))"
                params.extend([actor.get("id"), actor.get("name") or ""])
            elif not (all_company_data(actor) or role in ("кладовщик", "снабженец")):
                return []
            cur.execute(base + " ORDER BY name", tuple(params))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close(); conn.close()

    @app.post("/tools")
    def create_tool(
        tool: tool_model,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "create", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            scope, project_id = resolve_project_owner(cur, tool.project, company_id)
            if actor.get("role") == "прораб" and tool.project:
                project_access(actor, tool.project)
            cur.execute(
                "INSERT INTO tools (name,inventory_number,cost,status,location,project,master_id,master_name,issue_type,photo_url,notes,owner_scope,company_id,project_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (tool.name,tool.inventoryNumber,tool.cost,tool.status,tool.location,tool.project,tool.masterId,tool.masterName,tool.issueType,tool.photoUrl,tool.notes,scope,company_id,project_id),
            )
            row = dict(cur.fetchone()); conn.commit(); return row
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.put("/tools/{tool_id}")
    def update_tool(
        tool_id: int, tool: tool_model,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "update", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            require_tool_actor_access(cur, tool_id, actor, company_id)
            scope, project_id = resolve_project_owner(cur, tool.project, company_id)
            if actor.get("role") == "прораб" and tool.project:
                project_access(actor, tool.project)
            cur.execute(
                "UPDATE tools SET name=%s,inventory_number=%s,cost=%s,status=%s,location=%s,project=%s,master_id=%s,master_name=%s,issue_type=%s,photo_url=%s,notes=%s,owner_scope=%s,project_id=%s WHERE id=%s AND company_id=%s",
                (tool.name,tool.inventoryNumber,tool.cost,tool.status,tool.location,tool.project,tool.masterId,tool.masterName,tool.issueType,tool.photoUrl,tool.notes,scope,project_id,tool_id,company_id),
            )
            if cur.rowcount != 1: raise HTTPException(status_code=409, detail="Инструмент изменился одновременно с запросом")
            conn.commit(); return {"ok": True}
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.delete("/tools/{tool_id}")
    def delete_tool(
        tool_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles)),
    ):
        conn = get_db(); cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "delete", x_company_id, x_company_mode, warehouse_roles)
            require_tool_actor_access(cur, tool_id, actor, company_id)
            cur.execute("DELETE FROM tool_history WHERE tool_id=%s AND company_id=%s", (tool_id, company_id))
            cur.execute("DELETE FROM tools WHERE id=%s AND company_id=%s", (tool_id, company_id))
            conn.commit(); return {"ok": True}
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.get("/tool-history")
    def get_tool_history(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(cur, current_user, x_company_id, x_company_mode)
            company_sql, params = scope_filter(context, "company_id")
            if not actor and not all_leadership: return []
            actor = actor or current_user
            role = actor.get("role") or ""
            base = "SELECT id,tool_id as \"toolId\",tool_name as \"toolName\",action,from_location as \"fromLocation\",to_location as \"toLocation\",master_name as \"masterName\",project,issue_type as \"issueType\",condition,date,created_by as \"createdBy\" FROM tool_history WHERE TRUE" + company_sql
            if role == "прораб":
                allowed = user_projects(actor); base += " AND (owner_scope='company' OR project = ANY(%s))"; params.append(allowed)
            elif role in worker_roles:
                base += " AND master_name=%s"; params.append(actor.get("name") or "")
            elif not (all_company_data(actor) or role in ("кладовщик", "снабженец")):
                return []
            cur.execute(base + " ORDER BY id DESC", tuple(params))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close(); conn.close()

    @app.post("/tool-history")
    def create_tool_history(
        history: tool_history_model,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "create", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            tool = require_tool_actor_access(cur, history.toolId, actor, company_id)
            project = str(_row_value(tool, "project", 1, "") or "")
            if history.project and history.project != project:
                raise HTTPException(status_code=409, detail="Объект истории не совпадает с инструментом")
            cur.execute(
                "INSERT INTO tool_history (tool_id,tool_name,action,from_location,to_location,master_name,project,issue_type,condition,date,created_by,owner_scope,company_id,project_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (history.toolId,history.toolName,history.action,history.fromLocation,history.toLocation,history.masterName,project,history.issueType,history.condition,history.date,history.createdBy,_row_value(tool,"owner_scope",5),company_id,_row_value(tool,"project_id",7)),
            )
            row = dict(cur.fetchone()); conn.commit(); return row
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.get("/inventory")
    def get_inventory(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер", "бухгалтер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(cur, current_user, x_company_id, x_company_mode)
            company_sql, params = scope_filter(context, "company_id")
            if not actor and not all_leadership: return []
            actor = actor or current_user
            role = actor.get("role") or ""
            base = "SELECT * FROM inventory WHERE TRUE" + company_sql
            if not (all_company_data(actor) or role in ("кладовщик", "снабженец")):
                allowed = user_projects(actor)
                if not allowed: return []
                base += " AND project = ANY(%s)"; params.append(allowed)
            cur.execute(base + " ORDER BY id DESC", tuple(params))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close(); conn.close()

    @app.post("/inventory")
    def create_inventory(
        inventory: inventory_model,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "create", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            scope, project_id = resolve_project_owner(cur, inventory.project, company_id)
            if scope != "project": raise HTTPException(status_code=400, detail="Для инвентаризации укажите объект")
            if actor.get("role") == "прораб": project_access(actor, inventory.project)
            cur.execute("INSERT INTO inventory (project,date,created_by,notes,owner_scope,company_id,project_id) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *", (inventory.project,inventory.date,inventory.createdBy,inventory.notes,scope,company_id,project_id))
            row = dict(cur.fetchone()); conn.commit(); return row
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.put("/inventory/{inventory_id}")
    def update_inventory(
        inventory_id: int, data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "update", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            require_inventory_actor_access(cur, inventory_id, actor, company_id)
            if "status" in data: cur.execute("UPDATE inventory SET status=%s WHERE id=%s AND company_id=%s", (data["status"], inventory_id, company_id))
            conn.commit(); return {"ok": True}
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.delete("/inventory/{inventory_id}")
    def delete_inventory(
        inventory_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor()
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "delete", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            require_inventory_actor_access(cur, inventory_id, actor, company_id)
            cur.execute("DELETE FROM inventory_items WHERE inventory_id=%s AND company_id=%s", (inventory_id, company_id))
            cur.execute("DELETE FROM inventory WHERE id=%s AND company_id=%s", (inventory_id, company_id))
            conn.commit(); return {"ok": True}
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.get("/inventory/{inventory_id}/items")
    def get_inventory_items(
        inventory_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер", "бухгалтер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "read", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер", "бухгалтер"))
            require_inventory_actor_access(cur, inventory_id, actor, company_id)
            cur.execute("SELECT * FROM inventory_items WHERE inventory_id=%s AND company_id=%s", (inventory_id, company_id))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close(); conn.close()

    def insert_inventory_item(cur, inventory_id, data, actor, company_id):
        inventory = require_inventory_actor_access(cur, inventory_id, actor, company_id)
        cur.execute(
            "INSERT INTO inventory_items (inventory_id,material_name,unit,expected,actual,difference,notes,owner_scope,company_id,project_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (inventory_id,data["materialName"],data["unit"],data["expected"],data["actual"],data["difference"],data.get("notes", ""),_row_value(inventory,"owner_scope",2),company_id,_row_value(inventory,"project_id",4)),
        )
        return dict(cur.fetchone())

    @app.post("/inventory-items")
    def create_inventory_item(
        item: inventory_item_model,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "create", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            row = insert_inventory_item(cur, item.inventoryId, item.dict(), actor, company_id)
            conn.commit(); return row
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()

    @app.post("/inventory/{inventory_id}/items")
    def create_inventory_item_for_inventory(
        inventory_id: int, data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер")),
    ):
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(cur, current_user, "create", x_company_id, x_company_mode, (*warehouse_roles, "главный_инженер"))
            payload = {"materialName": data.get("materialName", ""), "unit": data.get("unit", ""), "expected": float(data.get("expected") or 0), "actual": float(data.get("actual") or 0), "difference": float(data.get("difference") or 0), "notes": data.get("notes", "")}
            row = insert_inventory_item(cur, inventory_id, payload, actor, company_id)
            conn.commit(); return row
        except Exception:
            conn.rollback(); raise
        finally:
            cur.close(); conn.close()
