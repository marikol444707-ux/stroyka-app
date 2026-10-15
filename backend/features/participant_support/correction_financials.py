"""Read-only issued-history metadata; never authority to revoke document access."""
from typing import Literal, Optional

from psycopg2 import sql
from pydantic import BaseModel

from .history_preview import contract_query
from .merge_inventory import tables


class DocumentCounts(BaseModel):
    orders: Optional[int]
    invoices: Optional[int]
    deliveries: Optional[int]
    receipts: Optional[int]
    contracts: Optional[int]


class FinancialReview(BaseModel):
    state: Literal['clear','review_required','needs_check']
    source: DocumentCounts
    connected: DocumentCounts


class DocumentContext(BaseModel):
    supplierCard: Literal['source','connected']
    requestId: Optional[int]
    offerId: Optional[int]
    linksConfirmed: bool


COUNTERS={
    'orders':('supplier_offers',{'id','company_id','supplier_id','status'}),
    'invoices':('supplier_invoices',{'id','company_id','supplier_id'}),
    'deliveries':('supply_deliveries',{'id','company_id','supplier_id'}),
    'receipts':('warehouse_invoices',{'id','company_id','supplier_id'}),
}
CONTRACT_COLUMNS={
    'supplier_contract_versions':{'id','company_id','offer_id'},
    'supplier_contract_registry_versions':{'registry_id','contract_version_id','company_id'},
    'supplier_contract_registry':{'id','company_id','supplier_id'},
    'supplier_offers':{'id','company_id','supplier_id'},
}


def inspect(cur,company,source,target,category,ids):
    schema=tables(cur)
    counts={side:{key:None for key in (*COUNTERS,'contracts')} for side in ('source','connected')}
    for key,(table,required) in COUNTERS.items():
        if not required<=schema.get(table,set()):continue
        predicate=sql.SQL('')
        if key=='orders':
            # Preserve even inconsistent legacy awarded rows as a review case.
            predicate=sql.SQL(" AND (t.status IN ('Утверждено','Выбрано','Принято') OR "
                "COALESCE(to_jsonb(t)->>'awarded_items_json','') NOT IN ('','[]','null'))")
        cur.execute(sql.SQL('SELECT t.supplier_id,count(*) AS total FROM {} t '
            'WHERE t.company_id=%s AND t.supplier_id=ANY(%s)').format(sql.Identifier(table))+
            predicate+sql.SQL(' GROUP BY t.supplier_id'),(company,[source,target]))
        by_supplier={r['supplier_id']:r['total'] for r in cur.fetchall()}
        for side,sid in (('source',source),('connected',target)):counts[side][key]=by_supplier.get(sid,0)
    if all(columns<=schema.get(table,set()) for table,columns in CONTRACT_COLUMNS.items()):
        for side,sid in (('source',source),('connected',target)):
            cur.execute('SELECT count(*) AS total FROM ('+contract_query()+') versions',(company,sid,sid))
            counts[side]['contracts']=cur.fetchone()['total']
    contexts=document_contexts(cur,company,source,target,category,ids,schema)
    unknown=any(value is None for group in counts.values() for value in group.values())
    state='needs_check' if unknown else 'review_required' if any(counts['connected'].values()) else 'clear'
    return dict(state=state,**counts),contexts


def document_contexts(cur,company,source,target,category,ids,schema):
    declarations={'invoices':('supplier_invoices','request_id','offer_id'),
        'offers':('supplier_offers','request_id',None),
        'receipts':('warehouse_invoices','supply_request_id',None)}
    if category not in declarations or not ids:return {}
    table,request_key,offer_key=declarations[category]
    required={'id','company_id','supplier_id',request_key}|({offer_key} if offer_key else set())
    if not required<=schema.get(table,set()):return {}
    columns=['id','supplier_id',request_key]+([offer_key] if offer_key else [])
    cur.execute(sql.SQL('SELECT {} FROM {} WHERE company_id=%s AND supplier_id=ANY(%s) AND id=ANY(%s)').format(
        sql.SQL(',').join(map(sql.Identifier,columns)),sql.Identifier(table)),(company,[source,target],ids))
    documents=cur.fetchall()
    # Batch the parents for the bounded page, never one query per displayed row.
    offers={r['id']:r for r in documents} if category=='offers' else {}
    if offer_key and {'id','company_id','supplier_id','request_id'}<=schema.get('supplier_offers',set()):
        cur.execute('SELECT id,supplier_id,request_id FROM supplier_offers WHERE company_id=%s AND id=ANY(%s)',
            (company,[r[offer_key] for r in documents if r[offer_key] is not None]))
        offers={r['id']:r for r in cur.fetchall()}
    request_ids={r[request_key] for r in documents}|{r['request_id'] for r in offers.values()}
    requests=set()
    if {'id','company_id'}<=schema.get('supply_requests',set()):
        cur.execute('SELECT id FROM supply_requests WHERE company_id=%s AND id=ANY(%s)',
            (company,[rid for rid in request_ids if rid is not None]))
        requests={r['id'] for r in cur.fetchall()}
    result={}
    for row in documents:
        request_id=row[request_key];offer_id=row.get(offer_key) if offer_key else row['id'] if category=='offers' else None
        offer=offers.get(offer_id)
        confirmed=offer_id is None or bool(offer and offer['supplier_id']==row['supplier_id'] and
            (request_id is None or offer['request_id']==request_id))
        if request_id is None and offer:request_id=offer['request_id']
        confirmed=confirmed and (request_id is None or request_id in requests)
        result[row['id']]=dict(supplierCard='source' if row['supplier_id']==source else 'connected',
            requestId=request_id if confirmed else None,offerId=offer_id if confirmed else None,linksConfirmed=confirmed)
    return result
