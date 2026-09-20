"""Public supplier identity, separate from each buyer's terms and subscription."""
import hashlib
import json
from fastapi import HTTPException
from .company_directory import PUBLIC_FIELDS, PUBLIC_LIMITS
from ..supplier_team import policy

FIELDS = {**PUBLIC_FIELDS, 'phone':'phone', 'email':'email', 'specialization':'specialization'}

LIMITS = {**PUBLIC_LIMITS, 'phone':100, 'email':255, 'specialization':255}

def authorize(cur, user, supplier_id, write=False):
    if user.get('role') in ('system_owner','platform_admin'):
        return
    if user.get('role') != 'поставщик':
        raise HTTPException(403, 'Профиль доступен руководителю поставщика')
    if policy.enabled():
        if write:
            from ..supplier_team.service import lock_leader
            lock_leader(cur, supplier_id, user['id'])
            return
        sql, params = policy.leader_policy(user.get('id'), 's.id')
        cur.execute('SELECT s.id FROM suppliers s WHERE s.id=%s AND '+sql, [supplier_id]+params)
    else:
        cur.execute("""SELECT s.id FROM suppliers s JOIN users u ON u.id=s.user_id
            WHERE s.id=%s AND u.id=%s AND u.role='поставщик' AND COALESCE(u.active,TRUE)""",
            (supplier_id,user.get('id')))
    if not cur.fetchone():
        raise HTTPException(403, 'Профиль доступен руководителю поставщика')


def load(cur, supplier_id, lock=False):
    cur.execute('SELECT '+','.join(column+' AS "'+key+'"' for key,column in FIELDS.items())+
                ' FROM suppliers WHERE id=%s'+(' FOR UPDATE' if lock else ''),(supplier_id,))
    row=cur.fetchone()
    if not row:
        raise HTTPException(404, 'Поставщик не найден')
    fields={key:str(row.get(key) or '') for key in FIELDS}
    version=hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'supplierId':supplier_id,'fields':fields,'version':version,'canEdit':True,'fieldLimits':LIMITS,
            'tariff':{'status':'not_configured'},
            'team':{'enabled':policy.enabled(),'customerAssignments':policy.customer_assignments_enabled(),
                    'managerLimit':None,'customersPerManagerLimit':None}}


def update(cur, supplier_id, data):
    current=load(cur,supplier_id,lock=True)
    if 'expectedProfileVersion' in data and data['expectedProfileVersion']!=current['version']:
        raise HTTPException(409,'Реквизиты изменены другим пользователем. Обновите профиль перед сохранением.')
    if 'address' in data and 'legalAddress' not in data:
        data={**data,'legalAddress':data['address']}
    values=[(column,str(data[key] or '').strip()) for key,column in FIELDS.items() if key in data]
    if not values:
        raise HTTPException(422,'Нет реквизитов для обновления')
    if any(len(str(data[key] or '').strip()) > LIMITS[key] for key in FIELDS if key in data):
        raise HTTPException(422,'Реквизиты слишком длинные')
    if 'name' in data and not str(data['name'] or '').strip():
        raise HTTPException(422,'Укажите название компании')
    cur.execute('UPDATE suppliers SET '+','.join(column+'=%s' for column,_ in values)+' WHERE id=%s',
                [value for _,value in values]+[supplier_id])
    return {'ok':True,**load(cur,supplier_id)}
