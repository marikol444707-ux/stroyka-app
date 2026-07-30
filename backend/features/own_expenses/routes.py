"""Own expense and Telegram webhook routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 29):
the own-expenses quartet plus the two Telegram bot webhooks keep
their URLs, role scopes, employee resolution, finance-expense mirror
sync and warehouse-intent protection. All cluster helpers moved
along as closures; shared services arrive through deps.
"""

import hmac
from typing import Optional

from fastapi import Depends, Header, HTTPException

try:
    from backend.config import TELEGRAM_BOT_API_TOKEN
except ModuleNotFoundError:
    from config import TELEGRAM_BOT_API_TOKEN


def register_own_expenses_module(app, deps):
    get_db = deps["get_db"]
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
            """
            SELECT id,name,role,project_name,assigned_projects,assigned_packages
              FROM users
             WHERE COALESCE(active,TRUE)=TRUE
               AND ((%s<>'' AND telegram_id=%s)
                 OR (%s<>'' AND telegram_chat_id=%s))
             ORDER BY id
             LIMIT 1
            """,
            (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
        )
        row = cur.fetchone()
        if row:
            return {
                "source": "users",
                "id": row[0],
                "name": row[1] or "",
                "role": row[2] or "",
                "projectName": row[3] or "",
                "assignedProjects": safe_project_list(row[4]),
                "assignedPackages": safe_project_list(row[5]),
            }

        cur.execute(
            """
            SELECT id,name,role,project
              FROM staff
             WHERE (%s<>'' AND telegram_id=%s)
                OR (%s<>'' AND telegram_chat_id=%s)
             ORDER BY id
             LIMIT 1
            """,
            (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "source": "staff",
            "id": row[0],
            "name": row[1] or "",
            "role": row[2] or "",
            "projectName": row[3] or "",
            "assignedProjects": [row[3]] if row[3] else [],
            "assignedPackages": [],
        }

    def _telegram_employee_has_project_access(employee: dict, project_name: str) -> bool:
        if not project_name:
            return True
        role = employee.get("role") or ""
        if role in finance_roles or role in leadership_roles:
            return True
        return project_name in user_project_names(employee)

    def _resolve_own_expense_employee(cur, data: dict, current_user: dict) -> tuple[str, int, str, str]:
        telegram_id = _own_expense_telegram_value(data, "telegramId", "telegram_id", "tgId", "tg_id")
        telegram_chat_id = _own_expense_telegram_value(data, "telegramChatId", "telegram_chat_id", "chatId", "chat_id")

        if current_user.get("role") in finance_roles and (telegram_id or telegram_chat_id):
            try:
                cur.execute(
                    """
                    SELECT id, name
                      FROM users
                     WHERE (%s<>'' AND telegram_id=%s)
                        OR (%s<>'' AND telegram_chat_id=%s)
                     LIMIT 1
                    """,
                    (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
                )
                row = cur.fetchone()
                if row:
                    return row[1] or "", row[0], telegram_id, telegram_chat_id
            except Exception:
                pass
            try:
                cur.execute(
                    """
                    SELECT id, name
                      FROM staff
                     WHERE (%s<>'' AND telegram_id=%s)
                        OR (%s<>'' AND telegram_chat_id=%s)
                     LIMIT 1
                    """,
                    (telegram_id, telegram_id, telegram_chat_id, telegram_chat_id),
                )
                row = cur.fetchone()
                if row:
                    return row[1] or "", row[0], telegram_id, telegram_chat_id
            except Exception:
                pass

        if current_user.get("role") in finance_roles:
            employee_name = data.get("employeeName") or current_user.get("name") or ""
            employee_id = data.get("employeeId") or current_user.get("id")
        else:
            employee_name = current_user.get("name") or ""
            employee_id = current_user.get("id")
        return employee_name, employee_id, telegram_id, telegram_chat_id

    def _sync_own_expense_to_finance_expense(cur, own_expense_id: int, project_name: str, description: str, amount, date_value, employee_name: str, photo_url: str = ""):
        finance_category = "other" if project_name else own_expense_no_project_category
        note_prefix = "Моя трата"
        note = f"{note_prefix}: {description or ''}".strip()
        if employee_name:
            note += f" · сотрудник: {employee_name}"
        cur.execute("SELECT id FROM expenses WHERE own_expense_id=%s LIMIT 1", (own_expense_id,))
        existing = cur.fetchone()
        if existing:
            expense_id = existing[0]
            cur.execute(
                "UPDATE expenses SET project=%s, category=%s, amount=%s, note=%s, date=%s, added_by=%s, source=%s, photo_url=%s WHERE id=%s",
                (project_name or "", finance_category, amount or 0, note, date_value or None, employee_name or "", "own_expense", photo_url or "", expense_id),
            )
        else:
            cur.execute(
                "INSERT INTO expenses (project,category,amount,note,date,added_by,own_expense_id,source,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (project_name or "", finance_category, amount or 0, note, date_value or None, employee_name or "", own_expense_id, "own_expense", photo_url or ""),
            )
            expense_id = cur.fetchone()[0]
        cur.execute("UPDATE own_expenses SET expense_id=%s WHERE id=%s", (expense_id, own_expense_id))
        return expense_id

    @app.get("/own-expenses")
    def get_own_expenses(project_name: str = "", employee_name: str = "", current_user: dict = Depends(require_roles(*own_expense_roles))):
        conn = get_db()
        cur = conn.cursor()
        cols = "id,project_name,employee_name,description,amount,photo_url,date,status,approved_by,category,employee_id"
        where, params = [], []

        if project_name:
            require_project_access(current_user, project_name)
            where.append("project_name=%s")
            params.append(project_name)
        if employee_name:
            where.append("employee_name=%s")
            params.append(employee_name)

        role = current_user.get("role")
        if role in own_expense_review_roles:
            pass
        elif role in worker_execution_roles or role in ("прораб", "главный_инженер", "сметчик", "кладовщик", "снабженец"):
            where.append("(employee_id=%s OR employee_name=%s)")
            params.extend([current_user.get("id"), current_user.get("name") or ""])
        else:
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            where.append("project_name = ANY(%s)")
            params.append(projects)

        q = f"SELECT {cols} FROM own_expenses"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC"
        cur.execute(q, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"projectName":r[1],"employeeName":r[2],"description":r[3],"amount":float(r[4] or 0),"photoUrl":r[5] or "","date":str(r[6]) if r[6] else "","status":r[7] or "Ожидает","approvedBy":r[8] or "","category":r[9] or "other","employeeId":r[10]} for r in rows]

    @app.post("/own-expenses")
    def create_own_expense(data: dict, current_user: dict = Depends(require_roles(*own_expense_roles))):
        project_name = (data.get("projectName") or "").strip()
        if project_name:
            require_project_access(current_user, project_name)
        conn = get_db()
        cur = conn.cursor()
        employee_name, employee_id, telegram_id, telegram_chat_id = _resolve_own_expense_employee(cur, data, current_user)
        description = str(data.get("description") or "").strip()
        amount = safe_float(data.get("amount"), None)
        if not description:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Укажите описание траты")
        if amount is None or amount <= 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Сумма траты должна быть больше нуля")
        date_value = data.get("date") or None
        category = data.get("category") or "other"
        if not project_name:
            category = own_expense_no_project_category
        cur.execute(
            """
            INSERT INTO own_expenses
                (project_name,employee_name,employee_id,description,amount,photo_url,date,category,telegram_id,telegram_chat_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                project_name,
                employee_name,
                employee_id,
                description,
                amount,
                data.get("photoUrl", ""),
                date_value,
                category,
                telegram_id,
                telegram_chat_id,
            ),
        )
        own_expense_id = cur.fetchone()[0]
        expense_id = _sync_own_expense_to_finance_expense(cur, own_expense_id, project_name, description, amount, date_value, employee_name, data.get("photoUrl", ""))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": own_expense_id, "expenseId": expense_id}

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
        amount = safe_float(data.get("amount"), None)
        if not description:
            raise HTTPException(status_code=400, detail="Укажите описание траты")
        if amount is None or amount <= 0:
            raise HTTPException(status_code=400, detail="Сумма траты должна быть больше нуля")

        project_name = (data.get("projectName") or data.get("project") or "").strip()
        conn = get_db()
        cur = conn.cursor()
        employee = _find_employee_by_telegram(cur, telegram_id, telegram_chat_id)
        if not employee:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Сотрудник с таким Telegram не найден")
        if project_name and not _telegram_employee_has_project_access(employee, project_name):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="У сотрудника нет доступа к объекту")

        date_value = data.get("date") or None
        category = data.get("category") or "other"
        if not project_name:
            category = own_expense_no_project_category

        cur.execute(
            """
            INSERT INTO own_expenses
                (project_name,employee_name,employee_id,description,amount,photo_url,date,category,telegram_id,telegram_chat_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                project_name,
                employee["name"],
                employee["id"],
                description,
                amount,
                data.get("photoUrl", ""),
                date_value,
                category,
                telegram_id,
                telegram_chat_id,
            ),
        )
        own_expense_id = cur.fetchone()[0]
        expense_id = _sync_own_expense_to_finance_expense(
            cur,
            own_expense_id,
            project_name,
            description,
            amount,
            date_value,
            employee["name"],
            data.get("photoUrl", ""),
        )
        conn.commit()
        cur.close(); conn.close()
        return {
            "ok": True,
            "id": own_expense_id,
            "expenseId": expense_id,
            "employeeName": employee["name"],
            "employeeSource": employee["source"],
            "projectName": project_name,
            "category": category,
        }

    @app.post("/telegram/warehouse-invoices")
    def create_telegram_warehouse_invoice(data: dict, _bot: dict = Depends(require_telegram_bot_token)):
        telegram_id = _own_expense_telegram_value(data, "telegramId", "telegram_id", "tgId", "tg_id")
        telegram_chat_id = _own_expense_telegram_value(data, "telegramChatId", "telegram_chat_id", "chatId", "chat_id")
        if not telegram_id and not telegram_chat_id:
            raise HTTPException(status_code=400, detail="Нужен telegram_id или telegram_chat_id")

        conn = get_db()
        cur = conn.cursor()
        employee = _find_employee_by_telegram(cur, telegram_id, telegram_chat_id)
        cur.close(); conn.close()
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
    def update_own_expense(id: int, data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        status = data.get("status", "Ожидает")
        cur.execute(
            """
            UPDATE own_expenses
               SET status=%s, approved_by=%s
             WHERE id=%s
         RETURNING project_name, employee_name, description, amount, date, photo_url
            """,
            (status, data.get("approvedBy", ""), id),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Трата не найдена")
        if status == "Отклонено":
            cur.execute("DELETE FROM expenses WHERE own_expense_id=%s", (id,))
            cur.execute("UPDATE own_expenses SET expense_id=NULL WHERE id=%s", (id,))
        else:
            project_name, employee_name, description, amount, date_value, photo_url = row
            _sync_own_expense_to_finance_expense(
                cur,
                id,
                project_name or "",
                description or "",
                amount or 0,
                date_value,
                employee_name or "",
                photo_url or "",
            )
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}

    @app.delete("/own-expenses/{id}")
    def delete_own_expense(id: int, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM expenses WHERE own_expense_id=%s", (id,))
        cur.execute("DELETE FROM own_expenses WHERE id=%s", (id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True}
