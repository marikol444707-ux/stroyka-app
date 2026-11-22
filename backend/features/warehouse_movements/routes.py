"""Routes moved verbatim from backend/main.py."""

import os
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import psycopg2

def register_warehouse_movements_module(app, deps):
    FINANCE_ROLES = deps['FINANCE_ROLES']
    MAIN_WAREHOUSE_WRITE_ROLES = deps['MAIN_WAREHOUSE_WRITE_ROLES']
    PACKAGE_LIMIT_ROLES = deps['PACKAGE_LIMIT_ROLES']
    WAREHOUSE_ROLES = deps['WAREHOUSE_ROLES']
    _apply_warehouse_movement = deps['_apply_warehouse_movement']
    _create_warehouse_movement_review_task_safely = deps['_create_warehouse_movement_review_task_safely']
    _positive_int_or_none = deps['_positive_int_or_none']
    _project_company_id = deps['_project_company_id']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _run_project_ai_control_safely = deps['_run_project_ai_control_safely']
    company_id_scope_filter = deps['company_id_scope_filter']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    has_package_access = deps['has_package_access']
    require_project_or_warehouse_access = deps['require_project_or_warehouse_access']
    require_roles = deps['require_roles']
    user_package_names = deps['user_package_names']
    user_project_names = deps['user_project_names']
    router = APIRouter()

    class WarehouseMovementModel(BaseModel):
        materialName: str
        fromLocation: str
        toLocation: str
        quantity: float
        unit: str = ""
        workPackage: str = ""
        date: str = ""
        createdBy: str = ""
        notes: str = ""
        invoiceId: Optional[int] = None
        invoiceLineIndex: Optional[int] = None

    @router.get("/warehouse-movements")
    def get_warehouse_movements(
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
            company_filter_sql, company_filter_params = company_id_scope_filter(company_context, "wm.company_id")
        except Exception:
            cur.close(); conn.close()
            raise
        select_sql = "SELECT wm.id,wm.company_id as \"companyId\",wm.material_name as \"materialName\",wm.from_location as \"fromLocation\",wm.to_location as \"toLocation\",wm.quantity,wm.unit,wm.work_package as \"workPackage\",wm.date,wm.created_by as \"createdBy\",wm.notes,wm.source_invoice_id as \"sourceInvoiceId\",wm.source_invoice_line_index as \"sourceInvoiceLineIndex\",wm.estimate_control_status as \"estimateControlStatus\",wm.estimate_control as \"estimateControl\",wm.estimate_review_task_id as \"estimateReviewTaskId\",wm.document_snapshot_json as \"documentSnapshot\",wm.document_snapshot_hash as \"documentSnapshotHash\",wm.document_snapshot_frozen_at as \"documentSnapshotFrozenAt\" FROM warehouse_movements wm WHERE TRUE"
        if current_user.get("role") == "прораб":
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            package_names = user_package_names(current_user)
            query = select_sql + company_filter_sql + " AND (wm.from_location = ANY(%s) OR wm.to_location = ANY(%s))"
            params = company_filter_params + [projects, projects]
            if package_names:
                query += " AND COALESCE(NULLIF(wm.work_package,''),'Основная') = ANY(%s)"
                params.append(package_names)
            cur.execute(query + " ORDER BY id DESC", tuple(params))
        elif current_user.get("role") in ("снабженец", "кладовщик"):
            projects = user_project_names(current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            cur.execute(select_sql + company_filter_sql + " AND (wm.from_location = ANY(%s) OR wm.to_location = ANY(%s)) ORDER BY wm.id DESC", tuple(company_filter_params + [projects, projects]))
        elif current_user.get("role") in WAREHOUSE_ROLES or current_user.get("role") in FINANCE_ROLES:
            cur.execute(select_sql + company_filter_sql + " ORDER BY wm.id DESC", company_filter_params)
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @router.post("/warehouse-movements")
    def create_warehouse_movement(
        m: WarehouseMovementModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*WAREHOUSE_ROLES)),
    ):
        if os.getenv('OWNED_DISTRIBUTION_QUALITY_ENABLED') == '1':
            raise HTTPException(status_code=409, detail="Для перемещения с журналом качества используйте распределение конкретной партии или возврат по распределению. Старое перемещение отключено.")
        material_name = (m.materialName or "").strip()
        from_location = (m.fromLocation or "").strip()
        to_location = (m.toLocation or "").strip()
        work_package = (m.workPackage or "Основная").strip() or "Основная"
        qty = float(m.quantity or 0)
        if not material_name:
            raise HTTPException(status_code=400, detail="Укажите материал")
        if not from_location or not to_location:
            raise HTTPException(status_code=400, detail="Укажите откуда и куда переместить материал")
        if from_location == to_location:
            raise HTTPException(status_code=400, detail="Источник и получатель перемещения совпадают")
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")
        if from_location != "Основной склад":
            require_project_or_warehouse_access(_current_user, from_location)
        if to_location != "Основной склад":
            require_project_or_warehouse_access(_current_user, to_location)
        if _current_user.get("role") in PACKAGE_LIMIT_ROLES and not has_package_access(_current_user, work_package or "Основная"):
            raise HTTPException(status_code=403, detail="Нет доступа к пакету материалов")
        if from_location == "Основной склад" and _current_user.get("role") not in MAIN_WAREHOUSE_WRITE_ROLES:
            raise HTTPException(status_code=403, detail="Перемещать материал с основного склада на объект может директор, замдиректора, снабженец или кладовщик")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        requested_company_ids = {
            company_id for company_id in (
                _project_company_id(cur, from_location),
                _project_company_id(cur, to_location),
            ) if _positive_int_or_none(company_id)
        }
        if len(requested_company_ids) > 1:
            cur.close(); conn.close()
            raise HTTPException(status_code=409, detail="Источник и получатель относятся к разным компаниям")
        company_context = _resolve_work_company_context(
            cur,
            _current_user,
            next(iter(requested_company_ids), None),
            "write",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
        company_id = int(company_context.get("companyId") or 0)
        if company_id <= 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=409, detail="Компания перемещения не определена")
        conn.autocommit = False
        try:
            try:
                from backend.features.material_traceability.guards import lock_distribution_compatible_stock
            except ModuleNotFoundError:
                from features.material_traceability.guards import lock_distribution_compatible_stock
            lock_distribution_compatible_stock(cur)
            row = _apply_warehouse_movement(cur, m, company_id, _current_user)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
        movement_result = dict(row)
        review_task = _create_warehouse_movement_review_task_safely(
            movement_result,
            to_location,
            company_id,
            _current_user,
        )
        if review_task.get("taskId"):
            movement_result["estimateReviewTaskId"] = review_task["taskId"]
            movement_result["estimateReviewTaskCreated"] = bool(review_task.get("created"))
        _run_project_ai_control_safely(to_location if to_location != "Основной склад" else from_location, "warehouse_movement:create")
        return movement_result

    app.include_router(router)

    globals().update({
        'WarehouseMovementModel': WarehouseMovementModel,
    })

