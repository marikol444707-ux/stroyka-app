"""Company-scoped salary-payment routes."""

import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException


_MONTH_RE = re.compile(r"^(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])$")


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


def register_salary_payments_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    finance_roles = {
        str(role or "").strip() for role in (deps.get("finance_roles") or ())
    }

    def selected_actor(cur, current_user, action_mode, x_company_id, x_company_mode):
        context = resolve_work_company_context(
            cur, current_user, None, action_mode,
            x_company_id=x_company_id, x_company_mode=x_company_mode,
        )
        if (context or {}).get("mode") != "company":
            raise HTTPException(
                status_code=409,
                detail="Для зарплаты выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания выплаты не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in finance_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет работать с зарплатой",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для зарплаты выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания выплаты не совпадает с выбранной компанией",
            )
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def actor_name(actor):
        return str(
            actor.get("name") or actor.get("email") or actor.get("id") or ""
        ).strip()

    def exact_staff(cur, company_id, staff_id, *, lock=False):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="staffId required")
        cur.execute(
            """SELECT id,name
                 FROM public.staff
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR SHARE" if lock else ""),
            (staff_id, company_id),
        )
        row = cur.fetchone()
        resolved_id = _positive_int(_row_value(row, "id", 0))
        resolved_name = str(_row_value(row, "name", 1) or "").strip()
        if resolved_id is None or not resolved_name:
            raise HTTPException(
                status_code=404,
                detail="Сотрудник не найден в выбранной компании",
            )
        return {"id": resolved_id, "name": resolved_name}

    def verified_payment(cur, company_id, payment_id, *, lock=False):
        if _positive_int(payment_id) is None:
            raise HTTPException(status_code=400, detail="id required")
        cur.execute(
            """SELECT id,company_id,staff_id
                 FROM public.salary_payments
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR UPDATE" if lock else ""),
            (payment_id, company_id),
        )
        row = cur.fetchone()
        result = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "companyId": _positive_int(_row_value(row, "company_id", 1)),
            "staffId": _positive_int(_row_value(row, "staff_id", 2)),
        }
        if result["id"] is None:
            raise HTTPException(status_code=404, detail="Выплата не найдена")
        if result["companyId"] != company_id or result["staffId"] is None:
            raise HTTPException(status_code=409, detail="Владелец выплаты не определён")
        return result

    @app.get("/salary-payments")
    def get_salary_payments(
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
            cur.execute(
                """SELECT id,staff_id,staff_name,month,amount,paid_by,
                          paid_date,note,created_at
                     FROM public.salary_payments
                    WHERE company_id=%s
                      AND company_scope_verified IS TRUE
                    ORDER BY id DESC""",
                (actor["companyId"],),
            )
            return [{
                "id": _row_value(row, "id", 0),
                "staffId": _row_value(row, "staff_id", 1),
                "staffName": _row_value(row, "staff_name", 2) or "",
                "month": _row_value(row, "month", 3) or "",
                "amount": float(_row_value(row, "amount", 4) or 0),
                "paidBy": _row_value(row, "paid_by", 5) or "",
                "paidDate": _row_value(row, "paid_date", 6) or "",
                "note": _row_value(row, "note", 7) or "",
                "createdAt": str(_row_value(row, "created_at", 8)),
            } for row in (cur.fetchall() or [])]
        finally:
            cur.close()
            conn.close()

    @app.post("/salary-payments")
    def create_salary_payment(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(
                cur, current_user, "write", x_company_id, x_company_mode
            )
            staff = exact_staff(
                cur, actor["companyId"], data.get("staffId"), lock=True
            )
            month = str(data.get("month") or "").strip()
            if not _MONTH_RE.fullmatch(month):
                raise HTTPException(status_code=400, detail="month invalid")
            amount = _positive_amount(data.get("amount"))
            if amount is None:
                raise HTTPException(status_code=400, detail="amount required")
            cur.execute(
                """INSERT INTO public.salary_payments
                       (company_id,company_scope_verified,staff_id,staff_name,
                        month,amount,paid_by,paid_date,note)
                       VALUES (%s,TRUE,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                (
                    actor["companyId"], staff["id"], staff["name"], month,
                    amount, actor_name(actor), date.today().isoformat(),
                    str(data.get("note") or "").strip(),
                ),
            )
            row = cur.fetchone()
            new_id = _positive_int(_row_value(row, "id", 0))
            if new_id is None:
                raise RuntimeError("salary payment insert failed")
            conn.commit()
            return {"ok": True, "id": new_id}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/salary-payments/{id}")
    def delete_salary_payment(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = selected_actor(
                cur, current_user, "write", x_company_id, x_company_mode
            )
            payment = verified_payment(cur, actor["companyId"], id, lock=True)
            cur.execute(
                """DELETE FROM public.salary_payments
                    WHERE id=%s AND company_id=%s AND staff_id=%s
                      AND company_scope_verified IS TRUE""",
                (id, actor["companyId"], payment["staffId"]),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Владелец выплаты изменился")
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
