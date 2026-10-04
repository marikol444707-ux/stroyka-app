"""Supply history routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 22):
GET/POST /supply-history and PUT /supply-history/{id} keep their
URLs, role-specific visibility branches, package checks and company
resolution. Shared supply helpers arrive through deps; the model
moved here — these routes were its only user.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
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
    companyId: Optional[int] = None


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

    resolve_context = deps["resolve_work_company_context"]
    effective_actors = deps["effective_company_actors"]

    @app.get("/supply-history")
    def get_supply_history(limit: Optional[int] = None, offset: int = 0, current_user: dict = Depends(get_current_user),
                           x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
                           x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            ensure_supply_runtime_columns(cur)
            conn.commit()
            role = current_user.get("role")
            page_sql, page_params = limit_offset_sql(limit, offset)
            select_sql = ("SELECT id,company_id as \"companyId\",supplier_id as \"supplierId\",material_name as \"materialName\",quantity,unit,"
                          "price_per_unit as \"pricePerUnit\",total_price as \"totalPrice\",project,date,status,"
                          "confirmed_by as \"confirmedBy\",COALESCE(work_package,'') as \"workPackage\" "
                          "FROM supply_history")
            if role == "поставщик":
                supplier_ids = current_supplier_ids(cur, current_user)
                if not supplier_ids:
                    return []
                cur.execute(select_sql + " WHERE supplier_id = ANY(%s) ORDER BY id DESC" + page_sql, [supplier_ids] + page_params)
            else:
                context = resolve_context(cur, current_user, None, "read",
                                          x_company_id=x_company_id, x_company_mode=x_company_mode)
                clauses, params = [], []
                for actor in effective_actors(current_user, context):
                    if not actor.get("companyId") or not (can_see_all_company_data(actor) or
                                                         actor.get("role") in (*write_roles, "прораб")):
                        continue
                    clause = "company_id=%s"
                    values = [actor["companyId"]]
                    if not can_see_all_company_data(actor):
                        project_sql, project_params = scoped_project_where(actor, "project")
                        if project_sql.startswith(" WHERE "):
                            clause += " AND (" + project_sql[7:] + ")"
                            values += project_params
                        package_sql, package_params = package_access_filter(actor)
                        clause += package_sql
                        values += package_params
                    clauses.append("(" + clause + ")")
                    params += values
                cur.execute(select_sql + " WHERE " + (" OR ".join(clauses) or "FALSE") +
                            " ORDER BY id DESC" + page_sql, params + page_params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            cur.close()
            conn.close()

    @app.post("/supply-history")
    def create_supply_history(d: SupplyHistoryModel, _current_user: dict = Depends(require_roles(*write_roles)),
                              x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
                              x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode")):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            ensure_supply_runtime_columns(cur)
            company_id = d.companyId or company_id_for_project_or_user(cur, d.project or "", _current_user)
            context = resolve_context(cur, _current_user, company_id, "create",
                                      x_company_id=x_company_id, x_company_mode=x_company_mode)
            actors = effective_actors(_current_user, context)
            if context.get("mode") != "company" or len(actors) != 1 or actors[0].get("role") not in write_roles:
                raise HTTPException(403, "Нет права добавлять поставки в выбранной компании")
            actor = actors[0]
            if actor.get("companyId") != company_id:
                raise HTTPException(409, "Компания записи не совпадает с выбранной компанией")
            if d.project:
                cur.execute('SELECT id FROM projects WHERE name=%s AND company_id=%s', (d.project, company_id))
                if not cur.fetchone():
                    raise HTTPException(403, "Объект не принадлежит выбранной компании")
                require_project_or_warehouse_access(actor, d.project)
            if not has_package_access(actor, d.workPackage or ""):
                raise HTTPException(403, "Нет доступа к этому пакету работ")
            cur.execute("""INSERT INTO supply_history
                           (company_id,supplier_id,material_name,quantity,unit,price_per_unit,total_price,project,date,status,work_package)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (company_id,d.supplierId,d.materialName,d.quantity,d.unit,d.pricePerUnit,d.totalPrice,d.project,d.date,d.status,d.workPackage or ""))
            row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.put("/supply-history/{id}")
    def update_supply_history(id: int, data: dict,
                              x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
                              x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
                              _current_user: dict = Depends(require_roles(*write_roles))):
        conn = get_db()
        cur = None
        try:
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            ensure_supply_runtime_columns(cur)
            cur.execute("SELECT company_id,project,COALESCE(NULLIF(work_package,''),'Основная') AS work_package FROM supply_history WHERE id=%s FOR UPDATE", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Запись истории поставок не найдена")
            from backend.features.company_context.service import resolve_resource_company_actor
            _context, actor = resolve_resource_company_actor(
                cur, _current_user, row.get("company_id"), "update",
                claimed_company_id=data.get("companyId", data.get("company_id")),
                x_company_id=x_company_id, x_company_mode=x_company_mode,
                allowed_roles=write_roles,
                platform_staff_roles=deps.get("platform_staff_roles", ()),
                client_account_roles=deps.get("client_account_roles", ()),
            )
            if row.get("project"):
                require_project_or_warehouse_access(actor, row["project"])
            if not has_package_access(actor, row["work_package"]):
                raise HTTPException(403, "Нет доступа к пакету поставки")
            cur.execute("UPDATE supply_history SET status=%s,confirmed_by=%s WHERE id=%s AND company_id=%s",
                        (data.get("status", ""), data.get("confirmedBy", ""), id, row["company_id"]))
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            conn.close()
