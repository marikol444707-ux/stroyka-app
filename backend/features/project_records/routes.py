import base64
import json
import os
import re

import psycopg2.extras
from fastapi import Depends, HTTPException


MEASUREMENT_ROOM_DRAFT_SELECT = """SELECT id,measurement_id,project_name,name,floor,liter,room_type,
                                          floor_area,wall_area,ceiling_area,height,windows,doors,
                                          notes,status,created_by,accepted_room_id,created_at
                                   FROM measurement_room_drafts"""


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


def _draft_rooms_with_ai(measurement: dict, yandex_api_key: str, yandex_folder_id: str):
    title = measurement.get("title") or ""
    notes = measurement.get("notes") or ""
    source_type = measurement.get("source_type") or ""
    doc_type = measurement.get("doc_type") or ""
    prompt = (
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
    if not (yandex_api_key and yandex_folder_id):
        return _fallback_room_drafts_from_text(title + "\n" + notes), "fallback"
    import openai as oa

    client = oa.OpenAI(api_key=yandex_api_key, base_url="https://ai.api.cloud.yandex.net/v1", project=yandex_folder_id)
    image_payload = None
    file_url = measurement.get("file_url") or ""
    if file_url:
        local_path = file_url.lstrip("/")
        if local_path.startswith("uploads/") and os.path.exists(local_path):
            ext = os.path.splitext(local_path)[1].lower()
            if ext in (".jpg", ".jpeg", ".png", ".webp"):
                with open(local_path, "rb") as f:
                    image_payload = base64.b64encode(f.read()).decode("utf-8")
    try:
        if image_payload:
            response = client.responses.create(
                model=f"gpt://{yandex_folder_id}/qwen3.6-35b-a3b/latest",
                temperature=0.1,
                instructions="Ты извлекаешь помещения из обмеров и проектов. Верни только валидный JSON.",
                input=[{"role": "user", "content": [
                    {"type": "input_image", "image_url": "data:image/jpeg;base64," + image_payload},
                    {"type": "input_text", "text": prompt}
                ]}],
                max_output_tokens=2500
            )
        else:
            response = client.responses.create(
                model=f"gpt://{yandex_folder_id}/qwen3.6-35b-a3b/latest",
                temperature=0.1,
                instructions="Ты извлекаешь помещения из обмеров и проектов. Верни только валидный JSON.",
                input=prompt,
                max_output_tokens=2500
            )
        parsed = _clean_ai_json(response.output_text or "")
        rooms = parsed.get("rooms", []) if isinstance(parsed, dict) else []
        if isinstance(rooms, list) and rooms:
            return rooms[:100], "ai"
    except Exception as e:
        print("MEASUREMENT AI DRAFT ERROR:", str(e))
    return _fallback_room_drafts_from_text(title + "\n" + notes), "fallback"


def register_project_records_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]
    visible_project_names = deps["visible_project_names"]
    read_roles = deps["read_roles"]
    write_roles = deps["write_roles"]
    worker_execution_roles = deps["worker_execution_roles"]
    yandex_api_key = deps.get("yandex_api_key", "")
    yandex_folder_id = deps.get("yandex_folder_id", "")

    read_access = require_roles(*read_roles)
    write_access = require_roles(*write_roles)

    @app.get("/project-documents")
    def get_project_documents(project_name: str = None, _current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(_current_user)
        side_filter = None
        if _current_user.get("role") == "заказчик":
            side_filter = "customer"
        elif _current_user.get("role") in worker_execution_roles:
            side_filter = "contractor"
        side_sql = " AND side=%s" if side_filter else ""
        worker_doc_sql = ""
        worker_doc_params = []
        if _current_user.get("role") in worker_execution_roles:
            worker_doc_sql = " AND (counterparty=%s OR uploaded_by=%s)"
            worker_doc_params = [_current_user.get("name") or "", _current_user.get("name") or ""]
        if project_name:
            if allowed_projects is not None and project_name not in allowed_projects:
                cur.close()
                conn.close()
                return []
            params = [project_name]
            if side_filter:
                params.append(side_filter)
            params.extend(worker_doc_params)
            cur.execute("SELECT id,project_name,side,doc_type,number,doc_date,counterparty,sign_status,scan_url,amount,notes,uploaded_by,created_at FROM project_documents WHERE project_name=%s" + side_sql + worker_doc_sql + " ORDER BY id DESC", tuple(params))
        elif allowed_projects is not None:
            if not allowed_projects:
                cur.close()
                conn.close()
                return []
            params = [allowed_projects]
            if side_filter:
                params.append(side_filter)
            params.extend(worker_doc_params)
            cur.execute("SELECT id,project_name,side,doc_type,number,doc_date,counterparty,sign_status,scan_url,amount,notes,uploaded_by,created_at FROM project_documents WHERE project_name = ANY(%s)" + side_sql + worker_doc_sql + " ORDER BY id DESC", tuple(params))
        else:
            params = []
            if side_filter:
                params.append(side_filter)
            params.extend(worker_doc_params)
            where_parts = []
            if side_filter:
                where_parts.append("side=%s")
            if worker_doc_sql:
                where_parts.append(worker_doc_sql.strip()[4:])
            where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""
            cur.execute("SELECT id,project_name,side,doc_type,number,doc_date,counterparty,sign_status,scan_url,amount,notes,uploaded_by,created_at FROM project_documents" + where_sql + " ORDER BY id DESC", tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "projectName": r[1], "side": r[2], "docType": r[3] or "", "number": r[4] or "", "docDate": str(r[5]) if r[5] else "", "counterparty": r[6] or "", "signStatus": r[7] or "", "scanUrl": r[8] or "", "amount": float(r[9] or 0), "notes": r[10] or "", "uploadedBy": r[11] or "", "createdAt": str(r[12])} for r in rows]

    @app.post("/project-documents")
    def create_project_document(data: dict, _current_user: dict = Depends(write_access)):
        require_project_access(_current_user, data.get("projectName", ""))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO project_documents (project_name,side,doc_type,number,doc_date,counterparty,sign_status,scan_url,amount,notes,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectName", ""), data.get("side", "customer"), data.get("docType", ""), data.get("number", ""),
             data.get("docDate") or None, data.get("counterparty", ""), data.get("signStatus", "Не подписан"),
             data.get("scanUrl", ""), data.get("amount") or 0, data.get("notes", ""), data.get("uploadedBy", "")))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": new_id}

    @app.put("/project-documents/{id}")
    def update_project_document(id: int, data: dict, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_documents", id, _current_user)
        fields = {"side": "side", "docType": "doc_type", "number": "number", "docDate": "doc_date", "counterparty": "counterparty", "signStatus": "sign_status", "scanUrl": "scan_url", "amount": "amount", "notes": "notes"}
        sets, vals = [], []
        for k, col in fields.items():
            if k in data:
                sets.append(col + "=%s")
                vals.append(data.get(k) if data.get(k) != "" or col not in ("doc_date",) else None)
        if sets:
            vals.append(id)
            cur.execute("UPDATE project_documents SET " + ",".join(sets) + " WHERE id=%s", tuple(vals))
            conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.delete("/project-documents/{id}")
    def delete_project_document(id: int, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_documents", id, _current_user)
        cur.execute("UPDATE project_documents SET sign_status='Аннулирован' WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.get("/project-measurements")
    def get_project_measurements(project_name: str = None, _current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(_current_user)
        select_sql = """SELECT id,project_name,source_type,doc_type,title,file_url,photo_url,status,rooms_created,notes,
                               uploaded_by,reviewed_by,reviewed_at,created_at
                        FROM project_measurements"""
        if project_name:
            if allowed_projects is not None and project_name not in allowed_projects:
                cur.close()
                conn.close()
                return []
            cur.execute(select_sql + " WHERE project_name=%s ORDER BY id DESC", (project_name,))
        elif allowed_projects is not None:
            if not allowed_projects:
                cur.close()
                conn.close()
                return []
            cur.execute(select_sql + " WHERE project_name = ANY(%s) ORDER BY id DESC", (allowed_projects,))
        else:
            cur.execute(select_sql + " ORDER BY id DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{
            "id": r[0],
            "projectName": r[1],
            "sourceType": r[2] or "Фактический обмер",
            "docType": r[3] or "Обмер",
            "title": r[4] or "",
            "fileUrl": r[5] or "",
            "photoUrl": r[6] or "",
            "status": r[7] or "Черновик",
            "roomsCreated": int(r[8] or 0),
            "notes": r[9] or "",
            "uploadedBy": r[10] or "",
            "reviewedBy": r[11] or "",
            "reviewedAt": str(r[12]) if r[12] else "",
            "createdAt": str(r[13]) if r[13] else "",
        } for r in rows]

    @app.post("/project-measurements")
    def create_project_measurement(data: dict, _current_user: dict = Depends(write_access)):
        project_name = data.get("projectName", "")
        require_project_access(_current_user, project_name)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO project_measurements
                           (project_name,source_type,doc_type,title,file_url,photo_url,status,rooms_created,notes,uploaded_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (project_name, data.get("sourceType", "Фактический обмер"), data.get("docType", "Обмер"),
             data.get("title", ""), data.get("fileUrl", ""), data.get("photoUrl", ""), data.get("status", "Черновик"),
             int(data.get("roomsCreated") or 0), data.get("notes", ""), data.get("uploadedBy", "")))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": new_id}

    @app.put("/project-measurements/{id}")
    def update_project_measurement(id: int, data: dict, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_measurements", id, _current_user)
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
        for k, col in fields.items():
            if k in data:
                sets.append(col + "=%s")
                vals.append(int(data.get(k) or 0) if k == "roomsCreated" else data.get(k, ""))
        if data.get("status") == "Принято":
            sets.append("reviewed_by=%s")
            vals.append(_current_user.get("name") or "")
            sets.append("reviewed_at=NOW()")
        if sets:
            vals.append(id)
            cur.execute("UPDATE project_measurements SET " + ",".join(sets) + " WHERE id=%s", tuple(vals))
            conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.delete("/project-measurements/{id}")
    def delete_project_measurement(id: int, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_measurements", id, _current_user)
        cur.execute("UPDATE measurement_room_drafts SET status='Отменён' WHERE measurement_id=%s", (id,))
        cur.execute("UPDATE project_measurements SET status='Отменён' WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.get("/measurement-room-drafts")
    def get_measurement_room_drafts(project_name: str = None, measurement_id: int = None, _current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(_current_user)
        where, params = [], []
        if project_name:
            require_project_access(_current_user, project_name)
            where.append("project_name=%s")
            params.append(project_name)
        elif allowed_projects is not None:
            if not allowed_projects:
                cur.close()
                conn.close()
                return []
            where.append("project_name = ANY(%s)")
            params.append(allowed_projects)
        if measurement_id:
            where.append("measurement_id=%s")
            params.append(measurement_id)
        q = MEASUREMENT_ROOM_DRAFT_SELECT
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC"
        cur.execute(q, tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [_room_draft_dict(r) for r in rows]

    @app.post("/project-measurements/{id}/ai-draft-rooms")
    def generate_measurement_room_drafts(id: int, data: dict = None, _current_user: dict = Depends(write_access)):
        data = data or {}
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM project_measurements WHERE id=%s", (id,))
        measurement = cur.fetchone()
        if not measurement:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Источник обмера не найден")
        require_project_access(_current_user, measurement.get("project_name") or "")
        rooms, source = _draft_rooms_with_ai(dict(measurement), yandex_api_key, yandex_folder_id)
        if data.get("replaceExisting"):
            cur.execute("DELETE FROM measurement_room_drafts WHERE measurement_id=%s AND status='Черновик ИИ'", (id,))
        created = 0
        for room in rooms:
            name = (room.get("name") or "").strip()
            if not name:
                continue
            cur.execute("""INSERT INTO measurement_room_drafts
                           (measurement_id,project_name,name,floor,liter,room_type,floor_area,wall_area,ceiling_area,height,windows,doors,notes,status,created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (id, measurement.get("project_name") or "", name[:255], int(room.get("floor") or 1),
                 str(room.get("liter") or ""), str(room.get("roomType") or room.get("room_type") or "Комната"),
                 float(room.get("floorArea") or room.get("floor_area") or 0),
                 float(room.get("wallArea") or room.get("wall_area") or 0),
                 float(room.get("ceilingArea") or room.get("ceiling_area") or room.get("floorArea") or room.get("floor_area") or 0),
                 float(room.get("height") or 0), int(room.get("windows") or 0), int(room.get("doors") or 0),
                 str(room.get("notes") or ""), "Черновик ИИ", _current_user.get("name") or ""))
            created += 1
        if created:
            cur.execute("UPDATE project_measurements SET status=%s WHERE id=%s", ("На проверке", id))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "created": created, "source": source}

    @app.put("/measurement-room-drafts/{id}")
    def update_measurement_room_draft(id: int, data: dict, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "measurement_room_drafts", id, _current_user, "project_name")
        fields = {
            "name": "name", "floor": "floor", "liter": "liter", "roomType": "room_type",
            "floorArea": "floor_area", "wallArea": "wall_area", "ceilingArea": "ceiling_area",
            "height": "height", "windows": "windows", "doors": "doors", "notes": "notes", "status": "status",
        }
        sets, vals = [], []
        for k, col in fields.items():
            if k in data:
                sets.append(col + "=%s")
                vals.append(data.get(k))
        if sets:
            vals.append(id)
            cur.execute("UPDATE measurement_room_drafts SET " + ",".join(sets) + " WHERE id=%s", tuple(vals))
            conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.post("/measurement-room-drafts/{id}/accept")
    def accept_measurement_room_draft(id: int, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "measurement_room_drafts", id, _current_user, "project_name")
        cur.execute("""SELECT measurement_id,project_name,name,floor,liter,room_type,floor_area,wall_area,ceiling_area,height,windows,doors,notes,status,accepted_room_id
                       FROM measurement_room_drafts WHERE id=%s""", (id,))
        d = cur.fetchone()
        if not d:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Черновик не найден")
        if d[14]:
            cur.close()
            conn.close()
            return {"ok": True, "roomId": d[14], "alreadyAccepted": True}
        cur.execute("""INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,height,ceiling_type,wall_material,floor_material,windows,doors,notes,floor,liter,room_type)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (d[1], d[2], float(d[6] or 0), float(d[7] or 0), float(d[8] or 0), float(d[9] or 0),
             "Простой", "Штукатурка", "Стяжка", int(d[10] or 0), int(d[11] or 0),
             ((d[12] or "") + "\nИсточник: черновик обмера №" + str(id)).strip(), int(d[3] or 1), d[4] or "", d[5] or "Комната"))
        room_id = cur.fetchone()[0]
        cur.execute("UPDATE measurement_room_drafts SET status='Принято', accepted_room_id=%s WHERE id=%s", (room_id, id))
        if d[0]:
            cur.execute("""UPDATE project_measurements
                           SET rooms_created=(SELECT COUNT(*) FROM measurement_room_drafts WHERE measurement_id=%s AND accepted_room_id IS NOT NULL)
                           WHERE id=%s""", (d[0], d[0]))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "roomId": room_id}

    @app.delete("/measurement-room-drafts/{id}")
    def delete_measurement_room_draft(id: int, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "measurement_room_drafts", id, _current_user, "project_name")
        cur.execute("DELETE FROM measurement_room_drafts WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}

    @app.get("/project-letters")
    def get_project_letters(project_name: str = None, _current_user: dict = Depends(read_access)):
        conn = get_db()
        cur = conn.cursor()
        allowed_projects = visible_project_names(_current_user)
        side_filter = None
        if _current_user.get("role") == "заказчик":
            side_filter = "customer"
        elif _current_user.get("role") in worker_execution_roles:
            side_filter = "contractor"
        side_sql = " AND side=%s" if side_filter else ""
        if project_name:
            if allowed_projects is not None and project_name not in allowed_projects:
                cur.close()
                conn.close()
                return []
            params = [project_name]
            if side_filter:
                params.append(side_filter)
            cur.execute("SELECT id,project_name,side,direction,subject,body,counterparty,letter_date,file_url,author,created_at FROM project_letters WHERE project_name=%s AND COALESCE(status,'') <> 'Аннулировано'" + side_sql + " ORDER BY id DESC", tuple(params))
        elif allowed_projects is not None:
            if not allowed_projects:
                cur.close()
                conn.close()
                return []
            params = [allowed_projects]
            if side_filter:
                params.append(side_filter)
            cur.execute("SELECT id,project_name,side,direction,subject,body,counterparty,letter_date,file_url,author,created_at FROM project_letters WHERE project_name = ANY(%s) AND COALESCE(status,'') <> 'Аннулировано'" + side_sql + " ORDER BY id DESC", tuple(params))
        else:
            params = []
            if side_filter:
                params.append(side_filter)
            cur.execute("SELECT id,project_name,side,direction,subject,body,counterparty,letter_date,file_url,author,created_at FROM project_letters WHERE COALESCE(status,'') <> 'Аннулировано'" + (" AND side=%s" if side_filter else "") + " ORDER BY id DESC", tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "projectName": r[1], "side": r[2], "direction": r[3] or "", "subject": r[4] or "", "body": r[5] or "", "counterparty": r[6] or "", "letterDate": str(r[7]) if r[7] else "", "fileUrl": r[8] or "", "author": r[9] or "", "createdAt": str(r[10])} for r in rows]

    @app.post("/project-letters")
    def create_project_letter(data: dict, _current_user: dict = Depends(write_access)):
        require_project_access(_current_user, data.get("projectName", ""))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO project_letters (project_name,side,direction,subject,body,counterparty,letter_date,file_url,author) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectName", ""), data.get("side", "customer"), data.get("direction", "outgoing"), data.get("subject", ""),
             data.get("body", ""), data.get("counterparty", ""), data.get("letterDate") or None, data.get("fileUrl", ""), data.get("author", "")))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "id": new_id}

    @app.delete("/project-letters/{id}")
    def delete_project_letter(id: int, _current_user: dict = Depends(write_access)):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "project_letters", id, _current_user)
        cur.execute("UPDATE project_letters SET status='Аннулировано' WHERE id=%s", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}
