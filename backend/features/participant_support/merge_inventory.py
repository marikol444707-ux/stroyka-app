"""Exact impact manifest; simulate ownership only in a SELECT-only CTE.

The runtime supplier policies are reused without changing business rows or
adding a projection option to the actual authorization APIs.
"""
import hashlib
import json
import os
from fastapi import HTTPException
from psycopg2 import sql

from ..document_access.supplier_files import authorize_read, supplier_ids
from ..supplier_access.contract_files import supplier_contract_file_visible
from ..supplier_access.service import supplier_invoice_visibility_filter, supplier_offer_visibility_filter, supplier_delivery_visibility_filter
from ..supply_claim_cases.access import CHAIN as CLAIM_CHAIN
from ..supplier_team.policy import enabled as team_enabled, access_ids

MAX_ROWS=2000
MAX_FILES=100
POLICY_TABLES=('supply_requests','supply_request_recipients','file_ownership','supplier_invoices','supplier_offers','warehouse_invoices',
               'supply_deliveries','supply_claims',
               'supplier_contract_versions','supplier_contract_registry_versions',
               'supplier_team_members','supplier_customer_assignments','supplier_offer_assignments')
POLICY_FLAGS=('SUPPLIER_TEAM_ENABLED','SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED',
              'SUPPLIER_DEAL_PARTIES_ENABLED','SUPPLIER_CONTRACT_SNAPSHOTS_ENABLED')


class ProjectedOwner:
    def __init__(self,cur,source,owner):self.cur,self.source,self.owner=cur,source,owner

    def execute(self,query,params=None):
        if not isinstance(query,str) or not query.lstrip().upper().startswith('SELECT '):
            raise ValueError('Ownership projection accepts SELECT statements only')
        self.cur.execute('''WITH suppliers AS (
            SELECT (jsonb_populate_record(NULL::public.suppliers,to_jsonb(s) ||
                CASE WHEN s.id=%s THEN jsonb_build_object('user_id',%s::int) ELSE '{}'::jsonb END)).*
            FROM public.suppliers s) '''+query,[self.source,self.owner]+list(params or []))

    def __getattr__(self,key):return getattr(self.cur,key)


def tables(cur):
    cur.execute("""SELECT table_name,array_agg(column_name::text) AS columns FROM information_schema.columns
        WHERE table_schema='public' GROUP BY table_name ORDER BY table_name""")
    return {r['table_name']:set(r['columns']) for r in cur.fetchall()}


def bounded(cur,query,params,limit=MAX_ROWS):
    cur.execute(query+sql.SQL(' LIMIT %s'),list(params)+[limit+1])
    rows=cur.fetchall()
    if len(rows)>limit:raise HTTPException(409,'История слишком большая для этой проверки. Требуется отдельный план объединения.')
    return rows


def visible_documents(cur,owner,company):
    ids=access_ids(cur,owner) if team_enabled() else supplier_ids(cur,owner)
    result={}
    for name,table,alias,policy in (('invoices','supplier_invoices','si',supplier_invoice_visibility_filter),
                                   ('offers','supplier_offers','supplier_offers',supplier_offer_visibility_filter)):
        scope,params=policy(ids,owner['id'])
        cur.execute('SELECT '+alias+'.id FROM '+table+' '+alias+' WHERE '+alias+'.company_id=%s'+scope+' ORDER BY '+alias+'.id',
                    [company]+params)
        result[name]=[r['id'] for r in cur.fetchall()]
    scope,params=supplier_delivery_visibility_filter(ids,owner['id'])
    cur.execute('SELECT d.id FROM supply_deliveries d WHERE d.company_id=%s AND '+scope+' ORDER BY d.id',[company]+params)
    result['deliveries']=[r['id'] for r in cur.fetchall()]
    cur.execute('SELECT c.id'+CLAIM_CHAIN+' WHERE d.company_id=%s AND '+scope+' ORDER BY c.id',[company]+params)
    result['claims']=[r['id'] for r in cur.fetchall()]
    return result


def visible_files(cur,owner,files,contracts,storage_check):
    ids=supplier_ids(cur,owner)
    result=[]
    for row in files:
        if row.get('deletion_status') not in (None,'','active'):continue
        try:
            if not contracts or not supplier_contract_file_visible(cur,owner,row,ids):authorize_read(cur,owner,row)
            storage_check(row)
            result.append(row['id'])
        except HTTPException as error:
            if error.status_code!=403:raise
    return result


def inventory(cur,company,source,target,owner,contracts,storage_check):
    # Array/group recipients also influence disclosure of already-owned offers.
    # A foreign reference to the provisional ID is never silently activated.
    cur.execute('''SELECT 1 FROM supply_requests WHERE company_id IS DISTINCT FROM %s
        AND %s=ANY(COALESCE(selected_suppliers,'{}'::int[])) LIMIT 1''',(company,source))
    if cur.fetchone():raise HTTPException(409,'Есть адресация карточки вне выбранной организации. Требуется проверка принадлежности')
    cur.execute('''SELECT 1 FROM supply_request_recipients WHERE company_id IS DISTINCT FROM %s
        AND (target_supplier_id=%s OR %s=ANY(COALESCE(supplier_group_ids,'{}'::int[]))) LIMIT 1''',(company,source,source))
    if cur.fetchone():raise HTTPException(409,'Есть адресация карточки вне выбранной организации. Требуется проверка принадлежности')
    schema=tables(cur)
    inspected={name for name,columns in schema.items() if 'supplier_id' in columns}|(set(POLICY_TABLES)&schema.keys())
    required={'file_ownership','supplier_contract_versions','supplier_contract_registry_versions'}
    if not required<=schema.keys():raise HTTPException(503,'Полная проверка истории требует обновления реестров документов')
    fingerprints={};affected={};files=[]
    for name in sorted(inspected):
        columns=schema[name]
        if name=='supply_claims':
            # The legacy claim has no company column. Use the same complete
            # parent chain as its runtime route; a loose delivery_id is not proof.
            known={r['id'] for r in bounded(cur,sql.SQL('SELECT c.id'+CLAIM_CHAIN+
                ' WHERE c.supplier_id=%s AND d.company_id=%s ORDER BY c.id'),[source,company])}
            clause='supplier_id=%s OR delivery_id IN (SELECT id FROM supply_deliveries WHERE company_id=%s)';params=[source,company]
        elif name in ('supplier_team_members','supplier_customer_assignments','supplier_offer_assignments'):
            clause='supplier_id=ANY(%s)';params=[[source,target]]
        elif name in POLICY_TABLES and 'company_id' in columns:
            clause='company_id=%s';params=[company]
        elif 'supplier_id' in columns:
            clause='supplier_id=%s';params=[source]
        elif name=='supplier_offer_assignments':
            clause='offer_id IN (SELECT id FROM supplier_offers WHERE company_id=%s)';params=[company]
        else:raise HTTPException(503,'Для реестра истории требуется проверка схемы')
        query=sql.SQL('SELECT to_jsonb(t) AS row FROM {} t WHERE '+clause+' ORDER BY to_jsonb(t)::text').format(sql.Identifier(name))
        rows=bounded(cur,query,params,MAX_FILES if name=='file_ownership' else MAX_ROWS)
        values=[r['row'] for r in rows]
        if name=='supply_claims' and any(r.get('supplier_id')==source and r['id'] not in known for r in values):
            raise HTTPException(409,'Принадлежность претензии не подтверждена цепочкой поставки. Требуется отдельная проверка')
        if (values and 'company_id' not in columns and name not in
                ('supplier_aliases','supplier_team_members','supplier_offer_assignments','supply_claims')):
            raise HTTPException(409,'У старой карточки есть данные без подтверждённой организации. Требуется отдельная проверка')
        fingerprints[name]=values
        if name=='file_ownership':files=values
        if 'supplier_id' in columns:
            affected[name]=[r['id'] for r in values if r.get('supplier_id')==source and 'id' in r]
    # Include exact source/target profiles, link versions and public legal keys.
    for name in ('suppliers','company_supplier_links'):
        key='id' if name=='suppliers' else 'supplier_id'
        query=sql.SQL('SELECT to_jsonb(t) AS row FROM {} t WHERE '+key+'=ANY(%s)'+
            (' AND company_id=%s' if name=='company_supplier_links' else '')+' ORDER BY t.id').format(sql.Identifier(name))
        fingerprints[name]=[r['row'] for r in bounded(cur,query,[[source,target]]+([company] if name!='suppliers' else []))]
    flags={key:os.getenv(key,'0') for key in POLICY_FLAGS}
    flags['contractFilesRuntimeEnabled']=contracts
    before=visible_documents(cur,owner,company);before['files']=visible_files(cur,owner,files,contracts,storage_check)
    projected=ProjectedOwner(cur,source,owner['id'])
    after=visible_documents(projected,owner,company);after['files']=visible_files(projected,owner,files,contracts,storage_check)
    digest=hashlib.sha256(json.dumps(dict(rows=fingerprints,flags=flags),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(digest=digest,tables=sorted(inspected),affected=affected,
                newAccess={key:sorted(set(after[key])-set(before[key])) for key in after},
                stillClosed={key:sorted(set(affected.get(table,[]))-set(after[key])) for key,table in
                             (('invoices','supplier_invoices'),('offers','supplier_offers'))},flags=flags)
