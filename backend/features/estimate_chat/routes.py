from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _actor_for_company(company_actors, company_id):
    normalized_company_id = _positive_int(company_id)
    for actor in company_actors or []:
        actor_company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        if actor_company_id == normalized_company_id:
            return actor
    raise HTTPException(status_code=404, detail="Смета не найдена")


def _row_id(row):
    if isinstance(row, dict):
        return _positive_int(row.get("id"))
    if isinstance(row, (list, tuple)) and row:
        return _positive_int(row[0])
    return None


def register_estimate_chat_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    estimate_visibility_filter = deps["estimate_visibility_filter"]
    resolve_estimate_parent = deps["resolve_estimate_parent"]
    project_document_roles = set(deps["project_document_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = tuple(deps["package_limit_roles"])
    active_only_roles = tuple(deps["active_only_roles"])
    customer_roles = tuple(deps["customer_roles"])
    package_optional_roles = tuple(deps["package_optional_roles"])
    worker_execution_roles = set(deps["worker_execution_roles"])
    clear_roles = set(deps["clear_roles"])
    generate_answer = deps["generate_answer"]

    def company_scope(cur, current_user, action_mode, x_company_id, x_company_mode):
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        company_actors = []
        for actor in effective_company_actors(current_user, company_context):
            normalized_role = str((actor or {}).get("role") or "").strip()
            if normalized_role not in project_document_roles:
                continue
            normalized_actor = dict(actor or {})
            normalized_actor["role"] = normalized_role
            company_actors.append(normalized_actor)
        visibility_sql, visibility_params = estimate_visibility_filter(
            company_actors,
            full_view_roles,
            package_limit_roles,
            active_only_roles,
            customer_roles,
            package_optional_roles,
            column_prefix="e",
        )
        return company_actors, visibility_sql, visibility_params

    def verified_parent(cur, current_user, estimate_id, action_mode, x_company_id, x_company_mode):
        company_actors, visibility_sql, visibility_params = company_scope(
            cur,
            current_user,
            action_mode,
            x_company_id,
            x_company_mode,
        )
        cur.execute(
            f"""SELECT e.id,e.company_id,e.project_id,e.project_name,
                        COALESCE(NULLIF(e.work_package,''),'Основная') AS work_package,
                        COALESCE(e.is_template,FALSE) AS is_template
                   FROM estimates e
                  WHERE e.id=%s AND {visibility_sql}""",
            (estimate_id, *visibility_params),
        )
        estimate_row = cur.fetchone()
        if not estimate_row:
            raise HTTPException(status_code=404, detail="Смета не найдена")
        actor = _actor_for_company(company_actors, estimate_row.get("company_id"))
        resolve_estimate_parent(
            cur,
            actor,
            estimate_id,
            for_update=action_mode == "write",
            allow_template=True,
            allow_unbound=True,
        )
        return actor

    def require_chat_actor(actor):
        if str((actor or {}).get("role") or "").strip() in worker_execution_roles:
            raise HTTPException(status_code=403, detail="Исполнители не имеют доступа к чату сметы")
        return actor

    @app.get("/estimates/{estimate_id}/chat-history")
    def get_estimate_chat(
        estimate_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = verified_parent(
                cur,
                current_user,
                estimate_id,
                "read",
                x_company_id,
                x_company_mode,
            )
            require_chat_actor(actor)
            cur.execute(
                """SELECT id,role,content,created_at
                     FROM estimate_chat_messages
                    WHERE estimate_id=%s
                    ORDER BY id ASC""",
                (estimate_id,),
            )
            return [
                {
                    "id": row.get("id"),
                    "role": row.get("role"),
                    "content": row.get("content"),
                    "createdAt": str(row.get("created_at") or ""),
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/estimate-chat")
    def estimate_chat(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        estimate_id = _positive_int((data or {}).get("estimateId"))
        user_message = str((data or {}).get("message") or "").strip()
        context = str((data or {}).get("context") or "").strip()
        history = (data or {}).get("history") or []
        if not estimate_id or not user_message:
            raise HTTPException(status_code=400, detail="estimateId and message required")
        if not isinstance(history, list):
            history = []

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = verified_parent(
                cur,
                current_user,
                estimate_id,
                "write",
                x_company_id,
                x_company_mode,
            )
            require_chat_actor(actor)
            cur.execute(
                """INSERT INTO estimate_chat_messages (estimate_id,role,content)
                   VALUES (%s,%s,%s) RETURNING id,created_at""",
                (estimate_id, "user", user_message),
            )
            user_row = cur.fetchone()
            user_message_id = _row_id(user_row)
            conn.commit()

            prompt_lines = []
            if context:
                prompt_lines.append("КОНТЕКСТ СМЕТЫ:\n" + context)
            if history:
                prompt_lines.append("\nПРЕДЫДУЩИЙ ДИАЛОГ:")
                for message in history[-20:]:
                    if not isinstance(message, dict):
                        continue
                    role = str(message.get("role") or "user")
                    content = str(message.get("content") or "")
                    prompt_lines.append(("Пользователь: " if role == "user" else "Ассистент: ") + content)
            prompt_lines.append("\nНОВЫЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n" + user_message)
            prompt_lines.append(
                "\nОтветь по-русски, используя факты из контекста сметы. "
                "Если для ответа недостаточно данных — скажи об этом. "
                "Если вопрос требует расчёта — приведи цифры явно."
            )
            instructions = (
                "Ты эксперт по строительным сметам. Помогаешь анализировать конкретную смету "
                "в формате диалога. Отвечаешь только по данной смете, не выдумываешь позиции. "
                "Используй конкретные числа из контекста."
            )
            answer = str(generate_answer("\n".join(prompt_lines), instructions) or "")

            actor = verified_parent(
                cur,
                current_user,
                estimate_id,
                "write",
                x_company_id,
                x_company_mode,
            )
            require_chat_actor(actor)
            cur.execute(
                """SELECT id
                     FROM estimate_chat_messages
                    WHERE id=%s AND estimate_id=%s AND role=%s
                    FOR UPDATE""",
                (user_message_id, estimate_id, "user"),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="История чата была очищена во время подготовки ответа",
                )

            cur.execute(
                """INSERT INTO estimate_chat_messages (estimate_id,role,content)
                   VALUES (%s,%s,%s) RETURNING id,created_at""",
                (estimate_id, "assistant", answer),
            )
            assistant_row = cur.fetchone()
            conn.commit()
            return {
                "response": answer,
                "userMessageId": user_message_id,
                "assistantMessageId": _row_id(assistant_row),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/estimates/{estimate_id}/chat-history")
    def clear_estimate_chat(
        estimate_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = verified_parent(
                cur,
                current_user,
                estimate_id,
                "write",
                x_company_id,
                x_company_mode,
            )
            if str((actor or {}).get("role") or "").strip() not in clear_roles:
                raise HTTPException(status_code=403, detail="Роль в выбранной компании не может очищать чат сметы")
            cur.execute("DELETE FROM estimate_chat_messages WHERE estimate_id=%s", (estimate_id,))
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
