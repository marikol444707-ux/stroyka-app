import psycopg2.extras
from fastapi import Depends

from .models import InventoryItemModel, InventoryModel, ToolHistoryModel, ToolModel


def register_tool_inventory_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    warehouse_roles = tuple(deps["warehouse_roles"])
    project_document_roles = tuple(deps["project_document_roles"])
    worker_execution_roles = set(deps["worker_execution_roles"])
    can_see_all_company_data = deps["can_see_all_company_data"]
    user_project_names = deps["user_project_names"]
    require_project_access = deps["require_project_access"]
    require_tool_access = deps["require_tool_access"]
    require_inventory_access = deps["require_inventory_access"]

    @app.get("/tools")
    def get_tools(current_user: dict = Depends(require_roles(*project_document_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = current_user.get("role")
        if can_see_all_company_data(current_user) or role in ("кладовщик", "снабженец"):
            cur.execute("SELECT id,name,inventory_number as \"inventoryNumber\",cost,status,location,project,master_id as \"masterId\",master_name as \"masterName\",issue_type as \"issueType\",photo_url as \"photoUrl\",notes FROM tools ORDER BY name")
        elif role == "прораб":
            allowed_projects = user_project_names(current_user)
            cur.execute("""SELECT id,name,inventory_number as "inventoryNumber",cost,status,location,project,master_id as "masterId",master_name as "masterName",issue_type as "issueType",photo_url as "photoUrl",notes
                           FROM tools
                           WHERE COALESCE(project,'')='' OR project = ANY(%s) OR location = ANY(%s)
                           ORDER BY name""", (allowed_projects, allowed_projects))
        elif role in worker_execution_roles:
            cur.execute("""SELECT id,name,inventory_number as "inventoryNumber",cost,status,location,project,master_id as "masterId",master_name as "masterName",issue_type as "issueType",photo_url as "photoUrl",notes
                           FROM tools
                           WHERE COALESCE(master_id,0)=%s OR (COALESCE(master_id,0)=0 AND master_name=%s)
                           ORDER BY name""", (current_user.get("id"), current_user.get("name") or ""))
        else:
            cur.close()
            conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.post("/tools")
    def create_tool(t: ToolModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        if _current_user.get("role") == "прораб" and t.project:
            require_project_access(_current_user, t.project)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "INSERT INTO tools (name,inventory_number,cost,status,location,project,master_id,master_name,issue_type,photo_url,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (t.name, t.inventoryNumber, t.cost, t.status, t.location, t.project, t.masterId, t.masterName, t.issueType, t.photoUrl, t.notes),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.put("/tools/{id}")
    def update_tool(id: int, t: ToolModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor()
        require_tool_access(cur, id, _current_user)
        if _current_user.get("role") == "прораб" and t.project:
            require_project_access(_current_user, t.project)
        cur.execute(
            "UPDATE tools SET name=%s,inventory_number=%s,cost=%s,status=%s,location=%s,project=%s,master_id=%s,master_name=%s,issue_type=%s,photo_url=%s,notes=%s WHERE id=%s",
            (t.name, t.inventoryNumber, t.cost, t.status, t.location, t.project, t.masterId, t.masterName, t.issueType, t.photoUrl, t.notes, id),
        )
        conn.close()
        return {"ok": True}

    @app.delete("/tools/{id}")
    def delete_tool(id: int, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor()
        require_tool_access(cur, id, _current_user)
        cur.execute("DELETE FROM tool_history WHERE tool_id=%s", (id,))
        cur.execute("DELETE FROM tools WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}

    @app.get("/tool-history")
    def get_tool_history(current_user: dict = Depends(require_roles(*project_document_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = current_user.get("role")
        if can_see_all_company_data(current_user) or role in ("кладовщик", "снабженец"):
            cur.execute("SELECT id,tool_id as \"toolId\",tool_name as \"toolName\",action,from_location as \"fromLocation\",to_location as \"toLocation\",master_name as \"masterName\",project,issue_type as \"issueType\",condition,date,created_by as \"createdBy\" FROM tool_history ORDER BY id DESC")
        elif role == "прораб":
            allowed_projects = user_project_names(current_user)
            cur.execute("""SELECT id,tool_id as "toolId",tool_name as "toolName",action,from_location as "fromLocation",to_location as "toLocation",master_name as "masterName",project,issue_type as "issueType",condition,date,created_by as "createdBy"
                           FROM tool_history
                           WHERE COALESCE(project,'')='' OR project = ANY(%s)
                           ORDER BY id DESC""", (allowed_projects,))
        elif role in worker_execution_roles:
            cur.execute("""SELECT id,tool_id as "toolId",tool_name as "toolName",action,from_location as "fromLocation",to_location as "toLocation",master_name as "masterName",project,issue_type as "issueType",condition,date,created_by as "createdBy"
                           FROM tool_history
                           WHERE master_name=%s
                           ORDER BY id DESC""", (current_user.get("name") or "",))
        else:
            cur.close()
            conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.post("/tool-history")
    def create_tool_history(h: ToolHistoryModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        require_tool_access(cur, h.toolId, _current_user)
        if _current_user.get("role") == "прораб" and h.project:
            require_project_access(_current_user, h.project)
        cur.execute(
            "INSERT INTO tool_history (tool_id,tool_name,action,from_location,to_location,master_name,project,issue_type,condition,date,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (h.toolId, h.toolName, h.action, h.fromLocation, h.toLocation, h.masterName, h.project, h.issueType, h.condition, h.date, h.createdBy),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.get("/inventory")
    def get_inventory(current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер", "бухгалтер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if can_see_all_company_data(current_user) or current_user.get("role") in ("кладовщик", "снабженец"):
            cur.execute("SELECT * FROM inventory ORDER BY id DESC")
        else:
            allowed_projects = user_project_names(current_user)
            if not allowed_projects:
                cur.close()
                conn.close()
                return []
            cur.execute("SELECT * FROM inventory WHERE project = ANY(%s) ORDER BY id DESC", (allowed_projects,))
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.post("/inventory")
    def create_inventory(inv: InventoryModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        if _current_user.get("role") == "прораб":
            require_project_access(_current_user, inv.project)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "INSERT INTO inventory (project,date,created_by,notes) VALUES (%s,%s,%s,%s) RETURNING *",
            (inv.project, inv.date, inv.createdBy, inv.notes),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.put("/inventory/{id}")
    def update_inventory(id: int, data: dict, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor()
        require_inventory_access(cur, id, _current_user)
        if "status" in data:
            cur.execute("UPDATE inventory SET status=%s WHERE id=%s", (data["status"], id))
        conn.close()
        return {"ok": True}

    @app.delete("/inventory/{id}")
    def delete_inventory(id: int, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor()
        require_inventory_access(cur, id, _current_user)
        cur.execute("DELETE FROM inventory_items WHERE inventory_id=%s", (id,))
        cur.execute("DELETE FROM inventory WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}

    @app.get("/inventory/{id}/items")
    def get_inventory_items(id: int, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер", "бухгалтер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        require_inventory_access(cur, id, _current_user)
        cur.execute("SELECT * FROM inventory_items WHERE inventory_id=%s", (id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @app.post("/inventory-items")
    def create_inventory_item(item: InventoryItemModel, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        require_inventory_access(cur, item.inventoryId, _current_user)
        cur.execute(
            "INSERT INTO inventory_items (inventory_id,material_name,unit,expected,actual,difference,notes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (item.inventoryId, item.materialName, item.unit, item.expected, item.actual, item.difference, item.notes),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.post("/inventory/{id}/items")
    def create_inventory_item_for_inventory(id: int, data: dict, _current_user: dict = Depends(require_roles(*warehouse_roles, "главный_инженер"))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        require_inventory_access(cur, id, _current_user)
        cur.execute(
            "INSERT INTO inventory_items (inventory_id,material_name,unit,expected,actual,difference,notes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (id, data.get("materialName", ""), data.get("unit", ""), float(data.get("expected") or 0), float(data.get("actual") or 0), float(data.get("difference") or 0), data.get("notes", "")),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row)
