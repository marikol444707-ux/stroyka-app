"""Connect an existing primary owner's cabinet, without claiming another card.

Lock order: buyer -> legal keys -> both supplier rows -> actors -> source link -> request.
The buyer row serializes this flow with catalog/merge/registration writers.
Matching legal keys locates a cabinet. Only its freshly authenticated primary
owner can consent; team leadership alone does not grant ownership authority.
"""
import os
import json
import re
import uuid
from contextlib import contextmanager

from fastapi import HTTPException
from psycopg2.extras import Json, RealDictCursor

from ..supplier_access.legal_identity import lock_legal_keys
from .connection_preview import diagnose
from .service import ADMIN_ROLES, ready

UNCHANGED_HISTORY_BLOCKERS={'OWNER_VERIFICATION_REQUIRED','HISTORY_REVIEW_REQUIRED','SHARED_SOURCE_CARD','DOCUMENT_OWNER_REVIEW'}


def owned_response_mutation(cur,user,path):
    """Narrow subscription classification; the command still authorizes under locks."""
    match=re.fullmatch(r'/supplier/connection-requests/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/(accept|decline)/?',str(path))
    if not match:return False
    cur.execute("SELECT to_regclass('public.supplier_buyer_connection_requests') AS relation")
    if not cur.fetchone()['relation']:return False
    cur.execute('''SELECT r.id FROM supplier_buyer_connection_requests r
        JOIN suppliers s ON s.id=r.target_supplier_id AND s.user_id=r.owner_user_id
        JOIN users u ON u.id=r.owner_user_id AND u.role='поставщик' AND COALESCE(u.active,TRUE)
        WHERE r.id=%s AND r.owner_user_id=%s''',(match.group(1),user.get('id')))
    return bool(cur.fetchone())


def connection_ready(cur):
    ready(cur)
    if os.getenv('PARTICIPANT_CONNECTIONS_ENABLED','0')!='1':
        raise HTTPException(503,'Подключение кабинетов пока не включено')
    cur.execute("SELECT to_regclass('public.supplier_buyer_connection_requests') AS relation")
    if not cur.fetchone()['relation']:
        raise HTTPException(503,'Подключение кабинетов требует обновления схемы')


@contextmanager
def transaction(deps):
    conn=deps['get_db']()
    try:
        conn.autocommit=False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            connection_ready(cur)
            yield cur
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def company_lock(cur, company_id):
    cur.execute('SELECT id,name,platform_account_id,active FROM companies WHERE id=%s FOR UPDATE',(company_id,))
    company=cur.fetchone()
    if not company or not company['platform_account_id']:
        raise HTTPException(404,'Организация недоступна')
    return company


def authorities(cur, source_id, target_id, actors):
    cur.execute('SELECT id,inn,ogrn FROM suppliers WHERE id=ANY(%s) ORDER BY id',([source_id,target_id],))
    before={r['id']:(r['inn'],r['ogrn']) for r in cur.fetchall()}
    lock_legal_keys(cur, [(key, value) for pair in before.values()
                          for key, value in zip(('inn', 'ogrn'), pair)])
    cur.execute('SELECT id,user_id,name,inn,ogrn,status,participant_owner_epoch FROM suppliers WHERE id=ANY(%s) ORDER BY id FOR UPDATE',([source_id,target_id],))
    suppliers={r['id']:r for r in cur.fetchall()}
    if before!={r['id']:(r['inn'],r['ogrn']) for r in suppliers.values()}:
        raise HTTPException(409,'Реквизиты изменились. Повторите проверку')
    cur.execute('SELECT id,role,active,supplier_team_epoch FROM users WHERE id=ANY(%s) ORDER BY id FOR SHARE',(sorted(set(actors)),))
    users={r['id']:r for r in cur.fetchall()}
    return suppliers,users


def is_admin(user):
    return user and user['active'] is not False and user['role'] in ADMIN_ROLES


def source_link(cur, company, supplier_id):
    cur.execute('''SELECT version,status,profile FROM company_supplier_links
        WHERE company_id=%s AND platform_account_id=%s AND supplier_id=%s FOR UPDATE''',
        (company['id'],company['platform_account_id'],supplier_id))
    row=cur.fetchone()
    if not row: raise HTTPException(404,'Карточка недоступна в выбранной организации')
    return row


def evidence(suppliers, source, target):
    return {key:{field:suppliers[key_id][field] for field in ('inn','ogrn')}
            for key,key_id in (('source',source),('target',target))}


def eligible(preview,target_id):
    return (preview['scenario']=='connect_existing' and preview['cabinet']
            and preview['cabinet']['supplierId']==target_id
            and not any(b['code'] not in UNCHANGED_HISTORY_BLOCKERS for b in preview['blockers']))


def view(row):
    return dict(id=str(row['id']),companyId=row['company_id'],targetSupplierId=row['target_supplier_id'],
                status=row['status'],version=row['version'],expiresAt=row['expires_at'])


def audit(cur, row, actor, action):
    # No cookies, invitation secrets, contacts or foreign customer details.
    cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,
        description,owner_scope,company_id) VALUES(%s,%s,%s,%s,'supplier_buyer_connection',%s,%s,'company',%s)''',
        (actor['id'],actor.get('name',''),actor['role'],'supplier_buyer_connection_'+action,row['target_supplier_id'],
         json.dumps(dict(requestId=str(row['id']),sourceSupplierId=row['source_supplier_id'],targetSupplierId=row['target_supplier_id'],
                         status=row['status'],version=row['version'])),row['company_id']))


def propose(deps, user, company_id, source_id, data):
    with transaction(deps) as cur:
        company=company_lock(cur,company_id)
        # Source provenance is checked before global target lookup.
        source_link(cur,company,source_id)
        cur.execute('SELECT user_id FROM suppliers WHERE id=%s',(data.targetSupplierId,))
        target=cur.fetchone()
        if not target or not target['user_id']:
            raise HTTPException(409,'Действующий кабинет не найден. Повторите проверку')
        suppliers,users=authorities(cur,source_id,data.targetSupplierId,[user['id'],target['user_id']])
        if suppliers[data.targetSupplierId]['user_id']!=target['user_id']:
            raise HTTPException(409,'Владелец кабинета изменился. Повторите проверку')
        issuer,owner=users.get(user['id']),users.get(target['user_id'])
        if not is_admin(issuer):raise HTTPException(403,'Полномочия администратора изменились')
        if not company['active']:raise HTTPException(409,'Компания отключена')
        link=source_link(cur,company,source_id)
        cur.execute('''SELECT * FROM supplier_buyer_connection_requests
            WHERE company_id=%s AND created_by_user_id=%s AND operation_key=%s''',
            (company_id,user['id'],str(data.requestId)))
        previous=cur.fetchone()
        if previous:
            if (previous['source_supplier_id']!=source_id or previous['target_supplier_id']!=data.targetSupplierId
                    or previous['source_version']!=data.expectedSourceVersion or previous['issuer_epoch']!=issuer['supplier_team_epoch']):
                raise HTTPException(409,'Повтор запроса не совпадает с исходным действием')
            return view(previous)
        if link['version']!=data.expectedSourceVersion:
            raise HTTPException(409,'Карточка изменилась. Повторите проверку')
        preview=diagnose(cur,company,source_id)
        # Shared source/doc history are intentionally untouched. They remain
        # blockers for a later merge, but do not prevent a separate buyer link.
        if (not eligible(preview,data.targetSupplierId)
                or suppliers[data.targetSupplierId]['status'] not in (None,'','Активный')
                or not owner or owner['active'] is False or owner['role']!='поставщик'):
            raise HTTPException(409,'Подключение требует новой проверки кабинета')
        cur.execute('''SELECT 1 FROM supplier_buyer_connection_requests
            WHERE company_id=%s AND target_supplier_id=%s AND status='pending' ''',(company_id,data.targetSupplierId))
        if cur.fetchone():raise HTTPException(409,'Запрос этому кабинету уже создан. Откройте или отзовите его')
        cur.execute('''INSERT INTO supplier_buyer_connection_requests
            (id,company_id,platform_account_id,source_supplier_id,target_supplier_id,source_version,
             owner_user_id,owner_epoch,target_owner_epoch,created_by_user_id,issuer_epoch,operation_key,evidence)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (str(uuid.uuid4()),company_id,company['platform_account_id'],source_id,data.targetSupplierId,link['version'],
             owner['id'],owner['supplier_team_epoch'],suppliers[data.targetSupplierId]['participant_owner_epoch'],
             issuer['id'],issuer['supplier_team_epoch'],str(data.requestId),
             Json(evidence(suppliers,source_id,data.targetSupplierId))))
        row=cur.fetchone();audit(cur,row,user,'requested')
        return view(row)


def decision(deps,user,request_id,data,action, *, company_id=None,source_id=None):
    with transaction(deps) as cur:
        cur.execute('SELECT * FROM supplier_buyer_connection_requests WHERE id=%s',(str(request_id),))
        initial=cur.fetchone()
        if not initial or (action=='revoke' and (initial['company_id']!=company_id or initial['source_supplier_id']!=source_id)):
            raise HTTPException(404,'Запрос недоступен')
        if action!='revoke' and initial['owner_user_id']!=user['id']:
            raise HTTPException(404,'Запрос недоступен')
        company=company_lock(cur,initial['company_id'])
        suppliers,users=authorities(cur,initial['source_supplier_id'],initial['target_supplier_id'],
                                    [initial['owner_user_id'],initial['created_by_user_id'],user['id']])
        actor=users.get(user['id'])
        target=suppliers.get(initial['target_supplier_id'])
        if action=='revoke':
            if not is_admin(actor):raise HTTPException(403,'Полномочия администратора изменились')
        elif not actor or actor['active'] is False or actor['role']!='поставщик' or not target or target['user_id']!=user['id']:
            raise HTTPException(404,'Запрос недоступен этому кабинету')
        link=source_link(cur,company,initial['source_supplier_id'])
        cur.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM supplier_buyer_connection_requests WHERE id=%s FOR UPDATE',(str(request_id),))
        row=cur.fetchone()
        state={'accept':'accepted','decline':'declined','revoke':'revoked'}[action]
        if row['status']==state:
            if (data.expectedVersion!=row['version']-1 or (action!='revoke' and
                    (actor['supplier_team_epoch']!=row['owner_epoch'] or target['participant_owner_epoch']!=row['target_owner_epoch']))):
                raise HTTPException(409,'Полномочия изменились. Обновите запросы')
            return view(row)
        if row['status']!='pending' or row['version']!=data.expectedVersion:
            raise HTTPException(409,'Запрос уже изменился. Обновите список')
        if action=='accept':
            issuer=users.get(row['created_by_user_id'])
            if (not row['valid'] or not company['active'] or company['platform_account_id']!=row['platform_account_id']
                    or not is_admin(issuer) or issuer['supplier_team_epoch']!=row['issuer_epoch']
                    or actor['supplier_team_epoch']!=row['owner_epoch'] or link['version']!=row['source_version']
                    or target['participant_owner_epoch']!=row['target_owner_epoch']
                    or target['status'] not in (None,'','Активный')
                    or evidence(suppliers,row['source_supplier_id'],row['target_supplier_id'])!=row['evidence']):
                raise HTTPException(409,'Запрос устарел или полномочия изменились. Нужна новая проверка')
            preview=diagnose(cur,company,row['source_supplier_id'])
            if not eligible(preview,row['target_supplier_id']):
                raise HTTPException(409,'Связи кабинета изменились. Нужна новая проверка')
            cur.execute('''INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id,source_type,source_detail)
                SELECT %s,%s,%s,'owner_confirmed_connection','Подключение подтверждено владельцем кабинета'
                WHERE %s>clock_timestamp() RETURNING id''',
                (company['id'],company['platform_account_id'],row['target_supplier_id'],row['expires_at']))
            if not cur.fetchone():raise HTTPException(409,'Срок запроса истёк. Нужна новая проверка')
        cur.execute('''UPDATE supplier_buyer_connection_requests SET status=%s,version=version+1,
            decided_at=NOW(),decided_by_user_id=%s WHERE id=%s RETURNING *''',(state,user['id'],str(request_id)))
        result=cur.fetchone();audit(cur,result,user,state)
        return view(result)
