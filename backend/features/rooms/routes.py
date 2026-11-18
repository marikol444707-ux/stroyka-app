"""Room measurement routes.

The rooms, windows and doors URLs stay the same. Reads and writes use the
selected company and the exact project, not a project name shared by companies.
"""
from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from ..room_ownership.access import RoomOwnership


class RoomModel(BaseModel):
    floor: int = 1
    liter: str = ''
    roomType: str = 'Комната'
    project: str
    projectId: Optional[int] = None
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


ROOM_COLUMNS = """r.id,r.project,r.name,
                               r.floor_area as "floorArea",
                               r.wall_area as "wallArea",
                               r.ceiling_area as "ceilingArea",
                               r.height,
                               r.ceiling_type as "ceilingType",
                               r.wall_material as "wallMaterial",
                               r.floor_material as "floorMaterial",
                               r.windows,r.doors,r.photo_url as "photoUrl",r.notes,r.floor,r.liter,r.room_type as "roomType",
                               r.company_id as "companyId", r.project_id as "projectId" """


def register_rooms_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    read_roles = tuple(deps.get("read_roles") or ())
    write_roles = tuple(deps.get("write_roles") or ())
    run_project_ai_control_safely = deps["run_project_ai_control_safely"]
    scope = RoomOwnership(
        deps["resolve_work_company_context"],
        deps["effective_company_actors"],
        full_view_roles=tuple(deps.get("full_view_roles") or ()),
        platform_staff_roles=tuple(deps.get("platform_staff_roles") or ()),
        read_roles=read_roles,
        write_roles=write_roles,
    )

    def positive_room_id(value):
        try:
            room_id = int(value)
        except (TypeError, ValueError):
            return None
        return room_id if room_id > 0 else None

    @app.get("/rooms")
    def get_rooms(current_user: dict = Depends(require_roles(*read_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            actors, mode = scope.actors(cur, current_user, request, write=False)
            join, where, params = scope.list_clause(actors, mode)
            cur.execute(
                f"SELECT {ROOM_COLUMNS} FROM rooms r {join} WHERE {where} ORDER BY r.id",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    @app.post("/rooms")
    def create_room(r: RoomModel, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            actors, _mode = scope.actors(cur, _current_user, request, write=True)
            parent = scope.verified_project(cur, actors[0], r)
            cur.execute("""INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,height,ceiling_type,wall_material,floor_material,windows,doors,photo_url,notes,floor,liter,room_type,company_id,project_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,project,name,floor_area as "floorArea",wall_area as "wallArea",ceiling_area as "ceilingArea",height,ceiling_type as "ceilingType",wall_material as "wallMaterial",floor_material as "floorMaterial",windows,doors,photo_url as "photoUrl",notes,floor,liter,room_type as "roomType",company_id as "companyId",project_id as "projectId" """,
                        (parent["name"], r.name, r.floorArea, r.wallArea, r.ceilingArea, r.height, r.ceilingType, r.wallMaterial, r.floorMaterial, r.windows, r.doors, r.photoUrl, r.notes, r.floor, r.liter, r.roomType, parent["companyId"], parent["id"]))
            row = dict(cur.fetchone())
            project_name = parent["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room:create")
        return row

    @app.put("/rooms/{id}")
    def update_room(id: int, r: RoomModel, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "rooms", id, actors, mode)
            parent = scope.verified_project(cur, actors[0], r)
            cur.execute("""UPDATE rooms SET floor=%s,liter=%s,room_type=%s, project=%s,name=%s,
                           floor_area=%s,wall_area=%s,ceiling_area=%s,height=%s,
                           ceiling_type=%s,wall_material=%s,floor_material=%s,
                           windows=%s,doors=%s,photo_url=%s,notes=%s,company_id=%s,project_id=%s WHERE id=%s""",
                        (r.floor, r.liter, r.roomType, parent["name"], r.name, r.floorArea, r.wallArea, r.ceilingArea, r.height, r.ceilingType, r.wallMaterial, r.floorMaterial, r.windows, r.doors, r.photoUrl, r.notes, parent["companyId"], parent["id"], id))
            project_name = parent["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room:update")
        return {"ok": True}

    @app.delete("/rooms/{id}")
    def delete_room(id: int, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "rooms", id, actors, mode)
            cur.execute("DELETE FROM room_windows WHERE room_id=%s", (id,))
            cur.execute("DELETE FROM room_doors WHERE room_id=%s", (id,))
            cur.execute("DELETE FROM room_works WHERE room_id=%s", (id,))
            cur.execute("DELETE FROM rooms WHERE id=%s", (id,))
        finally:
            conn.close()
        return {"ok": True}

    def list_children(current_user, request, table, columns, mapper):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, current_user, request, write=False)
            join, where, params = scope.list_clause(actors, mode, "w")
            cur.execute(
                f"SELECT {columns} FROM {table} w {join} WHERE {where} ORDER BY w.id",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [mapper(r) for r in rows]

    @app.get("/room-windows")
    def get_room_windows(current_user: dict = Depends(require_roles(*read_roles)), request: Request = None):
        return list_children(
            current_user, request, "room_windows",
            "w.id,w.room_id,w.name,w.width,w.height,w.window_type,w.reveal_depth,w.reveal_material,w.order_num,w.company_id,w.project_id",
            lambda r: {"id": r[0], "room_id": r[1], "name": r[2], "width": r[3], "height": r[4], "window_type": r[5], "reveal_depth": r[6], "reveal_material": r[7], "order_num": r[8], "companyId": r[9], "projectId": r[10]},
        )

    def opening_owner(cur, data, actors, mode):
        room_id = positive_room_id(data.get("roomId") or data.get("room_id"))
        if not room_id:
            raise HTTPException(status_code=404, detail="Помещение не найдено")
        return room_id, scope.mutable_row(cur, "rooms", room_id, actors, mode)

    @app.post("/room-windows")
    def create_room_window(data: dict, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            room_id, owner = opening_owner(cur, data, actors, mode)
            cur.execute("""INSERT INTO room_windows (room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num,company_id,project_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num""",
                        (room_id, data.get("name", ""), float(data.get("width", 0)), float(data.get("height", 0)), data.get("windowType") or data.get("window_type", "ПВХ"), float(data.get("revealDepth") or data.get("reveal_depth") or 0), data.get("revealMaterial") or data.get("reveal_material", "Штукатурка"), int(data.get("orderNum") or data.get("order_num") or 0), owner["companyId"], owner["projectId"]))
            conn.commit()
            row = cur.fetchone()
            project_name = owner["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room_window:create")
        return row

    @app.put("/room-windows/{id}")
    def update_room_window(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            room_id = data.get("roomId") or data.get("room_id")
            if not room_id:
                cur.execute("SELECT room_id FROM room_windows WHERE id=%s", (id,))
                existing_room = cur.fetchone()
                room_id = existing_room[0] if existing_room else None
            scope.mutable_row(cur, "room_windows", id, actors, mode)
            _room_id, owner = opening_owner(cur, {"roomId": room_id}, actors, mode)
            cur.execute("""UPDATE room_windows
                           SET room_id=%s,name=%s,width=%s,height=%s,window_type=%s,reveal_depth=%s,reveal_material=%s,order_num=%s,company_id=%s,project_id=%s
                           WHERE id=%s""",
                        (_room_id, data.get("name", ""), float(data.get("width", 0)), float(data.get("height", 0)), data.get("windowType") or data.get("window_type", "ПВХ"), float(data.get("revealDepth") or data.get("reveal_depth") or 0), data.get("revealMaterial") or data.get("reveal_material", "Штукатурка"), int(data.get("orderNum") or data.get("order_num") or 0), owner["companyId"], owner["projectId"], id))
            project_name = owner["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room_window:update")
        return {"ok": True}

    @app.delete("/room-windows/{id}")
    def delete_room_window(id: int, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "room_windows", id, actors, mode)
            cur.execute("DELETE FROM room_windows WHERE id=%s", (id,))
        finally:
            conn.close()
        return {"ok": True}

    @app.get("/room-doors")
    def get_room_doors(current_user: dict = Depends(require_roles(*read_roles)), request: Request = None):
        return list_children(
            current_user, request, "room_doors",
            "w.id,w.room_id,w.name,w.width,w.height,w.door_type,w.door_purpose,w.reveal_depth,w.reveal_material,w.order_num,w.company_id,w.project_id",
            lambda r: {"id": r[0], "room_id": r[1], "name": r[2], "width": r[3], "height": r[4], "door_type": r[5], "door_purpose": r[6], "reveal_depth": r[7], "reveal_material": r[8], "order_num": r[9], "companyId": r[10], "projectId": r[11]},
        )

    @app.post("/room-doors")
    def create_room_door(data: dict, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            room_id, owner = opening_owner(cur, data, actors, mode)
            cur.execute("""INSERT INTO room_doors (room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num,company_id,project_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num""",
                        (room_id, data.get("name", ""), float(data.get("width", 0)), float(data.get("height", 0)), data.get("doorType") or data.get("door_type", "Деревянная"), data.get("doorPurpose") or data.get("door_purpose", "Межкомнатная"), float(data.get("revealDepth") or data.get("reveal_depth") or 0), data.get("revealMaterial") or data.get("reveal_material", "Штукатурка"), int(data.get("orderNum") or data.get("order_num") or 0), owner["companyId"], owner["projectId"]))
            conn.commit()
            row = cur.fetchone()
            project_name = owner["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room_door:create")
        return row

    @app.put("/room-doors/{id}")
    def update_room_door(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            room_id = data.get("roomId") or data.get("room_id")
            if not room_id:
                cur.execute("SELECT room_id FROM room_doors WHERE id=%s", (id,))
                existing_room = cur.fetchone()
                room_id = existing_room[0] if existing_room else None
            scope.mutable_row(cur, "room_doors", id, actors, mode)
            _room_id, owner = opening_owner(cur, {"roomId": room_id}, actors, mode)
            cur.execute("""UPDATE room_doors
                           SET room_id=%s,name=%s,width=%s,height=%s,door_type=%s,door_purpose=%s,reveal_depth=%s,reveal_material=%s,order_num=%s,company_id=%s,project_id=%s
                           WHERE id=%s""",
                        (_room_id, data.get("name", ""), float(data.get("width", 0)), float(data.get("height", 0)), data.get("doorType") or data.get("door_type", "Деревянная"), data.get("doorPurpose") or data.get("door_purpose", "Межкомнатная"), float(data.get("revealDepth") or data.get("reveal_depth") or 0), data.get("revealMaterial") or data.get("reveal_material", "Штукатурка"), int(data.get("orderNum") or data.get("order_num") or 0), owner["companyId"], owner["projectId"], id))
            project_name = owner["name"]
        finally:
            conn.close()
        run_project_ai_control_safely(project_name, "room_door:update")
        return {"ok": True}

    @app.delete("/room-doors/{id}")
    def delete_room_door(id: int, _current_user: dict = Depends(require_roles(*write_roles)), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "room_doors", id, actors, mode)
            cur.execute("DELETE FROM room_doors WHERE id=%s", (id,))
        finally:
            conn.close()
        return {"ok": True}
