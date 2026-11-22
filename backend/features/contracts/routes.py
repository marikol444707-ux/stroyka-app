"""Selected-company access for master and subcontractor contracts."""

from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from ..record_company_scope import read_context, resolve_project_owner, selected_actor


class ContractModel(BaseModel):
    masterId: int
    masterName: str
    contractType: str = "ГПХ"
    contractNumber: str
    project: str
    startDate: str = ""
    endDate: str = ""


_LEADERSHIP = {"директор", "зам_директора", "бухгалтер", "главный_инженер"}


def register_contracts_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    resolve = deps["resolve_work_company_context"]
    actors_for = deps["effective_company_actors"]
    scope_filter = deps["company_id_scope_filter"]
    all_company_data = deps["can_see_all_company_data"]
    project_access = deps["require_project_access"]
    user_projects = deps["user_project_names"]
    contract_roles = tuple(deps.get("contract_roles") or ())
    create_roles = tuple(deps.get("create_roles") or ())
    delete_roles = tuple(deps.get("delete_roles") or ())
    worker_roles = tuple(deps.get("worker_execution_roles") or ())

    def limited_projects(actor):
        if not actor or all_company_data(actor):
            return None
        return user_projects(actor)

    @app.get("/contracts")
    def get_contracts(
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*contract_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            context, actor, all_leadership = read_context(
                resolve, actors_for, cur, _current_user, x_company_id, x_company_mode, _LEADERSHIP
            )
            if not actor and not all_leadership:
                return []
            actor = actor or _current_user
            company_sql, company_params = scope_filter(context, "company_id")
            where = ["TRUE"]
            params = []
            if actor.get("role") in worker_roles:
                where.append("(COALESCE(master_id,0)=%s OR (COALESCE(master_id,0)=0 AND master_name=%s))")
                params.extend([actor.get("id"), actor.get("name") or ""])
            allowed = None if all_leadership else limited_projects(actor)
            if allowed is not None:
                if not allowed:
                    return []
                where.append("(owner_scope='company' OR project = ANY(%s))")
                params.append(allowed)
            params.extend(company_params)
            query = (
                "SELECT id,master_id as \"masterId\",master_name as \"masterName\","
                "contract_type as \"contractType\",contract_number as \"contractNumber\","
                "project,start_date as \"startDate\",end_date as \"endDate\",status,"
                "company_id as \"companyId\",project_id as \"projectId\" "
                "FROM contracts WHERE " + " AND ".join(where) + company_sql + " ORDER BY id DESC"
            )
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/contracts")
    def create_contract(
        c: ContractModel,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*create_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "create", x_company_id, x_company_mode, create_roles
            )
            project_access(actor, c.project)
            scope, project_id = resolve_project_owner(cur, c.project, company_id)
            cur.execute(
                "INSERT INTO contracts (master_id,master_name,contract_type,contract_number,project,start_date,end_date,owner_scope,company_id,project_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (c.masterId, c.masterName, c.contractType, c.contractNumber, c.project, c.startDate, c.endDate, scope, company_id, project_id),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row)
        finally:
            cur.close()
            conn.close()

    @app.delete("/contracts/{id}")
    def delete_contract(
        id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(require_roles(*delete_roles)),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _context, actor, company_id = selected_actor(
                resolve, actors_for, cur, _current_user, "delete", x_company_id, x_company_mode, delete_roles
            )
            cur.execute(
                "SELECT id,project FROM contracts WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Договор не найден в выбранной компании")
            if not all_company_data(actor):
                project_access(actor, row.get("project") or "")
            cur.execute(
                "UPDATE contracts SET status='Аннулирован' WHERE id=%s AND company_id=%s",
                (id, company_id),
            )
            if getattr(cur, "rowcount", 1) not in (None, 1):
                raise HTTPException(status_code=404, detail="Договор не найден в выбранной компании")
            conn.commit()
            return {"ok": True}
        finally:
            cur.close()
            conn.close()
