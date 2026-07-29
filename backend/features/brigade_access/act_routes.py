"""Brigade act routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 28):
GET/POST /brigade-acts keep their URLs, company-scoped contract
resolution, package check and the acted-amount ceiling.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException


def register_brigade_acts_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    finance_roles = tuple(deps.get("finance_roles") or ())
    brigade_contract_read_scope = deps["brigade_contract_read_scope"]
    resolve_brigade_contract_actor = deps["resolve_brigade_contract_actor"]
    has_package_access = deps["has_package_access"]
    row_get = deps["row_get"]

    @app.get("/brigade-acts")
    def get_brigade_acts(
        contract_id: int = None,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        try:
            allowed_roles = (*finance_roles, "прораб", "главный_инженер", "сметчик")
            visibility_sql, params, _actors = brigade_contract_read_scope(
                conn,
                current_user,
                allowed_roles,
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            if visibility_sql == "FALSE":
                return []
            where = [visibility_sql]
            if contract_id:
                where.append("bc.id=%s")
                params.append(contract_id)
            cur = conn.cursor()
            try:
                cur.execute("""SELECT ba.id,ba.contract_id,ba.project_name,ba.brigade_name,
                                      ba.period_from,ba.period_to,ba.total_amount,ba.status,
                                      ba.created_at,bc.company_id
                               FROM brigade_acts ba
                               JOIN brigade_contracts bc ON bc.id=ba.contract_id
                               WHERE """ + " AND ".join(where) + " ORDER BY ba.id DESC", tuple(params))
                rows = cur.fetchall()
            finally:
                cur.close()
            return [{
                "id": row[0], "contractId": row[1], "projectName": row[2],
                "brigadeName": row[3], "periodFrom": str(row[4]) if row[4] else "",
                "periodTo": str(row[5]) if row[5] else "", "totalAmount": float(row[6] or 0),
                "status": row[7], "createdAt": str(row[8]), "companyId": row[9],
            } for row in rows]
        finally:
            conn.close()

    @app.post("/brigade-acts")
    def create_brigade_act(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            contract, actor, project = resolve_brigade_contract_actor(
                cur,
                current_user,
                data.get("contractId"),
                (*finance_roles, "прораб", "главный_инженер", "сметчик"),
                claimed_company_id=data.get("companyId") if "companyId" in data else data.get("company_id"),
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                for_update=True,
            )
            if data.get("projectName") and (data.get("projectName") or "").strip() != contract["projectName"]:
                raise HTTPException(status_code=403, detail="Договор бригады относится к другому объекту")
            if not has_package_access(actor, contract["workPackage"]):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету работ договора")
            total_amount = float(data.get("totalAmount") or 0)
            cur.execute("""SELECT COALESCE((
                                       SELECT SUM(CASE WHEN COALESCE(quantity,0)>0
                                                       THEN GREATEST(0, LEAST(COALESCE(done_quantity,0), COALESCE(quantity,0))) * COALESCE(price_brigade,0)
                                                       ELSE 0 END)
                                         FROM brigade_contract_items WHERE contract_id=%s
                                   ),0) AS done_amount,
                                   COALESCE((
                                       SELECT SUM(COALESCE(total_amount,0))
                                         FROM brigade_acts
                                        WHERE contract_id=%s AND COALESCE(status,'') <> 'Аннулирован'
                                   ),0) AS acted_amount""", (contract["id"], contract["id"]))
            totals = cur.fetchone()
            available_to_act = max(0, float(row_get(totals, "done_amount", 0, 0) or 0) - float(row_get(totals, "acted_amount", 1, 0) or 0))
            if total_amount <= 0:
                raise HTTPException(status_code=400, detail="Сумма акта должна быть больше нуля")
            if total_amount > available_to_act + 0.01:
                raise HTTPException(status_code=400, detail=f"Сумма акта превышает выполненный неактированный объём. Доступно к акту: {available_to_act:.2f} ₽")
            cur.execute("INSERT INTO brigade_acts (contract_id,project_name,brigade_name,period_from,period_to,total_amount,status) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (contract["id"], contract["projectName"], contract["brigadeName"] or data.get("brigadeName",""), data.get("periodFrom") or None, data.get("periodTo") or None, total_amount, data.get("status","Черновик")))
            row = cur.fetchone()
            conn.commit()
            return {"id": row_get(row, "id", 0), "ok": True, "companyId": contract["companyId"], "projectId": project["id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
