"""Supply history routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 22):
GET/POST /supply-history and PUT /supply-history/{id} keep their
URLs, role-specific visibility branches, package checks and company
resolution. Shared supply helpers arrive through deps; the model
moved here — these routes were its only user.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class SupplyHistoryModel(BaseModel):
    supplierId: int
    materialName: str
    quantity: float
    unit: str = ""
    pricePerUnit: float
    totalPrice: float
    project: str = ""
    date: str = ""
    status: str = "Ожидает поставки"
    workPackage: str = ""


def register_supply_history_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    write_roles = tuple(deps.get("write_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    limit_offset_sql = deps["limit_offset_sql"]
    ensure_supply_runtime_columns = deps["ensure_supply_runtime_columns"]
    can_see_all_company_data = deps["can_see_all_company_data"]
    scoped_project_where = deps["scoped_project_where"]
    current_supplier_ids = deps["current_supplier_ids"]
    user_project_names = deps["user_project_names"]
    package_access_filter = deps["package_access_filter"]
    has_package_access = deps["has_package_access"]
    require_project_or_warehouse_access = deps["require_project_or_warehouse_access"]
    company_id_for_project_or_user = deps["company_id_for_project_or_user"]

    @app.get("/supply-history")
    def get_supply_history(limit: Optional[int] = None, offset: int = 0, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ensure_supply_runtime_columns(cur)
        conn.commit()
        role = current_user.get("role")
        page_sql, page_params = limit_offset_sql(limit, offset)
        select_sql = ("SELECT id,company_id as \"companyId\",supplier_id as \"supplierId\",material_name as \"materialName\",quantity,unit,"
                      "price_per_unit as \"pricePerUnit\",total_price as \"totalPrice\",project,date,status,"
                      "confirmed_by as \"confirmedBy\",COALESCE(work_package,'') as \"workPackage\" "
                      "FROM supply_history")
        if can_see_all_company_data(current_user):
            cur.execute(select_sql + " ORDER BY id DESC" + page_sql, page_params)
        elif role in ("снабженец", "кладовщик"):
            project_sql, project_params = scoped_project_where(current_user, "project")
            cur.execute(select_sql + project_sql + " ORDER BY id DESC" + page_sql, project_params + page_params)
        elif role == "поставщик":
            supplier_ids = current_supplier_ids(cur, current_user)
            if not supplier_ids:
                cur.close(); conn.close()
                return []
            cur.execute(select_sql + " WHERE supplier_id = ANY(%s) ORDER BY id DESC" + page_sql, [supplier_ids] + page_params)
        elif role == "прораб":
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            package_sql, package_params = package_access_filter(current_user)
            cur.execute(select_sql + " WHERE project = ANY(%s)" + package_sql + " ORDER BY id DESC" + page_sql, [projects] + package_params + page_params)
        elif role in worker_execution_roles:
            cur.close(); conn.close()
            return []
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/supply-history")
    def create_supply_history(d: SupplyHistoryModel, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ensure_supply_runtime_columns(cur)
        conn.commit()
        if d.project:
            require_project_or_warehouse_access(_current_user, d.project)
        if not has_package_access(_current_user, d.workPackage or ""):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к этому пакету работ")
        company_id = company_id_for_project_or_user(cur, d.project or "", _current_user)
        cur.execute("""INSERT INTO supply_history
                       (company_id,supplier_id,material_name,quantity,unit,price_per_unit,total_price,project,date,status,work_package)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (company_id,d.supplierId,d.materialName,d.quantity,d.unit,d.pricePerUnit,d.totalPrice,d.project,d.date,d.status,d.workPackage or ""))
        row = cur.fetchone()
        conn.commit()
        conn.close()
        return dict(row)

    @app.put("/supply-history/{id}")
    def update_supply_history(id: int, data: dict, _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ensure_supply_runtime_columns(cur)
        conn.commit()
        cur.execute("SELECT project, COALESCE(NULLIF(work_package,''),'Основная') AS work_package FROM supply_history WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Запись истории поставок не найдена")
        if row.get("project"):
            require_project_or_warehouse_access(_current_user, row.get("project") or "")
        if not has_package_access(_current_user, row.get("work_package") or "Основная"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к пакету поставки")
        status = data.get('status','')
        confirmed_by = data.get('confirmedBy','')
        cur.execute("UPDATE supply_history SET status=%s,confirmed_by=%s WHERE id=%s", (status,confirmed_by,id))
        conn.commit()
        conn.close()
        return {"ok": True}
