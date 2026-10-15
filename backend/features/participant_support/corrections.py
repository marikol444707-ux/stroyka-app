"""Correct a buyer link with immutable evidence and atomic audit.

Separate modes withdraw unanswered requests or reject unawarded received quotes.
No mode reassigns cabinets, undoes merges, or rewrites issued documents.
Confirm takes business predicate locks before buyer/identity locks, matching the
history-merge order. Issued financial documents remain unchanged.
"""
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime

from fastapi import Depends, HTTPException, Path
from psycopg2 import errors, sql
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, StrictBool, constr, field_validator
from typing import Literal

from .connections import company_lock, authorities, is_admin, evidence
from .correction_inventory import inventory
from .service import ready
from . import correction_rfqs, correction_quotes, correction_issued, correction_invoice_access


class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operationId: uuid.UUID


class Confirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    reason: constr(strip_whitespace=True,min_length=10,max_length=1000)

    @field_validator('confirmed')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Подтвердите отключение этой связи')
        return value


class AffectedRequest(BaseModel):
    requestId: int
    recipientId: int
    offerIds: list[int]


class AffectedOffer(BaseModel):
    offerId: int
    statusBefore: Literal['Ожидает ответа','Получено','Утверждено']
    statusAfter: Literal['Отозвано','Отклонено','Ожидает ответа','Получено','Утверждено']


class PreservedIssuedDocument(BaseModel):
    kind: Literal['offer','invoice','delivery','receipt']
    id: int


class PlanView(BaseModel):
    id: uuid.UUID
    companyId: int
    companyName: str
    sourceId: int
    targetId: int
    targetName: str
    expiresAt: datetime
    retainedDocuments: dict[str,int]
    mode: Literal['disconnect_unused','withdraw_unanswered_rfq','reject_received_quotes','revoke_issued_access','revoke_invoice_access'] = 'disconnect_unused'
    affectedRequests: list[AffectedRequest] = Field(default_factory=list)
    queuedNotificationCount: int = 0
    affectedOffers: list[AffectedOffer] = Field(default_factory=list)
    preservedQuoteFileCount: int = 0
    preservedIssuedDocuments: list[PreservedIssuedDocument] = Field(default_factory=list)
    preservedIssuedFileCount: int = 0


class Result(BaseModel):
    ok: StrictBool
    planId: uuid.UUID
    companyId: int
    sourceId: int
    targetId: int
    relationshipStatus: str
    relationshipVersion: int
    withdrawnRequestCount: int = 0
    rejectedQuoteCount: int = 0
    revokedRequestCount: int = 0
    preservedIssuedCounts: dict[str,int] = Field(default_factory=dict)


@contextmanager
def transaction(deps,*,snapshot=False,mode='disconnect_unused'):
    conn=deps['get_db']()
    try:
        conn.autocommit=False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if snapshot:cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cur.execute("SET LOCAL statement_timeout='15s'; SET LOCAL lock_timeout='3s'")
            ready(cur)
            if os.getenv('PARTICIPANT_CORRECTIONS_ENABLED','0')!='1':
                raise HTTPException(503,'Исправление подключений пока не включено')
            flag={'disconnect_unused':None,correction_rfqs.MODE:'PARTICIPANT_RFQ_CORRECTIONS_ENABLED',correction_quotes.MODE:'PARTICIPANT_QUOTE_CORRECTIONS_ENABLED',
                correction_issued.MODE:'PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED',
                correction_invoice_access.MODE:'PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED'}[mode]
            if flag and os.getenv(flag,'0')!='1':
                raise HTTPException(503,'Этот способ исправления подключения пока не включён')
            cur.execute("SELECT to_regclass('public.supplier_connection_correction_plans') AS relation")
            if not cur.fetchone()['relation']:raise HTTPException(503,'Исправление подключений требует обновления схемы')
            yield cur
        conn.commit()
    except (errors.DeadlockDetected,errors.SerializationFailure,errors.LockNotAvailable,errors.QueryCanceled) as error:
        conn.rollback()
        if snapshot and isinstance(error,errors.SerializationFailure):raise
        raise HTTPException(409,'Данные сейчас изменяются. Повторите проверку подключения')
    except errors.UniqueViolation:
        conn.rollback()
        if snapshot:raise
        raise HTTPException(409,'Исправление уже записано. Обновите список')
    except Exception:
        conn.rollback();raise
    finally:conn.close()


def request_row(cur,company,source,request_id):
    cur.execute('''SELECT * FROM supplier_buyer_connection_requests WHERE id=%s
        AND company_id=%s AND platform_account_id=%s AND source_supplier_id=%s''',
        (str(request_id),company['id'],company['platform_account_id'],source))
    row=cur.fetchone()
    if not row:raise HTTPException(404,'Подключение недоступно в выбранной компании')
    if row['status']!='accepted':raise HTTPException(409,'Подключение ещё не выполнено')
    return row


def authorize(cur,company,source,request_id,user):
    request=request_row(cur,company,source,request_id)
    suppliers,users=authorities(cur,source,request['target_supplier_id'],[user['id'],request['owner_user_id']])
    actor,owner=users.get(user['id']),users.get(request['owner_user_id'])
    if not is_admin(actor):raise HTTPException(403,'Полномочия администратора изменились')
    target=suppliers.get(request['target_supplier_id']);original=suppliers.get(source)
    if (not company['active'] or not target or not original or not owner or owner['active'] is False
            or owner['role']!='поставщик' or target['user_id']!=owner['id']
            or owner['supplier_team_epoch']!=request['owner_epoch']
            or target['participant_owner_epoch']!=request['target_owner_epoch']
            or original['user_id'] is not None or original['participant_owner_epoch']!=0
            or evidence(suppliers,source,target['id'])!=request['evidence']):
        raise HTTPException(409,'Компания, владелец или реквизиты изменились. Нужна отдельная проверка')
    cur.execute('''SELECT *,created_at AT TIME ZONE current_setting('TimeZone') AS created_instant FROM company_supplier_links
        WHERE company_id=%s AND platform_account_id=%s AND supplier_id=ANY(%s) ORDER BY supplier_id FOR UPDATE''',
        (company['id'],company['platform_account_id'],[source,target['id']]))
    links={r['supplier_id']:r for r in cur.fetchall()}
    if set(links)!={source,target['id']}:raise HTTPException(404,'Связь недоступна в выбранной компании')
    cur.execute('SELECT * FROM supplier_buyer_connection_requests WHERE id=%s FOR UPDATE',(str(request_id),))
    request=cur.fetchone()
    return request,original,target,actor,owner,links


def checked_manifest(cur,company,request,source,target,owner,links,*,mode='disconnect_unused'):
    link=links[target['id']]
    if (link['status']!='Активный' or link['source_type']!='owner_confirmed_connection'
            or link['created_instant']!=request['decided_at'] or link['version']!=1
            or links[source['id']]['version']!=request['source_version']
            or any((r['profile'] or {}).get('mergedIntoSupplierId') for r in links.values())):
        raise HTTPException(409,'Связь уже изменялась или карточки объединены. Нужна отдельная проверка')
    if mode==correction_invoice_access.MODE and correction_invoice_access.PROFILE_KEY in (link['profile'] or {}):
        raise HTTPException(409,'У связи уже есть закрытые счета. Нужна отдельная проверка доступа')
    # A source was unowned in the accepted request. Never undo a later merge.
    manifest=inventory(cur,company['id'],source['id'],target['id'],owner,mode=mode)
    manifest['relationships']={str(key):dict(id=r['id'],version=r['version'],status=r['status']) for key,r in links.items()}
    return manifest


def view(row):
    rfq=row['manifest'].get('rfq') or {}
    return dict(id=str(row['id']),companyId=row['company_id'],companyName=row['manifest']['companyName'],
                sourceId=row['source_supplier_id'],targetId=row['target_supplier_id'],targetName=row['manifest']['targetName'],
                expiresAt=row['expires_at'],retainedDocuments=row['manifest']['retainedDocuments'],
                mode=rfq.get('mode','disconnect_unused'),affectedRequests=rfq.get('affectedRequests',[]),
                queuedNotificationCount=len(rfq.get('queuedMessageIds',[]))+len(rfq.get('queuedEmailIds',[])),
                affectedOffers=rfq.get('affectedOffers',[]),preservedQuoteFileCount=rfq.get('preservedQuoteFileCount',0),
                preservedIssuedDocuments=rfq.get('preservedIssuedDocuments',[]),preservedIssuedFileCount=rfq.get('preservedIssuedFileCount',0))


def propose(deps,user,company_id,source,request_id,data,*,mode='disconnect_unused'):
    # A repeatable-read snapshot may predate a concurrent identical proposal
    # waiting on the buyer lock. Retry that metadata-only transaction once.
    for attempt in range(2):
        try:return _propose(deps,user,company_id,source,request_id,data,mode=mode)
        except (errors.SerializationFailure,errors.UniqueViolation):
            if attempt:raise HTTPException(409,'Данные сейчас изменяются. Повторите проверку подключения')


def _propose(deps,user,company_id,source,request_id,data,*,mode='disconnect_unused'):
    with transaction(deps,snapshot=True,mode=mode) as cur:
        company=company_lock(cur,company_id)
        request,original,target,actor,owner,links=authorize(cur,company,source,request_id,user)
        cur.execute('SELECT * FROM supplier_connection_correction_plans WHERE company_id=%s AND actor_id=%s AND operation_id=%s',
                    (company_id,user['id'],str(data.operationId)))
        previous=cur.fetchone()
        if previous:
            if previous['connection_request_id']!=request['id'] or previous['source_supplier_id']!=source or previous['actor_epoch']!=actor['supplier_team_epoch'] or (previous['manifest'].get('rfq') or {}).get('mode','disconnect_unused')!=mode:
                raise HTTPException(409,'Повтор запроса не совпадает с исходной проверкой')
            cur.execute('SELECT expires_at>clock_timestamp() AS valid FROM supplier_connection_correction_plans WHERE id=%s',(str(previous['id']),))
            if not cur.fetchone()['valid'] or previous['applied_at']:raise HTTPException(409,'План уже завершён или устарел. Обновите список')
            return view(previous)
        manifest=checked_manifest(cur,company,request,original,target,owner,links,mode=mode)
        manifest.update(companyName=company['name'],targetName=target['name'])
        cur.execute('''INSERT INTO supplier_connection_correction_plans(id,connection_request_id,company_id,platform_account_id,
            source_supplier_id,target_supplier_id,target_link_id,actor_id,actor_epoch,owner_id,owner_epoch,target_owner_epoch,
            operation_id,manifest,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()+INTERVAL '15 minutes') RETURNING *''',
            (str(uuid.uuid4()),str(request_id),company_id,company['platform_account_id'],source,target['id'],links[target['id']]['id'],
             user['id'],actor['supplier_team_epoch'],owner['id'],owner['supplier_team_epoch'],target['participant_owner_epoch'],str(data.operationId),Json(manifest)))
        return view(cur.fetchone())


def audit(cur,actor,company,plan,result,reason):
    rfq=plan['manifest'].get('rfq')
    rfq_change=dict(before=dict(visible=True,recipientStatus='Ожидает ответа',offerStatus='Ожидает ответа'),
        after=dict(visible=False,recipientStatus='Отозвано',offerStatus='Отозвано'),
        cancelledMessageIds=rfq['queuedMessageIds'],cancelledEmailRecipientIds=rfq['queuedEmailIds']) if rfq else None
    if rfq and rfq.get('mode') in (correction_quotes.MODE,correction_issued.MODE,correction_invoice_access.MODE):
        rfq_change.update(before=dict(visible=True),after=dict(visible=False),
            recipientChanges=rfq['recipientChanges'],offerChanges=rfq['affectedOffers'])
        if rfq['mode'] in (correction_issued.MODE,correction_invoice_access.MODE):
            rfq_change.update(preservedIssuedDocuments=rfq['preservedIssuedDocuments'],preservedIssuedFileCount=rfq['preservedIssuedFileCount'])
        if rfq['mode']==correction_invoice_access.MODE:
            rfq_change['closedStandaloneInvoiceIds']=correction_invoice_access.direct_ids(rfq)
    cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,description,owner_scope,company_id)
        VALUES(%s,%s,%s,'supplier_connection_corrected','supplier',%s,%s,'company',%s)''',
        (actor['id'],actor.get('name',''),actor['role'],plan['target_supplier_id'],
         json.dumps(dict(planId=str(plan['id']),requestId=str(plan['connection_request_id']),sourceId=plan['source_supplier_id'],
                         targetId=plan['target_supplier_id'],linkId=plan['target_link_id'],before=plan['manifest']['relationships'][str(plan['target_supplier_id'])],
                         after=dict(status=result['relationshipStatus'],version=result['relationshipVersion']),
                         affectedRequests=(rfq or {}).get('affectedRequests',[]),rfqChange=rfq_change,reason=reason),ensure_ascii=False),company['id']))


def confirm(deps,user,company_id,source,request_id,plan_id,data,*,mode='disconnect_unused'):
    with transaction(deps,mode=mode) as cur:
        cur.execute('''SELECT * FROM supplier_connection_correction_plans WHERE id=%s AND company_id=%s
            AND source_supplier_id=%s AND connection_request_id=%s AND actor_id=%s''',
            (str(plan_id),company_id,source,str(request_id),user['id']))
        plan=cur.fetchone()
        if not plan:raise HTTPException(404,'План исправления недоступен')
        if (plan['manifest'].get('rfq') or {}).get('mode','disconnect_unused')!=mode:raise HTTPException(409,'Тип плана не совпадает с выбранной операцией')
        if not plan['applied_at']:
            for table in plan['manifest']['tables']:
                lock_mode=sql.SQL('SHARE ROW EXCLUSIVE') if mode!='disconnect_unused' and table in correction_rfqs.MUTABLE_TABLES else sql.SQL('SHARE')
                cur.execute(sql.SQL('LOCK TABLE {} IN {} MODE').format(sql.Identifier(table),lock_mode))
        company=company_lock(cur,company_id)
        request,original,target,actor,owner,links=authorize(cur,company,source,request_id,user)
        if (company['platform_account_id']!=plan['platform_account_id'] or actor['supplier_team_epoch']!=plan['actor_epoch']
                or owner['id']!=plan['owner_id'] or owner['supplier_team_epoch']!=plan['owner_epoch']
                or target['participant_owner_epoch']!=plan['target_owner_epoch'] or links[target['id']]['id']!=plan['target_link_id']):
            raise HTTPException(409,'Полномочия или связь изменились. Подготовьте новый план')
        cur.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM supplier_connection_correction_plans WHERE id=%s FOR UPDATE',(str(plan_id),))
        plan=cur.fetchone()
        if plan['applied_at']:
            if data.reason!=plan['reason'] or links[target['id']]['status']!='Неактивный' or links[target['id']]['version']!=plan['result']['relationshipVersion']:
                raise HTTPException(409,'Повтор не совпадает с выполненным исправлением')
            if mode!='disconnect_unused':correction_rfqs.verify_replay(cur,company_id,plan['manifest']['rfq'])
            if mode==correction_invoice_access.MODE:correction_invoice_access.verify_replay(cur,company_id,target['id'],plan['manifest']['rfq'])
            return plan['result']
        if not plan['valid']:raise HTTPException(409,'План устарел. Повторите проверку')
        current=checked_manifest(cur,company,request,original,target,owner,links,mode=mode)
        current.update(companyName=company['name'],targetName=target['name'])
        if current!=plan['manifest']:raise HTTPException(409,'Документы, адресаты или назначения изменились. Подготовьте новый план')
        if mode!='disconnect_unused':correction_rfqs.apply(cur,company_id,current['rfq'],actor,plan_id)
        profile_patch={correction_invoice_access.PROFILE_KEY:correction_invoice_access.direct_ids(current['rfq'])} if mode==correction_invoice_access.MODE else {}
        cur.execute('''UPDATE company_supplier_links SET status='Неактивный',version=version+1,
            profile=COALESCE(profile,'{}'::jsonb) || %s::jsonb
            WHERE id=%s AND EXISTS(SELECT 1 FROM supplier_connection_correction_plans p WHERE p.id=%s AND p.expires_at>clock_timestamp()) RETURNING version''',
            (Json(profile_patch),plan['target_link_id'],str(plan_id)))
        updated=cur.fetchone()
        if not updated:raise HTTPException(409,'Срок плана истёк. Повторите проверку')
        result=dict(ok=True,planId=str(plan_id),companyId=company_id,sourceId=source,targetId=target['id'],relationshipStatus='Неактивный',relationshipVersion=updated['version'])
        if mode not in ('disconnect_unused',correction_issued.MODE,correction_invoice_access.MODE):result['withdrawnRequestCount']=len(current['rfq']['affectedRequests'])
        if mode==correction_quotes.MODE:result['rejectedQuoteCount']=sum(o['statusBefore']=='Получено' for o in current['rfq']['affectedOffers'])
        if mode in (correction_issued.MODE,correction_invoice_access.MODE):
            result.update(revokedRequestCount=len(current['rfq']['affectedRequests']),preservedIssuedCounts=correction_issued.counts(current['rfq']))
        cur.execute('UPDATE supplier_connection_correction_plans SET applied_at=NOW(),reason=%s,result=%s WHERE id=%s',
                    (data.reason,Json(result),str(plan_id)))
        audit(cur,actor,company,plan,result,data.reason)
        return result


def register_corrections(app,deps,admin):
    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/correction-plans',response_model=PlanView)
    def proposal(request_id:uuid.UUID,data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,request_id,data)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/correction-plans/{plan_id}/confirm',response_model=Result)
    def apply(request_id:uuid.UUID,plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,request_id,plan_id,data)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/rfq-correction-plans',response_model=PlanView)
    def rfq_proposal(request_id:uuid.UUID,data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,request_id,data,mode=correction_rfqs.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/rfq-correction-plans/{plan_id}/confirm',response_model=Result)
    def rfq_apply(request_id:uuid.UUID,plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,request_id,plan_id,data,mode=correction_rfqs.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/quote-correction-plans',response_model=PlanView)
    def quote_proposal(request_id:uuid.UUID,data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,request_id,data,mode=correction_quotes.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/quote-correction-plans/{plan_id}/confirm',response_model=Result)
    def quote_apply(request_id:uuid.UUID,plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,request_id,plan_id,data,mode=correction_quotes.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/issued-access-plans',response_model=PlanView)
    def issued_proposal(request_id:uuid.UUID,data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,request_id,data,mode=correction_issued.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/issued-access-plans/{plan_id}/confirm',response_model=Result)
    def issued_apply(request_id:uuid.UUID,plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,request_id,plan_id,data,mode=correction_issued.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/invoice-access-plans',response_model=PlanView)
    def invoice_proposal(request_id:uuid.UUID,data:Proposal,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return propose(deps,user,company_id,supplier_id,request_id,data,mode=correction_invoice_access.MODE)

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/invoice-access-plans/{plan_id}/confirm',response_model=Result)
    def invoice_apply(request_id:uuid.UUID,plan_id:uuid.UUID,data:Confirmation,company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),user:dict=Depends(admin)):
        return confirm(deps,user,company_id,supplier_id,request_id,plan_id,data,mode=correction_invoice_access.MODE)
