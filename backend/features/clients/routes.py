"""Company-owned customer directory and legal requisites."""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class ClientModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=255)
    status: str = Field(default="Активный", max_length=100)
    notes: str = Field(default="", max_length=4000)
    inn: str = Field(default="", pattern=r"^(?:[0-9]{10}|[0-9]{12})?$")
    kpp: str = Field(default="", pattern=r"^(?:[0-9]{9})?$")
    ogrn: str = Field(default="", pattern=r"^(?:[0-9]{13}|[0-9]{15})?$")
    legalAddress: str = Field(default="", max_length=1000)
    actualAddress: str = Field(default="", max_length=1000)
    directorName: str = Field(default="", max_length=255)
    directorPosition: str = Field(default="", max_length=255)
    basis: str = Field(default="", max_length=1000)
    bankName: str = Field(default="", max_length=255)
    bik: str = Field(default="", pattern=r"^(?:[0-9]{9})?$")
    rs: str = Field(default="", pattern=r"^(?:[0-9]{20})?$")
    ks: str = Field(default="", pattern=r"^(?:[0-9]{20})?$")


SELECT_FIELDS = """id,company_id,name,phone,email,status,notes,inn,kpp,ogrn,
    legal_address,actual_address,director_name,director_position,basis,
    bank_name,bik,rs,ks"""


def _client_to_api(row):
    source = dict(row or {})
    return {
        "id": source.get("id"),
        "companyId": source.get("company_id"),
        "name": source.get("name") or "",
        "phone": source.get("phone") or "",
        "email": source.get("email") or "",
        "status": source.get("status") or "",
        "notes": source.get("notes") or "",
        "inn": source.get("inn") or "",
        "kpp": source.get("kpp") or "",
        "ogrn": source.get("ogrn") or "",
        "legalAddress": source.get("legal_address") or "",
        "actualAddress": source.get("actual_address") or "",
        "directorName": source.get("director_name") or "",
        "directorPosition": source.get("director_position") or "",
        "basis": source.get("basis") or "",
        "bankName": source.get("bank_name") or "",
        "bik": source.get("bik") or "",
        "rs": source.get("rs") or "",
        "ks": source.get("ks") or "",
    }


def _values(model):
    data = model.model_dump()
    return (
        data["name"], data["phone"], data["email"].lower(), data["status"], data["notes"],
        data["inn"], data["kpp"], data["ogrn"], data["legalAddress"], data["actualAddress"],
        data["directorName"], data["directorPosition"], data["basis"], data["bankName"],
        data["bik"], data["rs"], data["ks"],
    )


def register_clients_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_context = deps["resolve_work_company_context"]
    effective_actors = deps["effective_company_actors"]
    allowed_roles = set(deps.get("admin_roles") or ()) | {"менеджер_crm"}
    write_roles = set(deps.get("admin_roles") or ())

    def actor_for(conn, user, request, *, write=False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        headers = request.headers if request is not None else {}
        context = resolve_context(
            cur, user, None, "write" if write else "read",
            x_company_id=headers.get("x-company-id"),
            x_company_mode=headers.get("x-company-mode"),
        )
        if context.get("mode") != "company":
            cur.close()
            if write:
                raise HTTPException(409, "Для изменения заказчиков выберите одну компанию")
            return None
        actors = [actor for actor in effective_actors(user, context)
                  if actor.get("role") in (write_roles if write else allowed_roles)]
        cur.close()
        if len(actors) != 1 or not actors[0].get("companyId"):
            if write:
                raise HTTPException(403, "Нет права менять заказчиков выбранной компании")
            return None
        return actors[0]

    @app.get("/clients")
    def get_clients(current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        try:
            actor = actor_for(conn, current_user, request)
            if actor is None:
                return []
            company_id = int(actor["companyId"])
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"SELECT {SELECT_FIELDS} FROM clients WHERE company_id=%s ORDER BY name,id", (company_id,))
            rows = [_client_to_api(row) for row in cur.fetchall()]
            cur.close()
            return rows
        finally:
            conn.close()

    @app.post("/clients")
    def create_client(c: ClientModel, current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        try:
            actor = actor_for(conn, current_user, request, write=True)
            company_id = int(actor["companyId"])
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"""INSERT INTO clients
                (company_id,name,phone,email,status,notes,inn,kpp,ogrn,legal_address,
                 actual_address,director_name,director_position,basis,bank_name,bik,rs,ks)
                VALUES ({','.join(['%s'] * 18)}) RETURNING {SELECT_FIELDS}""",
                (company_id, *_values(c)))
            row = cur.fetchone()
            conn.commit()
            cur.close()
            return _client_to_api(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.put("/clients/{id}")
    def update_client(id: int, c: ClientModel, current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        try:
            actor = actor_for(conn, current_user, request, write=True)
            company_id = int(actor["companyId"])
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT id,company_id FROM clients WHERE id=%s AND company_id=%s FOR UPDATE", (id, company_id))
            if not cur.fetchone():
                raise HTTPException(404, "Заказчик не найден в выбранной компании")
            cur.execute("""UPDATE clients SET name=%s,phone=%s,email=%s,status=%s,notes=%s,
                    inn=%s,kpp=%s,ogrn=%s,legal_address=%s,actual_address=%s,director_name=%s,
                    director_position=%s,basis=%s,bank_name=%s,bik=%s,rs=%s,ks=%s
                WHERE id=%s AND company_id=%s""", (*_values(c), id, company_id))
            conn.commit()
            cur.close()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.delete("/clients/{id}")
    def delete_client(id: int, current_user: dict = Depends(get_current_user), request: Request = None):
        conn = get_db()
        try:
            actor = actor_for(conn, current_user, request, write=True)
            company_id = int(actor["companyId"])
            cur = conn.cursor()
            cur.execute("SELECT id FROM clients WHERE id=%s AND company_id=%s FOR UPDATE", (id, company_id))
            if not cur.fetchone():
                raise HTTPException(404, "Заказчик не найден в выбранной компании")
            cur.execute("UPDATE clients SET status='Архив' WHERE id=%s AND company_id=%s", (id, company_id))
            conn.commit()
            cur.close()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
