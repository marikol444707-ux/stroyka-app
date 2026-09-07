"""Company requisites routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 5):
GET /company-requisites and POST /company-requisites keep their URLs,
selected-company context resolution and per-company finance role
check.
"""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

try:
    from backend.features.company_requisites.service import (
        company_requisites_to_api,
        mirror_company_identity,
        upsert_company_requisites,
    )
except ModuleNotFoundError:
    from features.company_requisites.service import (
        company_requisites_to_api,
        mirror_company_identity,
        upsert_company_requisites,
    )


def register_company_requisites_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    effective_company_actors = deps["effective_company_actors"]
    positive_int_or_none = deps["positive_int_or_none"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/company-requisites")
    def get_company_requisites(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            company_context = resolve_work_company_context(
                cur,
                _current_user,
                None,
                "read",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            if company_context.get("mode") != "company":
                return {"companyId": None, "requiresCompanySelection": True}
            company_id = positive_int_or_none(company_context.get("companyId"))
            if not company_id:
                raise HTTPException(status_code=409, detail="Компания для реквизитов не определена")
            cur.execute("""SELECT id,company_id,full_name,short_name,inn,kpp,ogrn,legal_address,
                                  actual_address,phone,email,director_name,director_position,basis,
                                  bank_name,bik,rs,ks
                           FROM company_requisites WHERE company_id=%s ORDER BY id LIMIT 1""", (company_id,))
            row = cur.fetchone()
            if not row:
                return {"companyId": company_id}
            return company_requisites_to_api(row, company_id)
        finally:
            cur.close(); conn.close()

    @app.post("/company-requisites")
    def save_company_requisites(
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            claimed_company_id = data.get("companyId") if "companyId" in data else data.get("company_id")
            company_context = resolve_work_company_context(
                cur,
                _current_user,
                claimed_company_id,
                "write",
                x_company_id=x_company_id,
                x_company_mode=x_company_mode,
            )
            company_id = positive_int_or_none(company_context.get("companyId"))
            actors = effective_company_actors(_current_user, company_context)
            actor = actors[0] if len(actors) == 1 else {}
            if not company_id or not actor:
                raise HTTPException(status_code=409, detail="Компания для реквизитов не определена")
            if (actor.get("role") or "") not in finance_roles:
                raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет менять реквизиты")
            row = upsert_company_requisites(cur, company_id, data)
            mirror_company_identity(cur, company_id, data)
            conn.commit()
            return {**company_requisites_to_api(row, company_id), "ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close(); conn.close()
