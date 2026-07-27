import json
from datetime import datetime
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.features.ai_findings.service import resolve_project_owner
except ModuleNotFoundError:
    from features.ai_findings.service import resolve_project_owner


def _text(value, limit=500):
    return str(value or "").strip()[:limit]


def _json_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _event_time(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return _text(value, 100)


def _event_sort_key(event):
    value = _text(event.get("eventAt"), 100)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10]).timestamp()
        except ValueError:
            return float("-inf")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def register_project_events_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    allowed_roles = {str(role or "").strip() for role in deps["read_roles"]}
    full_view_roles = {str(role or "").strip() for role in deps["full_view_roles"]}

    def _selected_actor(cur, current_user, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur,
            current_user,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        if context.get("mode") == "all_companies":
            raise HTTPException(status_code=409, detail="Для событий объекта выберите одну компанию")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if _text((actor or {}).get("role"), 100) in allowed_roles
        ]
        if len(actors) != 1:
            raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет смотреть события объекта")
        actor = actors[0]
        company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
        if not company_id:
            raise HTTPException(status_code=409, detail="Компания объекта не определена")
        actor["companyId"] = company_id
        return actor

    def _require_project(cur, actor, project_name):
        project = resolve_project_owner(cur, project_name, company_id=actor["companyId"])
        assigned = {
            _text(value, 255)
            for value in (actor.get("assignedProjects") or actor.get("assigned_projects") or [])
            if _text(value, 255)
        }
        legacy_project = _text(actor.get("projectName") or actor.get("project_name"), 255)
        if legacy_project:
            assigned.add(legacy_project)
        if _text(actor.get("role"), 100) not in full_view_roles and project["name"] not in assigned:
            raise HTTPException(status_code=403, detail="Нет доступа к объекту")
        return project

    def _append_date_filter(where, params, column, date_from, date_to):
        if date_from:
            where.append(f"{column} >= %s")
            params.append(date_from)
        if date_to:
            where.append(f"{column} < (%s::date + INTERVAL '1 day')")
            params.append(date_to)

    @app.get("/project-events")
    def list_project_events(
        project_name: str,
        date_from: str = "",
        date_to: str = "",
        limit: int = 100,
        offset: int = 0,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        project_name = _text(project_name, 255)
        if not project_name:
            raise HTTPException(status_code=400, detail="Укажите объект")
        limit = max(1, min(int(limit or 100), 250))
        offset = max(0, int(offset or 0))
        source_limit = min(250, limit + offset + 1)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = _selected_actor(cur, current_user, x_company_id, x_company_mode)
            project = _require_project(cur, actor, project_name)
            company_id = actor["companyId"]
            events = []

            invoice_where, invoice_params = ["company_id=%s", "(project=%s OR location=%s)"], [company_id, project["name"], project["name"]]
            _append_date_filter(invoice_where, invoice_params, "created_at", date_from, date_to)
            cur.execute(
                """SELECT id,number,date,supplier_name,accepted_by,items,total_with_vat,status,
                          added_by,photo_url,photo_urls,warehouse_target,created_at
                     FROM warehouse_invoices WHERE """ + " AND ".join(invoice_where) + " ORDER BY created_at DESC LIMIT %s",
                tuple(invoice_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                photos = _json_list(row.get("photo_urls")) or ([row.get("photo_url")] if row.get("photo_url") else [])
                items = _json_list(row.get("items"))
                events.append({
                    "id": f"invoice:{row['id']}", "type": "receipt", "sourceKind": "warehouse_invoice", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("created_at")), "documentDate": _event_time(row.get("date")),
                    "title": "Приходная накладная" if row.get("warehouse_target") != "main" else "Приход на основной склад",
                    "summary": " · ".join(filter(None, [f"{len(items)} поз." if items else "", _text(row.get("supplier_name"), 160), _text(row.get("number"), 100)])),
                    "actor": _text(row.get("added_by") or row.get("accepted_by"), 160),
                    "supplierName": _text(row.get("supplier_name"), 255), "amount": float(row.get("total_with_vat") or 0),
                    "status": _text(row.get("status"), 100), "items": items, "photos": [p for p in photos if p],
                })

            history_where, history_params = ["company_id=%s", "project=%s"], [company_id, project["name"]]
            if date_from:
                history_where.append("date >= %s"); history_params.append(date_from)
            if date_to:
                history_where.append("date <= %s"); history_params.append(date_to)
            cur.execute(
                """SELECT id,material,type,quantity,unit,date,issued_to,issued_by,work_package,date_time
                     FROM warehouse_history WHERE """ + " AND ".join(history_where) + " ORDER BY id DESC LIMIT %s",
                tuple(history_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                qty = row.get("quantity") or 0
                unit = _text(row.get("unit"), 50)
                events.append({
                    "id": f"history:{row['id']}", "type": "warehouse_operation", "sourceKind": "warehouse_history", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("date_time") or row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": _text(row.get("type"), 160) or "Операция со складом",
                    "summary": f"{_text(row.get('material'), 300)} · {qty:g} {unit}".strip(),
                    "actor": _text(row.get("issued_by"), 160), "recipient": _text(row.get("issued_to"), 160),
                    "workPackage": _text(row.get("work_package"), 160), "items": [{"name": row.get("material"), "quantity": qty, "unit": unit}], "photos": [],
                })

            movement_where, movement_params = ["company_id=%s", "(from_location=%s OR to_location=%s)"], [company_id, project["name"], project["name"]]
            if date_from:
                movement_where.append("date >= %s"); movement_params.append(date_from)
            if date_to:
                movement_where.append("date <= %s"); movement_params.append(date_to)
            cur.execute(
                """SELECT id,material_name,from_location,to_location,quantity,unit,work_package,date,created_by,notes
                     FROM warehouse_movements WHERE """ + " AND ".join(movement_where) + " ORDER BY id DESC LIMIT %s",
                tuple(movement_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                qty = row.get("quantity") or 0
                unit = _text(row.get("unit"), 50)
                events.append({
                    "id": f"movement:{row['id']}", "type": "movement", "sourceKind": "warehouse_movement", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": "Перемещение материала",
                    "summary": f"{_text(row.get('material_name'), 300)} · {qty:g} {unit} · {_text(row.get('from_location'), 100)} → {_text(row.get('to_location'), 100)}",
                    "actor": _text(row.get("created_by"), 160), "workPackage": _text(row.get("work_package"), 160),
                    "note": _text(row.get("notes"), 500), "items": [{"name": row.get("material_name"), "quantity": qty, "unit": unit}], "photos": [],
                })

            finance_where, finance_params = ["company_id=%s", "project_name=%s"], [company_id, project["name"]]
            _append_date_filter(finance_where, finance_params, "created_at", date_from, date_to)
            cur.execute(
                """SELECT id,amount,note,date,added_by,work_package,created_at FROM project_payments WHERE """
                + " AND ".join(finance_where) + " ORDER BY created_at DESC LIMIT %s", tuple(finance_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                events.append({
                    "id": f"payment:{row['id']}", "type": "customer_payment", "sourceKind": "project_payment", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("created_at") or row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": "Оплата от заказчика", "summary": _text(row.get("note"), 500),
                    "actor": _text(row.get("added_by"), 160), "amount": float(row.get("amount") or 0),
                    "workPackage": _text(row.get("work_package"), 160), "items": [], "photos": [],
                })

            expense_where, expense_params = ["p.company_id=%s", "e.project=%s", "COALESCE(e.source,'') <> 'own_expense'"], [company_id, project["name"]]
            _append_date_filter(expense_where, expense_params, "e.created_at", date_from, date_to)
            cur.execute(
                """SELECT e.id,e.category,e.amount,e.note,e.date,e.added_by,e.photo_url,e.created_at
                     FROM expenses e JOIN projects p ON p.name=e.project WHERE """ + " AND ".join(expense_where) + " ORDER BY e.created_at DESC LIMIT %s",
                tuple(expense_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                events.append({
                    "id": f"expense:{row['id']}", "type": "expense", "sourceKind": "expense", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("created_at") or row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": "Расход по объекту", "summary": _text(row.get("note"), 500), "actor": _text(row.get("added_by"), 160),
                    "amount": float(row.get("amount") or 0), "category": _text(row.get("category"), 160), "items": [],
                    "photos": [row.get("photo_url")] if row.get("photo_url") else [],
                })

            own_where, own_params = ["p.company_id=%s", "oe.project_name=%s"], [company_id, project["name"]]
            _append_date_filter(own_where, own_params, "oe.created_at", date_from, date_to)
            cur.execute(
                """SELECT oe.id,oe.description,oe.amount,oe.photo_url,oe.date,oe.employee_name,oe.status,oe.created_at
                     FROM own_expenses oe JOIN projects p ON p.name=oe.project_name WHERE """ + " AND ".join(own_where) + " ORDER BY oe.created_at DESC LIMIT %s",
                tuple(own_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                events.append({
                    "id": f"own-expense:{row['id']}", "type": "own_expense", "sourceKind": "own_expense", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("created_at") or row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": "Трата сотрудника", "summary": _text(row.get("description"), 500), "actor": _text(row.get("employee_name"), 160),
                    "amount": float(row.get("amount") or 0), "status": _text(row.get("status"), 100), "items": [],
                    "photos": [row.get("photo_url")] if row.get("photo_url") else [],
                })

            work_where, work_params = ["company_id=%s", "project=%s"], [company_id, project["name"]]
            if date_from:
                work_where.append("date >= %s"); work_params.append(date_from)
            if date_to:
                work_where.append("date <= %s"); work_params.append(date_to)
            cur.execute(
                """SELECT id,master_name,description,unit,quantity,date,status,comment,photo_url,confirmed_by,confirmed_at,work_package
                     FROM work_journal WHERE """ + " AND ".join(work_where) + " ORDER BY id DESC LIMIT %s",
                tuple(work_params + [source_limit]),
            )
            for row in cur.fetchall() or []:
                qty = row.get("quantity") or 0
                unit = _text(row.get("unit"), 50)
                events.append({
                    "id": f"work:{row['id']}", "type": "work", "sourceKind": "work_journal", "sourceId": row["id"],
                    "eventAt": _event_time(row.get("confirmed_at") or row.get("date")), "documentDate": _event_time(row.get("date")),
                    "title": "Выполненная работа", "summary": f"{_text(row.get('description'), 300)} · {qty:g} {unit}".strip(),
                    "actor": _text(row.get("master_name"), 160), "status": _text(row.get("status"), 100),
                    "note": _text(row.get("comment"), 500), "workPackage": _text(row.get("work_package"), 160),
                    "items": [], "photos": [row.get("photo_url")] if row.get("photo_url") else [],
                })

            events.sort(key=_event_sort_key, reverse=True)
            return {
                "projectName": project["name"], "companyId": company_id,
                "items": events[offset:offset + limit], "hasMore": len(events) > offset + limit,
                "timingNote": "Время указано точно, когда источник хранит created_at или confirmed_at; иначе показана дата документа.",
            }
        finally:
            cur.close()
            conn.close()
