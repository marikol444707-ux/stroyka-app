"""Material directory routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 35):
the /materials quartet keeps its URLs, five role visibility branches,
stock/price hiding, the object-stock-only-via-documents rule and the
disabled physical delete. The model moved here — sole user.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class MaterialModel(BaseModel):
    name: str
    unit: str = "шт"
    quantity: float = 0
    price: float = 0
    minQuantity: float = 0
    project: str = ""
    category: str = ""
    workPackage: str = ""


def register_materials_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    main_warehouse_write_roles = tuple(deps.get("main_warehouse_write_roles") or ())
    material_price_history_roles = tuple(deps.get("material_price_history_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    user_project_names = deps["user_project_names"]
    package_access_filter = deps["package_access_filter"]
    can_see_warehouse_data = deps["can_see_warehouse_data"]
    require_project_or_warehouse_access = deps["require_project_or_warehouse_access"]
    has_package_access = deps["has_package_access"]
    limit_offset_sql = deps["limit_offset_sql"]
    norm_base_unit = deps["norm_base_unit"]
    log_audit = deps["log_audit"]

    @app.get("/materials")
    def get_materials(
        search: str = "",
        project_name: str = "",
        limit: Optional[int] = None,
        offset: int = 0,
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base = """SELECT id,name,unit,quantity,price,min_quantity as "minQuantity",
                         project,category,COALESCE(work_package,'') as "workPackage"
                  FROM materials"""
        projects = user_project_names(current_user)
        role = current_user.get("role")
        if role in ("заказчик", "технадзор"):
            cur.close(); conn.close()
            return []
        conditions = []
        params = []

        def add_condition(sql, *values):
            conditions.append(sql)
            params.extend(values)

        def run_material_query():
            search_value = (search or "").strip()
            if search_value:
                add_condition("""(
                    COALESCE(name, '') ILIKE %s OR
                    COALESCE(category, '') ILIKE %s OR
                    COALESCE(project, '') ILIKE %s OR
                    COALESCE(work_package, '') ILIKE %s
                )""", *([f"%{search_value}%"] * 4))
            project_value = (project_name or "").strip()
            if project_value:
                require_project_or_warehouse_access(current_user, project_value)
                add_condition("COALESCE(project, '') = %s", project_value)
            where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            page_sql, page_params = limit_offset_sql(limit, offset)
            cur.execute(base + where_sql + " ORDER BY project NULLS FIRST, name, id" + page_sql, params + page_params)

        if role == "прораб":
            if not projects:
                cur.close(); conn.close()
                return []
            package_sql, package_params = package_access_filter(current_user)
            add_condition("project = ANY(%s)", projects)
            if package_sql:
                add_condition(package_sql.replace(" AND ", "", 1), *package_params)
            run_material_query()
        elif role in ("снабженец", "кладовщик"):
            if not projects:
                cur.close(); conn.close()
                return []
            add_condition("project = ANY(%s)", projects)
            run_material_query()
        elif can_see_warehouse_data(current_user):
            run_material_query()
        elif projects:
            package_sql, package_params = package_access_filter(current_user)
            add_condition("project = ANY(%s)", projects)
            if package_sql:
                add_condition(package_sql.replace(" AND ", "", 1), *package_params)
            run_material_query()
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        can_see_stock = can_see_warehouse_data(current_user)
        can_see_prices = role in material_price_history_roles or role in finance_roles
        out = []
        for r in rows:
            d = dict(r)
            if not can_see_stock:
                d["quantity"] = 0
                d["minQuantity"] = 0
            if not can_see_prices:
                d["price"] = 0
            out.append(d)
        return out

    @app.post("/materials")
    def create_material(m: MaterialModel, _current_user: dict = Depends(require_roles(*main_warehouse_write_roles))):
        require_project_or_warehouse_access(_current_user, m.project or "")
        work_package = (m.workPackage or "Основная").strip() or "Основная"
        unit = norm_base_unit(m.unit or "шт") or "шт"
        if not has_package_access(_current_user, work_package):
            raise HTTPException(status_code=403, detail="Нет доступа к пакету материалов")
        if (m.project or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Материал на объект добавляется только через накладную, перемещение, выдачу или списание. Прямое создание остатка объекта отключено.",
            )
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""INSERT INTO materials (name,unit,quantity,price,min_quantity,project,category,work_package)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id,name,unit,quantity,price,min_quantity as "minQuantity",
                                 project,category,COALESCE(work_package,'') as "workPackage" """,
                    (m.name,unit,m.quantity,m.price,m.minQuantity,m.project,m.category,work_package))
        row = cur.fetchone()
        conn.commit()
        log_audit(
            _current_user.get("name", ""),
            _current_user.get("role", ""),
            "create",
            "interim_act",
            row.get("id"),
            ("Акт исполнителя: " + str(row.get("master_name") or "") + ", сумма " + str(row.get("total_amount") or ""))[:250],
            row.get("project") or "",
        )
        conn.close()
        return dict(row)

    @app.put("/materials/{id}")
    def update_material(id: int, m: MaterialModel, _current_user: dict = Depends(require_roles(*main_warehouse_write_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT project, quantity, COALESCE(NULLIF(work_package,''),'Основная') as work_package FROM materials WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Материал не найден")
        require_project_or_warehouse_access(_current_user, row.get("project") or "")
        require_project_or_warehouse_access(_current_user, m.project or "")
        old_work_package = row.get("work_package") or "Основная"
        new_work_package = (m.workPackage or old_work_package or "Основная").strip() or "Основная"
        unit = norm_base_unit(m.unit or "шт") or "шт"
        if not has_package_access(_current_user, old_work_package) or not has_package_access(_current_user, new_work_package):
            conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к пакету материалов")
        old_qty = float(row.get("quantity") or 0)
        old_project = (row.get("project") or "").strip()
        new_project = (m.project or "").strip()
        qty_delta = float(m.quantity or 0) - old_qty
        if old_project or new_project:
            if old_project != new_project or abs(qty_delta) > 0.000001:
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail="Остатки объекта нельзя менять прямой правкой материала. Используйте накладную, перемещение, выдачу или списание.",
                )
        cur.execute("""UPDATE materials
                       SET name=%s,unit=%s,quantity=%s,price=%s,min_quantity=%s,project=%s,category=%s,work_package=%s
                       WHERE id=%s""",
                    (m.name,unit,m.quantity,m.price,m.minQuantity,m.project,m.category,new_work_package,id))
        conn.commit()
        conn.close()
        return {"ok": True}

    @app.delete("/materials/{id}")
    def delete_material(id: int, _current_user: dict = Depends(require_roles("директор"))):
        raise HTTPException(
            status_code=405,
            detail="Физическое удаление материалов объекта отключено. Используйте списание, возврат, перемещение или корректировочную операцию, чтобы сохранить историю объекта.",
        )
