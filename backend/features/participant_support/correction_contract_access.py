"""Bounded contract evidence; originals and immutable registry rows are retained."""
from fastapi import HTTPException
from psycopg2 import sql
from .merge_inventory import bounded

MODE='revoke_contract_access'
PROFILE_KEY='closedContractVersionIds'
TABLES={'supplier_contract_versions','supplier_contract_registry','supplier_contract_registry_versions',
    'supplier_contract_registry_events','supplier_contract_publications'}
REQUIRED={
    'supplier_contract_versions':{'id','company_id','offer_id','source_file_id','snapshot_json','snapshot_hash'},
    'supplier_contract_registry':{'id','company_id','supplier_id','buyer_company_id','payer_company_id','archived'},
    'supplier_contract_registry_versions':{'registry_id','company_id','contract_version_id'},
    'supplier_contract_registry_events':{'registry_id','company_id','version'},
    'supplier_contract_publications':{'contract_version_id','company_id','snapshot_hash'},
}


def blocked(message):raise HTTPException(409,message)


def rows(cur,table,condition,params):
    return [r['row'] for r in bounded(cur,sql.SQL('SELECT to_jsonb(t) AS row FROM {} t WHERE '+condition+
        ' ORDER BY to_jsonb(t)::text').format(sql.Identifier(table)),params)]


def history(cur,company,target,documents,schema):
    if any(not cols<=schema.get(table,set()) for table,cols in REQUIRED.items()):
        raise HTTPException(503,'Закрытие доступа к договорам требует полного реестра версий')
    offers={r['id']:r for r in documents['supplier_offers']}
    versions=rows(cur,'supplier_contract_versions',
        """t.offer_id=ANY(%s) OR (t.company_id=%s AND t.snapshot_json #>> '{{supplier,supplierId}}'=%s)
        OR EXISTS(SELECT 1 FROM supplier_contract_registry_versions m JOIN supplier_contract_registry r
            ON r.id=m.registry_id WHERE m.contract_version_id=t.id AND r.company_id=%s AND r.supplier_id=%s)""",
        [list(offers),company,str(target),company,target])
    ids=[r['id'] for r in versions]
    mappings=rows(cur,'supplier_contract_registry_versions','t.contract_version_id=ANY(%s) OR t.registry_id IN '
        '(SELECT id FROM supplier_contract_registry WHERE company_id=%s AND supplier_id=%s)',[ids,company,target])
    registries=rows(cur,'supplier_contract_registry','(t.company_id=%s AND t.supplier_id=%s) OR t.id=ANY(%s)',
        [company,target,[r['registry_id'] for r in mappings]])
    by_registry={r['id']:r for r in registries}
    if any(r['company_id']!=company or r['supplier_id']!=target or r['buyer_company_id']!=company or
            r['payer_company_id']!=company for r in registries):
        blocked('Стороны реестра договоров требуют отдельного разбора')
    if ({m['contract_version_id'] for m in mappings}!=set(ids) or
            {m['registry_id'] for m in mappings}!=set(by_registry) or
            any(m['company_id']!=company for m in mappings)):
        blocked('Не подтверждён полный состав версий договора этой компании')
    for version in versions:
        snapshot=version.get('snapshot_json')
        parties={key:snapshot.get(key) for key in ('supplier','buyer','payer')} if isinstance(snapshot,dict) else {}
        if (version['company_id']!=company or not all(isinstance(parties.get(key),dict) for key in ('supplier','buyer','payer')) or
                parties['supplier'].get('supplierId')!=target or
                parties['buyer'].get('companyId')!=company or
                parties['payer'].get('companyId')!=company or
                (version['offer_id'] is not None and version['offer_id'] not in offers)):
            blocked('Стороны или КП версии договора не подтверждены. Нужен отдельный разбор')
        if sum(m['contract_version_id']==version['id'] for m in mappings)!=1:
            blocked('Версия договора не имеет точной связи с реестром')
    for table in ('supplier_invoices','supply_deliveries'):
        if any(r.get('contract_version_id') is not None and r['contract_version_id'] not in ids for r in documents[table]):
            blocked('Версия договора счёта или поставки не входит в проверенную цепочку')
    publications=rows(cur,'supplier_contract_publications','t.contract_version_id=ANY(%s)',[ids])
    hashes={v['id']:v['snapshot_hash'] for v in versions}
    if any(r['company_id']!=company or r['snapshot_hash']!=hashes[r['contract_version_id']] for r in publications):
        blocked('История передачи договора не совпадает с его версией')
    events=rows(cur,'supplier_contract_registry_events','t.registry_id=ANY(%s)',[list(by_registry)])
    if any(r['company_id']!=company for r in events):blocked('История архива договора относится к другой компании')
    documents.update(supplier_contract_versions=versions,supplier_contract_registry=registries)
    return dict(mappings=mappings,publications=publications,events=events)


def verify_replay(cur,company,target,plan):
    cur.execute('SELECT profile FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',(company,target))
    row=cur.fetchone()
    if not row or (row['profile'] or {}).get(PROFILE_KEY)!=plan['allowedDocuments']['supplier_contract_versions']:
        blocked('Список закрытых версий договора изменился. Нужна новая проверка')
