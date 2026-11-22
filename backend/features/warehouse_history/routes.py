"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import psycopg2

def register_warehouse_history_module(app, deps):
    CLIENT_ACCOUNT_ROLES = deps['CLIENT_ACCOUNT_ROLES']
    FINANCE_ROLES = deps['FINANCE_ROLES']
    LEADERSHIP_ROLES = deps['LEADERSHIP_ROLES']
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    WAREHOUSE_ROLES = deps['WAREHOUSE_ROLES']
    WORKER_EXECUTION_ROLES = deps['WORKER_EXECUTION_ROLES']
    _project_company_id = deps['_project_company_id']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    company_id_scope_filter = deps['company_id_scope_filter']
    effective_company_actors = deps['effective_company_actors']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    has_package_access = deps['has_package_access']
    require_project_or_warehouse_access = deps['require_project_or_warehouse_access']
    resolve_resource_company_actor = deps['resolve_resource_company_actor']
    user_package_names = deps['user_package_names']
    user_project_names = deps['user_project_names']
    router = APIRouter()

    class WarehouseHistoryModel(BaseModel):
        material: str
        type: str
        quantity: float
        unit: str = "шт"
        date: str
        project: str = ""
        issuedTo: str = ""
        issuedBy: str = ""
        workPackage: str = ""
        dateTime: str = ""

    @router.get("/warehouse-history")
    def get_warehouse_history(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = _resolve_work_company_context(
                cur,
                current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_filter_sql, company_filter_params = company_id_scope_filter(company_context, "wh.company_id")
        except Exception:
            cur.close(); conn.close()
            raise
        select_sql = "SELECT wh.id,wh.material,wh.type,wh.quantity,wh.date,wh.project,wh.issued_to as \"issuedTo\",wh.issued_by as \"issuedBy\",wh.work_package as \"workPackage\",wh.date_time as \"dateTime\",wh.source_type as \"sourceType\",wh.source_id as \"sourceId\",wh.source_invoice_id as \"sourceInvoiceId\",wh.source_invoice_line_index as \"sourceInvoiceLineIndex\" FROM warehouse_history wh WHERE TRUE"
        role = current_user.get("role")
        if role == "прораб":
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            package_names = user_package_names(current_user)
            query = select_sql + company_filter_sql + " AND wh.project = ANY(%s)"
            params = company_filter_params + [projects]
            if package_names:
                query += " AND COALESCE(NULLIF(wh.work_package,''),'Основная') = ANY(%s)"
                params.append(package_names)
            cur.execute(query + " ORDER BY id DESC", tuple(params))
        elif role in WORKER_EXECUTION_ROLES:
            package_names = user_package_names(current_user)
            if not package_names:
                cur.close(); conn.close()
                return []
            query = select_sql + company_filter_sql + " AND (wh.issued_by=%s OR wh.issued_to=%s)"
            params = company_filter_params + [current_user.get("name",""), current_user.get("name","")]
            query += " AND COALESCE(NULLIF(wh.work_package,''),'Основная') = ANY(%s)"
            params.append(package_names)
            cur.execute(query + " ORDER BY id DESC", tuple(params))
        elif role in WAREHOUSE_ROLES or role in FINANCE_ROLES:
            cur.execute(select_sql + company_filter_sql + " ORDER BY wh.id DESC", company_filter_params)
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @router.post("/warehouse-history")
    def create_warehouse_history(
        h: WarehouseHistoryModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        movement_type = (h.type or "").strip()
        if not movement_type.startswith("ручная корректировка"):
            raise HTTPException(
                status_code=400,
                detail="Прямое создание складских приходов, списаний и перемещений запрещено. Используйте накладную, перемещение или ЖПР.",
            )
        if not h.material or float(h.quantity or 0) <= 0:
            raise HTTPException(status_code=400, detail="Укажите материал и положительное количество")
        work_package = (h.workPackage or "").strip()
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            project_company_id = _project_company_id(cur, h.project)
            company_context = _resolve_work_company_context(
                cur,
                _current_user,
                project_company_id,
                "write",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_id = int(company_context.get("companyId") or 0)
            actors = effective_company_actors(_current_user, company_context)
            actor = actors[0] if len(actors) == 1 else {}
            if company_id <= 0 or not actor:
                raise HTTPException(status_code=409, detail="Компания складской корректировки не определена")
            if (actor.get("role") or "") not in LEADERSHIP_ROLES:
                raise HTTPException(status_code=403, detail="Ручную запись истории склада может добавить только директор или замдиректора выбранной компании")
            if h.project:
                require_project_or_warehouse_access(actor, h.project)
            if not has_package_access(actor, work_package or "Основная"):
                raise HTTPException(status_code=403, detail="Нет доступа к разделу сметы движения: " + (work_package or "Основная"))
            unit = (h.unit or "шт").strip() or "шт"
            cur.execute("INSERT INTO warehouse_history (material,type,quantity,unit,date,project,issued_to,issued_by,work_package,date_time,company_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (h.material,movement_type,h.quantity,unit,h.date,h.project,h.issuedTo,h.issuedBy,work_package,h.dateTime,company_id))
            row = cur.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
        return dict(row)

    @router.delete("/warehouse-history/{id}")
    def delete_warehouse_history(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT project,company_id FROM warehouse_history WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Запись движения склада не найдена")
            _context, actor = resolve_resource_company_actor(
                cur,
                _current_user,
                row.get("company_id"),
                "delete",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                allowed_roles=WAREHOUSE_ROLES,
                forbidden_detail="Роль в выбранной компании не позволяет работать с историей склада",
                platform_staff_roles=PLATFORM_STAFF_ROLES,
                client_account_roles=CLIENT_ACCOUNT_ROLES,
            )
            project_name = row.get("project") or ""
            if project_name:
                require_project_or_warehouse_access(actor, project_name)
        finally:
            cur.close(); conn.close()
        raise HTTPException(
            status_code=409,
            detail="Удаление записей движения склада запрещено: в warehouse_history нет полей статуса/сторно, физическое удаление нарушает аудит склада",
        )

    app.include_router(router)

