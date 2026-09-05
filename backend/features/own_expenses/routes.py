"""Own expense and Telegram webhook routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 29):
the own-expenses quartet plus the two Telegram bot webhooks keep
their URLs, role scopes, employee resolution, finance-expense mirror
sync and warehouse-intent protection. All cluster helpers moved
along as closures; shared services arrive through deps.
"""

import hmac
import math
from collections.abc import Mapping
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.config import TELEGRAM_BOT_API_TOKEN
except ModuleNotFoundError:
    from config import TELEGRAM_BOT_API_TOKEN


def register_own_expenses_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    require_roles = deps["require_roles"]
    own_expense_roles = tuple(deps.get("own_expense_roles") or ())
    own_expense_review_roles = tuple(deps.get("own_expense_review_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    leadership_roles = tuple(deps.get("leadership_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    warehouse_roles = tuple(deps.get("warehouse_roles") or ())
    own_expense_no_project_category = deps["own_expense_no_project_category"]
    require_project_access = deps["require_project_access"]
    user_project_names = deps["user_project_names"]
    safe_project_list = deps["safe_project_list"]
    safe_float = deps["safe_float"]
    supply_work_package = deps["supply_work_package"]
    create_warehouse_invoice_record = deps["create_warehouse_invoice_record"]

    def _positive_int(value):
        return value if type(value) is int and value > 0 else None

    def _positive_amount(value):
        if type(value) not in (int, float):
            return None
        if not math.isfinite(value) or value <= 0:
            return None
        return value

    def _row_value(row, key, index):
        if isinstance(row, Mapping):
            return row.get(key)
        if isinstance(row, (list, tuple)) and len(row) > index:
            return row[index]
        return None

    def _selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if (context or {}).get("mode") != "company":
            raise HTTPException(
                status_code=409,
                detail="Для личных трат выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания личной траты не определена")
        allowed_roles = {str(role or "").strip() for role in own_expense_roles}
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in allowed_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет работать с личными тратами",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для личных трат выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания личной траты не совпадает с выбранной компанией",
            )
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def _review_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        actor = _selected_actor(
            cur, current_user, action_mode, x_company_id, x_company_mode
        )
        if str(actor.get("role") or "").strip() not in finance_roles:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет согласовывать личные траты",
            )
        return actor

    def _actor_name(actor):
        return str(
            actor.get("name") or actor.get("email") or actor.get("id") or ""
        ).strip()

    def _exact_project(cur, company_id, project_id, *, lock=False):
        if project_id is None:
            return None
        if _positive_int(project_id) is None:
            raise HTTPException(status_code=400, detail="projectId invalid")
        cur.execute(
            """SELECT id,name
                 FROM public.projects
                WHERE id=%s AND company_id=%s
                LIMIT 2""" + (" FOR SHARE" if lock else ""),
            (project_id, company_id),
        )
        rows = list(cur.fetchall() or [])
        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Объект не найден в выбранной компании",
            )
        if len(rows) != 1:
            raise HTTPException(status_code=409, detail="Объект неоднозначен")
        project = {
            "id": _positive_int(_row_value(rows[0], "id", 0)),
            "name": str(_row_value(rows[0], "name", 1) or "").strip(),
        }
        if project["id"] is None or not project["name"]:
            raise HTTPException(status_code=409, detail="Владелец объекта не определён")
        return project

    def _exact_staff(cur, company_id, staff_id, *, lock=False):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="employeeId invalid")
        cur.execute(
            """SELECT id,name
                 FROM public.staff
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR SHARE" if lock else ""),
            (staff_id, company_id),
        )
        row = cur.fetchone()
        staff = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "name": str(_row_value(row, "name", 1) or "").strip(),
        }
        if staff["id"] is None or not staff["name"]:
            raise HTTPException(
                status_code=404,
                detail="Сотрудник не найден в выбранной компании",
            )
        return staff

    def _self_staff(cur, actor, *, lock=False):
        linked_staff_id = _positive_int(
            actor.get("staffId") or actor.get("staff_id")
        )
        if linked_staff_id is not None:
            return _exact_staff(
                cur,
                actor["companyId"],
                linked_staff_id,
                lock=lock,
            )
        email = str(actor.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(
                status_code=409,
                detail="Сотрудник текущего пользователя не определён",
            )
        cur.execute(
            """SELECT id,name
                 FROM public.staff
                WHERE company_id=%s
                  AND company_scope_verified IS TRUE
                  AND (LOWER(BTRIM(email_work))=%s
                       OR LOWER(BTRIM(email_personal))=%s)
                ORDER BY id
                LIMIT 2""" + (" FOR SHARE" if lock else ""),
            (actor["companyId"], email, email),
        )
        rows = list(cur.fetchall() or [])
        if len(rows) != 1:
            raise HTTPException(
                status_code=409,
                detail="Сотрудник текущего пользователя не определён однозначно",
            )
        staff = {
            "id": _positive_int(_row_value(rows[0], "id", 0)),
            "name": str(_row_value(rows[0], "name", 1) or "").strip(),
        }
        if staff["id"] is None or not staff["name"]:
            raise HTTPException(
                status_code=409,
                detail="Сотрудник текущего пользователя не определён",
            )
        return staff

    def _sync_verified_finance_mirror(
        cur,
        *,
        company_id,
        project,
        own_expense_id,
        description,
        amount,
        date_value,
        employee_name,
        photo_url,
    ):
        project_id = project["id"] if project else None
        project_name = project["name"] if project else ""
        finance_category = "other" if project else own_expense_no_project_category
        note = f"Моя трата: {description}".strip()
        if employee_name:
            note += f" · сотрудник: {employee_name}"
        cur.execute(
            """SELECT id
                 FROM public.expenses
                WHERE own_expense_id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE
                ORDER BY id LIMIT 2
                FOR UPDATE""",
            (own_expense_id, company_id),
        )
        existing = list(cur.fetchall() or [])
        if len(existing) > 1:
            raise HTTPException(status_code=409, detail="Зеркальный расход неоднозначен")
        if existing:
            expense_id = _positive_int(_row_value(existing[0], "id", 0))
            if expense_id is None:
                raise HTTPException(status_code=409, detail="Зеркальный расход повреждён")
            cur.execute(
                """UPDATE public.expenses
                      SET project_id=%s,project=%s,category=%s,amount=%s,note=%s,
                          date=%s,added_by=%s,source='own_expense',photo_url=%s
                    WHERE id=%s AND own_expense_id=%s AND company_id=%s
                      AND company_scope_verified IS TRUE""",
                (
                    project_id, project_name, finance_category, amount, note,
                    date_value, employee_name, photo_url, expense_id,
                    own_expense_id, company_id,
                ),
            )
        else:
            cur.execute(
                """INSERT INTO public.expenses
                       (company_id,project_id,company_scope_verified,project,
                        category,amount,note,date,added_by,own_expense_id,
                        source,photo_url)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'own_expense',%s)
                     RETURNING id""",
                (
                    company_id, project_id, True, project_name, finance_category,
                    amount, note, date_value, employee_name, own_expense_id,
                    photo_url,
                ),
            )
            expense_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if expense_id is None:
                raise HTTPException(status_code=409, detail="Зеркальный расход не создан")
        cur.execute(
            """UPDATE public.own_expenses
                  SET expense_id=%s
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE""",
            (expense_id, own_expense_id, company_id),
        )
        return expense_id

    def _verified_own_expense(cur, company_id, own_expense_id, *, lock=False):
        if _positive_int(own_expense_id) is None:
            raise HTTPException(status_code=400, detail="ownExpenseId invalid")
        cur.execute(
            """SELECT id,company_id,project_id,project_name,employee_id,
                      employee_name,description,amount,date,photo_url
                 FROM public.own_expenses
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR UPDATE" if lock else ""),
            (own_expense_id, company_id),
        )
        row = cur.fetchone()
        result = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "companyId": _positive_int(_row_value(row, "company_id", 1)),
            "projectId": _positive_int(_row_value(row, "project_id", 2)),
            "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
            "employeeId": _positive_int(_row_value(row, "employee_id", 4)),
            "employeeName": str(_row_value(row, "employee_name", 5) or "").strip(),
            "description": str(_row_value(row, "description", 6) or "").strip(),
            "amount": _row_value(row, "amount", 7),
            "date": _row_value(row, "date", 8),
            "photoUrl": str(_row_value(row, "photo_url", 9) or ""),
        }
        if result["id"] is None:
            raise HTTPException(status_code=404, detail="Трата не найдена")
        if result["companyId"] != company_id or result["employeeId"] is None:
            raise HTTPException(status_code=409, detail="Владелец личной траты не определён")
        if result["projectId"] is not None and not result["projectName"]:
            raise HTTPException(status_code=409, detail="Объект личной траты не определён")
        return result

    def _own_expense_telegram_value(data: dict, *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _safe_compare_secret(left: str, right: str) -> bool:
        return hmac.compare_digest(str(left or "").encode("utf-8"), str(right or "").encode("utf-8"))

    def require_telegram_bot_token(x_telegram_bot_token: Optional[str] = Header(default=None)) -> dict:
        if not TELEGRAM_BOT_API_TOKEN:
            raise HTTPException(status_code=503, detail="TELEGRAM_BOT_API_TOKEN не настроен")
        if not x_telegram_bot_token or not _safe_compare_secret(x_telegram_bot_token, TELEGRAM_BOT_API_TOKEN):
            raise HTTPException(status_code=403, detail="Недостаточно прав Telegram-бота")
        return {"role": "telegram_bot", "name": "Telegram Bot"}

    TELEGRAM_WAREHOUSE_INTENT_WORDS = (
        "warehouse",
        "warehouse_invoice",
        "invoice",
        "stock",
        "receipt",
        "склад",
        "наклад",
        "приход",
        "материал",
    )

    def _flatten_telegram_payload_values(value, depth=0):
        if depth > 3:
            return []
        if isinstance(value, dict):
            result = []
            for item in value.values():
                result.extend(_flatten_telegram_payload_values(item, depth + 1))
            return result
        if isinstance(value, list):
            result = []
            for item in value[:20]:
                result.extend(_flatten_telegram_payload_values(item, depth + 1))
            return result
        if value is None:
            return []
        return [str(value)]

    def _telegram_payload_requests_warehouse(data: dict) -> bool:
        direct_keys = (
            "intent", "action", "selectedAction", "type", "kind", "route",
            "destination", "mode", "context", "target", "flow", "warehouseTarget",
            "documentType", "document_type", "caption", "text", "description",
        )
        for key in direct_keys:
            value = str(data.get(key) or "").strip().lower()
            if value and any(word in value for word in TELEGRAM_WAREHOUSE_INTENT_WORDS):
                return True
        source = data.get("data") if isinstance(data.get("data"), dict) else {}
        for key in direct_keys:
            value = str(source.get(key) or "").strip().lower()
            if value and any(word in value for word in TELEGRAM_WAREHOUSE_INTENT_WORDS):
                return True
        route_values = " ".join(_flatten_telegram_payload_values({
            key: data.get(key) for key in ("items", "positions", "photos", "files", "warehouse", "invoice")
            if key in data
        })).lower()
        if route_values and any(word in route_values for word in ("наклад", "склад", "приход", "warehouse", "invoice")):
            return True
        return False

    def _normalize_telegram_invoice_payload(data: dict, employee: dict) -> dict:
        source = data.get("data") if isinstance(data.get("data"), dict) else data
        payload = dict(source)
        if not payload.get("items") and isinstance(source.get("positions"), list):
            payload["items"] = source.get("positions")
        if not payload.get("number"):
            payload["number"] = source.get("invoiceNumber") or source.get("invoice_number") or source.get("documentNumber") or ""
        if not payload.get("date"):
            payload["date"] = source.get("invoiceDate") or source.get("invoice_date") or source.get("documentDate") or None
        if not payload.get("supplierName"):
            payload["supplierName"] = source.get("supplier") or source.get("supplier_name") or source.get("seller") or ""
        if not payload.get("photoUrl"):
            payload["photoUrl"] = source.get("photoUrl") or source.get("fileUrl") or data.get("photoUrl") or data.get("fileUrl") or ""
        if not payload.get("totalWithVat"):
            payload["totalWithVat"] = source.get("total_with_vat") or source.get("total") or source.get("amount") or 0
        if not payload.get("totalVat"):
            payload["totalVat"] = source.get("total_vat") or source.get("vatAmount") or 0
        if not payload.get("totalBase"):
            payload["totalBase"] = source.get("total_base") or 0
        normalized_items = []
        for raw_item in payload.get("items") or []:
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            if not item.get("name"):
                item["name"] = item.get("title") or item.get("material") or item.get("product") or item.get("sourceText") or ""
            if not item.get("quantity"):
                item["quantity"] = item.get("qty") or item.get("count") or item.get("amount") or 0
            if not item.get("unit"):
                item["unit"] = item.get("measure") or item.get("uom") or "шт"
            if not item.get("price"):
                item["price"] = item.get("priceWithVat") or item.get("unitPriceWithVat") or item.get("unitPrice") or 0
            if not item.get("total"):
                item["total"] = item.get("lineTotalWithVat") or item.get("lineTotal") or 0
            normalized_items.append(item)
        payload["items"] = normalized_items
        payload["acceptedBy"] = payload.get("acceptedBy") or employee.get("name") or ""
        payload["addedBy"] = payload.get("addedBy") or employee.get("name") or ""
        return payload

    def _find_employee_by_telegram(cur, telegram_id: str, telegram_chat_id: str) -> Optional[dict]:
        if not telegram_id and not telegram_chat_id:
            return None
        cur.execute(
            """SELECT id,name,role,project,company_id,
                      '[]'::jsonb AS assigned_projects,
                      '[]'::jsonb AS assigned_packages
                 FROM public.staff
                WHERE company_scope_verified IS TRUE
                  AND ((%s<>'' AND telegram_id=%s)
                    OR (%s<>'' AND telegram_chat_id=%s))
                ORDER BY company_id,id
                LIMIT 2""",
            (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
        )
        direct_rows = list(cur.fetchall() or [])
        cur.execute(
            """SELECT staff_row.id,staff_row.name,membership.role,
                      staff_row.project,staff_row.company_id,
                      membership.assigned_projects,membership.assigned_packages
                 FROM public.users account
                 JOIN public.user_company_roles membership
                   ON membership.user_id=account.id
                  AND COALESCE(membership.active,TRUE)=TRUE
                 JOIN public.companies company_row
                   ON company_row.id=membership.company_id
                  AND COALESCE(company_row.active,TRUE)=TRUE
                 JOIN public.staff staff_row
                   ON staff_row.company_id=membership.company_id
                  AND staff_row.company_scope_verified IS TRUE
                  AND LOWER(BTRIM(account.email)) IN (
                        LOWER(BTRIM(staff_row.email_work)),
                        LOWER(BTRIM(staff_row.email_personal))
                  )
                WHERE COALESCE(account.active,TRUE)=TRUE
                  AND ((%s<>'' AND account.telegram_id=%s)
                    OR (%s<>'' AND account.telegram_chat_id=%s))
                ORDER BY staff_row.company_id,staff_row.id
                LIMIT 2""",
            (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
        )
        user_rows = list(cur.fetchall() or [])
        matches = {}
        for source, row in (("staff", row) for row in direct_rows):
            company_id = _positive_int(_row_value(row, "company_id", 4))
            staff_id = _positive_int(_row_value(row, "id", 0))
            if company_id is None or staff_id is None:
                continue
            matches[(company_id, staff_id)] = {
                "source": source,
                "id": staff_id,
                "name": str(_row_value(row, "name", 1) or "").strip(),
                "role": str(_row_value(row, "role", 2) or "").strip(),
                "projectName": str(_row_value(row, "project", 3) or "").strip(),
                "companyId": company_id,
                "company_id": company_id,
                "assignedProjects": safe_project_list(
                    _row_value(row, "assigned_projects", 5)
                ),
                "assignedPackages": safe_project_list(
                    _row_value(row, "assigned_packages", 6)
                ),
            }
        for row in user_rows:
            company_id = _positive_int(_row_value(row, "company_id", 4))
            staff_id = _positive_int(_row_value(row, "id", 0))
            if company_id is None or staff_id is None:
                continue
            matches[(company_id, staff_id)] = {
                "source": "users",
                "id": staff_id,
                "name": str(_row_value(row, "name", 1) or "").strip(),
                "role": str(_row_value(row, "role", 2) or "").strip(),
                "projectName": str(_row_value(row, "project", 3) or "").strip(),
                "companyId": company_id,
                "company_id": company_id,
                "assignedProjects": safe_project_list(
                    _row_value(row, "assigned_projects", 5)
                ),
                "assignedPackages": safe_project_list(
                    _row_value(row, "assigned_packages", 6)
                ),
            }
        if not matches:
            return None
        if len(matches) != 1:
            raise HTTPException(
                status_code=409,
                detail="Компания сотрудника Telegram не определена однозначно",
            )
        employee = next(iter(matches.values()))
        if not employee["name"]:
            raise HTTPException(status_code=409, detail="Сотрудник Telegram повреждён")
        if employee["projectName"] and not employee["assignedProjects"]:
            employee["assignedProjects"] = [employee["projectName"]]
        return employee

    def _telegram_employee_has_project_access(employee: dict, project_name: str) -> bool:
        if not project_name:
            return True
        role = employee.get("role") or ""
        if role in finance_roles or role in leadership_roles:
            return True
        return project_name in user_project_names(employee)

    def _telegram_project(cur, employee, data):
        company_id = _positive_int(employee.get("companyId"))
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания Telegram не определена")
        project_id = data.get("projectId") or data.get("project_id")
        project_name = str(data.get("projectName") or data.get("project") or "").strip()
        if project_id is not None:
            project = _exact_project(cur, company_id, project_id, lock=True)
        elif project_name:
            cur.execute(
                """SELECT id,name
                     FROM public.projects
                    WHERE company_id=%s AND BTRIM(name)=BTRIM(%s)
                    ORDER BY id LIMIT 2
                    FOR SHARE""",
                (company_id, project_name),
            )
            rows = list(cur.fetchall() or [])
            if not rows:
                raise HTTPException(status_code=404, detail="Объект Telegram не найден")
            if len(rows) != 1:
                raise HTTPException(status_code=409, detail="Объект Telegram неоднозначен")
            project = {
                "id": _positive_int(_row_value(rows[0], "id", 0)),
                "name": str(_row_value(rows[0], "name", 1) or "").strip(),
            }
            if project["id"] is None or not project["name"]:
                raise HTTPException(status_code=409, detail="Объект Telegram повреждён")
        else:
            return None
        if not _telegram_employee_has_project_access(employee, project["name"]):
            raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")
        return project

    @app.get("/own-expenses")
    def get_own_expenses(
        project_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(
                cur, current_user, "read", x_company_id, x_company_mode
            )
            where = ["company_id=%s", "company_scope_verified IS TRUE"]
            params = [actor["companyId"]]
            if project_id is not None:
                project = _exact_project(cur, actor["companyId"], project_id)
                where.append("project_id=%s")
                params.append(project["id"])

            role = str(actor.get("role") or "").strip()
            if role in own_expense_review_roles:
                if employee_id is not None:
                    staff = _exact_staff(cur, actor["companyId"], employee_id)
                    where.append("employee_id=%s")
                    params.append(staff["id"])
            else:
                staff = _self_staff(cur, actor)
                if employee_id is not None and employee_id != staff["id"]:
                    raise HTTPException(status_code=403, detail="Чужие личные траты недоступны")
                where.append("employee_id=%s")
                params.append(staff["id"])

            cur.execute(
                """SELECT id,project_name,employee_name,description,amount,
                          photo_url,date,status,approved_by,category,employee_id
                     FROM public.own_expenses
                    WHERE """
                + " AND ".join(where)
                + " ORDER BY id DESC",
                tuple(params),
            )
            return [
                {
                    "id": _row_value(row, "id", 0),
                    "projectName": _row_value(row, "project_name", 1) or "",
                    "employeeName": _row_value(row, "employee_name", 2) or "",
                    "description": _row_value(row, "description", 3) or "",
                    "amount": float(_row_value(row, "amount", 4) or 0),
                    "photoUrl": _row_value(row, "photo_url", 5) or "",
                    "date": str(_row_value(row, "date", 6))
                    if _row_value(row, "date", 6)
                    else "",
                    "status": _row_value(row, "status", 7) or "Ожидает",
                    "approvedBy": _row_value(row, "approved_by", 8) or "",
                    "category": _row_value(row, "category", 9) or "other",
                    "employeeId": _row_value(row, "employee_id", 10),
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/own-expenses")
    def create_own_expense(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if not isinstance(data, Mapping):
                raise HTTPException(status_code=400, detail="own expense payload invalid")
            actor = _selected_actor(
                cur, current_user, "write", x_company_id, x_company_mode
            )
            project = _exact_project(
                cur, actor["companyId"], data.get("projectId"), lock=True
            )
            if (
                str(actor.get("role") or "").strip() in finance_roles
                and data.get("employeeId") is not None
            ):
                staff = _exact_staff(
                    cur, actor["companyId"], data.get("employeeId"), lock=True
                )
            else:
                staff = _self_staff(cur, actor, lock=True)
            description = str(data.get("description") or "").strip()
            amount = _positive_amount(data.get("amount"))
            if not description:
                raise HTTPException(status_code=400, detail="Укажите описание траты")
            if len(description) > 10000:
                raise HTTPException(status_code=400, detail="Описание траты слишком длинное")
            if amount is None:
                raise HTTPException(status_code=400, detail="Сумма траты должна быть больше нуля")
            date_value = data.get("date") or None
            category = str(data.get("category") or "other").strip()[:100] or "other"
            if not project:
                category = own_expense_no_project_category
            photo_url = str(data.get("photoUrl") or "").strip()
            if len(photo_url) > 20000:
                raise HTTPException(status_code=400, detail="Список вложений слишком длинный")
            cur.execute(
                """INSERT INTO public.own_expenses
                       (company_id,project_id,company_scope_verified,
                        project_name,employee_name,employee_id,description,
                        amount,photo_url,date,category,telegram_id,telegram_chat_id)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL)
                     RETURNING id""",
                (
                    actor["companyId"],
                    project["id"] if project else None,
                    True,
                    project["name"] if project else "",
                    staff["name"],
                    staff["id"],
                    description,
                    amount,
                    photo_url,
                    date_value,
                    category,
                ),
            )
            own_expense_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if own_expense_id is None:
                raise HTTPException(status_code=409, detail="Личная трата не создана")
            expense_id = _sync_verified_finance_mirror(
                cur,
                company_id=actor["companyId"],
                project=project,
                own_expense_id=own_expense_id,
                description=description,
                amount=amount,
                date_value=date_value,
                employee_name=staff["name"],
                photo_url=photo_url,
            )
            conn.commit()
            return {"ok": True, "id": own_expense_id, "expenseId": expense_id}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/telegram/own-expenses")
    def create_telegram_own_expense(data: dict, _bot: dict = Depends(require_telegram_bot_token)):
        telegram_id = _own_expense_telegram_value(data, "telegramId", "telegram_id", "tgId", "tg_id")
        telegram_chat_id = _own_expense_telegram_value(data, "telegramChatId", "telegram_chat_id", "chatId", "chat_id")
        if not telegram_id and not telegram_chat_id:
            raise HTTPException(status_code=400, detail="Нужен telegram_id или telegram_chat_id")
        if _telegram_payload_requests_warehouse(data):
            raise HTTPException(
                status_code=400,
                detail="Это складская накладная. Отправьте её в /telegram/warehouse-invoices, а не в мои траты.",
            )

        description = str(data.get("description") or data.get("text") or "").strip()
        amount = _positive_amount(data.get("amount"))
        if not description:
            raise HTTPException(status_code=400, detail="Укажите описание траты")
        if amount is None:
            raise HTTPException(status_code=400, detail="Сумма траты должна быть больше нуля")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            employee = _find_employee_by_telegram(cur, telegram_id, telegram_chat_id)
            if not employee:
                raise HTTPException(status_code=404, detail="Сотрудник с таким Telegram не найден")
            project = _telegram_project(cur, employee, data)
            date_value = data.get("date") or None
            category = str(data.get("category") or "other").strip()[:100] or "other"
            if not project:
                category = own_expense_no_project_category
            photo_url = str(data.get("photoUrl") or "").strip()
            cur.execute(
                """INSERT INTO public.own_expenses
                       (company_id,project_id,company_scope_verified,
                        project_name,employee_name,employee_id,description,
                        amount,photo_url,date,category,telegram_id,telegram_chat_id)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     RETURNING id""",
                (
                    employee["companyId"],
                    project["id"] if project else None,
                    True,
                    project["name"] if project else "",
                    employee["name"],
                    employee["id"],
                    description,
                    amount,
                    photo_url,
                    date_value,
                    category,
                    telegram_id,
                    telegram_chat_id,
                ),
            )
            own_expense_id = _positive_int(_row_value(cur.fetchone(), "id", 0))
            if own_expense_id is None:
                raise HTTPException(status_code=409, detail="Личная трата Telegram не создана")
            expense_id = _sync_verified_finance_mirror(
                cur,
                company_id=employee["companyId"],
                project=project,
                own_expense_id=own_expense_id,
                description=description,
                amount=amount,
                date_value=date_value,
                employee_name=employee["name"],
                photo_url=photo_url,
            )
            conn.commit()
            return {
                "ok": True,
                "id": own_expense_id,
                "expenseId": expense_id,
                "employeeName": employee["name"],
                "employeeSource": employee["source"],
                "companyId": employee["companyId"],
                "projectName": project["name"] if project else "",
                "category": category,
            }
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.post("/telegram/warehouse-invoices")
    def create_telegram_warehouse_invoice(data: dict, _bot: dict = Depends(require_telegram_bot_token)):
        telegram_id = _own_expense_telegram_value(data, "telegramId", "telegram_id", "tgId", "tg_id")
        telegram_chat_id = _own_expense_telegram_value(data, "telegramChatId", "telegram_chat_id", "chatId", "chat_id")
        if not telegram_id and not telegram_chat_id:
            raise HTTPException(status_code=400, detail="Нужен telegram_id или telegram_chat_id")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            employee = _find_employee_by_telegram(cur, telegram_id, telegram_chat_id)
        finally:
            cur.close()
            conn.close()
        if not employee:
            raise HTTPException(status_code=404, detail="Сотрудник с таким Telegram не найден")
        if employee.get("role") not in warehouse_roles:
            raise HTTPException(status_code=403, detail="У сотрудника нет прав принимать складские накладные")

        source = data.get("data") if isinstance(data.get("data"), dict) else data
        project_name = (
            source.get("projectName")
            or source.get("project")
            or data.get("projectName")
            or data.get("project")
            or ""
        ).strip()
        location = (source.get("location") or data.get("location") or project_name or "Основной склад").strip()
        target_project = project_name or (location if location and location != "Основной склад" else "")
        if target_project and not _telegram_employee_has_project_access(employee, target_project):
            raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")

        payload = _normalize_telegram_invoice_payload(data, employee)
        payload["location"] = location or "Основной склад"
        payload["project"] = target_project
        payload["sourceType"] = payload.get("sourceType") or ("telegram_project_invoice" if target_project else "telegram_main_invoice")
        payload["sourceId"] = payload.get("sourceId") or data.get("telegramMessageId") or data.get("messageId") or data.get("fileUniqueId") or None
        payload["workPackage"] = supply_work_package(payload.get("workPackage") or payload.get("work_package") or source.get("workPackage") or source.get("work_package"))

        result = create_warehouse_invoice_record(payload, employee)
        result.update({
            "employeeName": employee.get("name", ""),
            "employeeSource": employee.get("source", ""),
            "projectName": target_project,
            "location": payload["location"],
            "sourceType": payload["sourceType"],
        })
        return result

    @app.put("/own-expenses/{id}")
    def update_own_expense(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if not isinstance(data, Mapping):
                raise HTTPException(status_code=400, detail="own expense payload invalid")
            actor = _review_actor(
                cur, current_user, "update", x_company_id, x_company_mode
            )
            status = data.get("status", "Ожидает")
            if status not in ("Ожидает", "Возмещено", "Отклонено"):
                raise HTTPException(status_code=400, detail="Статус личной траты недопустим")
            expense = _verified_own_expense(cur, actor["companyId"], id, lock=True)
            cur.execute(
                """UPDATE public.own_expenses
                      SET status=%s,approved_by=%s
                    WHERE id=%s AND company_id=%s
                      AND company_scope_verified IS TRUE""",
                (status, _actor_name(actor), id, actor["companyId"]),
            )
            if status == "Отклонено":
                cur.execute(
                    """DELETE FROM public.expenses
                        WHERE own_expense_id=%s AND company_id=%s
                          AND company_scope_verified IS TRUE""",
                    (id, actor["companyId"]),
                )
                cur.execute(
                    """UPDATE public.own_expenses
                          SET expense_id=NULL
                        WHERE id=%s AND company_id=%s
                          AND company_scope_verified IS TRUE""",
                    (id, actor["companyId"]),
                )
            else:
                project = (
                    {"id": expense["projectId"], "name": expense["projectName"]}
                    if expense["projectId"] is not None
                    else None
                )
                _sync_verified_finance_mirror(
                    cur,
                    company_id=actor["companyId"],
                    project=project,
                    own_expense_id=id,
                    description=expense["description"],
                    amount=expense["amount"],
                    date_value=expense["date"],
                    employee_name=expense["employeeName"],
                    photo_url=expense["photoUrl"],
                )
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/own-expenses/{id}")
    def delete_own_expense(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _review_actor(
                cur, current_user, "delete", x_company_id, x_company_mode
            )
            _verified_own_expense(cur, actor["companyId"], id, lock=True)
            cur.execute(
                """DELETE FROM public.expenses
                    WHERE own_expense_id=%s AND company_id=%s
                      AND company_scope_verified IS TRUE""",
                (id, actor["companyId"]),
            )
            cur.execute(
                """DELETE FROM public.own_expenses
                    WHERE id=%s AND company_id=%s
                      AND company_scope_verified IS TRUE""",
                (id, actor["companyId"]),
            )
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
