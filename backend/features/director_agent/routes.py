"""Routes moved verbatim from backend/main.py."""

import json
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import psycopg2

def register_director_agent_module(app, deps):
    ModelGatewayError = deps['ModelGatewayError']
    SHARED_DIRECTOR_AGENT_TOOLS = deps['SHARED_DIRECTOR_AGENT_TOOLS']
    YANDEX_API_KEY = deps['YANDEX_API_KEY']
    YANDEX_FOLDER_ID = deps['YANDEX_FOLDER_ID']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    generate_yandex_text = deps['generate_yandex_text']
    get_db = deps['get_db']
    log_audit = deps['log_audit']
    require_roles = deps['require_roles']
    # Keep the HTTP assistant and the background runner on one immutable read path.
    router = APIRouter()

    DIRECTOR_AGENT_ROLES = ("директор", "system_owner")

    DIRECTOR_AGENT_MAX_STEPS = 4

    DIRECTOR_AGENT_TOOLS = SHARED_DIRECTOR_AGENT_TOOLS

    def _director_agent_extract_json(text: str):
        t = (text or "").strip()
        if "```" in t:
            parts = t.split("```")
            if len(parts) >= 3:
                t = parts[1].replace("json", "", 1).strip()
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            t = t[start:end + 1]
        return json.loads(t)

    def _director_agent_call_yandex(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1600):
        if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
            raise HTTPException(status_code=503, detail="YANDEX_API_KEY / YANDEX_FOLDER_ID не настроены")
        system_parts = []
        conversation = []
        role_labels = {
            "user": "ПОЛЬЗОВАТЕЛЬ",
            "assistant": "АССИСТЕНТ",
        }
        for message in messages or []:
            role = str((message or {}).get("role") or "user")
            text = str((message or {}).get("text") or "")
            if role == "system":
                system_parts.append(text)
            else:
                conversation.append(role_labels.get(role, "ПОЛЬЗОВАТЕЛЬ") + ":\n" + text)
        try:
            return generate_yandex_text(
                capability="director_agent",
                instructions="\n\n".join(system_parts) or "Отвечай по-русски.",
                input_text="\n\n".join(conversation) or "Продолжи диалог.",
                temperature=temperature,
                max_output_tokens=max_tokens,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
        except ModelGatewayError as error:
            raise HTTPException(
                status_code=502,
                detail="YandexGPT не ответил: " + error.code,
            )

    @router.get("/director-agent/tools")
    def director_agent_tools(_current_user: dict = Depends(require_roles(*DIRECTOR_AGENT_ROLES))):
        return [{"name": k, "desc": v["desc"]} for k, v in DIRECTOR_AGENT_TOOLS.items()]

    @router.post("/director-agent/ask")
    def director_agent_ask(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(require_roles(*DIRECTOR_AGENT_ROLES)),
    ):
        question = str((data or {}).get("question") or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="Пустой вопрос")
        if len(question) > 1000:
            raise HTTPException(status_code=400, detail="Вопрос слишком длинный")
        context_conn = get_db()
        context_cur = context_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = _resolve_work_company_context(
                context_cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            request_company_ids = company_context.get("companyIds") or []
        finally:
            context_cur.close()
            context_conn.close()
        tools_desc = "\n".join([f"- {name}: {meta['desc']}" for name, meta in DIRECTOR_AGENT_TOOLS.items()])
        system = (
            "Ты — директорский помощник ERP СтройКа. Отвечай по-русски, кратко и управленчески.\n"
            "Ты ничего не меняешь в системе. Ты можешь только попросить данные через инструменты чтения.\n"
            "Данные могут быть неполными: если информации не хватает, прямо скажи что нужно уточнить.\n"
            "Инструменты:\n" + tools_desc + "\n\n"
            "Чтобы получить данные, ответь строго JSON без лишнего текста:\n"
            '{"tool":"имя_инструмента","args":{}}\n'
            "Когда данных достаточно, ответь строго JSON:\n"
            '{"tool":"answer","text":"ответ директору"}\n'
            "Не выдумывай суммы, объёмы, людей и сроки."
        )
        messages = [
            {"role": "system", "text": system},
            {"role": "user", "text": question},
        ]
        steps = []
        for _ in range(DIRECTOR_AGENT_MAX_STEPS):
            reply = _director_agent_call_yandex(messages, temperature=0.15)
            try:
                parsed = _director_agent_extract_json(reply)
            except Exception:
                log_audit(
                    user_id=current_user.get("id"),
                    user_name=current_user.get("name", ""),
                    user_role=current_user.get("role", ""),
                    action="director_agent_ask",
                    entity_type="director_agent",
                    description="Вопрос директорскому агенту: " + question[:180],
                )
                return {"answer": reply, "steps": steps, "model": "yandexgpt-lite"}
            tool = parsed.get("tool") or ""
            if tool == "answer":
                log_audit(
                    user_id=current_user.get("id"),
                    user_name=current_user.get("name", ""),
                    user_role=current_user.get("role", ""),
                    action="director_agent_ask",
                    entity_type="director_agent",
                    description="Вопрос директорскому агенту: " + question[:180],
                )
                return {"answer": parsed.get("text") or "", "steps": steps, "model": "yandexgpt-lite"}
            if tool not in DIRECTOR_AGENT_TOOLS:
                return {"answer": "Неизвестный инструмент: " + str(tool), "steps": steps, "model": "yandexgpt-lite"}
            args = parsed.get("args") or {}
            try:
                result = DIRECTOR_AGENT_TOOLS[tool]["fn"](args, request_company_ids)
            except Exception as e:
                result = {"error": str(e)}
            steps.append({"tool": tool, "args": args})
            messages.append({"role": "assistant", "text": json.dumps(parsed, ensure_ascii=False)})
            messages.append({
                "role": "user",
                "text": "Результат инструмента " + tool + ": " + json.dumps(result, ensure_ascii=False, default=str)[:12000],
            })
        messages.append({"role": "user", "text": "Дай финальный ответ директору на основе уже полученных данных обычным текстом."})
        reply = _director_agent_call_yandex(messages, temperature=0.25)
        log_audit(
            user_id=current_user.get("id"),
            user_name=current_user.get("name", ""),
            user_role=current_user.get("role", ""),
            action="director_agent_ask",
            entity_type="director_agent",
            description="Вопрос директорскому агенту: " + question[:180],
        )
        return {"answer": reply or "Не удалось получить ответ", "steps": steps, "model": "yandexgpt-lite"}

    app.include_router(router)

