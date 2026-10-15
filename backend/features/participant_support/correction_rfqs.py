"""Exact unanswered RFQs only; no correction of quotes, invoices or history."""
import hashlib
import json

from fastapi import HTTPException
from psycopg2 import sql

from ..supplier_access.email_attempts import EMAIL_QUEUED, EMAIL_UNCONFIRMED

MODE='withdraw_unanswered_rfq'
MUTABLE_TABLES={'supplier_offers','supplier_offer_events','supply_request_recipients','messenger_outbox'}
EXTRA_TABLES={'messenger_outbox','supplier_email_attempts','supplier_offer_events'}
REQUIRED_COLUMNS={
    'supply_requests':{'id','company_id','status','selected_suppliers','prorab_confirmed_at','director_approved_at'},
    'supply_request_recipients':{'id','company_id','request_id','supplier_id','target_supplier_id','supplier_user_id',
        'supplier_group_ids','visible_to_supplier','status','responded_at','email_notification_status','max_notification_status','max_outbox_id'},
    'supplier_offers':{'id','company_id','request_id','supplier_id','status','responded_at','price_per_unit','total_price',
        'delivery_days','pdf_url','valid_until','supplier_message','notes','delivery_status','items_kp_json','party_snapshot_json'},
    'supplier_offer_events':{'id','offer_id','event_type','status_from','status_to','actor_name','actor_role','payload_json'},
    'supplier_email_attempts':{'id','company_id','request_id','recipient_id','outcome','finished_at'},
    'messenger_outbox':{'id','company_id','owner_scope','provider','entity_type','entity_id','user_id','event_type','status','next_attempt_at','updated_at'},
}


def blocked(message):
    raise HTTPException(409,message)


def rows(cur,query,params):
    cur.execute(query+' LIMIT 2001',params)
    result=[r['row'] for r in cur.fetchall()]
    if len(result)>2000:blocked('Слишком много записей для отзыва заявок. Нужна отдельная проверка')
    return result


def offer_references(cur,schema):
    refs={table:{c for c in columns if c=='offer_id' or c.endswith('_offer_id')} for table,columns in schema.items()}
    cur.execute('''SELECT t.relname AS table_name,a.attname AS column_name FROM pg_constraint f
        JOIN pg_class t ON t.oid=f.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN LATERAL unnest(f.conkey,f.confkey) k(local_key,remote_key) ON TRUE
        JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.local_key
        JOIN pg_attribute p ON p.attrelid=f.confrelid AND p.attnum=k.remote_key AND p.attname='id'
        WHERE f.contype='f' AND f.confrelid='public.supplier_offers'::regclass AND n.nspname='public' ''')
    for row in cur.fetchall():refs.setdefault(row['table_name'],set()).add(row['column_name'])
    return refs


def unanswered(cur,company,target,owner,owner_ids,schema):
    if any(not columns<=schema.get(table,set()) for table,columns in REQUIRED_COLUMNS.items()):
        raise HTTPException(503,'Отзыв заявок требует полного реестра отправок')
    recipients=rows(cur,'''SELECT to_jsonb(r) AS row FROM supply_request_recipients r
        WHERE r.company_id=%s AND (r.supplier_id=%s OR r.target_supplier_id=%s
            OR %s=ANY(COALESCE(r.supplier_group_ids,'{}'::int[]))) ORDER BY r.id''',(company,target,target,target))
    if len(recipients)>50:blocked('Отзыв более 50 заявок требует отдельной проверки')
    request_ids=sorted({r['request_id'] for r in recipients})
    recipient_ids=[r['id'] for r in recipients]
    requests=rows(cur,'SELECT to_jsonb(q) AS row FROM supply_requests q WHERE q.id=ANY(%s) ORDER BY q.id',(request_ids,))
    by_request={q['id']:q for q in requests}
    for r in recipients:
        q=by_request.get(r['request_id'])
        if not q or q['company_id']!=company:blocked('Компания заявки или её адресата не подтверждена')
        if (r['supplier_id']!=target or r['target_supplier_id']!=target or r['supplier_user_id']!=owner['id']
                or set(r.get('supplier_group_ids') or [])-{target}):
            blocked('Заявка адресована группе карточек. Нужна отдельная проверка адресатов')
        if (not r['visible_to_supplier'] or r['status']!='Ожидает ответа' or r.get('responded_at')
                or not q.get('prorab_confirmed_at') or not q.get('director_approved_at')
                or q['status'] not in ('КП запрошены','Утверждена')):
            blocked('Заявка или ответ уже изменились. Автоматический отзыв недоступен')
        if r.get('email_notification_status')==EMAIL_UNCONFIRMED:
            blocked('Отправка письма ещё не подтверждена. Сначала проверьте результат доставки')
        if r.get('max_notification_status')=='В очереди MAX' and not r.get('max_outbox_id'):
            blocked('Не подтверждена очередь уведомления. Нужна отдельная проверка доставки')
    all_recipients=rows(cur,'''SELECT to_jsonb(r) AS row FROM supply_request_recipients r
        WHERE r.request_id=ANY(%s) ORDER BY r.id''',(request_ids,))
    for r in all_recipients:
        if r['company_id']!=company:blocked('У заявки есть адресаты другой компании. Сначала исправьте принадлежность')
        if r['id'] not in recipient_ids and r['visible_to_supplier'] and (
                r.get('supplier_user_id')==owner['id'] or r.get('supplier_id') in owner_ids
                or r.get('target_supplier_id') in owner_ids or set(r.get('supplier_group_ids') or [])&set(owner_ids)):
            blocked('Эта заявка доступна ещё одной карточке кабинета. Нужна отдельная проверка адресатов')
    offers=rows(cur,'''SELECT to_jsonb(o) AS row FROM supplier_offers o
        WHERE o.company_id=%s AND o.supplier_id=%s ORDER BY o.id''',(company,target))
    empty_fields=('responded_at','price_per_unit','total_price','delivery_days','pdf_url','valid_until',
                  'supplier_message','notes','delivery_status','approved_at','selected_at','party_snapshot_json')
    for o in offers:
        if (o.get('request_id') not in request_ids or o['status']!='Ожидает ответа'
                or any(o.get(key) is not None and o.get(key)!='' for key in empty_fields)
                or o.get('items_kp_json') not in (None,'','[]',[])):
            blocked('Поставщик уже начал ответ или прислал КП. Нужна отдельная проверка документов')
    if any(not any(o['request_id']==rid for o in offers) for rid in request_ids):
        blocked('У заявки не подтверждён ожидаемый ответ поставщика')
    offer_ids=[o['id'] for o in offers]
    reference_tables=[]
    for table,refs in sorted(offer_references(cur,schema).items()):
        if not refs or table=='supplier_offer_events':continue
        reference_tables.append(table)
        # An invoice/assignment under another buyer or another supplier is still
        # a business descendant of this exact quote, not independent history.
        clause=sql.SQL(' OR ').join(sql.SQL('{}=ANY(%s)').format(sql.Identifier(column)) for column in sorted(refs))
        cur.execute(sql.SQL('SELECT 1 FROM {} WHERE ').format(sql.Identifier(table))+clause+sql.SQL(' LIMIT 1'),[offer_ids]*len(refs))
        if cur.fetchone():blocked('У ожидаемого ответа есть связанные документы или назначения. Нужна отдельная проверка')
    events=rows(cur,'''SELECT to_jsonb(e) AS row FROM supplier_offer_events e
        WHERE e.offer_id=ANY(%s) ORDER BY e.id''',(offer_ids,))
    if any(e['event_type']!='created' for e in events):
        blocked('У ожидаемого ответа есть история изменений. Нужна отдельная проверка КП')
    # An invoice linked only to a request cannot safely be assigned to one quote.
    cur.execute('''SELECT 1 FROM supplier_invoices WHERE request_id=ANY(%s)
        AND offer_id IS NULL LIMIT 1''',(request_ids,))
    if cur.fetchone():blocked('По заявке есть счёт без точной связи с КП. Сначала проверьте документы')
    attempts=rows(cur,'''SELECT to_jsonb(a) AS row FROM supplier_email_attempts a
        WHERE a.recipient_id=ANY(%s) ORDER BY a.id''',(recipient_ids,))
    for a in attempts:
        if (a['company_id']!=company or a['request_id'] not in request_ids
                or a['outcome']=='unconfirmed' or not a['finished_at']):
            blocked('Результат отправки письма не подтверждён. Нужна отдельная проверка доставки')
    outbox_ids=sorted({r['max_outbox_id'] for r in recipients if r.get('max_outbox_id')})
    messages=rows(cur,'''SELECT to_jsonb(m) AS row FROM messenger_outbox m WHERE m.id=ANY(%s)
        OR (m.company_id=%s AND m.entity_type='supply_request' AND m.entity_id=ANY(%s)
            AND m.user_id=%s AND m.event_type='supplier_kp_requested') ORDER BY m.id''',
        (outbox_ids,company,request_ids,owner['id']))
    if {m['id'] for m in messages}!=set(outbox_ids):blocked('Уведомления заявки требуют отдельной проверки принадлежности')
    for m in messages:
        if (m['company_id']!=company or m['owner_scope']!='company' or m['provider']!='max'
                or m['entity_type']!='supply_request' or m['entity_id'] not in request_ids
                or m['user_id']!=owner['id'] or m['event_type']!='supplier_kp_requested'
                or m['status'] not in ('queued','sent','failed','cancelled')):
            blocked('Уведомление уже отправляется или его принадлежность не подтверждена')
    digest=hashlib.sha256(json.dumps(dict(recipients=all_recipients,offers=offers,events=events,attempts=attempts,messages=messages),
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(mode=MODE,digest=digest,referenceTables=reference_tables,
        affectedRequests=[dict(requestId=rid,recipientId=r['id'],offerIds=[o['id'] for o in offers if o['request_id']==rid])
            for rid in request_ids for r in recipients if r['request_id']==rid],
        queuedMessageIds=[m['id'] for m in messages if m['status']=='queued'],
        queuedEmailIds=[r['id'] for r in recipients if r.get('email_notification_status')==EMAIL_QUEUED])


def allowed(rfq,table,row):
    records=rfq['affectedRequests']
    if table=='supply_request_recipients':return row['id'] in {r['recipientId'] for r in records}
    if table=='supply_requests':return row['id'] in {r['requestId'] for r in records}
    if table=='supplier_offers':return row['id'] in {oid for r in records for oid in r['offerIds']}
    return False


def apply(cur,company,rfq,actor,plan_id):
    recipients=[r['recipientId'] for r in rfq['affectedRequests']]
    offers=[oid for r in rfq['affectedRequests'] for oid in r['offerIds']]
    cur.execute('''UPDATE supply_request_recipients SET visible_to_supplier=FALSE,status='Отозвано',
        email_notification_status=CASE WHEN id=ANY(%s) THEN 'Отменено' ELSE email_notification_status END,
        max_notification_status=CASE WHEN max_outbox_id=ANY(%s) THEN 'Отменено' ELSE max_notification_status END
        WHERE company_id=%s AND id=ANY(%s)''',(rfq['queuedEmailIds'],rfq['queuedMessageIds'],company,recipients))
    cur.execute("UPDATE supplier_offers SET status='Отозвано' WHERE company_id=%s AND id=ANY(%s)",(company,offers))
    for offer in offers:
        cur.execute('''INSERT INTO supplier_offer_events(offer_id,event_type,status_from,status_to,actor_name,actor_role,payload_json)
            VALUES(%s,'connection_corrected','Ожидает ответа','Отозвано',%s,%s,%s)''',
            (offer,actor.get('name',''),actor['role'],json.dumps(dict(action='connection_correction',planId=str(plan_id)))))
    cur.execute('''UPDATE messenger_outbox SET status='cancelled',next_attempt_at=NULL,updated_at=NOW()
        WHERE company_id=%s AND id=ANY(%s) AND status='queued' ''',(company,rfq['queuedMessageIds']))


def verify_replay(cur,company,rfq):
    cur.execute("SELECT count(*) AS total FROM messenger_outbox WHERE company_id=%s AND id=ANY(%s) AND status='cancelled'",(company,rfq['queuedMessageIds']))
    if cur.fetchone()['total']!=len(rfq['queuedMessageIds']):blocked('После отзыва очередь уведомлений изменилась. Обновите список')
    cur.execute("SELECT count(*) AS total FROM supply_request_recipients WHERE company_id=%s AND id=ANY(%s) AND email_notification_status='Отменено'",(company,rfq['queuedEmailIds']))
    if cur.fetchone()['total']!=len(rfq['queuedEmailIds']):blocked('После отзыва очередь писем изменилась. Обновите список')
    for row in rfq['affectedRequests']:
        cur.execute("SELECT 1 FROM supply_request_recipients WHERE company_id=%s AND id=%s AND NOT visible_to_supplier AND status='Отозвано'",(company,row['recipientId']))
        if not cur.fetchone():blocked('После отзыва адресат изменился. Обновите список')
        cur.execute("SELECT count(*) AS total FROM supplier_offers WHERE company_id=%s AND id=ANY(%s) AND status='Отозвано'",(company,row['offerIds']))
        if cur.fetchone()['total']!=len(row['offerIds']):blocked('После отзыва ожидаемый ответ изменился. Обновите список')
