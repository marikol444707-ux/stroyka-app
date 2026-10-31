"""Contract routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 21):
GET/POST /contracts and DELETE /contracts/{id} keep their URLs, role
guards, worker self-scope filter and soft-delete via status. The
model moved here — these routes were its only user.
"""

import psycopg2.extras
from fastapi import Depends, Request
from ..legacy_project_records.scope import require_record
from ..legacy_project_records.user_scope import require_user
from pydantic import BaseModel


class ContractModel(BaseModel):
    projectId: int | None = None
    masterId: int
    masterName: str
    contractType: str = "ГПХ"
    contractNumber: str
    project: str
    startDate: str = ""
    endDate: str = ""


def register_contracts_module(app, deps):
    scope, authenticated = deps['record_scope'], deps['get_current_user']
    contract_roles = tuple(deps['contract_roles'])
    create_roles = tuple(deps['create_roles'])
    delete_roles = tuple(deps['delete_roles'])
    worker_roles = tuple(deps['worker_execution_roles'])

    @app.get('/contracts')
    def get_contracts(request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user, request, contract_roles) as (cur, actors):
            conditions, params = [], []
            for actor in actors:
                where, values = scope.visible([actor], contract_roles)
                if actor.get('role') in worker_roles:
                    where += ' AND r.master_id=%s'
                    values = [*values,actor.get('id')]
                conditions.append('('+where+')'); params.extend(values)
            columns = 'r.id,r.master_id,r.master_name,r.contract_type,r.contract_number,p.name,r.start_date,r.end_date,r.status'
            cur.execute('SELECT '+columns+' FROM contracts r JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id WHERE '+
                        (' OR '.join(conditions) or 'FALSE')+' ORDER BY r.id DESC', params)
            rows = cur.fetchall()
        return [dict(zip(('id','masterId','masterName','contractType','contractNumber','project','startDate','endDate','status'),row)) for row in rows]

    @app.post('/contracts')
    def create_contract(c: ContractModel, request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user, request, create_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], {'projectId':c.projectId,'projectName':c.project}, create_roles)
            require_user(cur, actors, c.masterId)
            cur.execute('INSERT INTO contracts (company_id,project_id,master_id,master_name,contract_type,contract_number,project,start_date,end_date) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,status',
                        (parent['companyId'],parent['id'],c.masterId,c.masterName,c.contractType,c.contractNumber,parent['name'],c.startDate,c.endDate))
            record_id, status = cur.fetchone()
        return {'id':record_id,'company_id':parent['companyId'],'project_id':parent['id'],
                'master_id':c.masterId,'master_name':c.masterName,'contract_type':c.contractType,
                'contract_number':c.contractNumber,'project':parent['name'],'start_date':c.startDate,'end_date':c.endDate,'status':status}

    @app.delete('/contracts/{id}')
    def delete_contract(id: int, request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user, request, delete_roles, write=True) as (cur, actors):
            require_record(cur, scope, actors, delete_roles, 'contracts', id)
            cur.execute("UPDATE contracts SET status='Аннулирован' WHERE id=%s", (id,))
        return {'ok':True}
