import json
import re
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _read_by_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _message_response(row):
    item = dict(row or {})
    company_id = _positive_int(item.get("company_id"))
    return {
        "id": item.get("id"),
        "chat_type": item.get("chat_type") or "company",
        "project_id": item.get("project_id"),
        "author_id": item.get("author_id"),
        "author_name": item.get("author_name") or "",
        "author_role": item.get("author_role") or "",
        "text": item.get("text") or "",
        "photo_url": item.get("photo_url") or "",
        "created_at": str(item.get("created_at") or ""),
        "readBy": _read_by_list(item.get("read_by")),
        "companyId": company_id,
        "legacyUnscoped": company_id is None,
    }


def _selected_company_id(context):
    company_id = _positive_int((context or {}).get("companyId") or (context or {}).get("company_id"))
    if (context or {}).get("mode") != "company" or not company_id:
        raise HTTPException(status_code=400, detail="Для чата выберите конкретную компанию")
    return company_id


def _require_company_chat_payload(data):
    payload = data or {}
    chat_type = str(payload.get("chatType") or "company").strip().lower()
    if chat_type != "company":
        raise HTTPException(status_code=400, detail="Проектный чат использует отдельный маршрут")
    if payload.get("projectId") not in (None, ""):
        raise HTTPException(status_code=400, detail="Общий чат компании не принимает projectId")
    return payload


def _require_company_message_content(payload):
    item = dict(payload or {})
    text = str(item.get("text") or "")
    photo_url = str(item.get("photoUrl") or "").strip()
    if len(text) > 10000:
        raise HTTPException(status_code=400, detail="Текст сообщения слишком длинный")
    if not text.strip() and not photo_url:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    item["text"] = text
    item["photoUrl"] = photo_url
    return item


def _require_owned_chat_photo(cur, photo_url, company_id):
    value = str(photo_url or "").strip()
    if not value:
        return ""
    if len(value) > 2048:
        raise HTTPException(status_code=400, detail="Ссылка на фото слишком длинная")
    content_match = re.fullmatch(r"/tenant-files/([1-9][0-9]*)/content", value)
    if content_match:
        cur.execute(
            """SELECT id,company_id,project_id,context,
                      COALESCE(deletion_status,'active') AS deletion_status
                 FROM file_ownership
                WHERE id=%s AND company_id=%s
                FOR SHARE""",
            (int(content_match.group(1)), company_id),
        )
    else:
        cur.execute(
            """SELECT id,company_id,project_id,context,
                      COALESCE(deletion_status,'active') AS deletion_status
                 FROM file_ownership
                WHERE file_url=%s AND company_id=%s
                FOR SHARE""",
            (value, company_id),
        )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Фото чата не зарегистрировано")
    item = dict(row)
    if _positive_int(item.get("company_id")) != company_id:
        raise HTTPException(status_code=409, detail="Фото относится к другой компании")
    if item.get("project_id") not in (None, ""):
        raise HTTPException(status_code=409, detail="Фото объекта нельзя прикрепить к общему чату компании")
    if str(item.get("context") or "").strip().lower() != "company-chat":
        raise HTTPException(status_code=409, detail="Файл загружен не для общего чата компании")
    if str(item.get("deletion_status") or "active").strip().lower() != "active":
        raise HTTPException(status_code=410, detail="Фото удаляется или недоступно")
    return value


def register_company_messages_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_request_company_context = deps["resolve_request_company_context"]
    effective_company_user = deps["effective_company_user"]
    platform_staff_roles = tuple(deps.get("platform_staff_roles") or ())
    client_account_roles = tuple(deps.get("client_account_roles") or ())

    def resolve_context(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_request_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
            platform_staff_roles=platform_staff_roles,
            client_account_roles=client_account_roles,
        )
        return context, _selected_company_id(context)

    @app.get("/messages")
    def get_messages(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, company_id = resolve_context(cur, current_user, "read", x_company_id, x_company_mode)
            cur.execute(
                """SELECT id,company_id,chat_type,project_id,author_id,author_name,author_role,
                          text,photo_url,created_at,read_by
                     FROM (
                         SELECT id,company_id,chat_type,project_id,author_id,author_name,author_role,
                                text,photo_url,created_at,read_by
                           FROM messages
                          WHERE company_id=%s AND chat_type='company'
                          ORDER BY created_at DESC,id DESC
                          LIMIT 200
                     ) recent
                    ORDER BY created_at ASC,id ASC""",
                (company_id,),
            )
            return [_message_response(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/messages")
    def create_message(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = _require_company_message_content(_require_company_chat_payload(data))
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, company_id = resolve_context(cur, current_user, "create", x_company_id, x_company_mode)
            actor = effective_company_user(current_user, context)
            author_id = _positive_int(actor.get("id"))
            if not author_id:
                raise HTTPException(status_code=403, detail="Пользователь чата не определен")
            photo_url = _require_owned_chat_photo(cur, payload.get("photoUrl"), company_id)
            read_by = json.dumps([author_id])
            cur.execute(
                """INSERT INTO messages
                           (company_id,chat_type,project_id,author_id,author_name,author_role,text,photo_url,read_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id,company_id,chat_type,project_id,author_id,author_name,author_role,
                              text,photo_url,created_at,read_by""",
                (
                    company_id,
                    "company",
                    None,
                    author_id,
                    actor.get("name") or "",
                    actor.get("role") or "",
                    str(payload.get("text") or ""),
                    photo_url,
                    read_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return _message_response(row)
        finally:
            cur.close()
            conn.close()

    @app.post("/messages/mark-read")
    def mark_messages_read(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = _require_company_chat_payload(data)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, company_id = resolve_context(cur, current_user, "update", x_company_id, x_company_mode)
            actor = effective_company_user(current_user, context)
            user_id = _positive_int(actor.get("id"))
            if not user_id:
                raise HTTPException(status_code=403, detail="Пользователь чата не определен")
            read_by = json.dumps([user_id])
            cur.execute(
                """WITH visible AS (
                       SELECT id
                         FROM messages
                        WHERE company_id=%s AND chat_type=%s
                        ORDER BY created_at DESC,id DESC
                        LIMIT 200
                   )
                   UPDATE messages
                      SET read_by=COALESCE(read_by,'[]'::jsonb) || %s::jsonb
                    WHERE company_id=%s
                      AND id IN (SELECT id FROM visible)
                      AND NOT COALESCE(read_by,'[]'::jsonb) @> %s::jsonb""",
                (company_id, "company", read_by, company_id, read_by),
            )
            updated = cur.rowcount
            conn.commit()
            return {"ok": True, "updated": updated}
        finally:
            cur.close()
            conn.close()
