import json
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


_MESSAGE_COMPANY_SCOPE_SQL = """
    (
        messages.company_id=%s
        OR (
            messages.company_id IS NULL
            AND EXISTS (
                SELECT 1
                  FROM users legacy_author
                 WHERE legacy_author.id=messages.author_id
                   AND legacy_author.company_id=%s
                   AND NOT EXISTS (
                       SELECT 1
                         FROM user_company_roles other_membership
                        WHERE other_membership.user_id=legacy_author.id
                          AND COALESCE(other_membership.active,TRUE)=TRUE
                          AND other_membership.company_id<>%s
                   )
            )
        )
    )
"""


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
                f"""SELECT id,company_id,chat_type,project_id,author_id,author_name,author_role,
                           text,photo_url,created_at,read_by
                      FROM messages
                     WHERE {_MESSAGE_COMPANY_SCOPE_SQL}
                      AND chat_type='company'
                    ORDER BY created_at ASC
                    LIMIT 200""",
                (company_id, company_id, company_id),
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
        payload = _require_company_chat_payload(data)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, company_id = resolve_context(cur, current_user, "create", x_company_id, x_company_mode)
            actor = effective_company_user(current_user, context)
            author_id = _positive_int(actor.get("id"))
            if not author_id:
                raise HTTPException(status_code=403, detail="Пользователь чата не определен")
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
                    str(payload.get("photoUrl") or ""),
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
                f"""UPDATE messages
                      SET read_by=COALESCE(read_by,'[]'::jsonb) || %s::jsonb
                    WHERE {_MESSAGE_COMPANY_SCOPE_SQL}
                      AND chat_type=%s
                      AND NOT COALESCE(read_by,'[]'::jsonb) @> %s::jsonb""",
                (read_by, company_id, company_id, company_id, "company", read_by),
            )
            updated = cur.rowcount
            conn.commit()
            return {"ok": True, "updated": updated}
        finally:
            cur.close()
            conn.close()
