"""Material price history route.

Moved verbatim from backend/main.py. GET /material-price-history keeps its
URL, role guard and response shape.
"""

from fastapi import APIRouter, Depends


def register_material_price_history_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    material_price_history_roles = tuple(deps.get("material_price_history_roles") or ())
    router = APIRouter()

    @router.get("/material-price-history")
    def material_price_history(material: str = "", _current_user: dict = Depends(require_roles(*material_price_history_roles))):
        """Прошлые цены по материалу: из истории поставок + текущие предложения каталога.
        Помогает снабженцу понять адекватную цену при создании заявки."""
        material = (material or "").strip()
        if not material:
            return {"history": [], "catalog": [], "stats": None}
        conn = get_db()
        cur = conn.cursor()
        like = "%" + material + "%"
        # реально закупленные позиции (история поставок)
        cur.execute(
            "SELECT h.material_name, h.price_per_unit, h.unit, h.quantity, h.project, h.date, "
            "COALESCE(s.name, h.confirmed_by, '') AS supplier_name "
            "FROM supply_history h LEFT JOIN suppliers s ON s.id = h.supplier_id "
            "WHERE h.material_name ILIKE %s AND COALESCE(h.price_per_unit,0) > 0 "
            "ORDER BY h.id DESC LIMIT 15", (like,))
        history = [{"materialName": r[0], "price": float(r[1] or 0), "unit": r[2] or "",
                   "quantity": float(r[3] or 0), "project": r[4] or "", "date": r[5] or "",
                   "supplierName": r[6] or ""} for r in cur.fetchall()]
        # актуальные предложения из каталогов поставщиков
        cur.execute(
            "SELECT material_name, supplier_name, price, unit, delivery_days, in_stock "
            "FROM supplier_catalog WHERE material_name ILIKE %s AND COALESCE(price,0) > 0 "
            "ORDER BY price ASC LIMIT 15", (like,))
        catalog = [{"materialName": r[0], "supplierName": r[1] or "", "price": float(r[2] or 0),
                    "unit": r[3] or "", "deliveryDays": r[4] or 3, "inStock": r[5]} for r in cur.fetchall()]
        cur.close(); conn.close()
        prices = [h["price"] for h in history] + [c["price"] for c in catalog]
        stats = None
        if prices:
            stats = {"min": round(min(prices), 2), "max": round(max(prices), 2),
                     "avg": round(sum(prices) / len(prices), 2), "count": len(prices)}
        return {"history": history, "catalog": catalog, "stats": stats}

    app.include_router(router)
