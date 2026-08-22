"""Company-scoped expense-report routes."""

import json
import math
from collections.abc import Mapping
from datetime import date
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


def _nonnegative_amount(value):
    if type(value) not in (int, float):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _row_value(row, key, index):
    if isinstance(row, Mapping):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def register_expense_reports_module(app, deps):
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
                detail="Для авансовых отчётов выберите одну конкретную компанию",
            )
        company_id = _positive_int(
            (context or {}).get("companyId") or (context or {}).get("company_id")
        )
        if company_id is None:
            raise HTTPException(status_code=409, detail="Компания отчёта не определена")
        actors = [
            dict(actor or {})
            for actor in effective_company_actors(current_user, context)
            if str((actor or {}).get("role") or "").strip() in finance_roles
        ]
        if not actors:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет работать с отчётами",
            )
        if len(actors) != 1:
            raise HTTPException(
                status_code=409,
                detail="Для авансовых отчётов выберите одну конкретную компанию",
            )
        actor = actors[0]
        actor_company_id = _positive_int(
            actor.get("companyId") or actor.get("company_id")
        )
        if actor_company_id != company_id:
            raise HTTPException(
                status_code=409,
                detail="Компания отчёта не совпадает с выбранной компанией",
            )
        actor["companyId"] = company_id
        actor["company_id"] = company_id
        return actor

    def actor_name(actor):
        return str(
            actor.get("name") or actor.get("email") or actor.get("id") or ""
        ).strip()

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
            raise HTTPException(
                status_code=404,
                detail="Объект не найден в выбранной компании",
            )
        if len(rows) != 1:
            raise HTTPException(
                status_code=409,
                detail="Объект в выбранной компании неоднозначен",
            )
        row = rows[0]
        resolved_id = _positive_int(_row_value(row, "id", 0))
        resolved_name = str(_row_value(row, "name", 1) or "").strip()
        if resolved_id is None or not resolved_name:
            raise HTTPException(status_code=409, detail="Владелец объекта не определён")
        return {"id": resolved_id, "name": resolved_name}

    def exact_staff(cur, company_id, staff_id, *, lock=False):
        if _positive_int(staff_id) is None:
            raise HTTPException(status_code=400, detail="employeeId required")
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

    def verified_report(cur, company_id, report_id, *, lock=False):
        if _positive_int(report_id) is None:
            raise HTTPException(status_code=400, detail="id required")
        cur.execute(
            """SELECT id,company_id,project_id,project_name,status,purpose,
                      issued_amount
                 FROM public.expense_reports
                WHERE id=%s AND company_id=%s
                  AND company_scope_verified IS TRUE"""
            + (" FOR UPDATE" if lock else ""),
            (report_id, company_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Авансовый отчет не найден")
        result = {
            "id": _positive_int(_row_value(row, "id", 0)),
            "companyId": _positive_int(_row_value(row, "company_id", 1)),
            "projectId": _positive_int(_row_value(row, "project_id", 2)),
            "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
            "status": str(_row_value(row, "status", 4) or ""),
            "purpose": str(_row_value(row, "purpose", 5) or ""),
            "issuedAmount": _row_value(row, "issued_amount", 6),
        }
        if (
            result["id"] is None
            or result["companyId"] != company_id
            or result["projectId"] is None
        ):
            raise HTTPException(status_code=409, detail="Владелец отчёта не определён")
        return result

    @app.get("/expense-reports")
    def list_expense_reports(
        employee_id: int = None,
        project_name: str = None,
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
            where = ["company_id=%s", "company_scope_verified IS TRUE"]
            params = [actor["companyId"]]
            if employee_id is not None:
                employee = exact_staff(cur, actor["companyId"], employee_id)
                where.append("employee_id=%s")
                params.append(employee["id"])
            if str(project_name or "").strip():
                project = exact_project(
                    cur, actor["companyId"], project_name=project_name
                )
                where.append("project_id=%s")
                params.append(project["id"])
            cur.execute(
                """SELECT id,employee_id,employee_name,project_name,project_id,
                          report_type,purpose,total_amount,issued_amount,
                          spent_amount,balance,items_json,photo_url,date_from,
                          date_to,status,approved_by,approved_at,created_at
                     FROM public.expense_reports
                    WHERE """
                + " AND ".join(where)
                + " ORDER BY id DESC",
                tuple(params),
            )
            output = []
            for row in cur.fetchall() or []:
                raw_items = _row_value(row, "items_json", 11)
                try:
                    items = json.loads(raw_items) if raw_items else []
                except (TypeError, ValueError):
                    items = []
                output.append({
                    "id": _row_value(row, "id", 0),
                    "employeeId": _row_value(row, "employee_id", 1),
                    "employeeName": _row_value(row, "employee_name", 2) or "",
                    "projectName": _row_value(row, "project_name", 3) or "",
                    "projectId": _row_value(row, "project_id", 4),
                    "reportType": _row_value(row, "report_type", 5) or "Авансовый отчёт",
                    "purpose": _row_value(row, "purpose", 6) or "",
                    "totalAmount": float(_row_value(row, "total_amount", 7) or 0),
                    "issuedAmount": float(_row_value(row, "issued_amount", 8) or 0),
                    "spentAmount": float(_row_value(row, "spent_amount", 9) or 0),
                    "balance": float(_row_value(row, "balance", 10) or 0),
                    "items": items,
                    "photoUrl": _row_value(row, "photo_url", 12) or "",
                    "dateFrom": str(_row_value(row, "date_from", 13)) if _row_value(row, "date_from", 13) else "",
                    "dateTo": str(_row_value(row, "date_to", 14)) if _row_value(row, "date_to", 14) else "",
                    "status": _row_value(row, "status", 15) or "На утверждении",
                    "approvedBy": _row_value(row, "approved_by", 16) or "",
                    "approvedAt": str(_row_value(row, "approved_at", 17)) if _row_value(row, "approved_at", 17) else "",
                    "createdAt": str(_row_value(row, "created_at", 18)),
                })
            return output
        finally:
            cur.close()
            conn.close()

    @app.post("/expense-reports")
    def create_expense_report(
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
            project = exact_project(
                cur, actor["companyId"], project_id=data.get("projectId"), lock=True
            )
            employee = exact_staff(
                cur, actor["companyId"], data.get("employeeId"), lock=True
            )
            issued = _positive_amount(data.get("issuedAmount"))
            spent = _nonnegative_amount(data.get("spentAmount", 0))
            if issued is None:
                raise HTTPException(status_code=400, detail="issuedAmount required")
            if spent is None:
                raise HTTPException(status_code=400, detail="spentAmount invalid")
            items_value = data.get("items") or []
            if type(items_value) is not list:
                raise HTTPException(status_code=400, detail="items invalid")
            balance = issued - spent
            total = spent or issued
            cur.execute(
                """INSERT INTO public.expense_reports
                       (company_id,project_id,company_scope_verified,employee_id,
                        employee_name,project_name,report_type,purpose,total_amount,
                        issued_amount,spent_amount,balance,items_json,photo_url,
                        date_from,date_to,status)
                       VALUES (%s,%s,TRUE,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id""",
                (
                    actor["companyId"], project["id"], employee["id"],
                    employee["name"], project["name"],
                    str(data.get("reportType") or "Авансовый отчёт").strip(),
                    str(data.get("purpose") or "").strip(), total, issued, spent,
                    balance, json.dumps(items_value, ensure_ascii=False),
                    str(data.get("photoUrl") or "").strip(),
                    data.get("dateFrom") or None, data.get("dateTo") or None,
                    "На утверждении",
                ),
            )
            row = cur.fetchone()
            report_id = _positive_int(_row_value(row, "id", 0))
            if report_id is None:
                raise RuntimeError("expense report insert failed")
            conn.commit()
            return {"id": report_id, "ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/expense-reports/{id}")
    def update_expense_report(
        id: int,
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
            report = verified_report(cur, actor["companyId"], id, lock=True)
            sets, values = [], []
            if "status" in data:
                status = str(data.get("status") or "").strip()
                if status not in ("На утверждении", "Утверждён", "Отклонён"):
                    raise HTTPException(status_code=400, detail="status invalid")
                sets.append("status=%s")
                values.append(status)
                if status in ("Утверждён", "Отклонён"):
                    sets.extend(("approved_by=%s", "approved_at=%s"))
                    values.extend((actor_name(actor), date.today()))
            if "spentAmount" in data:
                spent = _nonnegative_amount(data.get("spentAmount"))
                try:
                    issued_value = float(report["issuedAmount"])
                except (TypeError, ValueError, OverflowError):
                    issued_value = None
                issued = _nonnegative_amount(issued_value)
                if spent is None or issued is None:
                    raise HTTPException(status_code=400, detail="spentAmount invalid")
                sets.extend(("spent_amount=%s", "balance=%s"))
                values.extend((spent, issued - spent))
            if "purpose" in data:
                sets.append("purpose=%s")
                values.append(str(data.get("purpose") or "").strip())
            if not sets:
                conn.rollback()
                return {"ok": True}
            values.extend((id, actor["companyId"], report["projectId"]))
            cur.execute(
                "UPDATE public.expense_reports SET "
                + ", ".join(sets)
                + " WHERE id=%s AND company_id=%s AND project_id=%s "
                  "AND company_scope_verified IS TRUE",
                tuple(values),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Владелец отчёта изменился")
            conn.commit()
            return {"ok": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/expense-reports/{id}")
    def delete_expense_report(
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
            report = verified_report(cur, actor["companyId"], id, lock=True)
            if report["status"] == "Аннулирован":
                conn.rollback()
                return {"ok": True, "cancelled": True, "alreadyCancelled": True}
            cancel_note = "Аннулировано без физического удаления " + date.today().isoformat()
            name = actor_name(actor)
            if name:
                cancel_note += " (" + name + ")"
            new_purpose = (
                (report["purpose"] + "\n" + cancel_note).strip()
                if report["purpose"] else cancel_note
            )
            cur.execute(
                """UPDATE public.expense_reports
                      SET status=%s,purpose=%s,approved_by=%s,approved_at=%s
                    WHERE id=%s AND company_id=%s AND project_id=%s
                      AND company_scope_verified IS TRUE""",
                (
                    "Аннулирован", new_purpose, name, date.today(), id,
                    actor["companyId"], report["projectId"],
                ),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Владелец отчёта изменился")
            conn.commit()
            return {"ok": True, "cancelled": True}
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
