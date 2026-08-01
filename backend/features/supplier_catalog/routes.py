"""Supplier catalog routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 43):
the supplier catalog quartet keeps its URLs, per-supplier self-scope
and role checks.
"""

from fastapi import Depends, HTTPException


def register_supplier_catalog_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    current_supplier_ids = deps["current_supplier_ids"]
    supply_roles = tuple(deps.get("supply_roles") or ())
    warehouse_roles = tuple(deps.get("warehouse_roles") or ())
    finance_roles = tuple(deps.get("finance_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())

    @app.get("/supplier-catalog")
    def get_supplier_catalog(supplier_id: int = None, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            if not own_supplier_ids:
                cur.close(); conn.close()
                return []
            if supplier_id and supplier_id not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к каталогу этого поставщика")
            cur.execute("SELECT id,supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes FROM supplier_catalog WHERE supplier_id = ANY(%s) ORDER BY material_name", (own_supplier_ids,))
        elif role in worker_execution_roles:
            cur.close(); conn.close()
            return []
        elif role in supply_roles or role in warehouse_roles or role in finance_roles:
            if supplier_id:
                cur.execute("SELECT id,supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes FROM supplier_catalog WHERE supplier_id=%s ORDER BY material_name", (supplier_id,))
            else:
                cur.execute("SELECT id,supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes FROM supplier_catalog ORDER BY material_name")
        else:
            cur.close(); conn.close()
            return []
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"supplierId":r[1],"supplierName":r[2],"materialName":r[3],"unit":r[4],"price":float(r[5] or 0),"minQuantity":float(r[6] or 1),"deliveryDays":r[7] or 3,"inStock":r[8],"notes":r[9] or ""} for r in rows]

    @app.post("/supplier-catalog")
    def create_supplier_catalog(data: dict, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        supplier_id = int(data.get("supplierId") or 0)
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            if not own_supplier_ids or supplier_id not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к каталогу этого поставщика")
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute("INSERT INTO supplier_catalog (supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (supplier_id,data.get("supplierName",""),data.get("materialName",""),data.get("unit","шт"),data.get("price",0),data.get("minQuantity",1),data.get("deliveryDays",3),data.get("inStock",True),data.get("notes","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.put("/supplier-catalog/{id}")
    def update_supplier_catalog(id: int, data: dict, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            cur.execute("SELECT supplier_id FROM supplier_catalog WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row or row[0] not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к каталогу этого поставщика")
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute("UPDATE supplier_catalog SET price=%s,in_stock=%s,delivery_days=%s,notes=%s WHERE id=%s",
            (data.get("price",0),data.get("inStock",True),data.get("deliveryDays",3),data.get("notes",""),id))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}

    @app.delete("/supplier-catalog/{id}")
    def delete_supplier_catalog(id: int, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            cur.execute("SELECT supplier_id FROM supplier_catalog WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row or row[0] not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к каталогу этого поставщика")
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute("DELETE FROM supplier_catalog WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
