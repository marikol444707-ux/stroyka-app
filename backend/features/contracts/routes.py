"""Contract routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 21):
GET/POST /contracts and DELETE /contracts/{id} keep their URLs, role
guards, worker self-scope filter and soft-delete via status. The
model moved here — these routes were its only user.
"""

import psycopg2.extras
from fastapi import Depends
from pydantic import BaseModel


class ContractModel(BaseModel):
    masterId: int
    masterName: str
    contractType: str = "ГПХ"
    contractNumber: str
    project: str
    startDate: str = ""
    endDate: str = ""


def register_contracts_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    contract_roles = tuple(deps.get("contract_roles") or ())
    create_roles = tuple(deps.get("create_roles") or ())
    delete_roles = tuple(deps.get("delete_roles") or ())
    worker_execution_roles = tuple(deps.get("worker_execution_roles") or ())
    visible_project_names = deps["visible_project_names"]
    require_project_access = deps["require_project_access"]
    require_row_project_access = deps["require_row_project_access"]

    @app.get("/contracts")
    def get_contracts(_current_user: dict = Depends(require_roles(*contract_roles))):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        allowed_projects = visible_project_names(_current_user)
        if allowed_projects is not None and not allowed_projects:
            conn.close()
            return []
        where, params = [], []
        if allowed_projects is not None:
            where.append("project = ANY(%s)")
            params.append(allowed_projects)
        if _current_user.get("role") in worker_execution_roles:
            where.append("(COALESCE(master_id,0)=%s OR (COALESCE(master_id,0)=0 AND master_name=%s))")
            params.extend([_current_user.get("id"), _current_user.get("name") or ""])
        q = "SELECT id,master_id as \"masterId\",master_name as \"masterName\",contract_type as \"contractType\",contract_number as \"contractNumber\",project,start_date as \"startDate\",end_date as \"endDate\",status FROM contracts"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC"
        cur.execute(q, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/contracts")
    def create_contract(c: ContractModel, _current_user: dict = Depends(require_roles(*create_roles))):
        require_project_access(_current_user, c.project)
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO contracts (master_id,master_name,contract_type,contract_number,project,start_date,end_date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (c.masterId,c.masterName,c.contractType,c.contractNumber,c.project,c.startDate,c.endDate))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return dict(row)

    @app.delete("/contracts/{id}")
    def delete_contract(id: int, _current_user: dict = Depends(require_roles(*delete_roles))):
        conn = get_db()
        cur = conn.cursor()
        require_row_project_access(cur, "contracts", id, _current_user, "project")
        cur.execute("UPDATE contracts SET status='Аннулирован' WHERE id=%s", (id,))
        conn.commit()
        conn.close()
        return {"ok": True}
