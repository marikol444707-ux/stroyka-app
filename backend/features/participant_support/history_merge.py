"""Fresh, company-scoped historical disclosure with immutable impact evidence."""
import json
import os
import uuid
from contextlib import contextmanager

from fastapi import Depends, HTTPException, Path
from psycopg2 import sql, errors
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, StrictBool, conint, constr

from .connection_preview import diagnose
from .connections import company_lock, authorities, is_admin, source_link
from .service import ready
from .merge_inventory import inventory
from ..supplier_access.company_merge import pair, apply_pair

PLAN_TTL_SECONDS=900
Id=conint(strict=True,ge=1,le=2147483647)

class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    targetSupplierId: Id

class Confirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    reason: constr(strip_whitespace=True,min_length=10,max_length=1000)


@contextmanager
def transaction(deps,*,snapshot=False):
    conn=deps['get_db']()
    try:
        conn.autocommit=False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if snapshot:cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cur.execute("SET LOCAL statement_timeout='15s'; SET LOCAL lock_timeout='3s'")
            ready(cur)
            if os.getenv('PARTICIPANT_HISTORY_MERGE_ENABLED','0')!='1':raise HTTPException(503,'Объединение истории пока не включено')
            cur.execute("SELECT to_regclass('public.supplier_history_merge_plans') AS relation")
            if not cur.fetchone()['relation']:raise HTTPException(503,'Объединение истории требует обновления схемы')
            yield cur
            conn.commit()
    except (errors.DeadlockDetected,errors.SerializationFailure,errors.LockNotAvailable,errors.QueryCanceled):
        conn.rollback()
        raise HTTPException(409,'История сейчас изменяется. Повторите проверку и объединение')
    except Exception:
        conn.rollback();raise
    finally:conn.close()


def authorized_pair(cur,company,source,target,actor):
    source_link(cur,company,source)
    if source_link(cur,company,target)['status']!='Активный':raise HTTPException(409,'Связь кабинета с компанией отключена. Сначала проверьте доступ')
    cur.execute('''SELECT s.user_id FROM suppliers s JOIN company_supplier_links l ON l.supplier_id=s.id
        WHERE s.id=%s AND l.company_id=%s AND l.platform_account_id=%s''',
        (target,company['id'],company['platform_account_id']))
    cabinet=cur.fetchone()
    if not cabinet or not cabinet['user_id']:raise HTTPException(404,'Кабинет недоступен в выбранной организации')
    suppliers,users=authorities(cur,source,target,[actor['id'],cabinet['user_id']])
    current,owner=users.get(actor['id']),users.get(cabinet['user_id'])
    if not is_admin(current):raise HTTPException(403,'Полномочия администратора изменились')
    if (not company['active'] or not owner or owner['active'] is False or owner['role']!='поставщик'
            or suppliers[target]['user_id']!=owner['id']):raise HTTPException(409,'Компания или владелец кабинета изменились')
    target_row,source_row=pair(cur,company,target,source)
    review=diagnose(cur,company,source)
    allowed={'HISTORICAL_ACCESS_REVIEW_REQUIRED','HISTORY_REVIEW_REQUIRED'}
    if (review['scenario']!='merge_cards' or not review['cabinet'] or review['cabinet']['supplierId']!=target
            or any(b['code'] not in allowed for b in review['blockers'])):
        raise HTTPException(409,'Принадлежность карточек требует новой проверки')
    return target_row,source_row,current,owner


def view(row):
    manifest=row['manifest']
    return dict(id=str(row['id']),companyId=row['company_id'],sourceId=row['source_supplier_id'],
                targetId=row['target_supplier_id'],expiresAt=row['expires_at'],
                affected=manifest['affected'],newAccess=manifest['newAccess'],stillClosed=manifest['stillClosed'])


def propose(deps,user,company_id,source,data,contracts=False):
    with transaction(deps,snapshot=True) as cur:
        company=company_lock(cur,company_id)
        target,source_row,actor,owner=authorized_pair(cur,company,source,data.targetSupplierId,user)
        manifest=inventory(cur,company_id,source,target['id'],owner,contracts,deps['history_file_storage'])
        cur.execute('''INSERT INTO supplier_history_merge_plans
            (id,company_id,platform_account_id,source_supplier_id,target_supplier_id,actor_id,actor_epoch,
             owner_id,owner_epoch,target_owner_epoch,manifest,expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()+%s*INTERVAL '1 second') RETURNING *''',
            (str(uuid.uuid4()),company_id,company['platform_account_id'],source,target['id'],actor['id'],
             actor['supplier_team_epoch'],owner['id'],owner['supplier_team_epoch'],target['participant_owner_epoch'],
             Json(manifest),PLAN_TTL_SECONDS))
        return view(cur.fetchone())


def confirm(deps,user,company_id,source,plan_id,data,contracts=False):
    if data.confirmed is not True:raise HTTPException(422,'Подтвердите принадлежность карточек и документов')
    with transaction(deps) as cur:
        cur.execute('''SELECT * FROM supplier_history_merge_plans WHERE id=%s AND company_id=%s
            AND source_supplier_id=%s AND actor_id=%s''',(str(plan_id),company_id,source,user['id']))
        plan=cur.fetchone()
        if not plan:raise HTTPException(404,'План объединения недоступен')
        # Pin all inspected predicates, including new attachments/recipients,
        # through the mutation. Contended writers time out safely before apply.
        for table in plan['manifest']['tables']:
            cur.execute(sql.SQL('LOCK TABLE {} IN SHARE MODE').format(sql.Identifier(table)))
        company=company_lock(cur,company_id)
        suppliers,users=authorities(cur,source,plan['target_supplier_id'],[user['id'],plan['owner_id']])
        actor,owner=users.get(user['id']),users.get(plan['owner_id'])
        target=suppliers.get(plan['target_supplier_id'])
        if not is_admin(actor):raise HTTPException(403,'Полномочия администратора изменились')
        if (company['platform_account_id']!=plan['platform_account_id'] or not company['active']
            or actor['supplier_team_epoch']!=plan['actor_epoch'] or not owner or owner['role']!='поставщик'
            or owner['active'] is False or owner['supplier_team_epoch']!=plan['owner_epoch']
            or not target or target['user_id']!=plan['owner_id'] or target['participant_owner_epoch']!=plan['target_owner_epoch']):
            raise HTTPException(409,'Полномочия или кабинет изменились. Создайте новый план')
        cur.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM supplier_history_merge_plans WHERE id=%s FOR UPDATE',(str(plan_id),))
        plan=cur.fetchone()
        if plan['applied_at']:
            if (data.reason!=plan['reason'] or suppliers[source]['user_id']!=plan['owner_id']
                    or suppliers[source]['participant_owner_epoch']!=plan['result']['sourceOwnerEpoch']):
                raise HTTPException(409,'Повтор не совпадает с выполненным объединением')
            return plan['result']
        if not plan['valid']:raise HTTPException(409,'План устарел. Повторите проверку')
        target,source_row,actor,owner=authorized_pair(cur,company,source,plan['target_supplier_id'],user)
        current=inventory(cur,company_id,source,target['id'],owner,contracts,deps['history_file_storage'])
        if current!=plan['manifest']:raise HTTPException(409,'Документы или назначения изменились. Повторите проверку')
        cur.execute('SELECT expires_at>clock_timestamp() AS valid FROM supplier_history_merge_plans WHERE id=%s',(str(plan_id),))
        if not cur.fetchone()['valid']:raise HTTPException(409,'Срок плана истёк. Повторите проверку')
        apply_pair(cur,target,source_row)
        result=dict(ok=True,planId=str(plan_id),companyId=company_id,sourceId=source,targetId=target['id'],
                    sourceOwnerEpoch=source_row['participant_owner_epoch']+1)
        cur.execute('UPDATE supplier_history_merge_plans SET applied_at=NOW(),reason=%s,result=%s WHERE id=%s',
                    (data.reason,Json(result),str(plan_id)))
        cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,
            description,owner_scope,company_id) VALUES(%s,%s,%s,'supplier_history_merged','supplier',%s,%s,'company',%s)''',
            (actor['id'],user.get('name',''),actor['role'],source,
             json.dumps(dict(planId=str(plan_id),sourceId=source,targetId=target['id'],ownerId=owner['id'],
                             before=dict(sourceOwner=None,sourceVersion=source_row['link_version'],targetVersion=target['link_version']),
                             after=dict(sourceOwner=owner['id'],sourceVersion=source_row['link_version']+1,targetVersion=target['link_version']+1))),company_id))
        return result


def register_history_merge(app,deps,admin):
    # Match the file router's startup configuration, including in test fixtures.
    contracts=all(os.getenv(key,'0')=='1' for key in ('SUPPLIER_DEAL_PARTIES_ENABLED','SUPPLIER_CONTRACT_SNAPSHOTS_ENABLED'))
    @app.post('/system/companies/{company_id}/participants/{supplier_id}/history-merge-plans')
    def preview(data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,data,contracts)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/history-merge-plans/{plan_id}/confirm')
    def apply(plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,plan_id,data,contracts)
