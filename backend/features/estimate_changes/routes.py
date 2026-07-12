import copy
import json
import re
import time
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _optional_id(data, key, label):
    value = (data or {}).get(key)
    if value in (None, ""):
        return None
    raw_value = str(value).strip() if not isinstance(value, bool) else ""
    if not re.fullmatch(r"[1-9][0-9]*", raw_value):
        raise HTTPException(status_code=400, detail=label + " должен быть положительным целым числом")
    return int(raw_value)


def _row_id(row):
    if isinstance(row, dict):
        return _positive_int(row.get("id"))
    if isinstance(row, (list, tuple)) and row:
        return _positive_int(row[0])
    return None


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _change_ids(data):
    values = (data or {}).get("changeIds") or (data or {}).get("change_ids") or []
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail="changeIds должен быть массивом идентификаторов")
    result = []
    for value in values:
        raw_value = str(value).strip() if not isinstance(value, bool) else ""
        if not re.fullmatch(r"[1-9][0-9]*", raw_value):
            raise HTTPException(status_code=400, detail="changeIds содержит некорректный идентификатор")
        normalized = int(raw_value)
        if normalized not in result:
            result.append(normalized)
    return result


def _number(value):
    return float(value or 0)


def _assert_same_project(estimate, project, label):
    estimate_company_id = _positive_int((estimate or {}).get("companyId") or (estimate or {}).get("company_id"))
    estimate_project_id = _positive_int((estimate or {}).get("projectId") or (estimate or {}).get("project_id"))
    project_company_id = _positive_int((project or {}).get("companyId") or (project or {}).get("company_id"))
    project_id = _positive_int((project or {}).get("id"))
    if estimate_company_id != project_company_id or estimate_project_id != project_id:
        raise HTTPException(status_code=409, detail=label + " относится к другому объекту")


def register_estimate_changes_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_project_write_actor = deps["require_project_write_actor"]
    require_project_row_company = deps["require_project_row_company"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_parent_access = deps["require_project_parent_access"]
    resolve_estimate_parent = deps["resolve_estimate_parent"]
    has_package_access = deps["has_package_access"]
    visibility_filter = deps["visibility_filter"]
    project_document_roles = {str(role or "").strip() for role in deps["project_document_roles"]}
    journal_write_roles = tuple(deps["journal_write_roles"])
    project_write_roles = tuple(deps["project_write_roles"])
    full_view_roles = tuple(deps["full_view_roles"])
    package_limit_roles = set(deps["package_limit_roles"])
    package_unrestricted_roles = tuple(deps["package_unrestricted_roles"])
    customer_roles = tuple(deps["customer_roles"])
    customer_statuses = tuple(deps["customer_statuses"])
    worker_execution_roles = set(deps["worker_execution_roles"])
    approved_statuses = set(deps["approved_statuses"])
    leadership_roles = tuple(deps["leadership_roles"])
    estimate_write_roles = tuple(deps["estimate_write_roles"])
    log_audit = deps["log_audit"]
    yandex_api_key = deps.get("yandex_api_key")
    yandex_folder_id = deps.get("yandex_folder_id")

    def estimate_mutation_scope(
        cur,
        current_user,
        estimate_id,
        allowed_roles,
        action_mode,
        x_company_id,
        x_company_mode,
    ):
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actor = require_project_write_actor(
            effective_company_actors(current_user, company_context),
            allowed_roles,
        )
        estimate = resolve_estimate_parent(cur, actor, estimate_id, for_update=True)
        project = resolve_project_parent(
            cur,
            actor,
            project_id=estimate.get("projectId"),
            project_name=estimate.get("projectName"),
            for_update=True,
        )
        require_project_parent_access(cur, actor, project, full_view_roles)
        _assert_same_project(estimate, project, "Смета")
        return actor, estimate, project

    def load_estimate_for_change(cur, estimate, *, include_sections):
        columns = (
            "id,company_id,project_id,project_name,name,version,sections_json,"
            "COALESCE(smeta_type,'Заказчик') AS smeta_type,"
            "COALESCE(NULLIF(work_package,''),'Основная') AS work_package,status"
            if include_sections
            else
            "id,company_id,project_id,project_name,"
            "COALESCE(smeta_type,'Заказчик') AS smeta_type,"
            "COALESCE(NULLIF(work_package,''),'Основная') AS work_package,status"
        )
        cur.execute(
            "SELECT " + columns + " FROM estimates "
            "WHERE id=%s AND company_id=%s AND project_id=%s FOR UPDATE",
            (estimate["id"], estimate["companyId"], estimate["projectId"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Смета изменилась во время проверки владельца")
        return row

    def load_changes_for_estimate(
        cur,
        *,
        company_id,
        project_id,
        estimate_id,
        selected_ids,
        include_payload,
    ):
        columns = (
            "id,company_id,project_id,description,unit,quantity,price,total,change_type,estimate_id,"
            "section_name,estimate_item_name,base_quantity,new_required_quantity,delta_quantity,reason,"
            "status,included_in_estimate_id"
            if include_payload
            else "id,company_id,project_id,status,included_in_estimate_id"
        )
        if selected_ids:
            cur.execute(
                "SELECT " + columns + " FROM unexpected_works "
                "WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                (selected_ids,),
            )
            rows = cur.fetchall() or []
            found_ids = {_positive_int(_row_value(row, "id", 0)) for row in rows}
            if found_ids != set(selected_ids):
                raise HTTPException(status_code=404, detail="Одно или несколько изменений не найдены")
            for row in rows:
                if (
                    _positive_int(_row_value(row, "company_id", 1)) != company_id
                    or _positive_int(_row_value(row, "project_id", 2)) != project_id
                ):
                    raise HTTPException(status_code=403, detail="Изменение относится к другой компании или объекту")
            eligible_ids = []
            for row in rows:
                change_id = _positive_int(_row_value(row, "id", 0))
                status_index = 16 if include_payload else 3
                included_index = 17 if include_payload else 4
                if (
                    str(_row_value(row, "status", status_index) or "") not in approved_statuses
                    or _row_value(row, "included_in_estimate_id", included_index) is not None
                ):
                    raise HTTPException(status_code=409, detail="Изменение уже включено или не утверждено")
                eligible_ids.append(change_id)
            return rows, eligible_ids

        cur.execute(
            "SELECT " + columns + " FROM unexpected_works "
            "WHERE company_id=%s AND project_id=%s "
            "AND status = ANY(%s) AND included_in_estimate_id IS NULL "
            "AND (estimate_id=%s OR estimate_id IS NULL) ORDER BY id FOR UPDATE",
            (company_id, project_id, sorted(approved_statuses), estimate_id),
        )
        rows = cur.fetchall() or []
        return rows, [_positive_int(_row_value(row, "id", 0)) for row in rows]

    def mutation_scope(cur, current_user, record_id, action_mode, x_company_id, x_company_mode):
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        actor = require_project_write_actor(
            effective_company_actors(current_user, company_context),
            project_write_roles,
        )
        cur.execute(
            """SELECT id,company_id,project_id,project_name,status,description,unit,quantity,
                      added_by,change_type
                 FROM unexpected_works
                WHERE id=%s
                FOR UPDATE""",
            (record_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        stored_company_id = _positive_int(row.get("company_id"))
        stored_project_id = _positive_int(row.get("project_id"))
        if not stored_company_id or not stored_project_id:
            raise HTTPException(status_code=409, detail="Владелец изменения к смете не определён")
        require_project_row_company(actor, stored_company_id)

        project = resolve_project_parent(
            cur,
            actor,
            project_id=stored_project_id,
            project_name=str(row.get("project_name") or "").strip(),
            for_update=True,
        )
        require_project_parent_access(cur, actor, project, full_view_roles)
        if (
            _positive_int(project.get("companyId") or project.get("company_id")) != stored_company_id
            or _positive_int(project.get("id")) != stored_project_id
        ):
            raise HTTPException(status_code=409, detail="Владелец изменения не совпадает с объектом")
        return actor, project, row

    def read_scope(cur, current_user, x_company_id, x_company_mode):
        company_context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        company_actors = []
        for actor in effective_company_actors(current_user, company_context):
            company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
            role = str((actor or {}).get("role") or "").strip()
            if not company_id or role not in project_document_roles:
                continue
            normalized_actor = dict(actor or {})
            normalized_actor["companyId"] = company_id
            normalized_actor["company_id"] = company_id
            normalized_actor["role"] = role
            company_actors.append(normalized_actor)
        visibility_sql, visibility_params = visibility_filter(
            company_actors,
            project_document_roles,
            full_view_roles,
            package_limit_roles,
            package_unrestricted_roles,
            customer_roles,
            customer_statuses,
            project_prefix="p",
            change_prefix="uw",
        )
        return company_actors, visibility_sql, visibility_params

    @app.get("/unexpected-works")
    def get_unexpected_works(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_actors, visibility_sql, visibility_params = read_scope(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
            )
            cur.execute(
                f"""SELECT uw.id,uw.project_name,uw.description,uw.unit,uw.quantity,uw.price,
                            uw.total,uw.added_by,uw.added_by_role,uw.status,uw.approved_by,
                            uw.approved_at,uw.notes,uw.photo_url,uw.change_type,uw.estimate_id,
                            uw.section_name,uw.estimate_item_name,uw.base_quantity,
                            uw.new_required_quantity,uw.delta_quantity,uw.included_in_estimate_id,
                            uw.reason,uw.company_id
                       FROM unexpected_works uw
                       JOIN projects p ON p.id=uw.project_id AND p.company_id=uw.company_id
                      WHERE {visibility_sql}
                      ORDER BY uw.id DESC""",
                tuple(visibility_params),
            )
            actors_by_company = {
                _positive_int(actor.get("companyId") or actor.get("company_id")): actor
                for actor in company_actors
            }
            result = []
            for row in cur.fetchall() or []:
                actor = actors_by_company.get(_positive_int(row.get("company_id")))
                if not actor:
                    continue
                hide_money = actor.get("role") in worker_execution_roles
                result.append({
                    "id": row.get("id"),
                    "projectName": row.get("project_name"),
                    "description": row.get("description"),
                    "unit": row.get("unit"),
                    "quantity": _number(row.get("quantity")),
                    "price": 0 if hide_money else _number(row.get("price")),
                    "total": 0 if hide_money else _number(row.get("total")),
                    "addedBy": row.get("added_by"),
                    "addedByRole": row.get("added_by_role"),
                    "status": row.get("status"),
                    "approvedBy": row.get("approved_by"),
                    "approvedAt": row.get("approved_at"),
                    "notes": row.get("notes"),
                    "photoUrl": row.get("photo_url"),
                    "changeType": row.get("change_type") or "Работа вне сметы",
                    "estimateId": row.get("estimate_id"),
                    "sectionName": row.get("section_name") or "",
                    "estimateItemName": row.get("estimate_item_name") or "",
                    "baseQuantity": _number(row.get("base_quantity")),
                    "newRequiredQuantity": _number(row.get("new_required_quantity")),
                    "deltaQuantity": _number(row.get("delta_quantity")),
                    "includedInEstimateId": row.get("included_in_estimate_id"),
                    "reason": row.get("reason") or "",
                })
            return result
        finally:
            cur.close()
            conn.close()

    @app.post("/unexpected-works/{id}/ai-estimate")
    def ai_estimate_unexpected_work(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        """Estimate one visible change only after its stored tenant owner is verified."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _actors, visibility_sql, visibility_params = read_scope(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
            )
            cur.execute(
                f"""SELECT uw.description,uw.unit,uw.quantity
                       FROM unexpected_works uw
                       JOIN projects p ON p.id=uw.project_id AND p.company_id=uw.company_id
                      WHERE uw.id=%s AND {visibility_sql}""",
                (id, *visibility_params),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="запись не найдена")
            description = str(row.get("description") or "")
            unit = str(row.get("unit") or "")
            quantity = _number(row.get("quantity"))
            keyword_parts = description.lower().split()
            keyword = keyword_parts[0][:5] if keyword_parts else ""
            cur.execute(
                """SELECT name,unit,price FROM pricelist_items
                    WHERE LOWER(name) LIKE %s LIMIT 10""",
                ("%" + keyword + "%",),
            )
            similar = cur.fetchall() or []
        finally:
            cur.close()
            conn.close()

        import openai as oa

        similar_lines = [
            str(item.get("name") or "")
            + " · "
            + str(item.get("unit") or "")
            + " · "
            + str(item.get("price") or 0)
            + " ₽/"
            + str(item.get("unit") or "шт")
            for item in similar
        ]
        user_text = (
            "Описание работы: " + description + "\n"
            "Единица: " + unit + "\n"
            "Объём: " + str(quantity) + "\n\n"
            "Похожие позиции из прайсов (для ориентира):\n"
            + ("\n".join(similar_lines) if similar_lines else "(нет данных)")
            + "\n\n"
            "Верни СТРОГО JSON: {\"pricePerUnit\": число, \"justification\": \"строка\"}\n"
            "pricePerUnit — оценочная цена за единицу в рублях для строительных работ в России в 2026 году.\n"
            "justification — 1-2 строки обоснования."
        )
        instructions = "Ты эксперт по строительной смете. Отвечай СТРОГО JSON без markdown."
        client = oa.OpenAI(
            api_key=yandex_api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=yandex_folder_id,
        )

        def call(model_id):
            try:
                response = client.responses.create(
                    model="gpt://" + str(yandex_folder_id or "") + "/" + model_id,
                    temperature=0.2,
                    instructions=instructions,
                    input=user_text,
                    max_output_tokens=800,
                )
                return response.output_text or "", None
            except Exception as exc:
                return "", str(exc)

        answer, error = call("qwen3.6-35b-a3b/latest")
        if not answer.strip():
            answer, error = call("yandexgpt-5.1/latest")
        if not answer.strip():
            raise HTTPException(status_code=502, detail="AI вернул пустой ответ: " + str(error))
        match = re.search(r"\{.*\}", answer.strip(), re.DOTALL)
        raw_json = match.group(0) if match else answer.strip()
        try:
            parsed = json.loads(raw_json)
        except Exception:
            raise HTTPException(status_code=502, detail="AI вернул невалидный JSON")
        price = _number(parsed.get("pricePerUnit"))
        return {
            "ok": True,
            "pricePerUnit": price,
            "estimatedTotal": round(price * quantity, 2),
            "justification": str(parsed.get("justification") or "").strip(),
            "similar": similar_lines,
        }

    @app.get("/unexpected-works/limit-check")
    def check_unexpected_limit(
        project_name: str,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        """Calculate the project change limit inside one verified company owner."""
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_actors, _visibility_sql, _visibility_params = read_scope(
                cur,
                current_user,
                x_company_id,
                x_company_mode,
            )
            if len(company_actors) != 1:
                raise HTTPException(
                    status_code=409,
                    detail="Для проверки лимита выберите одну компанию",
                )
            actor = company_actors[0]
            project = resolve_project_parent(
                cur,
                actor,
                project_name=str(project_name or "").strip(),
            )
            require_project_parent_access(cur, actor, project, full_view_roles)
            company_id = _positive_int(project.get("companyId") or project.get("company_id"))
            project_id = _positive_int(project.get("id"))
            canonical_name = str(project.get("name") or "").strip()
            if not company_id or not project_id or not canonical_name:
                raise HTTPException(status_code=409, detail="Объект не имеет точного владельца")
            cur.execute(
                "SELECT budget FROM projects WHERE id=%s AND company_id=%s",
                (project_id, company_id),
            )
            budget_row = cur.fetchone()
            if not budget_row:
                raise HTTPException(status_code=404, detail="проект не найден")
            budget = _number(budget_row.get("budget"))
            cur.execute(
                """SELECT COALESCE(SUM(total),0) AS total
                     FROM unexpected_works
                    WHERE company_id=%s AND project_id=%s
                      AND status = ANY(%s)
                      AND COALESCE(change_type,'') <> %s
                      AND included_in_estimate_id IS NULL""",
                (company_id, project_id, sorted(approved_statuses), "Исключение объёма"),
            )
            approved_sum = _number((cur.fetchone() or {}).get("total"))
            cur.execute(
                """SELECT COALESCE(SUM(total),0) AS total
                     FROM unexpected_works
                    WHERE company_id=%s AND project_id=%s
                      AND status='Ожидает согласования'
                      AND COALESCE(change_type,'') <> %s""",
                (company_id, project_id, "Исключение объёма"),
            )
            pending_sum = _number((cur.fetchone() or {}).get("total"))
        finally:
            cur.close()
            conn.close()

        limit_pct = 10.0
        percent = approved_sum / budget * 100 if budget > 0 else 0
        over_limit = percent > limit_pct
        return {
            "projectName": canonical_name,
            "budget": budget,
            "approvedSum": approved_sum,
            "pendingSum": pending_sum,
            "percentOfBudget": round(percent, 2),
            "limitPct": limit_pct,
            "overLimit": over_limit,
            "warning": (
                "Утверждённые изменения к смете превысили "
                + str(limit_pct)
                + "% от бюджета — стоит оформить доп.соглашение или новую редакцию сметы"
                if over_limit
                else None
            ),
        }

    @app.post("/unexpected-works")
    def create_unexpected_work(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = data or {}
        project_name = str(payload.get("projectName") or "").strip()
        project_id_claim = _optional_id(payload, "projectId", "projectId")
        estimate_id = _optional_id(payload, "estimateId", "estimateId")
        included_estimate_id = _optional_id(
            payload,
            "includedInEstimateId",
            "includedInEstimateId",
        )
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "create",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            actor = require_project_write_actor(
                effective_company_actors(current_user, company_context),
                journal_write_roles,
            )
            project = resolve_project_parent(
                cur,
                actor,
                project_id=project_id_claim,
                project_name=project_name,
            )
            require_project_parent_access(cur, actor, project, full_view_roles)

            company_id = _positive_int(project.get("companyId") or project.get("company_id"))
            project_id = _positive_int(project.get("id"))
            canonical_project_name = str(project.get("name") or "").strip()
            if not company_id or not project_id or not canonical_project_name:
                raise HTTPException(status_code=409, detail="Объект не имеет точного владельца")

            if estimate_id:
                estimate = resolve_estimate_parent(cur, actor, estimate_id)
                _assert_same_project(estimate, project, "Смета")
            if included_estimate_id:
                included_estimate = resolve_estimate_parent(cur, actor, included_estimate_id)
                _assert_same_project(included_estimate, project, "Смета включения")

            role = str(actor.get("role") or "").strip()
            section_name = str(
                payload.get("sectionName") or payload.get("workPackage") or "Основная"
            ).strip() or "Основная"
            if role in package_limit_roles and not has_package_access(actor, section_name):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ: " + section_name)

            price = float(payload.get("price", 0) or 0)
            total = float(payload.get("total", 0) or 0)
            status = payload.get("status", "Ожидает согласования")
            added_by = payload.get("addedBy", "") or actor.get("name", "")
            added_by_role = payload.get("addedByRole", "") or role
            if role in worker_execution_roles:
                price = 0
                total = 0
                status = "Ожидает согласования"
                added_by = actor.get("name", "")
                added_by_role = role

            cur.execute(
                """INSERT INTO unexpected_works
                       (project_name,project_id,company_id,description,unit,quantity,price,total,
                        added_by,added_by_role,status,notes,photo_url,change_type,estimate_id,
                        section_name,estimate_item_name,base_quantity,new_required_quantity,
                        delta_quantity,included_in_estimate_id,reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                (
                    canonical_project_name,
                    project_id,
                    company_id,
                    payload.get("description", ""),
                    payload.get("unit", "шт"),
                    float(payload.get("quantity", 0)),
                    price,
                    total,
                    added_by,
                    added_by_role,
                    status,
                    payload.get("notes", ""),
                    payload.get("photoUrl", ""),
                    payload.get("changeType") or "Работа вне сметы",
                    estimate_id,
                    section_name,
                    payload.get("estimateItemName", ""),
                    float(payload.get("baseQuantity") or 0),
                    float(payload.get("newRequiredQuantity") or 0),
                    float(payload.get("deltaQuantity") or 0),
                    included_estimate_id,
                    payload.get("reason", ""),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"id": _row_id(row), "ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/unexpected-works/{id}")
    def update_unexpected_work(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = data or {}
        included_estimate_id = _optional_id(
            payload,
            "includedInEstimateId",
            "includedInEstimateId",
        )
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        audit_payload = None
        response = None
        try:
            actor, project, row = mutation_scope(
                cur,
                current_user,
                id,
                "update",
                x_company_id,
                x_company_mode,
            )
            company_id = _positive_int(row.get("company_id"))
            project_id = _positive_int(row.get("project_id"))
            project_name = str(project.get("name") or "").strip()
            if included_estimate_id:
                included_estimate = resolve_estimate_parent(cur, actor, included_estimate_id)
                _assert_same_project(included_estimate, project, "Смета включения")

            old_status = str(row.get("status") or "")
            new_status = str(payload.get("status") or "")
            price = _number(payload.get("price"))
            total = _number(payload.get("total"))
            approved_by = str(actor.get("name") or payload.get("approvedBy") or "")
            approved_at = payload.get("approvedAt", "")
            cur.execute(
                """UPDATE unexpected_works SET
                       status=%s, price=%s, total=%s, approved_by=%s, approved_at=%s,
                       included_in_estimate_id=COALESCE(%s,included_in_estimate_id),
                       reason=COALESCE(%s,reason)
                     WHERE id=%s AND company_id=%s AND project_id=%s
                     RETURNING id""",
                (
                    new_status,
                    price,
                    total,
                    approved_by,
                    approved_at,
                    included_estimate_id,
                    payload.get("reason") if "reason" in payload else None,
                    id,
                    company_id,
                    project_id,
                ),
            )
            if not _row_id(cur.fetchone()):
                raise HTTPException(status_code=409, detail="Изменение изменилось во время проверки владельца")

            auto_journal_id = None
            should_create_journal = (
                new_status in approved_statuses
                and old_status not in approved_statuses
                and str(row.get("change_type") or "") != "Исключение объёма"
            )
            if should_create_journal:
                cur.execute("SELECT id FROM work_journal WHERE unexpected_work_id=%s LIMIT 1", (id,))
                existing = cur.fetchone()
                description = str(row.get("description") or "").strip()
                if not existing and description:
                    cur.execute("SAVEPOINT estimate_change_journal")
                    try:
                        from datetime import date

                        cur.execute(
                            """INSERT INTO work_journal
                               (company_id,master_id,master_name,project,description,unit,quantity,
                                price_per_unit,total,date,status,comment,unexpected_work_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               RETURNING id""",
                            (
                                company_id,
                                None,
                                row.get("added_by") or "(изменение к смете)",
                                project_name,
                                description,
                                row.get("unit") or "шт",
                                _number(row.get("quantity")),
                                price,
                                total,
                                date.today().isoformat(),
                                "На проверке",
                                "Авто-запись по утверждённому изменению к смете №"
                                + str(id)
                                + " ("
                                + str(row.get("change_type") or "Работа вне сметы")
                                + ")",
                                id,
                            ),
                        )
                        auto_journal_id = _row_id(cur.fetchone())
                        cur.execute("RELEASE SAVEPOINT estimate_change_journal")
                    except Exception as error:
                        cur.execute("ROLLBACK TO SAVEPOINT estimate_change_journal")
                        cur.execute("RELEASE SAVEPOINT estimate_change_journal")
                        print("UNEXPECTED→JOURNAL ERROR:", str(error))

            conn.commit()
            if new_status != old_status:
                audit_payload = {
                    "user_name": actor.get("name") or "—",
                    "user_role": actor.get("role") or "—",
                    "action": "status_change",
                    "entity_type": "unexpected_work",
                    "entity_id": id,
                    "description": "Статус: "
                    + (old_status or "—")
                    + " → "
                    + new_status
                    + ", сумма: "
                    + str(total)
                    + " ₽",
                    "project_name": project_name,
                }
            response = {"ok": True, "journalId": auto_journal_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        if audit_payload:
            log_audit(**audit_payload)
        return response

    @app.delete("/unexpected-works/{id}")
    def delete_unexpected_work(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _actor, _project, row = mutation_scope(
                cur,
                current_user,
                id,
                "delete",
                x_company_id,
                x_company_mode,
            )
            company_id = _positive_int(row.get("company_id"))
            project_id = _positive_int(row.get("project_id"))
            cur.execute(
                """UPDATE unexpected_works
                      SET status='Аннулировано'
                    WHERE id=%s AND company_id=%s AND project_id=%s
                    RETURNING id""",
                (id, company_id, project_id),
            )
            if not _row_id(cur.fetchone()):
                raise HTTPException(status_code=409, detail="Изменение изменилось во время проверки владельца")
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/estimates/{id}/include-changes")
    def include_estimate_changes(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = data or {}
        selected_ids = _change_ids(payload)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, estimate, project = estimate_mutation_scope(
                cur,
                current_user,
                id,
                leadership_roles,
                "update",
                x_company_id,
                x_company_mode,
            )
            company_id = _positive_int(estimate.get("companyId"))
            project_id = _positive_int(estimate.get("projectId"))
            estimate_row = load_estimate_for_change(cur, estimate, include_sections=True)
            project_name = str(estimate.get("projectName") or project.get("name") or "").strip()
            name = str(estimate_row.get("name") or "Смета")
            version = str(estimate_row.get("version") or "1.0")
            smeta_type = str(estimate_row.get("smeta_type") or "Заказчик")
            work_package = str(estimate_row.get("work_package") or "Основная")
            sections_value = estimate_row.get("sections_json")
            try:
                sections = sections_value if isinstance(sections_value, list) else json.loads(sections_value or "[]")
            except Exception:
                sections = []
            sections = copy.deepcopy(sections if isinstance(sections, list) else [])

            changes, eligible_ids = load_changes_for_estimate(
                cur,
                company_id=company_id,
                project_id=project_id,
                estimate_id=id,
                selected_ids=selected_ids,
                include_payload=True,
            )
            if not changes:
                raise HTTPException(status_code=400, detail="Нет утверждённых изменений для включения")

            def normalize(value):
                return re.sub(
                    r"[^a-zа-я0-9]+",
                    " ",
                    str(value or "").lower().replace("ё", "е"),
                ).strip()

            def find_item(section_name, item_name):
                section_key = normalize(section_name)
                item_key = normalize(item_name)
                fallback = None
                for section in sections:
                    section_matches = normalize(section.get("name")) == section_key if section_key else True
                    for item in section.get("items") or []:
                        if normalize(item.get("name")) != item_key:
                            continue
                        if section_matches:
                            return section, item
                        fallback = fallback or (section, item)
                return fallback

            def changes_section():
                for section in sections:
                    if normalize(section.get("name")) == normalize("Изменения к смете"):
                        return section
                section = {
                    "id": int(time.time() * 1000),
                    "name": "Изменения к смете",
                    "items": [],
                }
                sections.append(section)
                return section

            not_applied = []
            applied_ids = []
            for index, change in enumerate(changes):
                change_id = _positive_int(change.get("id"))
                description = change.get("description")
                unit = change.get("unit")
                quantity = _number(change.get("delta_quantity")) or _number(change.get("quantity"))
                price = _number(change.get("price"))
                change_type = str(change.get("change_type") or "Работа вне сметы")
                section_name = change.get("section_name")
                item_name = change.get("estimate_item_name")
                target = find_item(section_name, item_name or description) if item_name or description else None
                if change_type in ("Дополнительный объём к строке сметы", "Исключение объёма") and target:
                    _section, item = target
                    old_quantity = _number(item.get("quantity"))
                    required = _number(change.get("new_required_quantity"))
                    if required <= 0:
                        required = (
                            old_quantity + quantity
                            if change_type == "Дополнительный объём к строке сметы"
                            else max(0, old_quantity - quantity)
                        )
                    item["quantity"] = required
                    if _number(item.get("doneQuantity")) > required:
                        item["doneQuantity"] = required
                    if price > 0:
                        if _number(item.get("priceWork")) > 0 or not _number(item.get("priceMaterial")):
                            item["priceWork"] = price
                        else:
                            item["priceMaterial"] = price
                    item["sourceUnexpectedWorkId"] = change_id
                    item["changeType"] = change_type
                    applied_ids.append(change_id)
                    continue
                if change_type == "Исключение объёма":
                    not_applied.append(description or item_name or str(change_id))
                    continue
                section = changes_section()
                section.setdefault("items", []).append({
                    "id": int(time.time() * 1000) + index + 1,
                    "itemType": "work",
                    "name": description or item_name or "Изменение к смете",
                    "unit": unit or "шт",
                    "quantity": quantity,
                    "priceWork": price,
                    "priceMaterial": 0,
                    "measurementBasis": "manual",
                    "sourceUnexpectedWorkId": change_id,
                    "changeType": change_type,
                    "reason": change.get("reason") or "",
                })
                applied_ids.append(change_id)

            if not_applied:
                raise HTTPException(
                    status_code=400,
                    detail="Не найдены строки для исключения объёма: " + ", ".join(not_applied[:5]),
                )
            if not applied_ids or set(applied_ids) != set(eligible_ids):
                raise HTTPException(status_code=409, detail="Не все выбранные изменения удалось применить")

            version_parts = version.split(".")
            try:
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                next_version = ".".join(version_parts)
            except Exception:
                next_version = version + "+1"
            new_version = str(payload.get("version") or next_version)
            new_name = str(payload.get("name") or name + " — ред. " + new_version)
            cur.execute(
                """UPDATE estimates SET status='Архив'
                     WHERE company_id=%s AND project_id=%s
                       AND COALESCE(smeta_type,'Заказчик')=%s
                       AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                       AND status='Активная'""",
                (company_id, project_id, smeta_type, work_package),
            )
            cur.execute(
                """INSERT INTO estimates
                   (company_id,project_id,project_name,name,version,sections_json,smeta_type,work_package,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Активная')
                   RETURNING id,created_at""",
                (
                    company_id,
                    project_id,
                    project_name,
                    new_name,
                    new_version,
                    json.dumps(sections, ensure_ascii=False),
                    smeta_type,
                    work_package,
                ),
            )
            created = cur.fetchone()
            new_id = _positive_int(_row_value(created, "id", 0))
            created_at = _row_value(created, "created_at", 1)
            if not new_id:
                raise HTTPException(status_code=409, detail="Новая версия сметы не создана")
            cur.execute(
                """UPDATE unexpected_works
                      SET status='Включено в новую смету',included_in_estimate_id=%s,
                          approved_by=COALESCE(NULLIF(approved_by,''),%s),
                          approved_at=COALESCE(approved_at,TO_CHAR(CURRENT_DATE,'YYYY-MM-DD'))
                    WHERE company_id=%s AND project_id=%s AND id = ANY(%s)
                      AND status = ANY(%s) AND included_in_estimate_id IS NULL
                    RETURNING id""",
                (
                    new_id,
                    str(actor.get("name") or ""),
                    company_id,
                    project_id,
                    applied_ids,
                    sorted(approved_statuses),
                ),
            )
            updated_ids = {_row_id(row) for row in (cur.fetchall() or [])}
            if updated_ids != set(applied_ids):
                raise HTTPException(status_code=409, detail="Изменения изменились во время включения в смету")
            conn.commit()
            return {
                "ok": True,
                "id": new_id,
                "includedChangeIds": applied_ids,
                "estimate": {
                    "id": new_id,
                    "projectId": project_id,
                    "projectName": project_name,
                    "name": new_name,
                    "version": new_version,
                    "sections": sections,
                    "smetaType": smeta_type,
                    "workPackage": work_package,
                    "status": "Активная",
                    "createdAt": str(created_at) if created_at else "",
                },
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/estimates/{id}/reconcile-changes")
    def reconcile_estimate_changes(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        payload = data or {}
        selected_ids = _change_ids(payload)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor, estimate, project = estimate_mutation_scope(
                cur,
                current_user,
                id,
                estimate_write_roles,
                "update",
                x_company_id,
                x_company_mode,
            )
            company_id = _positive_int(estimate.get("companyId"))
            project_id = _positive_int(estimate.get("projectId"))
            estimate_row = load_estimate_for_change(cur, estimate, include_sections=False)
            if (
                str(estimate_row.get("smeta_type") or "Заказчик") != "Заказчик"
                or str(estimate_row.get("status") or "Черновик") != "Активная"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Сверка изменений доступна только для активной сметы заказчика",
                )
            if not selected_ids:
                conn.commit()
                return {"ok": True, "includedChangeIds": []}
            _rows, allowed_ids = load_changes_for_estimate(
                cur,
                company_id=company_id,
                project_id=project_id,
                estimate_id=id,
                selected_ids=selected_ids,
                include_payload=False,
            )
            note = "Автоматически сопоставлено с новой сметой №" + str(id)
            cur.execute(
                """UPDATE unexpected_works
                      SET status='Включено в новую смету',included_in_estimate_id=%s,
                          approved_by=COALESCE(NULLIF(approved_by,''),%s),
                          approved_at=COALESCE(approved_at,TO_CHAR(CURRENT_DATE,'YYYY-MM-DD')),
                          reason=CASE
                            WHEN COALESCE(reason,'')='' THEN %s
                            WHEN reason LIKE %s THEN reason
                            ELSE reason || '; ' || %s
                          END
                    WHERE company_id=%s AND project_id=%s AND id = ANY(%s)
                      AND status = ANY(%s) AND included_in_estimate_id IS NULL
                    RETURNING id""",
                (
                    id,
                    str(actor.get("name") or ""),
                    note,
                    "%" + note + "%",
                    note,
                    company_id,
                    project_id,
                    allowed_ids,
                    sorted(approved_statuses),
                ),
            )
            updated_ids = {_row_id(row) for row in (cur.fetchall() or [])}
            if updated_ids != set(allowed_ids):
                raise HTTPException(status_code=409, detail="Изменения изменились во время сверки")
            conn.commit()
            return {"ok": True, "includedChangeIds": allowed_ids}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
