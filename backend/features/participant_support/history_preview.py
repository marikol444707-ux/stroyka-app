"""Company-owned history inventory. No projected grants or business mutations.

Current supplier access uses the portal's live recipient policies. Inventory is
not authority to apply a merge or to read an original file.
"""
import os
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Path, Query
from pydantic import BaseModel

from .connection_preview import diagnose
from .service import admin_transaction
from ..supplier_access.service import supplier_invoice_visibility_filter, supplier_offer_visibility_filter
from ..supplier_team.policy import access_ids, enabled as team_enabled

Category = Literal['invoices','receipts','offers','contracts','files']
TABLES = {'invoices':'supplier_invoices','receipts':'warehouse_invoices','offers':'supplier_offers'}


class HistoryItem(BaseModel):
    id: int
    currentSupplierAccess: Literal['available','unavailable','needs_check']


class HistoryPlan(BaseModel):
    companyId: int
    platformAccountId: int
    sourceId: int
    targetId: int
    sourceVersion: int
    targetVersion: int
    sourceName: Optional[str]
    targetName: Optional[str]
    summary: dict[str, Optional[int]]
    unresolvedPrimaryFiles: int
    category: Category
    items: list[HistoryItem]
    hasMore: bool
    blockers: list[dict[str,str]]
    canApply: Literal[False]
    teamAssignmentsChanged: Literal[False]


def exists(cur, table):
    cur.execute('SELECT to_regclass(%s) AS relation', ('public.'+table,))
    return bool(cur.fetchone()['relation'])


def contract_query():
    return '''SELECT DISTINCT v.id FROM supplier_contract_versions v
        WHERE v.company_id=%s AND (
            EXISTS(SELECT 1 FROM supplier_offers o WHERE o.id=v.offer_id
                AND o.company_id=v.company_id AND o.supplier_id=%s)
            OR EXISTS(SELECT 1 FROM supplier_contract_registry_versions m
                JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id
                WHERE m.contract_version_id=v.id AND m.company_id=v.company_id AND r.supplier_id=%s))'''


def primary_urls():
    return '''SELECT o.pdf_url AS url FROM supplier_offers o WHERE o.company_id=%s AND o.supplier_id=%s
        UNION SELECT i.file_url FROM supplier_invoices i WHERE i.company_id=%s AND i.supplier_id=%s
        UNION SELECT i.photo_url FROM supplier_invoices i WHERE i.company_id=%s AND i.supplier_id=%s
        UNION SELECT w.photo_url FROM warehouse_invoices w WHERE w.company_id=%s AND w.supplier_id=%s'''


def file_query(contracts_ready):
    # Fixed declarations only. Never return URLs, storage locators or snapshots.
    contract_refs = '''UNION SELECT v.source_file_id FROM supplier_contract_versions v
        WHERE v.id IN ('''+contract_query()+''')''' if contracts_ready else ''
    return 'WITH urls AS ('+primary_urls()+'''), file_ids AS (
        SELECT f.id FROM file_ownership f JOIN urls u ON u.url=f.file_url
            OR u.url='/tenant-files/' || f.id::text || '/content'
        '''+contract_refs+'''
    ) SELECT DISTINCT f.id FROM file_ownership f JOIN file_ids i ON i.id=f.id
        WHERE f.company_id=%s'''


def inventory(cur, company_id, source_id):
    queries={kind:('SELECT id FROM '+table+' WHERE company_id=%s AND supplier_id=%s', [company_id,source_id])
             for kind,table in TABLES.items()}
    contracts_ready=all(exists(cur,t) for t in ('supplier_contract_versions','supplier_contract_registry','supplier_contract_registry_versions'))
    if contracts_ready:queries['contracts']=(contract_query(),[company_id,source_id,source_id])
    if exists(cur,'file_ownership'):
        queries['files']=(file_query(contracts_ready),[company_id,source_id]*4+
                          ([company_id,source_id,source_id] if contracts_ready else [])+[company_id])
    summary={kind:None for kind in ('invoices','receipts','offers','contracts','files')}
    for kind,(query,params) in queries.items():
        cur.execute('SELECT count(*) AS n FROM ('+query+') history',params)
        summary[kind]=cur.fetchone()['n']
    unresolved=0
    if 'files' in queries:
        cur.execute('''SELECT count(*) AS n FROM ('''+primary_urls()+''') u
            WHERE COALESCE(trim(u.url),'')<>'' AND NOT EXISTS(SELECT 1 FROM file_ownership f
                WHERE f.company_id=%s AND (f.file_url=u.url OR u.url='/tenant-files/' || f.id::text || '/content'))''',
            [company_id,source_id]*4+[company_id])
        unresolved=cur.fetchone()['n']
    return queries,summary,unresolved


def live_access(cur, owner_id, company_id, source_id, category, ids):
    if category not in ('invoices','offers'):
        # Receipt originals and contract versions have additional parent/file
        # checks. A directory count cannot substitute those policies.
        return {sid:'needs_check' for sid in ids}
    cur.execute("SELECT id,role,active FROM users WHERE id=%s",(owner_id,))
    owner=cur.fetchone()
    if not owner or owner['active'] is False or owner['role']!='поставщик':return {}
    if team_enabled():owned_ids=access_ids(cur,owner)
    else:
        cur.execute('SELECT id FROM suppliers WHERE user_id=%s',(owner_id,))
        owned_ids=[r['id'] for r in cur.fetchall()]
    alias='si' if category=='invoices' else 'supplier_offers'
    policy=supplier_invoice_visibility_filter if category=='invoices' else supplier_offer_visibility_filter
    scope,params=policy(owned_ids,owner_id)
    cur.execute('SELECT '+alias+'.id FROM '+TABLES[category]+' '+alias+
                ' WHERE '+alias+'.company_id=%s AND '+alias+'.supplier_id=%s AND '+alias+'.id=ANY(%s)'+scope,
                [company_id,source_id,ids]+params)
    return {r['id']:'available' for r in cur.fetchall()}


def register_history_preview(app,deps,admin):
    @app.get('/system/companies/{company_id}/participants/{supplier_id}/history-preview',response_model=HistoryPlan)
    def history(company_id:int=Path(...,ge=1,le=2147483647),supplier_id:int=Path(...,ge=1,le=2147483647),
                targetSupplierId:int=Query(...,ge=1,le=2147483647), category:Category=Query('invoices'),
                offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user:dict=Depends(admin)):
        with admin_transaction(deps,user,company_id,snapshot=True) as (cur,company):
            if os.getenv('PARTICIPANT_HISTORY_PREVIEW_ENABLED','0')!='1':
                raise HTTPException(503,'Проверка старой истории пока не включена')
            data=diagnose(cur,company,supplier_id)
            target=data['cabinet']
            if (data['scenario']!='merge_cards' or not target or target['supplierId']!=targetSupplierId
                    or not target['hasBuyerRelationship']):
                raise HTTPException(404,'В выбранной организации нет этой пары карточек для объединения')
            queries,summary,unresolved=inventory(cur,company_id,supplier_id)
            if unresolved:
                data['blockers'].append(dict(code='FILE_REFERENCE_REVIEW_REQUIRED',message='У одного или нескольких основных файлов не подтверждена принадлежность выбранной компании.'))
            if any(value is None for value in summary.values()):
                data['blockers'].append(dict(code='HISTORY_SCHEMA_REVIEW_REQUIRED',message='Часть реестра истории недоступна. Требуется проверка схемы; отсутствие данных не означает пустой архив.'))
            if category not in queries:raise HTTPException(503,'Для этого вида документов требуется обновление схемы')
            query,params=queries[category]
            cur.execute('SELECT id FROM ('+query+') history ORDER BY id LIMIT %s OFFSET %s',params+[limit+1,offset])
            rows=cur.fetchall();ids=[r['id'] for r in rows[:limit]]
            access=live_access(cur,target['ownerUserId'],company_id,supplier_id,category,ids)
            return dict(companyId=company_id,platformAccountId=company['platform_account_id'],sourceId=supplier_id,
                targetId=targetSupplierId,sourceVersion=data['supplier']['relationshipVersion'],
                targetVersion=target['relationshipVersion'],sourceName=data['supplier']['name'],targetName=target['name'],
                summary=summary,unresolvedPrimaryFiles=unresolved,category=category,items=[dict(id=sid,currentSupplierAccess=access.get(sid,'unavailable')) for sid in ids],
                hasMore=len(rows)>limit,blockers=data['blockers'],canApply=False,teamAssignmentsChanged=False)
