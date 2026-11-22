"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Request

def register_tb_journal_module(app, deps):
    ModelGatewayError = deps['ModelGatewayError']
    PROJECT_DOCUMENT_ROLES = deps['PROJECT_DOCUMENT_ROLES']
    YANDEX_API_KEY = deps['YANDEX_API_KEY']
    YANDEX_FOLDER_ID = deps['YANDEX_FOLDER_ID']
    generate_yandex_text = deps['generate_yandex_text']
    get_current_user = deps['get_current_user']
    project_record_scope = deps['project_record_scope']
    router = APIRouter()

    @router.post("/tb-journal/ai-generate")
    def ai_generate_tb_instruction(data: dict, current_user: dict = Depends(get_current_user), request: Request = None):
        """AI генерирует текст инструктажа по ГОСТ 12.0.004-2015 для указанного типа работ."""
        instruction_type = data.get("instructionType", "Первичный инструктаж")
        work_context = data.get("workContext", "")
        with project_record_scope.transaction(current_user, request, PROJECT_DOCUMENT_ROLES) as (cur, actors):
            if len(actors) != 1:
                raise HTTPException(403, "Выберите компанию с доступом к объекту")
            parent = project_record_scope.parent(cur, actors[0], data, PROJECT_DOCUMENT_ROLES)
            project_name = parent["name"]

        user_text = (
            "Тип инструктажа: " + instruction_type + "\n"
            "Объект: " + project_name + "\n"
            "Контекст работ: " + (work_context or "общие строительно-монтажные работы") + "\n\n"
            "Сгенерируй текст инструктажа по охране труда по ГОСТ 12.0.004-2015. "
            "Включи: 1) программу (3-5 пунктов), 2) основные требования техники безопасности под этот тип работ, "
            "3) последовательность действий при ЧП. "
            "Используй официальный канцелярский русский. Объём 8-15 строк."
        )
        instructions = "Ты эксперт по охране труда в строительстве. Отвечай прямым связным текстом, без markdown."
        try:
            answer = generate_yandex_text(
                capability="tb_instruction",
                instructions=instructions,
                input_text=user_text,
                temperature=0.2,
                max_output_tokens=2000,
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
        except ModelGatewayError as error:
            raise HTTPException(status_code=502, detail="AI не ответил: " + error.code)
        return {"ok": True, "instructionText": answer.strip()}

    app.include_router(router)

