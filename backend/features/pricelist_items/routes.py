"""Pricelist item routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 17):
POST/PUT/DELETE for /pricelist-items keep their URLs, role guard and
payloads. The model moved here — these routes were its only user.
"""

import psycopg2.extras
from fastapi import Depends
from pydantic import BaseModel


class PricelistItemModel(BaseModel):
    pricelistId: int
    name: str
    unit: str = "м2"
    price: float = 0
    category: str = ""
    specialization: str = ""


def register_pricelist_items_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    manage_roles = tuple(deps.get("manage_roles") or ())

    @app.post("/pricelist-items")
    def create_pricelist_item(item: PricelistItemModel, _current_user: dict = Depends(require_roles(*manage_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO pricelist_items (pricelist_id,name,unit,price,category,specialization) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,pricelist_id as \"pricelistId\",name,unit,price,category,specialization",
                    (item.pricelistId,item.name,item.unit,item.price,item.category,item.specialization))
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @app.put("/pricelist-items/{id}")
    def update_pricelist_item(id: int, item: PricelistItemModel, _current_user: dict = Depends(require_roles(*manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE pricelist_items SET name=%s,unit=%s,price=%s,category=%s,specialization=%s WHERE id=%s",
                    (item.name,item.unit,item.price,item.category,item.specialization,id))
        conn.close()
        return {"ok": True}

    @app.delete("/pricelist-items/{id}")
    def delete_pricelist_item(id: int, _current_user: dict = Depends(require_roles(*manage_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pricelist_items WHERE id=%s", (id,))
        conn.close()
        return {"ok": True}
