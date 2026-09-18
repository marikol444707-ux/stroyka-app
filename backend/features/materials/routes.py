"""Material directory routes.

Company membership scopes reads and writes; effective company roles preserve
project/package visibility, stock/price hiding and document-only object stock.
Physical deletion remains disabled.
"""

from typing import Annotated, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, conint


class MaterialModel(BaseModel):
    companyId: Optional[conint(strict=True, gt=0)] = None
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
    resolve_context = deps["resolve_work_company_context"]
    effective_actors = deps["effective_company_actors"]

    def company_actors(cur, user, action, company_id, header_id, header_mode):
        context = resolve_context(cur, user, company_id, action,
                                  x_company_id=header_id, x_company_mode=header_mode)
        if action != "read":
            if (context.get("mode") != "company" or context.get("source") != "membership"
                    or not context.get("membershipId") or not context.get("active")
                    or not context.get("companyActive")):
                raise HTTPException(403, "Требуется активная роль в компании")
            # Keep authorization stable while stock locks are acquired. A
            # pending revocation must finish before we authorize this write.
            cur.execute("SELECT id FROM users WHERE id=%s AND active=TRUE FOR SHARE", (user["id"],))
            if not cur.fetchone():
                raise HTTPException(403, "Пользователь отключён")
            cur.execute("SELECT id FROM companies WHERE id=%s FOR SHARE", (context["companyId"],))
            cur.fetchone()
            membership_id = context["membershipId"]
            cur.execute("SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE",
                        (membership_id, user["id"], context["companyId"]))
            if not cur.fetchone():
                raise HTTPException(403, "Членство больше не действует")
            context = resolve_context(cur, user, context["companyId"], action)
            if context.get("membershipId") != membership_id:
                raise HTTPException(403, "Членство больше не действует")
        contexts = context.get("companies", []) if context.get("mode") == "all_companies" else [context]
        # The shared resolver has a legacy-user fallback. This directory requires
        # an actual active membership and its explicit role and assignments.
        allowed = {item.get("companyId"): item for item in contexts
                   if item.get("source") == "membership" and item.get("membershipId")
                   and item.get("active") and item.get("companyActive")
                   and str(item.get("role") or "").strip()}
        actors = []
        for actor in effective_actors(user, context):
            membership = allowed.get(actor.get("companyId"))
            if membership:
                actor = dict(actor, role=membership["role"], projectName="", project_name="")
                actors.append(actor)
        if not actors:
            raise HTTPException(403, "Требуется активная роль в компании")
        if action != "read" and (len(actors) != 1 or actors[0].get("role") not in main_warehouse_write_roles):
            raise HTTPException(403, "Роль в выбранной компании не позволяет менять материалы")
        return actors

    @app.get("/materials")
    def get_materials(
        search: str = "",
        project_name: str = "",
        limit: Optional[int] = None,
        offset: int = 0,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None,
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base = """SELECT id,company_id as "companyId",name,unit,quantity,price,min_quantity as "minQuantity",
                         project,category,COALESCE(work_package,'') as "workPackage"
                  FROM materials"""
        try:
            actors = company_actors(cur, current_user, "read", None, x_company_id, x_company_mode)
            actors_by_company = {actor["companyId"]: actor for actor in actors}
            scopes, params = [], []
            for actor in actors:
                role = actor.get("role")
                projects = user_project_names(actor)
                if role in ("заказчик", "технадзор"):
                    continue
                conditions = ["company_id=%s"]
                values = [actor["companyId"]]
                restricted = role in ("прораб", "снабженец", "кладовщик") or not can_see_warehouse_data(actor)
                if restricted:
                    if not projects:
                        continue
                    conditions.append("project = ANY(%s)")
                    values.append(projects)
                    if role not in ("снабженец", "кладовщик"):
                        package_sql, package_params = package_access_filter(actor)
                        if package_sql:
                            conditions.append(package_sql.replace(" AND ", "", 1))
                            values.extend(package_params)
                project_value = (project_name or "").strip()
                if project_value:
                    try:
                        require_project_or_warehouse_access(actor, project_value)
                    except HTTPException as error:
                        if error.status_code != 403 or len(actors) == 1:
                            raise
                        continue
                    conditions.append("COALESCE(project, '') = %s")
                    values.append(project_value)
                scopes.append("(" + " AND ".join(conditions) + ")")
                params.extend(values)
            if not scopes:
                return []
            where = " WHERE (" + " OR ".join(scopes) + ")"
            search_value = (search or "").strip()
            if search_value:
                where += """ AND (
                    COALESCE(name, '') ILIKE %s OR
                    COALESCE(category, '') ILIKE %s OR
                    COALESCE(project, '') ILIKE %s OR
                    COALESCE(work_package, '') ILIKE %s
                )"""
                params.extend([f"%{search_value}%"] * 4)
            page_sql, page_params = limit_offset_sql(limit, offset)
            cur.execute(base + where + " ORDER BY project NULLS FIRST, name, id" + page_sql, params + page_params)
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            actor = actors_by_company[d["companyId"]]
            can_see_stock = can_see_warehouse_data(actor)
            can_see_prices = actor.get("role") in material_price_history_roles or actor.get("role") in finance_roles
            if not can_see_stock:
                d["quantity"] = 0
                d["minQuantity"] = 0
            if not can_see_prices:
                d["price"] = 0
            out.append(d)
        return out

    @app.post("/materials")
    def create_material(m: MaterialModel, _current_user: dict = Depends(get_current_user),
                        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
                        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            actor = company_actors(cur, _current_user, "create", m.companyId, x_company_id, x_company_mode)[0]
            require_project_or_warehouse_access(actor, m.project or "")
            work_package = (m.workPackage or "Основная").strip() or "Основная"
            unit = norm_base_unit(m.unit or "шт") or "шт"
            if not has_package_access(actor, work_package):
                raise HTTPException(403, "Нет доступа к пакету материалов")
            if (m.project or "").strip():
                raise HTTPException(400, "Материал на объект добавляется только через накладную, перемещение, выдачу или списание. Прямое создание остатка объекта отключено.")
            cur.execute("""INSERT INTO materials (name,unit,quantity,price,min_quantity,project,category,work_package,company_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id,company_id as "companyId",name,unit,quantity,price,min_quantity as "minQuantity",
                                 project,category,COALESCE(work_package,'') as "workPackage" """,
                        (m.name,unit,m.quantity,m.price,m.minQuantity,m.project,m.category,work_package,actor["companyId"]))
            row = cur.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        log_audit(
            actor.get("name", ""),
            actor.get("role", ""),
            "create",
            "material",
            row.get("id"),
            ("Материал создан: " + str(row.get("name") or "") + ", " + str(row.get("quantity") or 0) + " " + str(row.get("unit") or ""))[:250],
            row.get("project") or "",
            user_id=actor.get("id"),
            owner_scope="company",
            company_id=actor["companyId"],
        )
        return dict(row)

    @app.put("/materials/{id}")
    def update_material(id: int, m: MaterialModel, _current_user: dict = Depends(get_current_user),
                        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
                        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _current_user = company_actors(cur, _current_user, "update", m.companyId, x_company_id, x_company_mode)[0]
            company_id = _current_user["companyId"]
            from ..material_traceability.guards import lock_distribution_compatible_stock
            lock_distribution_compatible_stock(cur)
            cur.execute("SELECT project, quantity, COALESCE(NULLIF(work_package,''),'Основная') as work_package FROM materials WHERE id=%s AND company_id=%s FOR UPDATE", (id, company_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Материал не найден")
            require_project_or_warehouse_access(_current_user, row.get("project") or "")
            require_project_or_warehouse_access(_current_user, m.project or "")
            old_work_package = row.get("work_package") or "Основная"
            new_work_package = (m.workPackage or old_work_package or "Основная").strip() or "Основная"
            unit = norm_base_unit(m.unit or "шт") or "шт"
            if not has_package_access(_current_user, old_work_package) or not has_package_access(_current_user, new_work_package):
                raise HTTPException(status_code=403, detail="Нет доступа к пакету материалов")
            old_qty = float(row.get("quantity") or 0)
            old_project = (row.get("project") or "").strip()
            new_project = (m.project or "").strip()
            qty_delta = float(m.quantity or 0) - old_qty
            if old_project or new_project:
                if old_project != new_project or abs(qty_delta) > 0.000001:
                    raise HTTPException(
                        status_code=400,
                        detail="Остатки объекта нельзя менять прямой правкой материала. Используйте накладную, перемещение, выдачу или списание.",
                    )
            if old_project:
                # Object stock belongs to document operations, never metadata edits.
                cur.execute("""UPDATE materials
                               SET name=%s,unit=%s,price=%s,min_quantity=%s,project=%s,category=%s,work_package=%s
                               WHERE id=%s AND company_id=%s""",
                            (m.name,unit,m.price,m.minQuantity,m.project,m.category,new_work_package,id,company_id))
            else:
                cur.execute("""UPDATE materials
                               SET name=%s,unit=%s,quantity=%s,price=%s,min_quantity=%s,project=%s,category=%s,work_package=%s
                               WHERE id=%s AND company_id=%s""",
                            (m.name,unit,m.quantity,m.price,m.minQuantity,m.project,m.category,new_work_package,id,company_id))
            conn.commit()
        except psycopg2.Error as error:
            conn.rollback()
            if error.pgcode in ('40P01', '40001', '55P03', 'P0001'):
                raise HTTPException(status_code=409, detail="Складские данные изменились или защищены от изменения. Обновите карточку.") from error
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        return {"ok": True}

    @app.delete("/materials/{id}")
    def delete_material(id: int, _current_user: dict = Depends(require_roles("директор"))):
        raise HTTPException(
            status_code=405,
            detail="Физическое удаление материалов объекта отключено. Используйте списание, возврат, перемещение или корректировочную операцию, чтобы сохранить историю объекта.",
        )
