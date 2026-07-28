"""Project payment routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 23):
GET/POST /project-payments and DELETE /project-payments/{id} keep
their URLs, company-scoped visibility, duplicate guard and the
reversal (storno) flow. The visibility filter comes from this
feature's service; company actor resolution from company_context.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.features.project_payment_access.service import project_payment_visibility_filter
    from backend.features.company_context.service import resolve_resource_company_actor
except ModuleNotFoundError:
    from features.project_payment_access.service import project_payment_visibility_filter
    from features.company_context.service import resolve_resource_company_actor


def register_project_payments_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    finance_roles = tuple(deps.get("finance_roles") or ())
    platform_staff_roles = tuple(deps.get("platform_staff_roles") or ())
    client_account_roles = tuple(deps.get("client_account_roles") or ())
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    resolve_project_payment_actor = deps["resolve_project_payment_actor"]
    positive_int_or_none = deps["positive_int_or_none"]
    require_project_access = deps["require_project_access"]
    has_package_access = deps["has_package_access"]

    @app.get("/project-payments")
    def get_project_payments(
        project_name: str = "",
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = resolve_work_company_context(
                cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            visibility_sql, params = project_payment_visibility_filter(
                effective_company_actors(current_user, company_context),
                finance_roles,
            )
            if visibility_sql == "FALSE":
                return []
            where = [visibility_sql]
            if project_name:
                where.append("pp.project_name=%s")
                params.append(project_name)
            cur.execute(f"""SELECT id,company_id,project_name,amount,note,date,added_by,
                                   COALESCE(work_package,'') AS work_package
                            FROM (
                                SELECT DISTINCT ON (
                                    pp.company_id, pp.project_name, COALESCE(pp.work_package,''),
                                    pp.amount, COALESCE(pp.note,''), pp.date, COALESCE(pp.added_by,'')
                                )
                                    pp.id,pp.company_id,pp.project_name,pp.amount,pp.note,pp.date,
                                    pp.added_by,pp.work_package
                                FROM project_payments pp
                                WHERE {' AND '.join(where)}
                                ORDER BY pp.company_id, pp.project_name, COALESCE(pp.work_package,''),
                                         pp.amount, COALESCE(pp.note,''), pp.date,
                                         COALESCE(pp.added_by,''), pp.id DESC
                            ) p
                            ORDER BY id DESC""", tuple(params))
            rows = cur.fetchall()
            return [{
                "id": row.get("id"),
                "companyId": row.get("company_id"),
                "projectName": row.get("project_name") or "",
                "amount": float(row.get("amount") or 0),
                "note": row.get("note") or "",
                "date": str(row.get("date")) if row.get("date") else "",
                "addedBy": row.get("added_by") or "",
                "workPackage": row.get("work_package") or "",
            } for row in rows]
        finally:
            cur.close(); conn.close()

    @app.post("/project-payments")
    def create_project_payment(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            project_name = str(data.get("projectName") or data.get("project_name") or "").strip()
            amount = data.get("amount", 0)
            note = data.get("note", "")
            work_package = (data.get("workPackage") or data.get("work_package") or "").strip()
            pay_date = data.get("date") or None
            added_by = data.get("addedBy") or data.get("paidBy") or ""
            claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
            company_id, _actor = resolve_project_payment_actor(
                cur,
                _current_user,
                project_name,
                work_package,
                claimed_company_id=claimed_company_id,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            if note:
                cur.execute("""SELECT id FROM project_payments
                               WHERE company_id=%s AND project_name=%s
                                 AND COALESCE(work_package,'')=%s AND amount=%s
                                 AND COALESCE(note,'')=%s AND date IS NOT DISTINCT FROM %s
                                 AND COALESCE(added_by,'')=%s
                               ORDER BY id DESC LIMIT 1""",
                            (company_id, project_name, work_package, amount, note, pay_date, added_by))
                existing = cur.fetchone()
                if existing:
                    return {"id": existing.get("id"), "companyId": company_id, "ok": True, "duplicate": True}
            cur.execute("""INSERT INTO project_payments
                               (company_id,project_name,work_package,amount,note,date,added_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (company_id, project_name, work_package, amount, note, pay_date, added_by))
            row = cur.fetchone()
            conn.commit()
            return {"id": row.get("id"), "companyId": company_id, "ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()

    @app.delete("/project-payments/{id}")
    def delete_project_payment(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        from datetime import date
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""SELECT company_id,project_name,COALESCE(work_package,'') AS work_package,
                                  amount,note,date,added_by
                           FROM project_payments WHERE id=%s FOR UPDATE""", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Платеж по объекту не найден")
            _company_context, actor = resolve_resource_company_actor(
                cur,
                _current_user,
                row.get("company_id"),
                "delete",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                allowed_roles=finance_roles,
                forbidden_detail="Роль в выбранной компании не позволяет сторнировать платеж",
                platform_staff_roles=platform_staff_roles,
                client_account_roles=client_account_roles,
            )
            company_id = positive_int_or_none(row.get("company_id"))
            project_name = row.get("project_name") or ""
            work_package = row.get("work_package") or ""
            require_project_access(actor, project_name)
            if not has_package_access(actor, work_package or "Основная"):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету платежа")
            amount = row.get("amount") or 0
            note = row.get("note") or ""
            reversal_note = "Сторно платежа #" + str(id)
            if note:
                reversal_note += ": " + str(note)
            cur.execute("""SELECT id FROM project_payments
                           WHERE company_id=%s AND project_name=%s
                             AND COALESCE(work_package,'')=%s AND amount=%s
                             AND COALESCE(note,'')=%s
                           ORDER BY id DESC LIMIT 1""",
                        (company_id, project_name, work_package, -amount, reversal_note))
            existing = cur.fetchone()
            if existing:
                conn.rollback()
                return {
                    "ok": True,
                    "reversed": True,
                    "alreadyReversed": True,
                    "reversalId": existing.get("id"),
                }
            actor_name = actor.get("name") or row.get("added_by") or ""
            cur.execute("""INSERT INTO project_payments
                               (company_id,project_name,work_package,amount,note,date,added_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (company_id, project_name, work_package, -amount, reversal_note,
                         date.today().isoformat(), actor_name))
            reversal = cur.fetchone()
            conn.commit()
            return {
                "ok": True,
                "companyId": company_id,
                "reversed": True,
                "reversalId": reversal.get("id"),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
