"""Supplier-owned team commands. Never lock purchase/offer rows from this module."""
from contextlib import contextmanager
from hashlib import sha256
import json
from uuid import UUID

from fastapi import HTTPException
from psycopg2.extras import Json, RealDictCursor

from .policy import enabled, customer_assignments_enabled, leader_policy, access_ids


def require_enabled():
    if not enabled() or not customer_assignments_enabled():
        raise HTTPException(404, 'Управление командой пока недоступно')


def integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise HTTPException(422, 'Некорректный идентификатор или версия')
    return value


@contextmanager
def transaction(get_db):
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SET LOCAL lock_timeout='5s'")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lock_leader(cur, supplier_id, user_id):
    # All team writers serialize on this parent, including absent assignments.
    cur.execute('SELECT id,user_id,name FROM suppliers WHERE id=%s FOR UPDATE', (supplier_id,))
    supplier = cur.fetchone()
    cur.execute('SELECT id FROM users WHERE id=%s FOR SHARE', (user_id,))
    cur.fetchall()
    cur.execute('SELECT id FROM supplier_team_members WHERE supplier_id=%s AND user_id=%s FOR SHARE',
                (supplier_id, user_id))
    cur.fetchall()
    sql, params = leader_policy(user_id, 's.id')
    cur.execute('SELECT s.id FROM suppliers s WHERE s.id=%s AND '+sql, [supplier_id]+params)
    if not supplier or not cur.fetchone():
        raise HTTPException(403, 'Управление доступно только руководителю поставщика')
    return supplier


def customers(cur, supplier_id, user_id):
    from ..supplier_access.service import supplier_offer_visibility_filter
    scope, params = supplier_offer_visibility_filter([supplier_id], user_id)
    cur.execute('''SELECT c.id,c.name,a.member_id AS "memberId",COALESCE(a.version,0) AS version
        FROM companies c LEFT JOIN supplier_customer_assignments a
          ON a.company_id=c.id AND a.supplier_id=%s
        WHERE EXISTS(SELECT 1 FROM company_supplier_links l
                     WHERE l.company_id=c.id AND l.supplier_id=%s)
          OR EXISTS(SELECT 1 FROM supplier_offers WHERE supplier_offers.company_id=c.id
                    AND supplier_offers.supplier_id=%s '''+scope+''') ORDER BY c.name,c.id''',
        [supplier_id,supplier_id,supplier_id]+params)
    return [dict(r) for r in cur.fetchall()]


def replay(cur, supplier_id, actor_id, data, action):
    try:
        request_id = str(UUID(str(data.get('requestId'))))
    except (ValueError, TypeError):
        raise HTTPException(422, 'Нужен идентификатор операции')
    details = {key: value for key,value in data.items() if key != 'requestId'}
    digest = sha256(json.dumps([action,details], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cur.execute('SELECT actor_id,payload_hash,result FROM supplier_team_operations WHERE supplier_id=%s AND request_id=%s',
                (supplier_id,request_id))
    row = cur.fetchone()
    if row and (row['actor_id'] != actor_id or row['payload_hash'] != digest):
        raise HTTPException(409, 'Идентификатор уже использован другой операцией')
    return request_id,digest,details,dict(row['result']) if row else None


def record(cur, supplier_id, actor_id, operation, action, result):
    request_id,digest,details,_ = operation
    cur.execute('''INSERT INTO supplier_team_operations
        (supplier_id,actor_id,request_id,payload_hash,action,details,result) VALUES(%s,%s,%s,%s,%s,%s,%s)''',
        (supplier_id,actor_id,request_id,digest,action,Json(details),Json(result)))
    return result


def assign(cur, supplier_id, user_id, data):
    company_id = integer(data.get('companyId'))
    version = integer(data.get('version'),0)
    member_id = data.get('memberId')
    if member_id is not None:
        integer(member_id)
    lock_leader(cur,supplier_id,user_id)
    operation = replay(cur,supplier_id,user_id,data,'assign_customer')
    if operation[3] is not None:
        return operation[3]
    if company_id not in {r['id'] for r in customers(cur,supplier_id,user_id)}:
        raise HTTPException(403, 'Заказчик недоступен этому поставщику')
    if member_id is not None:
        cur.execute('''SELECT m.id FROM supplier_team_members m JOIN users u ON u.id=m.user_id
            WHERE m.id=%s AND m.supplier_id=%s AND m.active AND m.role='manager'
              AND COALESCE(u.active,TRUE) AND u.role='поставщик' FOR SHARE OF m,u''',(member_id,supplier_id))
        if not cur.fetchone():
            raise HTTPException(409, 'Выберите действующего менеджера своей команды')
    cur.execute('SELECT version,member_id FROM supplier_customer_assignments WHERE supplier_id=%s AND company_id=%s',
                (supplier_id,company_id))
    old=cur.fetchone()
    if (old['version'] if old else 0) != version:
        raise HTTPException(409, 'Ответственный уже изменён. Обновите список')
    cur.execute('''INSERT INTO supplier_customer_assignments(supplier_id,company_id,member_id)
        VALUES(%s,%s,%s) ON CONFLICT(supplier_id,company_id) DO UPDATE SET
        member_id=EXCLUDED.member_id,version=supplier_customer_assignments.version+1,updated_at=NOW()
        RETURNING version''',(supplier_id,company_id,member_id))
    result={'companyId':company_id,'memberId':member_id,'previousMemberId':old['member_id'] if old else None,'version':cur.fetchone()['version']}
    return record(cur,supplier_id,user_id,operation,'assign_customer',result)


def set_member_active(cur,supplier_id,user_id,data):
    member_id=integer(data.get('memberId'));version=integer(data.get('version'))
    reason=data.get('reason','')
    if not isinstance(reason,str) or len(reason)>500:
        raise HTTPException(422,'Причина должна быть текстом до 500 символов')
    if type(data.get('active')) is not bool:
        raise HTTPException(422,'Укажите состояние менеджера')
    lock_leader(cur,supplier_id,user_id)
    operation=replay(cur,supplier_id,user_id,data,'member_active')
    if operation[3] is not None:return operation[3]
    cur.execute("SELECT * FROM supplier_team_members WHERE id=%s AND supplier_id=%s AND role='manager' FOR UPDATE",(member_id,supplier_id))
    member=cur.fetchone()
    if not member:raise HTTPException(404,'Менеджер не найден')
    if member['version']!=version:raise HTTPException(409,'Состав команды изменился. Обновите список')
    cur.execute('UPDATE supplier_team_members SET active=%s,version=version+1 WHERE id=%s RETURNING version',(data['active'],member_id))
    result={'memberId':member_id,'active':data['active'],'previousActive':member['active'],'version':cur.fetchone()['version']}
    if not data['active']:
        cur.execute('''UPDATE supplier_customer_assignments SET member_id=NULL,version=version+1,updated_at=NOW()
            WHERE supplier_id=%s AND member_id=%s RETURNING company_id''',(supplier_id,member_id))
        result['releasedCompanyIds']=[r['company_id'] for r in cur.fetchall()]
    return record(cur,supplier_id,user_id,operation,'member_active',result)
