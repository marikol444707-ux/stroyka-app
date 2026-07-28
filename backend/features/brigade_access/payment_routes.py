"""Brigade payment routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 14):
GET/POST /brigade-payments and DELETE /brigade-payments/{id} keep
their URLs, company-scoped contract resolution, act-scan payment
guard, overpayment ceiling and the project-payment mirror/reversal
logic. Contract scope helpers stay in main.py and arrive through
deps; child-row and amount guards come from this feature's service.
"""

import datetime as dt
import math
from typing import Optional

from fastapi import Depends, Header, HTTPException

try:
    from backend.features.brigade_access.service import (
        require_brigade_child_company,
        require_brigade_project_payment_link,
        require_positive_brigade_amount,
    )
except ModuleNotFoundError:
    from features.brigade_access.service import (
        require_brigade_child_company,
        require_brigade_project_payment_link,
        require_positive_brigade_amount,
    )


def register_brigade_payments_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    finance_roles = tuple(deps.get("finance_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    brigade_contract_read_scope = deps["brigade_contract_read_scope"]
    resolve_brigade_contract_actor = deps["resolve_brigade_contract_actor"]
    row_get = deps["row_get"]

    @app.get("/brigade-payments")
    def get_brigade_payments(
        contract_id: int = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        try:
            visibility_sql, params, _actors = brigade_contract_read_scope(
                conn,
                _current_user,
                (*finance_roles, *worker_execution_roles),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            if visibility_sql == "FALSE":
                return []
            where = [
                visibility_sql,
                "bp.amount IS NOT NULL",
                "bp.amount NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)",
            ]
            if contract_id:
                where.append("bc.id=%s")
                params.append(contract_id)
            cur = conn.cursor()
            try:
                cur.execute("""SELECT bp.id,bp.contract_id,bp.amount,bp.paid_by,bp.paid_date,
                                      bp.note,bp.created_at,bp.company_id
                               FROM brigade_payments bp
                               JOIN brigade_contracts bc
                                 ON bc.id=bp.contract_id AND bc.company_id=bp.company_id
                               WHERE """ + " AND ".join(where) + " ORDER BY bp.id DESC", tuple(params))
                rows = cur.fetchall()
            finally:
                cur.close()
            return [{
                "id": row[0], "contractId": row[1], "amount": float(row[2] or 0),
                "paidBy": row[3] or "", "paidDate": str(row[4]) if row[4] else "",
                "note": row[5] or "", "createdAt": str(row[6]), "companyId": row[7],
            } for row in rows]
        finally:
            conn.close()

    @app.post("/brigade-payments")
    def create_brigade_payment(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
        try:
            contract, actor, _project = resolve_brigade_contract_actor(
                cur,
                _current_user,
                data.get("contractId"),
                finance_roles,
                claimed_company_id=claimed_company_id,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            company_id = int(contract["companyId"])
            cur.execute("""SELECT company_id FROM brigade_payments
                           WHERE contract_id=%s AND company_id IS DISTINCT FROM %s
                           LIMIT 1""", (contract["id"], company_id))
            inconsistent_payment = cur.fetchone()
            if inconsistent_payment:
                require_brigade_child_company(
                    row_get(inconsistent_payment, "company_id", 0),
                    company_id,
                )
            cur.execute("""SELECT id FROM brigade_payments
                           WHERE contract_id=%s AND company_id=%s
                             AND (amount IS NULL
                                  OR amount IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric))
                           LIMIT 1""", (contract["id"], company_id))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="В выплатах договора найдена некорректная сумма. Нужна ручная сверка.",
                )
            if not (contract["actScanUrl"] or "").strip():
                raise HTTPException(status_code=400, detail="Оплата заблокирована: загрузите скан подписанного акта")
            amount = require_positive_brigade_amount(data.get("amount"))
            cur.execute("""SELECT
                                  COALESCE((SELECT SUM(CASE WHEN COALESCE(quantity,0)>0 THEN GREATEST(0, LEAST(COALESCE(done_quantity,0), COALESCE(quantity,0))) * COALESCE(price_brigade,0) ELSE 0 END)
                                              FROM brigade_contract_items WHERE contract_id=%s),0) AS done_amount,
                                  COALESCE((SELECT SUM(COALESCE(amount,0))
                                             FROM brigade_payments
                                             WHERE contract_id=%s AND company_id=%s
                                               AND amount IS NOT NULL
                                               AND amount NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)),0) AS paid_amount""",
                        (contract["id"], contract["id"], company_id))
            amounts = cur.fetchone()
            done_amount = float(row_get(amounts, "done_amount", 0, 0) or 0)
            paid_amount = float(row_get(amounts, "paid_amount", 1, 0) or 0)
            if not math.isfinite(done_amount) or not math.isfinite(paid_amount):
                raise HTTPException(
                    status_code=409,
                    detail="В договоре найдена некорректная сумма. Нужна ручная сверка.",
                )
            available_to_pay = max(0, done_amount - paid_amount)
            if float(amount) > available_to_pay + 0.01:
                raise HTTPException(status_code=400, detail=f"Оплата превышает выполненный неоплаченный объём. Доступно к оплате: {available_to_pay:.2f} ₽")
            project_name = (contract["projectName"] or "").strip()
            if not project_name:
                raise HTTPException(status_code=409, detail="У договора не определен объект для денежной проводки")
            paid_by = data.get("paidBy", "")
            paid_date = data.get("paidDate") or None
            cur.execute("""INSERT INTO brigade_payments
                              (company_id,contract_id,amount,paid_by,paid_date,note)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (company_id, contract["id"], amount, paid_by, paid_date, data.get("note", "")))
            new_id = cur.fetchone()[0]
            payment_note = "Оплата бригаде " + contract["brigadeName"]
            cur.execute("""INSERT INTO project_payments
                               (company_id,project_name,amount,note,date,added_by)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (company_id, project_name, amount, payment_note, paid_date, paid_by))
            project_payment_id = cur.fetchone()[0]
            cur.execute("""UPDATE brigade_payments
                           SET project_payment_id=%s
                           WHERE id=%s AND company_id=%s""",
                        (project_payment_id, new_id, company_id))
            conn.commit()
            return {"ok": True, "id": new_id, "companyId": company_id, "projectPaymentId": project_payment_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete("/brigade-payments/{id}")
    def delete_brigade_payment(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute("SELECT contract_id FROM brigade_payments WHERE id=%s", (id,))
            payment_link = cur.fetchone()
            if not payment_link:
                return {"ok": True}
            contract_id = row_get(payment_link, "contract_id", 0)
            contract, actor, _project = resolve_brigade_contract_actor(
                cur,
                _current_user,
                contract_id,
                finance_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            company_id = int(contract["companyId"])
            cur.execute("""SELECT paid_by,company_id,project_payment_id
                           FROM brigade_payments
                           WHERE id=%s AND contract_id=%s
                           FOR UPDATE""", (id, contract["id"]))
            payment = cur.fetchone()
            if not payment:
                return {"ok": True}
            require_brigade_child_company(
                row_get(payment, "company_id", 1),
                company_id,
            )
            paid_by = row_get(payment, "paid_by", 0, "") or ""
            linked_project_payment_id = require_brigade_project_payment_link(
                row_get(payment, "project_payment_id", 2),
            )
            cur.execute("""SELECT id,project_name,COALESCE(work_package,''),amount,note,date,added_by
                           FROM project_payments
                           WHERE id=%s AND company_id=%s
                           FOR UPDATE""", (linked_project_payment_id, company_id))
            project_payment = cur.fetchone()
            if not project_payment:
                raise HTTPException(
                    status_code=409,
                    detail="Связанная денежная проводка не найдена в компании. Нужна ручная сверка.",
                )
            if project_payment[3] is None:
                raise HTTPException(
                    status_code=409,
                    detail="В денежной проводке не указана сумма. Нужна ручная сверка.",
                )
            project_payment_amount = float(project_payment[3])
            if not math.isfinite(project_payment_amount):
                raise HTTPException(
                    status_code=409,
                    detail="В денежной проводке найдена некорректная сумма. Нужна ручная сверка.",
                )
            cur.execute(
                "DELETE FROM brigade_payments WHERE id=%s AND contract_id=%s AND company_id=%s",
                (id, contract["id"], company_id),
            )
            project_payment_reversal_id = None
            reversal_project_name = project_payment[1] or contract["projectName"]
            payment_note = project_payment[4] or ("Оплата бригаде " + contract["brigadeName"])
            reversal_note = "Сторно платежа #" + str(project_payment[0]) + ": " + payment_note
            cur.execute("""SELECT id FROM project_payments
                           WHERE company_id=%s AND project_name=%s
                             AND amount=%s AND COALESCE(note,'')=%s
                           ORDER BY id DESC LIMIT 1""",
                        (company_id, reversal_project_name, -project_payment_amount, reversal_note))
            existing_reversal = cur.fetchone()
            if existing_reversal:
                project_payment_reversal_id = existing_reversal[0]
            else:
                cur.execute("""INSERT INTO project_payments
                                   (company_id,project_name,work_package,amount,note,date,added_by)
                               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                            (company_id, reversal_project_name, project_payment[2] or "",
                             -project_payment_amount, reversal_note,
                             dt.date.today().isoformat(), actor.get("name") or paid_by))
                project_payment_reversal_id = cur.fetchone()[0]
            conn.commit()
            return {
                "ok": True,
                "companyId": company_id,
                "projectPaymentReversalId": project_payment_reversal_id,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
