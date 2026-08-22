"""Company-scoped accountable payment and expense routes."""

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


def register_accountable_payments_module(app, deps):
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
                detail="Для подотчёта выберите одну конкретную компанию",
            )
        context_company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if context_company_id is None:
            raise HTTPException(status_code=409, detail="Компания подотчёта не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in finance_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет работать с подотчётом",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для подотчёта выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != context_company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания подотчёта не совпадает с выбранной компанией",
            )
        actor["companyId"] = actor_company_id
        actor["company_id"] = actor_company_id
        return actor

    def exact_project(
        cur, company_id, project_id=None, project_name=None, *, lock=False,
    ):
        lock_clause = " FOR SHARE" if lock else ""
        if project_id is not None:
            if _positive_int(project_id) is None:
                raise HTTPException(status_code=400, detail="projectId required")
            cur.execute(
                "SELECT id,name FROM public.projects WHERE id=%s AND company_id=%s"
                + lock_clause,
                (project_id, company_id),
            )
        else:
            if not str(project_name or "").strip():
                raise HTTPException(status_code=400, detail="projectName required")
            cur.execute(
                """SELECT id,name
                     FROM public.projects
                    WHERE company_id=%s AND BTRIM(name)=BTRIM(%s)
                    ORDER BY id LIMIT 2""" + lock_clause,
                (company_id, project_name),
            )
        rows = list(cur.fetchall() or [])
        if not rows:
            raise HTTPException(status_code=404, detail="Объект не найден в выбранной компании")
        if len(rows) != 1:
            raise HTTPException(status_code=409, detail="Объект в выбранной компании неоднозначен")
        row = rows[0]
        resolved_id = _positive_int(_row_value(row, "id", 0))
        resolved_name = str(_row_value(row, "name", 1) or "").strip()
        if resolved_id is None or not resolved_name:
            raise HTTPException(status_code=409, detail="Владелец объекта не определён")
        return {"id": resolved_id, "name": resolved_name}

    def exact_staff(cur, company_id, staff_id):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="givenToId required")
        cur.execute(
            """SELECT id,name
                 FROM public.staff
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE
                FOR SHARE""",
            (staff_id, company_id),
        )
        row = cur.fetchone()
        resolved_id = _positive_int(_row_value(row, "id", 0))
        resolved_name = str(_row_value(row, "name", 1) or "").strip()
        if resolved_id is None or not resolved_name:
            raise HTTPException(status_code=404, detail="Сотрудник не найден в выбранной компании")
        return {"id": resolved_id, "name": resolved_name}

    def verified_payment(cur, company_id, payment_id, *, lock=False):
        if _positive_int(payment_id) is None:
            raise HTTPException(status_code=400, detail="paymentId required")
        cur.execute(
            """SELECT id,company_id,project_id,project_name
                 FROM public.accountable_payments
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR UPDATE" if lock else ""),
            (payment_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Подотчётная выдача не найдена")
        result = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "companyId": _positive_int(_row_value(row, "company_id", 1)),
            "projectId": _positive_int(_row_value(row, "project_id", 2)),
            "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
        }
        if (
            result["id"] is None
            or result["companyId"] != company_id
            or result["projectId"] is None
        ):
            raise HTTPException(status_code=409, detail="Владелец подотчётной выдачи не определён")
        return result

    def actor_name(actor):
        return str(actor.get("name") or actor.get("email") or actor.get("id") or "").strip()

    @app.get("/accountable-payments")
    def get_accountable_payments(
        project_name: str = "",
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            params = [actor["companyId"]]
            project_clause = ""
            if str(project_name or "").strip():
                project = exact_project(
                    cur, actor["companyId"], project_name=project_name
                )
                project_clause = " AND project_id=%s"
                params.append(project["id"])
            cur.execute(
                """SELECT id,project_name,project_id,given_to,amount,
                          payment_method,purpose,date,added_by,status,spent_amount
                     FROM public.accountable_payments
                    WHERE company_id=%s
                      AND company_scope_verified IS TRUE"""
                + project_clause
                + " ORDER BY id DESC",
                tuple(params),
            )
            return [
                {
                    "id": _row_value(row, "id", 0),
                    "projectName": _row_value(row, "project_name", 1) or "",
                    "projectId": _row_value(row, "project_id", 2),
                    "givenTo": _row_value(row, "given_to", 3) or "",
                    "amount": float(_row_value(row, "amount", 4) or 0),
                    "paymentMethod": _row_value(row, "payment_method", 5) or "Наличные",
                    "purpose": _row_value(row, "purpose", 6) or "",
                    "date": str(_row_value(row, "date", 7)) if _row_value(row, "date", 7) else "",
                    "addedBy": _row_value(row, "added_by", 8) or "",
                    "status": _row_value(row, "status", 9) or "Открыт",
                    "spentAmount": float(_row_value(row, "spent_amount", 10) or 0),
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/accountable-payments")
    def create_accountable_payment(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            project = exact_project(
                cur,
                actor["companyId"],
                project_id=(data or {}).get("projectId"),
                lock=True,
            )
            staff = exact_staff(cur, actor["companyId"], (data or {}).get("givenToId"))
            amount = _positive_amount((data or {}).get("amount"))
            if amount is None:
                raise HTTPException(status_code=400, detail="amount must be positive")
            cur.execute(
                """INSERT INTO public.accountable_payments
                       (company_id,project_id,company_scope_verified,
                        project_name,given_to,given_to_id,amount,payment_method,
                        purpose,date,added_by)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     RETURNING id""",
                (
                    actor["companyId"], project["id"], True,
                    project["name"], staff["name"], staff["id"], amount,
                    (data or {}).get("paymentMethod") or "Наличные",
                    (data or {}).get("purpose") or "",
                    (data or {}).get("date") or None,
                    actor_name(actor),
                ),
            )
            row = cur.fetchone()
            payment_id = _positive_int(_row_value(row, "id", 0))
            if payment_id is None:
                raise HTTPException(status_code=409, detail="Подотчётная выдача не создана")
            conn.commit()
            return {"id": payment_id, "ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/accountable-expenses")
    def get_accountable_expenses(
        payment_id: int = 0,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "read", x_company_id, x_company_mode)
            params = [actor["companyId"]]
            payment_clause = ""
            if payment_id:
                parent = verified_payment(cur, actor["companyId"], payment_id)
                payment_clause = " AND payment_id=%s AND project_id=%s"
                params.extend((parent["id"], parent["projectId"]))
            cur.execute(
                """SELECT id,payment_id,project_name,project_id,description,
                          amount,photo_url,date,added_by
                     FROM public.accountable_expenses
                    WHERE company_id=%s
                      AND company_scope_verified IS TRUE"""
                + payment_clause
                + " ORDER BY id DESC",
                tuple(params),
            )
            return [
                {
                    "id": _row_value(row, "id", 0),
                    "paymentId": _row_value(row, "payment_id", 1),
                    "projectName": _row_value(row, "project_name", 2) or "",
                    "projectId": _row_value(row, "project_id", 3),
                    "description": _row_value(row, "description", 4) or "",
                    "amount": float(_row_value(row, "amount", 5) or 0),
                    "photoUrl": _row_value(row, "photo_url", 6) or "",
                    "date": str(_row_value(row, "date", 7)) if _row_value(row, "date", 7) else "",
                    "addedBy": _row_value(row, "added_by", 8) or "",
                }
                for row in (cur.fetchall() or [])
            ]
        finally:
            cur.close()
            conn.close()

    @app.post("/accountable-expenses")
    def create_accountable_expense(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(cur, current_user, "write", x_company_id, x_company_mode)
            parent = verified_payment(
                cur, actor["companyId"], (data or {}).get("paymentId"), lock=True
            )
            project = exact_project(
                cur,
                actor["companyId"],
                project_id=parent["projectId"],
                lock=True,
            )
            if project["name"] != parent["projectName"]:
                raise HTTPException(status_code=409, detail="Объект подотчётной выдачи изменился")
            amount = _positive_amount((data or {}).get("amount"))
            if amount is None:
                raise HTTPException(status_code=400, detail="amount must be positive")
            cur.execute(
                """INSERT INTO public.accountable_expenses
                       (payment_id,company_id,project_id,company_scope_verified,
                        project_name,description,amount,photo_url,date,added_by)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     RETURNING id""",
                (
                    parent["id"], actor["companyId"], project["id"], True,
                    project["name"], (data or {}).get("description") or "",
                    amount, (data or {}).get("photoUrl") or "",
                    (data or {}).get("date") or None, actor_name(actor),
                ),
            )
            row = cur.fetchone()
            if _positive_int(_row_value(row, "id", 0)) is None:
                raise HTTPException(status_code=409, detail="Авансовый расход не создан")
            cur.execute(
                """UPDATE public.accountable_payments
                      SET spent_amount=spent_amount+%s
                    WHERE id=%s AND company_id=%s AND project_id=%s
                      AND company_scope_verified IS TRUE""",
                (amount, parent["id"], actor["companyId"], project["id"]),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Подотчётная выдача изменилась")
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
