"""Room measurement routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 37):
the rooms quartet plus room-windows and room-doors keep their URLs,
role guards, cascade delete of children and the fire-and-forget AI
control recalculation hook (injected, no AI logic moves). The room
model moved here — sole user.
"""

import psycopg2.extras
from fastapi import Depends
from pydantic import BaseModel


class RoomModel(BaseModel):
    floor: int = 1
    liter: str = ''
    roomType: str = 'Комната'
    project: str
    name: str
    floorArea: float = 0
    wallArea: float = 0
    ceilingArea: float = 0
    height: float = 0
    ceilingType: str = "Простой"
    wallMaterial: str = "Штукатурка"
    floorMaterial: str = "Стяжка"
    windows: int = 0
    doors: int = 0
    photoUrl: str = ""
    notes: str = ""


def register_rooms_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]
    require_room_access = deps["require_room_access"]
    require_room_child_access = deps["require_room_child_access"]
    run_project_ai_control_safely = deps["run_project_ai_control_safely"]

    @app.get("/rooms")
    def get_rooms(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        allowed_projects = visible_project_names(current_user)
        select_sql = """SELECT id,project,name,
                               floor_area as "floorArea",
                               wall_area as "wallArea",
                               ceiling_area as "ceilingArea",
                               height,
                               ceiling_type as "ceilingType",
                               wall_material as "wallMaterial",
    	                           floor_material as "floorMaterial",
    	                           windows,doors,photo_url as "photoUrl",notes,floor,liter,room_type as "roomType"
                        FROM rooms"""
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute(select_sql + " WHERE project = ANY(%s) ORDER BY id", (allowed_projects,))
        else:
            cur.execute(select_sql + " ORDER BY id")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/rooms")
    def create_room(r: RoomModel, _current_user: dict = Depends(require_roles(*write_roles))):
        require_project_access(_current_user, r.project)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,height,ceiling_type,wall_material,floor_material,windows,doors,photo_url,notes,floor,liter,room_type)
    	                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    	                   RETURNING id,project,name,floor_area as "floorArea",wall_area as "wallArea",ceiling_area as "ceilingArea",height,ceiling_type as "ceilingType",wall_material as "wallMaterial",floor_material as "floorMaterial",windows,doors,photo_url as "photoUrl",notes,floor,liter,room_type as "roomType" """,
    	                (r.project,r.name,r.floorArea,r.wallArea,r.ceilingArea,r.height,r.ceilingType,r.wallMaterial,r.floorMaterial,r.windows,r.doors,r.photoUrl,r.notes,r.floor,r.liter,r.roomType))
        row = cur.fetchone()
        conn.close()
        run_project_ai_control_safely(r.project, "room:create")
        return dict(row)

    @app.put("/rooms/{id}")
    def update_room(id: int, r: RoomModel, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "rooms", id, _current_user, "project")
        require_project_access(_current_user, r.project)
        cur.execute("""UPDATE rooms SET floor=%s,liter=%s,room_type=%s, project=%s,name=%s,
                       floor_area=%s,wall_area=%s,ceiling_area=%s,height=%s,
    	                   ceiling_type=%s,wall_material=%s,floor_material=%s,
    	                   windows=%s,doors=%s,photo_url=%s,notes=%s WHERE id=%s""",
    	                (r.floor,r.liter,r.roomType,r.project,r.name,r.floorArea,r.wallArea,r.ceilingArea,r.height,r.ceilingType,r.wallMaterial,r.floorMaterial,r.windows,r.doors,r.photoUrl,r.notes,id))
        conn.close()
        run_project_ai_control_safely(r.project, "room:update")
        return {"ok": True}

    @app.delete("/rooms/{id}")
    def delete_room(id: int, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "rooms", id, _current_user, "project")
        cur.execute("DELETE FROM room_windows WHERE room_id=%s", (id,))
        cur.execute("DELETE FROM room_doors WHERE room_id=%s", (id,))
        cur.execute("DELETE FROM room_works WHERE room_id=%s", (id,))
        cur.execute("DELETE FROM rooms WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}

    @app.get("/room-windows")
    def get_room_windows(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(current_user)
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("""SELECT w.id,w.room_id,w.name,w.width,w.height,w.window_type,w.reveal_depth,w.reveal_material,w.order_num
                           FROM room_windows w
                           JOIN rooms r ON r.id = w.room_id
                           WHERE r.project = ANY(%s)
                           ORDER BY w.id""", (allowed_projects,))
        else:
            cur.execute("SELECT id,room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num FROM room_windows ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"room_id":r[1],"name":r[2],"width":r[3],"height":r[4],"window_type":r[5],"reveal_depth":r[6],"reveal_material":r[7],"order_num":r[8]} for r in rows]

    @app.post("/room-windows")
    def create_room_window(data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        room_id = data.get('roomId') or data.get('room_id')
        require_room_access(cur, room_id, _current_user)
        cur.execute("INSERT INTO room_windows (room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (room_id,data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('windowType') or data.get('window_type','ПВХ'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0)))
        conn.commit()
        row = cur.fetchone()
        cur.execute("SELECT project FROM rooms WHERE id=%s", (room_id,))
        project_row = cur.fetchone()
        project_name = project_row[0] if project_row else ""
        cur.close(); conn.close()
        run_project_ai_control_safely(project_name, "room_window:create")
        return row

    @app.put("/room-windows/{id}")
    def update_room_window(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_room_child_access(cur, "room_windows", id, _current_user)
        room_id = data.get('roomId') or data.get('room_id')
        if not room_id:
            cur.execute("SELECT room_id FROM room_windows WHERE id=%s", (id,))
            existing_room = cur.fetchone()
            room_id = existing_room[0] if existing_room else None
        if room_id:
            require_room_access(cur, room_id, _current_user)
        cur.execute("""UPDATE room_windows
                       SET room_id=%s,name=%s,width=%s,height=%s,window_type=%s,reveal_depth=%s,reveal_material=%s,order_num=%s
                       WHERE id=%s""",
            (room_id,data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('windowType') or data.get('window_type','ПВХ'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0),id))
        cur.execute("""SELECT r.project FROM room_windows w JOIN rooms r ON r.id=w.room_id WHERE w.id=%s""", (id,))
        project_row = cur.fetchone()
        project_name = project_row[0] if project_row else ""
        cur.close(); conn.close()
        run_project_ai_control_safely(project_name, "room_window:update")
        return {"ok": True}

    @app.delete("/room-windows/{id}")
    def delete_room_window(id: int, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_room_child_access(cur, "room_windows", id, _current_user)
        cur.execute("DELETE FROM room_windows WHERE id=%s", (id,))
        cur.close(); conn.close()
        return {"ok": True}

    @app.get("/room-doors")
    def get_room_doors(current_user: dict = Depends(require_roles(*read_roles))):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(current_user)
        if allowed_projects is not None:
            if not allowed_projects:
                cur.close(); conn.close()
                return []
            cur.execute("""SELECT d.id,d.room_id,d.name,d.width,d.height,d.door_type,d.door_purpose,d.reveal_depth,d.reveal_material,d.order_num
                           FROM room_doors d
                           JOIN rooms r ON r.id = d.room_id
                           WHERE r.project = ANY(%s)
                           ORDER BY d.id""", (allowed_projects,))
        else:
            cur.execute("SELECT id,room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num FROM room_doors ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"room_id":r[1],"name":r[2],"width":r[3],"height":r[4],"door_type":r[5],"door_purpose":r[6],"reveal_depth":r[7],"reveal_material":r[8],"order_num":r[9]} for r in rows]

    @app.post("/room-doors")
    def create_room_door(data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        room_id = data.get('roomId') or data.get('room_id')
        require_room_access(cur, room_id, _current_user)
        cur.execute("INSERT INTO room_doors (room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (room_id,data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('doorType') or data.get('door_type','Деревянная'),data.get('doorPurpose') or data.get('door_purpose','Межкомнатная'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0)))
        conn.commit()
        row = cur.fetchone()
        cur.execute("SELECT project FROM rooms WHERE id=%s", (room_id,))
        project_row = cur.fetchone()
        project_name = project_row[0] if project_row else ""
        cur.close(); conn.close()
        run_project_ai_control_safely(project_name, "room_door:create")
        return row

    @app.put("/room-doors/{id}")
    def update_room_door(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_room_child_access(cur, "room_doors", id, _current_user)
        room_id = data.get('roomId') or data.get('room_id')
        if not room_id:
            cur.execute("SELECT room_id FROM room_doors WHERE id=%s", (id,))
            existing_room = cur.fetchone()
            room_id = existing_room[0] if existing_room else None
        if room_id:
            require_room_access(cur, room_id, _current_user)
        cur.execute("""UPDATE room_doors
                       SET room_id=%s,name=%s,width=%s,height=%s,door_type=%s,door_purpose=%s,reveal_depth=%s,reveal_material=%s,order_num=%s
                       WHERE id=%s""",
            (room_id,data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('doorType') or data.get('door_type','Деревянная'),data.get('doorPurpose') or data.get('door_purpose','Межкомнатная'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0),id))
        cur.execute("""SELECT r.project FROM room_doors d JOIN rooms r ON r.id=d.room_id WHERE d.id=%s""", (id,))
        project_row = cur.fetchone()
        project_name = project_row[0] if project_row else ""
        cur.close(); conn.close()
        run_project_ai_control_safely(project_name, "room_door:update")
        return {"ok": True}

    @app.delete("/room-doors/{id}")
    def delete_room_door(id: int, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_room_child_access(cur, "room_doors", id, _current_user)
        cur.execute("DELETE FROM room_doors WHERE id=%s", (id,))
        cur.close(); conn.close()
        return {"ok": True}
