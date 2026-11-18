import base64
import json
import os
import re

import psycopg2.extras
from fastapi import Depends, HTTPException, Request

from ..room_ownership.access import RoomOwnership

from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
    ModelInputPart,
    build_model_request,
)
from backend.features.model_gateway.yandex_adapter import build_yandex_model_adapter


MEASUREMENT_ROOM_DRAFT_COLUMNS = """r.id,r.measurement_id,r.project_name,r.name,r.floor,r.liter,r.room_type,
                                          r.floor_area,r.wall_area,r.ceiling_area,r.height,r.windows,r.doors,
                                          r.notes,r.status,r.created_by,r.accepted_room_id,r.created_at,
                                          r.company_id,r.project_id"""
_ROOM_DRAFT_INSTRUCTIONS = (
    "Ты извлекаешь помещения из обмеров и проектов. Верни только валидный JSON."
)


def _room_draft_dict(r):
    return {
        "id": r[0],
        "measurementId": r[1],
        "projectName": r[2] or "",
        "name": r[3] or "",
        "floor": int(r[4] or 1),
        "liter": r[5] or "",
        "roomType": r[6] or "Комната",
        "floorArea": float(r[7] or 0),
        "wallArea": float(r[8] or 0),
        "ceilingArea": float(r[9] or 0),
        "height": float(r[10] or 0),
        "windows": int(r[11] or 0),
        "doors": int(r[12] or 0),
        "notes": r[13] or "",
        "status": r[14] or "Черновик ИИ",
        "createdBy": r[15] or "",
        "acceptedRoomId": r[16],
        "createdAt": str(r[17]) if r[17] else "",
        "companyId": r[18],
        "projectId": r[19],
    }


def _clean_ai_json(text: str):
    clean = (text or "").replace("```json", "").replace("```", "").strip()
    if not clean:
        return None
    try:
        return json.loads(clean)
    except Exception:
        start = clean.find("{")
        end = clean.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(clean[start:end + 1])
            except Exception:
                return None
    return None


def _fallback_room_drafts_from_text(text: str):
    rooms = []
    for line in (text or "").splitlines():
        src = line.strip()
        if len(src) < 4:
            continue
        nums = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[,.]\d+)?)\s*(?:м2|м²|кв\.?\s*м|м\b)", src.lower())]
        if not nums:
            continue
        name = re.sub(r"\d+(?:[,.]\d+)?\s*(?:м2|м²|кв\.?\s*м|м\b)", "", src, flags=re.I).strip(" -:;,.")
        if not name:
            name = "Помещение " + str(len(rooms) + 1)
        floor_area = nums[0]
        height = nums[1] if len(nums) > 1 and nums[1] < 6 else 0
        rooms.append({
            "name": name[:120],
            "floor": 1,
            "liter": "",
            "roomType": "Комната",
            "floorArea": floor_area,
            "wallArea": 0,
            "ceilingArea": floor_area,
            "height": height,
            "windows": 0,
            "doors": 0,
            "notes": "Черновик из строки обмера: " + src[:300],
        })
    return rooms[:80]


def _room_draft_prompt(measurement: dict) -> str:
    title = measurement.get("title") or ""
    notes = measurement.get("notes") or ""
    source_type = measurement.get("source_type") or ""
    doc_type = measurement.get("doc_type") or ""
    return (
        "Извлеки помещения из строительного проекта или обмера. Верни только JSON без markdown. "
        "Формат: {\"rooms\":[{\"name\":\"\",\"floor\":1,\"liter\":\"\",\"roomType\":\"Комната\","
        "\"floorArea\":0,\"wallArea\":0,\"ceilingArea\":0,\"height\":0,\"windows\":0,\"doors\":0,\"notes\":\"\"}]}. "
        "Если точного значения нет — ставь 0 или пустую строку. Не выдумывай площади. "
        "Оконные и дверные проёмы отдельно не считай в wallArea, только количество если явно есть.\n\n"
        "Тип источника: " + source_type + "\n"
        "Тип документа: " + doc_type + "\n"
        "Название: " + title + "\n"
        "Текст/примечания:\n" + notes
    )


def _room_draft_image_data_url(measurement: dict) -> str:
    file_url = measurement.get("file_url") or ""
    if not file_url:
        return ""
    local_path = file_url.lstrip("/")
    if not local_path.startswith("uploads/"):
        return ""
    upload_root = os.path.realpath("uploads")
    resolved_path = os.path.realpath(local_path)
    try:
        if os.path.commonpath((upload_root, resolved_path)) != upload_root:
            return ""
    except ValueError:
        return ""
    if not os.path.exists(resolved_path):
        return ""
    if os.path.splitext(resolved_path)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        return ""
    with open(resolved_path, "rb") as image_file:
        image_payload = base64.b64encode(image_file.read()).decode("utf-8")
    return "data:image/jpeg;base64," + image_payload


def _room_draft_ai_result(output_text: str):
    parsed = _clean_ai_json(output_text or "")
    rooms = parsed.get("rooms", []) if isinstance(parsed, dict) else []
    if isinstance(rooms, list) and rooms:
        return rooms[:100], "ai"
    return None


def _room_draft_fallback(measurement: dict):
    title = measurement.get("title") or ""
    notes = measurement.get("notes") or ""
    return _fallback_room_drafts_from_text(title + "\n" + notes), "fallback"


def _draft_rooms_with_ai(
    measurement: dict,
    yandex_api_key: str,
    yandex_folder_id: str,
):
    if not (yandex_api_key and yandex_folder_id):
        return _room_draft_fallback(measurement)
    prompt = _room_draft_prompt(measurement)
    image_data_url = _room_draft_image_data_url(measurement)
    try:
        request_arguments = {
            "capability": "project_room_draft",
            "instructions": _ROOM_DRAFT_INSTRUCTIONS,
            "temperature": 0.1,
            "max_output_tokens": 2500,
            "deadline_seconds": 120,
        }
        if image_data_url:
            request_arguments["input_parts"] = (
                ModelInputPart(kind="image_data_url", value=image_data_url),
                ModelInputPart(kind="text", value=prompt),
            )
        else:
            request_arguments["input_text"] = prompt
        request = build_model_request(**request_arguments)
        gateway = build_yandex_model_adapter(
            api_key=yandex_api_key,
            folder_id=yandex_folder_id,
        )
        response = gateway.generate(request)
        result = _room_draft_ai_result(response.output_text)
        if result is not None:
            return result
    except ModelGatewayError as error:
        print("MEASUREMENT AI DRAFT ERROR:", error.code)
    except Exception:
        print("MEASUREMENT AI DRAFT ERROR:", MODEL_GATEWAY_PROVIDER_FAILED)
    return _room_draft_fallback(measurement)


def register_project_records_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]
    visible_project_names = deps["visible_project_names"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_user = deps["effective_company_user"]
    read_roles = deps["read_roles"]
    write_roles = deps["write_roles"]
    worker_execution_roles = deps["worker_execution_roles"]
    yandex_api_key = deps.get("yandex_api_key", "")
    yandex_folder_id = deps.get("yandex_folder_id", "")

    read_access = require_roles(*read_roles)
    write_access = require_roles(*write_roles)

    from .owned_routes import register_owned_record_routes
    register_owned_record_routes(app, deps)

    scope = RoomOwnership(
        resolve_work_company_context,
        deps["effective_company_actors"],
        full_view_roles=tuple(deps.get("full_view_roles") or ()),
        platform_staff_roles=tuple(deps.get("platform_staff_roles") or ()),
        read_roles=tuple(read_roles),
        write_roles=tuple(write_roles),
    )
    _ = (require_project_access, require_row_project_access, visible_project_names, effective_company_user, worker_execution_roles)

    def measurement_dict(row):
        return {
            "id": row[0],
            "projectName": row[1],
            "sourceType": row[2] or "Фактический обмер",
            "docType": row[3] or "Обмер",
            "title": row[4] or "",
            "fileUrl": row[5] or "",
            "photoUrl": row[6] or "",
            "status": row[7] or "Черновик",
            "roomsCreated": int(row[8] or 0),
            "notes": row[9] or "",
            "uploadedBy": row[10] or "",
            "reviewedBy": row[11] or "",
            "reviewedAt": str(row[12]) if row[12] else "",
            "createdAt": str(row[13]) if row[13] else "",
            "companyId": row[14],
            "projectId": row[15],
        }

    def scoped_where(cur, user, request, *, write, project_name=None):
        actors, mode = scope.actors(cur, user, request, write=write)
        join, where, params = scope.list_clause(actors, mode)
        if project_name:
            if mode == "platform_unowned":
                where += " AND r.project_name=%s"
            else:
                where += " AND p.name=%s"
            params = [*params, project_name]
        return actors, mode, join, where, params

    @app.get("/project-measurements")
    def get_project_measurements(project_name: str = None, _current_user: dict = Depends(read_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            _actors, _mode, join, where, params = scoped_where(cur, _current_user, request, write=False, project_name=project_name)
            cur.execute(
                """SELECT r.id,r.project_name,r.source_type,r.doc_type,r.title,r.file_url,r.photo_url,r.status,r.rooms_created,r.notes,
                          r.uploaded_by,r.reviewed_by,r.reviewed_at,r.created_at,r.company_id,r.project_id
                   FROM project_measurements r """ + join + " WHERE " + where + " ORDER BY r.id DESC",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [measurement_dict(row) for row in rows]

    @app.post("/project-measurements")
    def create_project_measurement(data: dict, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, _mode = scope.actors(cur, _current_user, request, write=True)
            parent = scope.verified_project(cur, actors[0], data)
            cur.execute("""INSERT INTO project_measurements
                               (project_name,source_type,doc_type,title,file_url,photo_url,status,rooms_created,notes,uploaded_by,company_id,project_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (parent["name"], data.get("sourceType", "Фактический обмер"), data.get("docType", "Обмер"),
                 data.get("title", ""), data.get("fileUrl", ""), data.get("photoUrl", ""), data.get("status", "Черновик"),
                 int(data.get("roomsCreated") or 0), data.get("notes", ""), data.get("uploadedBy", ""),
                 parent["companyId"], parent["id"]))
            new_id = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "id": new_id}

    @app.put("/project-measurements/{id}")
    def update_project_measurement(id: int, data: dict, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            current = scope.mutable_row(cur, "project_measurements", id, actors, mode)
            fields = {
                "sourceType": "source_type",
                "docType": "doc_type",
                "title": "title",
                "fileUrl": "file_url",
                "photoUrl": "photo_url",
                "status": "status",
                "roomsCreated": "rooms_created",
                "notes": "notes",
            }
            sets, vals = [], []
            for key, column in fields.items():
                if key in data:
                    sets.append(column + "=%s")
                    vals.append(int(data.get(key) or 0) if key == "roomsCreated" else data.get(key, ""))
            if data.get("projectName") not in (None, "") or data.get("projectId") not in (None, ""):
                parent = scope.verified_project(cur, actors[0], data)
                sets.extend(["project_name=%s", "company_id=%s", "project_id=%s"])
                vals.extend([parent["name"], parent["companyId"], parent["id"]])
                cur.execute("""UPDATE measurement_room_drafts
                               SET project_name=%s, company_id=%s, project_id=%s
                               WHERE measurement_id=%s AND company_id=%s""",
                            (parent["name"], parent["companyId"], parent["id"], id, current["companyId"]))
            if data.get("status") == "Принято":
                sets.append("reviewed_by=%s")
                vals.append(_current_user.get("name") or "")
                sets.append("reviewed_at=NOW()")
            if sets:
                vals.append(id)
                cur.execute("UPDATE project_measurements SET " + ",".join(sets) + " WHERE id=%s", tuple(vals))
                conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.delete("/project-measurements/{id}")
    def delete_project_measurement(id: int, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "project_measurements", id, actors, mode)
            cur.execute("UPDATE measurement_room_drafts SET status='Отменён' WHERE measurement_id=%s", (id,))
            cur.execute("UPDATE project_measurements SET status='Отменён' WHERE id=%s", (id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.get("/measurement-room-drafts")
    def get_measurement_room_drafts(project_name: str = None, measurement_id: int = None, _current_user: dict = Depends(read_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            _actors, mode, join, where, params = scoped_where(cur, _current_user, request, write=False, project_name=project_name)
            if measurement_id:
                where += " AND r.measurement_id=%s"
                params = [*params, measurement_id]
            cur.execute(
                "SELECT " + MEASUREMENT_ROOM_DRAFT_COLUMNS + " FROM measurement_room_drafts r "
                + join + " WHERE " + where + " ORDER BY r.id DESC",
                tuple(params),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [_room_draft_dict(row) for row in rows]

    @app.post("/project-measurements/{id}/ai-draft-rooms")
    def generate_measurement_room_drafts(id: int, data: dict = None, _current_user: dict = Depends(write_access), request: Request = None):
        data = data or {}
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            owner = scope.mutable_row(cur, "project_measurements", id, actors, mode)
            cur.execute("SELECT * FROM project_measurements WHERE id=%s", (id,))
            measurement = cur.fetchone()
            if not measurement:
                raise HTTPException(status_code=404, detail="Источник обмера не найден")
            rooms, source = _draft_rooms_with_ai(dict(measurement), yandex_api_key, yandex_folder_id)
            if data.get("replaceExisting"):
                cur.execute("DELETE FROM measurement_room_drafts WHERE measurement_id=%s AND status='Черновик ИИ' AND company_id=%s", (id, owner["companyId"]))
            created = 0
            for room in rooms:
                name = (room.get("name") or "").strip()
                if not name:
                    continue
                cur.execute("""INSERT INTO measurement_room_drafts
                               (measurement_id,project_name,name,floor,liter,room_type,floor_area,wall_area,ceiling_area,height,windows,doors,notes,status,created_by,company_id,project_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (id, owner["name"], name[:255], int(room.get("floor") or 1),
                     str(room.get("liter") or ""), str(room.get("roomType") or room.get("room_type") or "Комната"),
                     float(room.get("floorArea") or room.get("floor_area") or 0),
                     float(room.get("wallArea") or room.get("wall_area") or 0),
                     float(room.get("ceilingArea") or room.get("ceiling_area") or room.get("floorArea") or room.get("floor_area") or 0),
                     float(room.get("height") or 0), int(room.get("windows") or 0), int(room.get("doors") or 0),
                     str(room.get("notes") or ""), "Черновик ИИ", _current_user.get("name") or "",
                     owner["companyId"], owner["projectId"]))
                created += 1
            if created:
                cur.execute("UPDATE project_measurements SET status=%s WHERE id=%s", ("На проверке", id))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "created": created, "source": source}

    @app.put("/measurement-room-drafts/{id}")
    def update_measurement_room_draft(id: int, data: dict, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "measurement_room_drafts", id, actors, mode)
            fields = {
                "name": "name", "floor": "floor", "liter": "liter", "roomType": "room_type",
                "floorArea": "floor_area", "wallArea": "wall_area", "ceilingArea": "ceiling_area",
                "height": "height", "windows": "windows", "doors": "doors", "notes": "notes", "status": "status",
            }
            sets, vals = [], []
            for key, column in fields.items():
                if key in data:
                    sets.append(column + "=%s")
                    vals.append(data.get(key))
            if sets:
                vals.append(id)
                cur.execute("UPDATE measurement_room_drafts SET " + ",".join(sets) + " WHERE id=%s", tuple(vals))
                conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/measurement-room-drafts/{id}/accept")
    def accept_measurement_room_draft(id: int, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            owner = scope.mutable_row(cur, "measurement_room_drafts", id, actors, mode)
            cur.execute("""SELECT measurement_id,name,floor,liter,room_type,floor_area,wall_area,ceiling_area,height,windows,doors,notes,accepted_room_id
                           FROM measurement_room_drafts WHERE id=%s""", (id,))
            draft = cur.fetchone()
            if not draft:
                raise HTTPException(status_code=404, detail="Черновик не найден")
            if draft[12]:
                return {"ok": True, "roomId": draft[12], "alreadyAccepted": True}
            cur.execute("""INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,height,ceiling_type,wall_material,floor_material,windows,doors,notes,floor,liter,room_type,company_id,project_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (owner["name"], draft[1], float(draft[5] or 0), float(draft[6] or 0), float(draft[7] or 0), float(draft[8] or 0),
                 "Простой", "Штукатурка", "Стяжка", int(draft[9] or 0), int(draft[10] or 0),
                 ((draft[11] or "") + "\nИсточник: черновик обмера №" + str(id)).strip(), int(draft[2] or 1), draft[3] or "", draft[4] or "Комната",
                 owner["companyId"], owner["projectId"]))
            room_id = cur.fetchone()[0]
            cur.execute("UPDATE measurement_room_drafts SET status='Принято', accepted_room_id=%s WHERE id=%s", (room_id, id))
            if draft[0]:
                cur.execute("""UPDATE project_measurements
                               SET rooms_created=(SELECT COUNT(*) FROM measurement_room_drafts WHERE measurement_id=%s AND accepted_room_id IS NOT NULL)
                               WHERE id=%s""", (draft[0], draft[0]))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "roomId": room_id}

    @app.delete("/measurement-room-drafts/{id}")
    def delete_measurement_room_draft(id: int, _current_user: dict = Depends(write_access), request: Request = None):
        conn = get_db()
        try:
            cur = conn.cursor()
            actors, mode = scope.actors(cur, _current_user, request, write=True)
            scope.mutable_row(cur, "measurement_room_drafts", id, actors, mode)
            cur.execute("DELETE FROM measurement_room_drafts WHERE id=%s", (id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}
