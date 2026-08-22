"""Verified-company manual expense routes."""

import math
from collections.abc import Mapping
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


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


def _bounded_text(value, *, limit, field, default=""):
    if value is None:
        return default
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field} must be text")
    result = value.strip()
    if len(result) > limit:
        raise HTTPException(status_code=400, detail=f"{field} is too long")
    return result or default


def register_expenses_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    finance_roles = {
        str(role or "").strip() for role in (deps.get("finance_roles") or ())
    }

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
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
                detail="Для расходов выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания расходов не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in finance_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет работать с расходами",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для расходов выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания расхода не совпадает с выбранной компанией",
            )
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def exact_project(cur, company_id, project_id, *, lock=False):
        if _positive_int(project_id) is None:
            raise HTTPException(status_code=400, detail="projectId required")
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
            raise HTTPException(
                status_code=409,
                detail="Объект в выбранной компании неоднозначен",
            )
        project = {
            "id": _positive_int(_row_value(rows[0], "id", 0)),
            "name": str(_row_value(rows[0], "name", 1) or "").strip(),
        }
        if project["id"] is None or not project["name"]:
            raise HTTPException(status_code=409, detail="Владелец объекта не определён")
        return project

    def actor_name(actor):
        return str(
            actor.get("name") or actor.get("email") or actor.get("id") or ""
        ).strip()

    @app.get("/expenses")
    def get_expenses(
        project_id: Optional[int] = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(
                cur, current_user, "read", x_company_id, x_company_mode
            )
            params = [actor["companyId"]]
            project_clause = ""
            if project_id is not None:
                project = exact_project(cur, actor["companyId"], project_id)
                project_clause = " AND project_id=%s"
                params.append(project["id"])
            cur.execute(
                """SELECT id,project,category,amount,note,date,added_by,
                          own_expense_id,source,photo_url
                     FROM public.expenses
                    WHERE company_id=%s
                      AND company_scope_verified IS TRUE"""
                + project_clause
                + " ORDER BY id DESC",
                tuple(params),
            )
            return [
                {
                    "id": _row_value(row, "id", 0),
                    "project": _row_value(row, "project", 1) or "",
                    "category": _row_value(row, "category", 2) or "",
                    "amount": float(_row_value(row, "amount", 3) or 0),
                    "note": _row_value(row, "note", 4) or "",
                    "date": str(_row_value(row, "date", 5))
                    if _row_value(row, "date", 5)
                    else "",
                    "addedBy": _row_value(row, "added_by", 6) or "",
                    "ownExpenseId": _row_value(row, "own_expense_id", 7),
                    "source": _row_value(row, "source", 8) or "",
                    "photoUrl": _row_value(row, "photo_url", 9) or "",
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/expenses")
    def create_expense(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if not isinstance(data, Mapping):
                raise HTTPException(status_code=400, detail="expense payload invalid")
            actor = selected_actor(
                cur, current_user, "write", x_company_id, x_company_mode
            )
            project = exact_project(
                cur, actor["companyId"], data.get("projectId"), lock=True
            )
            amount = _positive_amount(data.get("amount"))
            if amount is None:
                raise HTTPException(status_code=400, detail="amount must be positive")
            cur.execute(
                """INSERT INTO public.expenses
                       (company_id,project_id,company_scope_verified,
                        project,category,amount,note,date,added_by,photo_url,
                        own_expense_id,source)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'manual')
                     RETURNING id""",
                (
                    actor["companyId"],
                    project["id"],
                    True,
                    project["name"],
                    _bounded_text(
                        data.get("category"), limit=100, field="category", default="other"
                    ),
                    amount,
                    _bounded_text(data.get("note"), limit=10000, field="note"),
                    _bounded_text(data.get("date"), limit=50, field="date") or None,
                    actor_name(actor),
                    _bounded_text(
                        data.get("photoUrl") or data.get("photo_url"),
                        limit=20000,
                        field="photoUrl",
                    ),
                ),
            )
            row = cur.fetchone()
            expense_id = _positive_int(_row_value(row, "id", 0))
            if expense_id is None:
                raise HTTPException(status_code=409, detail="Расход не создан")
            conn.commit()
            return {"id": expense_id, "ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
