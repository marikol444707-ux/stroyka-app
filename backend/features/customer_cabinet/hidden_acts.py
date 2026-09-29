"""Customer acknowledgement of confirmed hidden work, without internal finance."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from ..work_acceptance.records import guard_hidden_act

ROLES = ('заказчик',)
FIELDS = ('id','company_id','project_name','work_journal_id','act_number','work_name',
          'section_name','quantity','unit','work_date','conclusion','city')


def revision(row):
    terms = {key:row[key] for key in FIELDS}
    return hashlib.sha256(json.dumps(terms, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def register_customer_hidden_acts(app, scope, authenticated, lock_settlement, effective_status):
    def read(cur, actors, row_id=None, lock=False):
        where, params = scope.visible(actors, ROLES)
        if row_id is not None:
            where += ' AND h.id=%s'; params = [*params,row_id]
        fields = (*FIELDS,'signed_customer','signed_customer_at','status','signed_supervisor','signed_contractor','signed_subcontractor')
        cur.execute('SELECT ' + ','.join('h.'+key for key in fields) + ',p.id '
            'FROM hidden_works_acts h JOIN work_journal w ON w.id=h.work_journal_id AND w.company_id=h.company_id '
            'JOIN projects p ON p.company_id=w.company_id AND p.name=w.project AND p.name=h.project_name '
            "WHERE w.status='Подтверждено' AND COALESCE(h.status,'') NOT IN ('Аннулирован','Аннулировано') "
            'AND NOT EXISTS (SELECT 1 FROM projects other WHERE other.company_id=p.company_id '
            'AND other.name=p.name AND other.id<>p.id) AND ' + where + ' ORDER BY h.id DESC'
            + (' FOR UPDATE OF h,w,p' if lock else ''),params)
        return [dict(zip((*fields,'project_id'),row)) for row in cur.fetchall()]

    @app.get('/hidden-works-acts/customer-visible')
    def listing(current_user:dict=Depends(authenticated), request:Request=None):
        with scope.transaction(current_user,request,ROLES) as (cur,actors):
            return [{'id':r['id'],'companyId':r['company_id'],'projectId':r['project_id'],
                     'actNumber':r['act_number'],'workName':r['work_name'],'sectionName':r['section_name'],
                     'quantity':r['quantity'],'unit':r['unit'],'workDate':r['work_date'],
                     'conclusion':r['conclusion'],'city':r['city'],
                     'signedCustomer':r['signed_customer'],'signedCustomerAt':r['signed_customer_at'],
                     'revision':revision(r)} for r in read(cur,actors)]

    @app.post('/hidden-works-acts/{act_id}/customer-confirm')
    def confirm(act_id:int,data:dict,current_user:dict=Depends(authenticated),request:Request=None):
        if set(data)!={'revision'} or not isinstance(data.get('revision'),str):
            raise HTTPException(422,'Укажите версию акта')
        with scope.transaction(current_user,request,ROLES,write=True) as (cur,actors):
            lock_settlement(cur)
            rows=read(cur,actors,act_id,lock=True)
            if not rows:
                raise HTTPException(404,'Акт не найден среди подтверждённых работ вашего объекта')
            row,actor=rows[0],actors[0]
            guard_hidden_act(cur,act_id)
            if revision(row)!=data['revision']:
                raise HTTPException(409,'Акт изменился. Обновите его перед подтверждением.')
            evidence=json.dumps(data,sort_keys=True)
            if row['signed_customer']:
                cur.execute("SELECT 1 FROM audit_log WHERE entity_type='hidden_works_act' AND entity_id=%s "
                            "AND action='customer_confirm' AND company_id=%s AND project_id=%s "
                            'AND user_id=%s AND description=%s LIMIT 1',
                            (act_id,row['company_id'],row['project_id'],actor['id'],evidence))
                if cur.fetchone():
                    return {'ok':True}
                raise HTTPException(409,'Акт уже подтверждён. Обновите страницу.')
            name=str(actor.get('name') or '').strip()
            if not name:
                raise HTTPException(409,'Заполните имя в профиле перед подтверждением')
            status=effective_status(row['status'],name,row['signed_supervisor'],row['signed_contractor'],row['signed_subcontractor'])
            cur.execute('UPDATE hidden_works_acts SET signed_customer=%s,signed_customer_at=%s,status=%s WHERE id=%s',
                        (name,datetime.now(ZoneInfo('Europe/Moscow')).date().isoformat(),status,act_id))
            cur.execute('INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,'
                        'description,project_name,owner_scope,company_id,project_id) '
                        "VALUES(%s,%s,'заказчик','customer_confirm','hidden_works_act',%s,%s,%s,'company',%s,%s)",
                        (actor['id'],name,act_id,evidence,row['project_name'],row['company_id'],row['project_id']))
        return {'ok':True}
