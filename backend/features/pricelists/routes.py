"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg2

def register_pricelists_module(app, deps):
    PRICELIST_MANAGE_ROLES = deps['PRICELIST_MANAGE_ROLES']
    WORKER_EXECUTION_ROLES = deps['WORKER_EXECUTION_ROLES']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    require_roles = deps['require_roles']
    user_project_names = deps['user_project_names']
    router = APIRouter()

    PRICELIST_VIEW_ROLES = (*PRICELIST_MANAGE_ROLES, "бухгалтер", "снабженец", "кладовщик", "технадзор", "стройконтроль")

    class PricelistModel(BaseModel):
        name: str
        description: str = ""
        forWho: str = ""
        coefficient: float = 1.0

    class CopyPricelistModel(BaseModel):
        name: str

    @router.get("/pricelists")
    def get_pricelists(_current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        role = _current_user.get("role")
        if role in WORKER_EXECUTION_ROLES:
            projects = user_project_names(_current_user)
            if not projects:
                cur.close(); conn.close()
                return []
            cur.execute("""SELECT DISTINCT pl.id,pl.name,pl.description,pl.for_who as "forWho",pl.coefficient
                           FROM pricelists pl
                           JOIN projects p ON p.pricelist_id=pl.id
                           WHERE p.name = ANY(%s)
                             AND NOT EXISTS (
                                 SELECT 1 FROM estimates e
                                 WHERE e.project_name=p.name
                                   AND e.status='Активная'
                                   AND COALESCE(e.smeta_type,'Заказчик')='Заказчик'
                             )""", (projects,))
        elif role not in PRICELIST_VIEW_ROLES:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Нет доступа к прайс-листам")
        else:
            cur.execute("SELECT id,name,description,for_who as \"forWho\",coefficient FROM pricelists")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @router.post("/pricelists")
    def create_pricelist(p: PricelistModel, _current_user: dict = Depends(require_roles(*PRICELIST_MANAGE_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO pricelists (name,description,for_who,coefficient) VALUES (%s,%s,%s,%s) RETURNING id,name,description,for_who as \"forWho\",coefficient",
                    (p.name,p.description,p.forWho,p.coefficient))
        row = cur.fetchone()
        conn.close()
        return dict(row)

    @router.put("/pricelists/{id}")
    def update_pricelist(id: int, p: PricelistModel, _current_user: dict = Depends(require_roles(*PRICELIST_MANAGE_ROLES))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE pricelists SET name=%s,description=%s,for_who=%s,coefficient=%s WHERE id=%s",
                    (p.name,p.description,p.forWho,p.coefficient,id))
        conn.close()
        return {"ok": True}

    @router.delete("/pricelists/{id}")
    def delete_pricelist(id: int, _current_user: dict = Depends(require_roles(*PRICELIST_MANAGE_ROLES))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pricelists WHERE id=%s", (id,))
        cur.execute("DELETE FROM pricelist_items WHERE pricelist_id=%s", (id,))
        conn.close()
        return {"ok": True}

    @router.post("/pricelists/{id}/copy")
    def copy_pricelist(id: int, data: CopyPricelistModel, _current_user: dict = Depends(require_roles(*PRICELIST_MANAGE_ROLES))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM pricelists WHERE id=%s", (id,))
        pl = cur.fetchone()
        cur.execute("INSERT INTO pricelists (name,description,for_who,coefficient) VALUES (%s,%s,%s,%s) RETURNING *",
                    (data.name,pl['description'],pl['for_who'],pl['coefficient']))
        new_pl = cur.fetchone()
        cur.execute("SELECT * FROM pricelist_items WHERE pricelist_id=%s", (id,))
        items = cur.fetchall()
        for item in items:
            cur.execute("INSERT INTO pricelist_items (pricelist_id,name,unit,price,category,specialization) VALUES (%s,%s,%s,%s,%s,%s)",
                        (new_pl['id'],item['name'],item['unit'],item['price'],item['category'],item['specialization']))
        conn.close()
        return dict(new_pl)

    @router.get("/pricelists/{id}/items")
    def get_pricelist_items(id: int, _current_user: dict = Depends(get_current_user)):
        role = _current_user.get("role")
        if role in WORKER_EXECUTION_ROLES:
            projects = user_project_names(_current_user)
            if not projects:
                raise HTTPException(status_code=403, detail="Нет доступа к прайс-листу")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""SELECT COUNT(*) FROM projects p
                           WHERE p.pricelist_id=%s
                             AND p.name = ANY(%s)
                             AND NOT EXISTS (
                                 SELECT 1 FROM estimates e
                                 WHERE e.project_name=p.name
                                   AND e.status='Активная'
                                   AND COALESCE(e.smeta_type,'Заказчик')='Заказчик'
                             )""", (id, projects))
            allowed = (cur.fetchone() or [0])[0]
            cur.close(); conn.close()
            if not allowed:
                raise HTTPException(status_code=403, detail="Исполнители видят только прайс, привязанный к объекту без активной сметы заказчика")
        elif role not in PRICELIST_VIEW_ROLES:
            raise HTTPException(status_code=403, detail="Нет доступа к прайс-листу")
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id,pricelist_id as \"pricelistId\",name,unit,price,category,specialization FROM pricelist_items WHERE pricelist_id=%s ORDER BY category,name", (id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    app.include_router(router)

