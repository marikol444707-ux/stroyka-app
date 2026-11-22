"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import psycopg2

def register_warehouse_main_module(app, deps):
    CLIENT_ACCOUNT_ROLES = deps['CLIENT_ACCOUNT_ROLES']
    FINANCE_ROLES = deps['FINANCE_ROLES']
    MAIN_WAREHOUSE_WRITE_ROLES = deps['MAIN_WAREHOUSE_WRITE_ROLES']
    MATERIAL_PRICE_HISTORY_ROLES = deps['MATERIAL_PRICE_HISTORY_ROLES']
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    _norm_base_unit = deps['_norm_base_unit']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    can_see_warehouse_data = deps['can_see_warehouse_data']
    company_id_scope_filter = deps['company_id_scope_filter']
    effective_company_actors = deps['effective_company_actors']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    require_roles = deps['require_roles']
    resolve_resource_company_actor = deps['resolve_resource_company_actor']
    router = APIRouter()

    class WarehouseMainModel(BaseModel):
        name: str
        unit: str = "шт"
        quantity: float = 0
        price: float = 0
        minQuantity: float = 0
        category: str = ""

    @router.get("/warehouse-main")
    def get_warehouse_main(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        if not can_see_warehouse_data(current_user):
            return []
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
            cur.execute(
                "SELECT wm.id,wm.name,wm.unit,wm.quantity,wm.price,wm.min_quantity as \"minQuantity\",wm.category "
                "FROM warehouse_main wm WHERE TRUE" + company_filter_sql,
                company_filter_params,
            )
        except Exception:
            cur.close(); conn.close()
            raise
        rows = cur.fetchall()
        conn.close()
        can_see_prices = current_user.get("role") in MATERIAL_PRICE_HISTORY_ROLES or current_user.get("role") in FINANCE_ROLES
        out = []
        for r in rows:
            d = dict(r)
            if not can_see_prices:
                d["price"] = 0
            out.append(d)
        return out

    @router.post("/warehouse-main")
    def create_warehouse_main(
        m: WarehouseMainModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        unit = _norm_base_unit(m.unit or "шт") or "шт"
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = _resolve_work_company_context(
                cur,
                _current_user,
                None,
                "write",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_id = int(company_context.get("companyId") or 0)
            actors = effective_company_actors(_current_user, company_context)
            actor = actors[0] if len(actors) == 1 else {}
            if company_id <= 0 or not actor:
                raise HTTPException(status_code=409, detail="Компания основного склада не определена")
            if (actor.get("role") or "") not in MAIN_WAREHOUSE_WRITE_ROLES:
                raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет менять основной склад")
            cur.execute("INSERT INTO warehouse_main (name,unit,quantity,price,min_quantity,category,company_id) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,unit,quantity,price,min_quantity as \"minQuantity\",category,company_id as \"companyId\"",
                        (m.name,unit,m.quantity,m.price,m.minQuantity,m.category,company_id))
            row = cur.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
        return dict(row)

    @router.put("/warehouse-main/{id}")
    def update_warehouse_main(
        id: int,
        m: WarehouseMainModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        unit = _norm_base_unit(m.unit or "шт") or "шт"
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            # Acquire the eventual UPDATE relation lock before its row lock; otherwise
            # a concurrent batch's stronger relation lock can cause a lock upgrade cycle.
            cur.execute('LOCK TABLE warehouse_main IN ROW EXCLUSIVE MODE')
            cur.execute("SELECT id,company_id,name,unit,quantity FROM warehouse_main WHERE id=%s FOR UPDATE", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Материал основного склада не найден")
            _company_context, _actor = resolve_resource_company_actor(
                cur,
                _current_user,
                row.get("company_id"),
                "update",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
                allowed_roles=MAIN_WAREHOUSE_WRITE_ROLES,
                forbidden_detail="Роль в выбранной компании не позволяет менять основной склад",
                platform_staff_roles=PLATFORM_STAFF_ROLES,
                client_account_roles=CLIENT_ACCOUNT_ROLES,
            )
            try:
                from backend.features.material_traceability.guards import guard_main_stock_edit
            except ModuleNotFoundError:
                from features.material_traceability.guards import guard_main_stock_edit
            guard_main_stock_edit(cur, row, name=m.name, unit=unit, quantity=m.quantity)
            cur.execute("UPDATE warehouse_main SET name=%s,unit=%s,quantity=%s,price=%s,min_quantity=%s,category=%s WHERE id=%s AND company_id=%s",
                        (m.name,unit,m.quantity,m.price,m.minQuantity,m.category,id,row.get("company_id")))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
        return {"ok": True}

    @router.delete("/warehouse-main/{id}")
    def delete_warehouse_main(id: int, _current_user: dict = Depends(require_roles("директор"))):
        raise HTTPException(
            status_code=405,
            detail="Физическое удаление материалов основного склада отключено. Используйте корректировку склада, перемещение или инвентаризацию, чтобы сохранить историю движения.",
        )

    app.include_router(router)

