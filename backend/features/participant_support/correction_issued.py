"""Revoke addressed access; preserve every issued business row and its status."""
import hashlib
import json
import re

from fastapi import HTTPException
from psycopg2 import sql

from .merge_inventory import bounded, visible_documents, visible_files
from ..document_access.supplier_files import supplier_ids
from ..supplier_access.service import supplier_history_visibility_filter, supplier_delivery_visibility_filter
from . import correction_invoice_access, correction_contract_access
from ..supply_claim_cases.access import CHAIN as CLAIM_CHAIN

MODE='revoke_issued_access'
TABLE_KINDS={'supplier_offers':'offer','supplier_invoices':'invoice','supply_deliveries':'delivery','warehouse_invoices':'receipt',
    'supplier_contract_versions':'contract','supply_claims':'claim'}
REQUIRED={
    'supplier_invoices':{'id','company_id','supplier_id','offer_id','request_id','warehouse_invoice_id','file_url','photo_url'},
    'supply_deliveries':{'id','company_id','supplier_id','offer_id','request_id','project','work_package','document_url','photo_url'},
    'warehouse_invoices':{'id','company_id','supplier_id','supplier_invoice_id','supply_delivery_id','supply_request_id','photo_url','photo_urls'},
    'file_ownership':{'id','company_id','file_url','context','deletion_status'},
    'supplier_contract_versions':{'id','source_file_id','snapshot_json'},
    'supplier_shipment_batches':{'id','company_id','offer_id','delivery_ids'},
    'supply_claims':{'id','delivery_id','request_id','offer_id','supplier_id','project','work_package','photo_url',
        'material_name','claim_type','description','expected_quantity','received_quantity','shortage_quantity',
        'status','resolution','resolved_at','version','created_at','updated_at'},
    'supply_history':{'id','company_id','supplier_id','request_id','delivery_id','project','work_package'},
    'supplier_customer_assignments':{'supplier_id','company_id','member_id','version'},
    'supplier_offer_assignments':{'supplier_id','offer_id','member_id','version'},
}


def blocked(message):
    raise HTTPException(409,message)


class ClosedRecipients:
    """SELECT-only simulation, using the same policies as the live supplier API."""
    def __init__(self,cur,ids):self.cur,self.ids=cur,ids

    def execute(self,query,params=None):
        if not isinstance(query,str) or not query.lstrip().upper().startswith('SELECT '):
            raise ValueError('Recipient projection accepts SELECT statements only')
        self.cur.execute('''WITH supply_request_recipients AS (
            SELECT (jsonb_populate_record(NULL::public.supply_request_recipients,to_jsonb(r) ||
                CASE WHEN r.id=ANY(%s) THEN '{"visible_to_supplier":false}'::jsonb ELSE '{}'::jsonb END)).*
            FROM public.supply_request_recipients r) '''+query,[self.ids]+list(params or []))

    def __getattr__(self,key):return getattr(self.cur,key)


def records(cur,table,condition,params):
    query=sql.SQL('SELECT to_jsonb(t) AS row FROM {} t WHERE '+condition+' ORDER BY t.id').format(sql.Identifier(table))
    return [r['row'] for r in bounded(cur,query,params)]


def history(cur,company,target,offers,schema,*,standalone=False):
    if any(not columns<=schema.get(table,set()) for table,columns in REQUIRED.items()):
        raise HTTPException(503,'Закрытие доступа требует полного реестра счетов, поставок и оригиналов')
    offer_map={o['id']:o for o in offers};offer_ids=list(offer_map)
    result={'supplier_offers':offers}
    for table in ('supplier_invoices','supply_deliveries'):
        result[table]=records(cur,table,'(t.company_id=%s AND t.supplier_id=%s) OR t.offer_id=ANY(%s)',(company,target,offer_ids))
        for row in result[table]:
            if standalone and table=='supplier_invoices' and row['offer_id'] is None:
                if row['company_id']!=company or row['supplier_id']!=target or row['request_id'] is not None:
                    blocked('Отдельный счёт связан с заявкой без КП. Нужен отдельный разбор')
                continue
            offer=offer_map.get(row['offer_id'])
            if (not offer or row['company_id']!=company or row['supplier_id']!=target
                    or (row['request_id']!=offer['request_id'] and not (table=='supplier_invoices' and row['request_id'] is None))
                    or offer['status']!='Утверждено'):
                blocked('Счёт или поставка не имеют точной связи с заказом этой компании. Нужен отдельный разбор')
    invoices={r['id']:r for r in result['supplier_invoices']}
    deliveries={r['id']:r for r in result['supply_deliveries']}
    result['supply_history']=records(cur,'supply_history',
        '(t.company_id=%s AND t.supplier_id=%s) OR t.delivery_id=ANY(%s)',(company,target,list(deliveries)))
    for row in result['supply_history']:
        delivery=deliveries.get(row['delivery_id'])
        if (not delivery or row['company_id']!=company or row['supplier_id']!=target
                or row['request_id']!=delivery['request_id'] or row['project']!=delivery['project']
                or (row['work_package'] or '')!=(delivery.get('work_package') or '')):
            blocked('История поставки не имеет точной цепочки этой компании. Нужен отдельный разбор')
    # Claims are buyer records attached to exact deliveries. Include them in
    # the immutable plan so an issued-access correction cannot leave the
    # supplier-facing claim list or its photo as an unreviewed side door.
    cur.execute('SELECT c.id'+CLAIM_CHAIN+' WHERE d.company_id=%s AND c.supplier_id=%s', (company,target))
    expected_claim_ids={r['id'] for r in cur.fetchall()}
    claim_rows=records(cur,'supply_claims','t.id=ANY(%s) OR t.delivery_id=ANY(%s)',
        (sorted(expected_claim_ids),list(deliveries)))
    for claim in claim_rows:
        delivery=deliveries.get(claim.get('delivery_id'))
        if (claim['id'] not in expected_claim_ids or not delivery or claim['supplier_id']!=target
                or delivery['company_id']!=company or claim['request_id']!=delivery['request_id']
                or claim['offer_id']!=delivery['offer_id'] or claim['project']!=delivery['project']
                or (claim.get('work_package') or '')!=(delivery.get('work_package') or '')):
            blocked('Претензия не имеет точной связи с поставкой этой компании. Нужен отдельный разбор')
    result['supply_claims']=claim_rows
    result['supplier_shipment_batches']=records(cur,'supplier_shipment_batches','t.offer_id=ANY(%s)',(offer_ids,))
    for batch in result['supplier_shipment_batches']:
        if (batch['company_id']!=company or not batch['delivery_ids'] or any(
                did not in deliveries or deliveries[did]['offer_id']!=batch['offer_id'] for did in batch['delivery_ids'])):
            blocked('Пакет отгрузки не подтверждён этой цепочкой. Нужен отдельный разбор')
    result['warehouse_invoices']=records(cur,'warehouse_invoices',
        '(t.company_id=%s AND t.supplier_id=%s) OR t.supplier_invoice_id=ANY(%s) OR t.supply_delivery_id=ANY(%s) OR t.id=ANY(%s)',
        (company,target,list(invoices),list(deliveries),[r['warehouse_invoice_id'] for r in invoices.values() if r['warehouse_invoice_id']]))
    for row in result['warehouse_invoices']:
        invoice=invoices.get(row['supplier_invoice_id']);delivery=deliveries.get(row['supply_delivery_id'])
        reverse=[r for r in invoices.values() if r['warehouse_invoice_id']==row['id']]
        requests={o['request_id'] for o in offers if o['status']=='Утверждено'}
        parents=[parent for parent in [invoice,delivery]+reverse if parent]
        direct=any(parent.get('offer_id') is None for parent in parents)
        if (row['company_id']!=company or row['supplier_id']!=target
                or (row['supplier_invoice_id'] is not None and not invoice)
                or (row['supply_delivery_id'] is not None and not delivery)
                or (row['supply_request_id'] is not None and row['supply_request_id'] not in requests)
                or (not invoice and not delivery and not reverse and row['supply_request_id'] is None)
                or (invoice and delivery and invoice['offer_id']!=delivery['offer_id'])
                or (direct and (row['supply_delivery_id'] is not None or row['supply_request_id'] is not None
                    or len({parent['id'] for parent in parents})!=1))
                or len({parent['offer_id'] for parent in [invoice,delivery]+reverse if parent})>1
                or (row['supply_request_id'] is not None and any(
                    offer_map[parent['offer_id']]['request_id']!=row['supply_request_id'] for parent in (invoice,delivery) if parent))):
            blocked('Накладная не имеет точной цепочки этой компании. Нужен отдельный разбор')
    receipts={r['id']:r for r in result['warehouse_invoices']}
    for invoice in invoices.values():
        receipt=receipts.get(invoice['warehouse_invoice_id'])
        if invoice['warehouse_invoice_id'] is not None and (not receipt or
                (receipt['supplier_invoice_id'] is not None and receipt['supplier_invoice_id']!=invoice['id']) or
                (receipt['supply_delivery_id'] is not None and deliveries[receipt['supply_delivery_id']]['offer_id']!=invoice['offer_id']) or
                (receipt['supply_request_id'] is not None and receipt['supply_request_id']!=offer_map[invoice['offer_id']]['request_id'])):
            blocked('Обратная связь счёта с накладной требует отдельного разбора')
    return result


def assignment_key(table,row):
    keys=('supplier_id','company_id','member_id','version') if table=='supplier_customer_assignments' else ('supplier_id','offer_id','member_id','version')
    return {key:row.get(key) for key in keys}


def allowed(proof,table,row):
    if table in ('supplier_customer_assignments','supplier_offer_assignments'):
        return assignment_key(table,row) in proof['retainedAssignments'].get(table,[])
    return row.get('id') in proof['allowedDocuments'].get(table,[])


def assignments(cur,company,target,offer_ids):
    result={}
    for table,clause,params in (
        ('supplier_customer_assignments','supplier_id=%s AND company_id=%s',(target,company)),
        ('supplier_offer_assignments','offer_id=ANY(%s)',(offer_ids,))):
        cur.execute(sql.SQL('SELECT to_jsonb(a) AS row FROM {} a WHERE '+clause+' ORDER BY to_jsonb(a)::text LIMIT 2001').format(sql.Identifier(table)),params)
        rows=cur.fetchall()
        if len(rows)>2000:blocked('Слишком много назначений для этой проверки')
        result[table]=[]
        for record in rows:
            row=record['row']
            if row['supplier_id']!=target:blocked('Назначение относится к другой карточке поставщика')
            result[table].append(assignment_key(table,row))
    return result


def originals(cur,company,documents):
    urls=set()
    contract_ids=set()
    for version in documents.get('supplier_contract_versions',[]):
        contract_ids.add(version['source_file_id'])
        addenda=version['snapshot_json'].get('addenda',[])
        if not isinstance(addenda,list) or any(not isinstance(a,dict) or type(a.get('sourceFileId')) is not int or a['sourceFileId']<1 for a in addenda):
            blocked('Состав приложений договора требует отдельной проверки')
        contract_ids.update(a['sourceFileId'] for a in addenda)
    if any(type(fid) is not int or fid<1 for fid in contract_ids):blocked('Оригинал договора не подтверждён')
    urls.update(f'/tenant-files/{fid}/content' for fid in contract_ids)
    fields={'supplier_offers':('pdf_url',),'supplier_invoices':('file_url','photo_url'),
        'supply_deliveries':('document_url','photo_url'),'warehouse_invoices':('photo_url',),
        'supply_claims':('photo_url',)}
    for table,rows in documents.items():
        if table not in fields:continue
        for row in rows:
            urls.update(str(row[key]) for key in fields[table] if row.get(key))
            if table=='warehouse_invoices' and row.get('photo_urls'):
                try:photos=json.loads(row['photo_urls']) if isinstance(row['photo_urls'],str) else row['photo_urls']
                except (ValueError,TypeError):blocked('Список оригиналов накладной требует отдельного разбора')
                if not isinstance(photos,list) or any(not isinstance(u,str) for u in photos):
                    blocked('Список оригиналов накладной требует отдельного разбора')
                urls.update(u for u in photos if u)
    files=[r['row'] for r in bounded(cur,sql.SQL('SELECT to_jsonb(t) AS row FROM file_ownership t WHERE company_id=%s ORDER BY id'),[company],100)]
    selected={}
    for url in urls:
        match=re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content',url)
        matches=[f for f in files if (f['id']==int(match[1]) if match else f['file_url']==url)]
        if len(matches)!=1 or matches[0]['deletion_status'] not in (None,'','active'):
            blocked('Оригинал документа не подтверждён в архиве компании')
        selected[matches[0]['id']]=matches[0]
    contexts={f'supplier-offer-{o["id"]}' for o in documents['supplier_offers']}
    selected.update({f['id']:f for f in files if f.get('context') in contexts and f['deletion_status'] in (None,'','active')})
    aliases=sorted(urls|{str(f['file_url']) for f in selected.values() if f.get('file_url')}|
        {f'/tenant-files/{fid}/content' for fid in selected})
    for table,columns in fields.items():
        condition=sql.SQL(' OR ').join(sql.SQL('{}=ANY(%s)').format(sql.Identifier(c)) for c in columns)
        params=[aliases]*len(columns)
        if table=='warehouse_invoices':
            condition+=sql.SQL(" OR EXISTS(SELECT 1 FROM unnest(%s::text[]) u WHERE POSITION(u IN COALESCE(photo_urls,''))>0)")
            params.append(aliases)
        cur.execute(sql.SQL('SELECT 1 FROM {} WHERE NOT(id=ANY(%s)) AND (').format(sql.Identifier(table))+
            condition+sql.SQL(') LIMIT 1'),[[r['id'] for r in documents[table]]]+params)
        if cur.fetchone():blocked('Оригинал используется в другом документе. Нужен отдельный разбор доступа')
    cur.execute('''SELECT 1 FROM supplier_contract_versions WHERE NOT(id=ANY(%s)) AND (source_file_id=ANY(%s)
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(snapshot_json->'addenda')='array'
            THEN snapshot_json->'addenda' ELSE '[]'::jsonb END) a WHERE a->>'sourceFileId'=ANY(%s))) LIMIT 1''',
        ([v['id'] for v in documents.get('supplier_contract_versions',[])],list(selected),[str(i) for i in selected]))
    if cur.fetchone():blocked('Оригинал относится к договору. Доступ к договору исправляется отдельно')
    return [selected[fid] for fid in sorted(selected)]


def proof(cur,company,target,owner,offers,recipients,schema,*,standalone=False,contracts=False):
    documents=history(cur,company,target,offers,schema,standalone=standalone)
    contract_metadata=correction_contract_access.history(cur,company,target,documents,schema) if contracts else None
    direct=[r['id'] for r in documents['supplier_invoices'] if r['offer_id'] is None]
    retained_assignments=assignments(cur,company,target,[o['id'] for o in offers])
    files=originals(cur,company,documents)
    projected=(correction_invoice_access.ClosedInvoiceAccess(cur,[r['id'] for r in recipients],company,target,direct,
        contracts=[v['id'] for v in documents['supplier_contract_versions']] if contracts else None)
        if standalone else ClosedRecipients(cur,[r['id'] for r in recipients]))
    before=visible_documents(cur,owner,company);after=visible_documents(projected,owner,company)
    for kind,table in (('offers','supplier_offers'),('invoices','supplier_invoices'),('deliveries','supply_deliveries')):
        expected={r['id'] for r in documents[table]}
        if not expected<=set(before[kind]) or set(before[kind])-set(after[kind])!=expected or set(after[kind])-set(before[kind]):
            blocked('Доступ к документам не закрывается только для этой связи. Нужен отдельный разбор адресатов')
    before_files=visible_files(cur,owner,files,True,lambda _:None)
    after_files=visible_files(projected,owner,files,True,lambda _:None)
    if set(before_files)!={f['id'] for f in files} or after_files:
        blocked('Оригиналы имеют независимый или неподтверждённый доступ. Нужен отдельный разбор')
    supplier_claim_ids=sorted({r['id'] for r in documents['supply_claims']})
    if supplier_claim_ids:
        claim_scope,claim_params=supplier_delivery_visibility_filter(supplier_ids(cur,owner),owner['id'])
        claim_query='SELECT c.id'+CLAIM_CHAIN+' WHERE c.id=ANY(%s) AND '+claim_scope
        cur.execute(claim_query,[supplier_claim_ids]+claim_params)
        claim_before={r['id'] for r in cur.fetchall()}
        projected.execute(claim_query,[supplier_claim_ids]+claim_params)
        claim_after={r['id'] for r in projected.fetchall()}
        if claim_before!=set(supplier_claim_ids) or claim_after:
            blocked('Доступ к претензиям не закрывается вместе с точной поставкой')
    scope,params=supplier_history_visibility_filter(supplier_ids(cur,owner),owner['id'])
    query='SELECT h.id FROM supply_history h WHERE h.company_id=%s AND '+scope
    cur.execute(query,[company]+params);history_before={r['id'] for r in cur.fetchall()}
    projected.execute(query,[company]+params);history_after={r['id'] for r in projected.fetchall()}
    expected={r['id'] for r in documents['supply_history']}
    if history_before-history_after!=expected or history_after-history_before:
        blocked('История поставки имеет независимый или неподтверждённый доступ')
    result=dict(allowedDocuments={t:[r['id'] for r in rows] for t,rows in documents.items()},
        retainedAssignments=retained_assignments,
        preservedIssuedDocuments=[dict(kind=TABLE_KINDS[t],id=r['id']) for t,rows in documents.items() if t in TABLE_KINDS for r in rows],
        preservedIssuedFileCount=len(files),
        issuedDigest=hashlib.sha256(json.dumps(dict(documents=documents,files=files,before=before,after=after,contractMetadata=contract_metadata),
            sort_keys=True,separators=(',',':')).encode()).hexdigest())
    if standalone:result['closedStandaloneInvoiceIds']=direct
    return result


def counts(plan):
    docs=plan['allowedDocuments']
    result=dict(offers=len(docs['supplier_offers']),invoices=len(docs['supplier_invoices']),
        deliveries=len(docs['supply_deliveries']),receipts=len(docs['warehouse_invoices']))
    if 'supplier_contract_versions' in docs:result['contracts']=len(docs['supplier_contract_versions'])
    if docs.get('supply_claims'):result['claims']=len(docs['supply_claims'])
    return result
