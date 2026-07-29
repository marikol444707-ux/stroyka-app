"""Interim act routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 24):
the five /interim-acts routes keep their URLs, role guards,
confirmed-work ceilings, daily-act protections, payment mirroring
into project_payments and audit logging. The daily-act sync helpers
stay in main.py (the work journal calls them); everything the routes
need arrives through deps. The model moved here — sole user.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel


class InterimActModel(BaseModel):
    masterId: int
    masterName: str
    project: str
    workPackage: str = ""
    periodStart: str
    periodEnd: str
    totalAmount: float = 0
    paidAmount: float = 0
    contractId: Optional[int] = None
    workJournalIds: list[int] = []


def register_interim_acts_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    contract_roles = tuple(deps.get("contract_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    delete_roles = tuple(deps.get("delete_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    visible_project_names = deps["visible_project_names"]
    package_access_filter = deps["package_access_filter"]
    require_project_access = deps["require_project_access"]
    has_package_access = deps["has_package_access"]
    require_row_project_access = deps["require_row_project_access"]
    confirmed_execution_total_for_act = deps["confirmed_execution_total_for_act"]
    resolve_project_payment_actor = deps["resolve_project_payment_actor"]
    daily_work_act_source_type = deps["daily_work_act_source_type"]
    interim_act_locked_statuses = deps["interim_act_locked_statuses"]
    log_audit = deps["log_audit"]

    @app.get("/interim-acts")
    def get_interim_acts(_current_user: dict = Depends(require_roles(*contract_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        allowed_projects = visible_project_names(_current_user)
        if allowed_projects is not None and not allowed_projects:
            conn.close()
            return []
        where, params = [], []
        if allowed_projects is not None:
            where.append("project = ANY(%s)")
            params.append(allowed_projects)
        if _current_user.get("role") in worker_execution_roles:
            where.append("(COALESCE(master_id,0)=%s OR (COALESCE(master_id,0)=0 AND master_name=%s))")
            params.extend([_current_user.get("id"), _current_user.get("name") or ""])
        package_sql, package_params = package_access_filter(_current_user)
        if package_sql:
            where.append("1=1" + package_sql)
            params.extend(package_params)
        q = "SELECT id,master_id as \"masterId\",master_name as \"masterName\",project,COALESCE(work_package,'') as \"workPackage\",period_start as \"periodStart\",period_end as \"periodEnd\",total_amount as \"totalAmount\",paid_amount as \"paidAmount\",contract_id as \"contractId\",status,scan_url as \"scanUrl\",COALESCE(work_journal_ids,'[]') as \"workJournalIds\",COALESCE(source_type,'') as \"sourceType\",COALESCE(photo_urls,'[]') as \"photoUrls\" FROM interim_acts"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC"
        cur.execute(q, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/interim-acts")
    def create_interim_act(a: InterimActModel, _current_user: dict = Depends(require_roles(*finance_roles))):
        require_project_access(_current_user, a.project)
        if not has_package_access(_current_user, a.workPackage or ""):
            raise HTTPException(status_code=403, detail="Нет доступа к этому пакету работ")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        total_amount = float(a.totalAmount or 0)
        paid_amount = float(a.paidAmount or 0)
        if _current_user.get("role") not in finance_roles and paid_amount > 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Оплату по акту указывает только директор, замдиректора или бухгалтер")
        available_total = confirmed_execution_total_for_act(cur, a.masterId, a.masterName, a.project, a.workPackage, a.periodStart, a.periodEnd)
        if total_amount <= 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Сумма акта должна быть больше нуля")
        if total_amount > available_total + 0.01:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail=f"Сумма акта превышает подтверждённые работы за период. Доступно к акту: {available_total:.2f} ₽")
        if paid_amount < 0 or paid_amount > total_amount + 0.01:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Оплата по акту не может быть меньше 0 или больше суммы акта")
        import json as _json
        work_journal_ids = [int(x) for x in (a.workJournalIds or []) if str(x).isdigit()]
        if not work_journal_ids:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Акт должен быть привязан к конкретным подтверждённым работам ЖПР")
        package = (a.workPackage or "Основная").strip() or "Основная"
        master_name = (a.masterName or "").strip().lower()
        cur.execute("""SELECT id, COALESCE(execution_total,0) AS execution_total
                       FROM work_journal
                       WHERE id = ANY(%s)
                         AND project=%s
                         AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                         AND status='Подтверждено'
                         AND (room_id IS NOT NULL OR COALESCE(NULLIF(room_name,''),'') <> '')
                         AND date BETWEEN %s AND %s
                         AND ((%s::int IS NOT NULL AND master_id=%s) OR (%s::int IS NULL AND LOWER(TRIM(COALESCE(master_name,'')))=%s))""",
                    (work_journal_ids, a.project, package, a.periodStart, a.periodEnd, a.masterId, a.masterId, a.masterId, master_name))
        selected_rows = cur.fetchall() or []
        selected_ids = {int(r["id"]) for r in selected_rows}
        missing_ids = sorted(set(work_journal_ids) - selected_ids)
        if missing_ids:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="В акт попали работы не этого исполнителя, пакета или периода: " + ", ".join(map(str, missing_ids[:10])))
        cur.execute("""SELECT id FROM interim_acts
                       WHERE COALESCE(status,'') <> 'Аннулирован'
                         AND COALESCE(source_type,'') <> %s
                         AND COALESCE(NULLIF(work_journal_ids,''),'[]')::jsonb ?| %s
                       LIMIT 1""", (daily_work_act_source_type, [str(x) for x in work_journal_ids]))
        duplicate_act = cur.fetchone()
        if duplicate_act:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Одна или несколько работ ЖПР уже включены в другой акт")
        selected_total = sum(float(r["execution_total"] or 0) for r in selected_rows)
        if abs(total_amount - selected_total) > 0.01:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail=f"Сумма акта должна равняться выбранным подтверждённым ЖПР: {selected_total:.2f} ₽. Удержания и частичную оплату фиксируйте отдельными полями.")
        cur.execute("""INSERT INTO interim_acts
                       (master_id,master_name,project,work_package,period_start,period_end,total_amount,paid_amount,contract_id,work_journal_ids)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (a.masterId,a.masterName,a.project,a.workPackage or "",a.periodStart,a.periodEnd,total_amount,paid_amount,a.contractId,_json.dumps(work_journal_ids, ensure_ascii=False)))
        row = cur.fetchone()
        conn.commit()
        conn.close()
        return dict(row)

    @app.put("/interim-acts/{id}")
    def update_interim_act(id: int, data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        import json as _json
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "interim_acts", id, _current_user, "project")
        cur.execute("""SELECT master_id, master_name, project, COALESCE(NULLIF(work_package,''),'Основная'),
                              period_start, period_end, total_amount, paid_amount,
                              COALESCE(status,''), COALESCE(scan_url,''), COALESCE(work_journal_ids,'[]'),
                              COALESCE(source_type,'')
                       FROM interim_acts WHERE id=%s""", (id,))
        act_row = cur.fetchone()
        if not act_row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Акт не найден")
        master_id, master_name, project, work_package, period_start, period_end, total_amount, current_paid, current_status, scan_url, current_work_ids, source_type = act_row
        if not has_package_access(_current_user, work_package or "Основная"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к разделу сметы акта")
        total_amount = float(total_amount or 0)
        current_paid = float(current_paid or 0)
        new_paid = float(data.get("paidAmount", current_paid) or 0)
        new_total = float(data.get("totalAmount", total_amount) or 0)
        finance_update_keys = {"paidAmount", "totalAmount", "workJournalIds"}
        finance_statuses = interim_act_locked_statuses
        if str(source_type or "") == daily_work_act_source_type and (
            any(k in data for k in finance_update_keys) or str(data.get("status") or "") in finance_statuses
        ):
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Дневной акт является контрольным пакетом. Для оплаты сформируйте акт подрядчику за месяц, период или всё время работ.")
        if _current_user.get("role") not in finance_roles and (
            any(k in data for k in finance_update_keys) or str(data.get("status") or "") in finance_statuses
        ):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Финансовые поля и оплату акта меняет только директор, замдиректора или бухгалтер")
        if "workJournalIds" in data or "totalAmount" in data:
            if current_status in ("Подписан", "Оплачен", "Частично оплачен", "Оплачен частично"):
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Подписанный или оплаченный акт нельзя менять. Создайте новый акт корректировки.")
            work_journal_ids = [int(x) for x in (data.get("workJournalIds") or []) if str(x).isdigit()]
            if not work_journal_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Акт должен быть привязан к конкретным подтверждённым работам ЖПР")
            master_name_key = (master_name or "").strip().lower()
            cur.execute("""SELECT id, COALESCE(execution_total,0) AS execution_total
                           FROM work_journal
                           WHERE id = ANY(%s)
                             AND project=%s
                             AND COALESCE(NULLIF(work_package,''),'Основная')=%s
                             AND status='Подтверждено'
                             AND (room_id IS NOT NULL OR COALESCE(NULLIF(room_name,''),'') <> '')
                             AND date BETWEEN %s AND %s
                             AND ((%s::int IS NOT NULL AND master_id=%s) OR (%s::int IS NULL AND LOWER(TRIM(COALESCE(master_name,'')))=%s))""",
                        (work_journal_ids, project, work_package, period_start, period_end, master_id, master_id, master_id, master_name_key))
            selected_rows = cur.fetchall() or []
            selected_ids = {int(r[0]) for r in selected_rows}
            missing_ids = sorted(set(work_journal_ids) - selected_ids)
            if missing_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="В акт попали работы не этого исполнителя, пакета или периода: " + ", ".join(map(str, missing_ids[:10])))
            cur.execute("""SELECT id FROM interim_acts
                           WHERE id<>%s
                             AND COALESCE(status,'') <> 'Аннулирован'
                             AND COALESCE(source_type,'') <> %s
                             AND COALESCE(NULLIF(work_journal_ids,''),'[]')::jsonb ?| %s
                           LIMIT 1""", (id, daily_work_act_source_type, [str(x) for x in work_journal_ids]))
            duplicate_act = cur.fetchone()
            if duplicate_act:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Одна или несколько работ ЖПР уже включены в другой акт")
            selected_total = sum(float(r[1] or 0) for r in selected_rows)
            if abs(new_total - selected_total) > 0.01:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail=f"Сумма акта должна равняться выбранным подтверждённым ЖПР: {selected_total:.2f} ₽")
            cur.execute("UPDATE interim_acts SET total_amount=%s, work_journal_ids=%s WHERE id=%s",
                        (new_total, _json.dumps(work_journal_ids, ensure_ascii=False), id))
            total_amount = new_total
        if new_paid < 0 or new_paid > total_amount + 0.01:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Оплата по акту не может быть меньше 0 или больше суммы акта")
        if data.get("status") == "Оплачен" and new_paid <= 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Нельзя отметить акт оплаченным без суммы оплаты")
        if 'status' in data:
            cur.execute("UPDATE interim_acts SET status=%s WHERE id=%s", (data['status'],id))
        if 'paidAmount' in data:
            cur.execute("UPDATE interim_acts SET paid_amount=%s WHERE id=%s", (data['paidAmount'],id))
        if 'scanUrl' in data:
            cur.execute("UPDATE interim_acts SET scan_url=%s WHERE id=%s", (data['scanUrl'],id))
        conn.commit()
        log_audit(
            _current_user.get("name", ""),
            _current_user.get("role", ""),
            str(data.get("status") or "update"),
            "interim_act",
            id,
            ("Акт исполнителя обновлен: " + str(master_name or "") + ", статус " + str(data.get("status") or current_status or ""))[:250],
            project or "",
        )
        conn.close()
        return {"ok": True}

    @app.post("/interim-acts/{id}/pay")
    def pay_interim_act(
        id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute("""SELECT total_amount, paid_amount, project, COALESCE(work_package,''), master_name, COALESCE(source_type,'')
                           FROM interim_acts WHERE id=%s FOR UPDATE""", (id,))
            act = cur.fetchone()
            if not act:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Акт не найден")
            project = act[2] or ""
            work_package = act[3] or "Основная"
            source_type = act[5] or ""
            if source_type == daily_work_act_source_type:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Дневной акт является контрольным пакетом. Для оплаты сформируйте акт подрядчику за месяц, период или всё время работ.")
            claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
            company_id, actor = resolve_project_payment_actor(
                cur,
                _current_user,
                project,
                work_package,
                claimed_company_id=claimed_company_id,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                require_unambiguous_project=True,
            )
            _current_user = actor
            total_amount = float(act[0] or 0)
            current_paid = float(act[1] or 0)
            amount = float(data.get("amount") or 0)
            if amount <= 0:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Сумма оплаты должна быть больше нуля")
            next_paid = current_paid + amount
            if next_paid > total_amount + 0.01:
                conn.rollback()
                raise HTTPException(status_code=400, detail=f"Оплата превышает сумму акта. Остаток к оплате: {max(0, total_amount-current_paid):.2f} ₽")
            status = "Оплачен" if next_paid >= total_amount - 0.01 else "Частично оплачен"
            cur.execute("UPDATE interim_acts SET paid_amount=%s, status=%s WHERE id=%s", (next_paid, status, id))
            paid_by = data.get("paidBy") or _current_user.get("name") or ""
            paid_date = data.get("paidDate") or None
            note = data.get("note") or ("Оплата исполнителю " + (act[4] or "") + " · акт #" + str(id))
            cur.execute("""INSERT INTO project_payments
                               (company_id,project_name,amount,note,date,added_by,work_package)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (company_id, project, -amount, note, paid_date, paid_by, work_package))
            payment_id = cur.fetchone()[0]
            conn.commit()
            log_audit(
                _current_user.get("name", ""),
                _current_user.get("role", ""),
                "pay",
                "interim_act",
                id,
                ("Оплата акта исполнителя: " + str(amount) + " ₽, статус " + str(status))[:250],
                project,
            )
            return {"ok": True, "paidAmount": next_paid, "status": status, "projectPaymentId": payment_id}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cur.close()
            conn.close()

    @app.delete("/interim-acts/{id}")
    def delete_interim_act(id: int, _current_user: dict = Depends(require_roles(*delete_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "interim_acts", id, _current_user, "project")
        cur.execute("SELECT COALESCE(work_package,''), COALESCE(project,''), COALESCE(master_name,'') FROM interim_acts WHERE id=%s", (id,))
        act_row = cur.fetchone()
        if act_row and not has_package_access(_current_user, act_row[0] or "Основная"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к разделу сметы акта")
        cur.execute("UPDATE interim_acts SET status='Аннулирован' WHERE id=%s", (id,))
        conn.commit()
        log_audit(
            _current_user.get("name", ""),
            _current_user.get("role", ""),
            "cancel",
            "interim_act",
            id,
            ("Акт исполнителя аннулирован: " + str(act_row[2] if act_row else ""))[:250],
            (act_row[1] if act_row else "") or "",
        )
        conn.close()
        return {"ok": True}
