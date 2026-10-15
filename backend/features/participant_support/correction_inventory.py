"""Bounded company evidence for an exact supplier connection correction.

Keep only digests/counts in the saved plan. Raw rows, invitation secrets, file
locators and financial snapshots never leave the transaction or enter the plan.
"""
import hashlib
import json
import os

from fastapi import HTTPException
from psycopg2 import sql

from .merge_inventory import POLICY_TABLES, POLICY_FLAGS, tables
from ..supplier_team.policy import access_ids, enabled as team_enabled
from ..supply_claim_cases.access import CHAIN
from . import correction_rfqs

IGNORED = {'supplier_connection_correction_plans', 'supplier_history_merge_plans',
           'supplier_buyer_connection_requests', 'supplier_team_operations',
           'supplier_team_invites', 'supplier_aliases'}
ARRAY_REFS = {'selected_suppliers', 'supplier_group_ids', 'supplier_ids'}
REQUIRED = set(POLICY_TABLES) | {'supplier_contract_registry', 'supplier_documents'}


def supplier_references(cur, schema):
    # Include typed supplier FKs even when a future module calls it vendor_id.
    cur.execute('''SELECT t.relname AS table_name,a.attname AS column_name
        FROM pg_constraint f JOIN pg_class t ON t.oid=f.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=ANY(f.conkey)
        WHERE f.contype='f' AND f.confrelid='public.suppliers'::regclass AND n.nspname='public' ''')
    refs = {}
    for row in cur.fetchall():refs.setdefault(row['table_name'],set()).add(row['column_name'])
    for name,columns in schema.items():
        refs.setdefault(name,set()).update(c for c in columns if c=='supplier_id' or c.endswith('_supplier_id'))
    return refs


def reference_condition(columns, refs, ids):
    parts=[];params=[]
    for column in sorted(refs):
        parts.append(sql.SQL('t.{}=ANY(%s)').format(sql.Identifier(column)));params.append(ids)
    for column in sorted(columns & ARRAY_REFS):
        parts.append(sql.SQL("COALESCE(t.{},'{{}}'::int[]) && %s::int[]").format(sql.Identifier(column)));params.append(ids)
    return sql.SQL(' OR ').join(parts) if parts else sql.SQL('FALSE'),params


def used_by_target(row, refs, source, target, owner):
    if any(row.get(key)==target for key in refs):return True
    if any(target in (row.get(key) or []) for key in ARRAY_REFS):return True
    # Recipient policies can address the user or an owned/group card as well.
    if row.get('supplier_user_id')==owner and (
            row.get('supplier_id') in (None,source) or row.get('target_supplier_id') in (None,source)):
        return True
    return False


def inventory(cur, company, source, target, owner, *, mode='disconnect_unused'):
    schema=tables(cur)
    if not REQUIRED <= schema.keys():
        raise HTTPException(503,'Для исправления требуется полный реестр документов и назначений')
    refs=supplier_references(cur,schema)
    inspected=(set(POLICY_TABLES)|{n for n,c in schema.items() if refs.get(n) or c & ARRAY_REFS})-IGNORED
    if team_enabled():owner_ids=access_ids(cur,owner)
    else:
        cur.execute('SELECT id FROM suppliers WHERE user_id=%s ORDER BY id',(owner['id'],))
        owner_ids=[r['id'] for r in cur.fetchall()]
    rfq=correction_rfqs.request_plan(cur,company,target,owner,owner_ids,schema,mode=mode) if mode!='disconnect_unused' else None
    fingerprints={};locked=[]
    retained={kind:0 for kind in ('invoices','receipts','offers')}
    names={'supplier_invoices':'invoices','warehouse_invoices':'receipts','supplier_offers':'offers'}
    for name in sorted(inspected):
        columns=schema[name];reference,params=reference_condition(columns,refs.get(name,set()),[source,target])
        if name=='company_supplier_links':
            clause=sql.SQL('t.company_id=%s');params=[company]
        elif name=='supplier_team_members':
            clause=reference
        elif name=='supplier_offer_assignments':
            clause=sql.SQL('t.offer_id IN (SELECT id FROM supplier_offers WHERE company_id=%s) OR (')+reference+sql.SQL(' AND NOT EXISTS (SELECT 1 FROM supplier_offers o WHERE o.id=t.offer_id))')
            params=[company]+params
        elif name=='supply_claims':
            clause=sql.SQL('t.id IN (SELECT c.id'+CHAIN+' WHERE d.company_id=%s AND c.supplier_id=ANY(%s)) OR (')+reference+sql.SQL(' AND NOT EXISTS(SELECT 1 FROM (SELECT c.id'+CHAIN+') valid WHERE valid.id=t.id))')
            params=[company,[source,target]]+params
        elif 'company_id' in columns:
            # Include all buyer policy rows so changed recipients/addenda/files
            # invalidate confirmation, including an insertion into an empty set.
            if name in POLICY_TABLES or name=='supplier_contract_registry':
                clause=sql.SQL('t.company_id=%s OR (t.company_id IS NULL AND (')+reference+sql.SQL('))')
                params=[company]+params
            else:
                clause=sql.SQL('(t.company_id=%s OR t.company_id IS NULL) AND (')+reference+sql.SQL(')')
                params=[company]+params
        else:
            clause=reference
        query=sql.SQL('SELECT to_jsonb(t) AS row FROM {} t WHERE ').format(sql.Identifier(name))+clause+sql.SQL(' ORDER BY to_jsonb(t)::text')
        limit=100 if name=='file_ownership' else 2000
        cur.execute(query+sql.SQL(' LIMIT %s'),params+[limit+1])
        rows=cur.fetchall()
        if len(rows)>limit:
            raise HTTPException(409,'Архив слишком большой для автоматического отключения. Нужна отдельная проверка')
        values=[r['row'] for r in rows]
        fingerprints[name]=values
        if name=='supply_claims' and values:
            cur.execute('SELECT c.id'+CHAIN+' WHERE d.company_id=%s AND c.supplier_id=ANY(%s)',(company,[source,target]))
            valid={r['id'] for r in cur.fetchall()}
            if any(r['id'] not in valid for r in values):
                raise HTTPException(409,'Принадлежность претензии не подтверждена. Требуется отдельная проверка')
        # Catalog writers serialize on the buyer; supplier/team writers also
        # lock the exact parent. Do not SHARE-lock tables that this command updates.
        if name not in ('company_supplier_links','supplier_team_members'):locked.append(name)
        if name=='company_supplier_links':
            if any((r.get('profile') or {}).get('mergedIntoSupplierId') in (source,target) or
                   str((r.get('profile') or {}).get('mergedIntoSupplierId')) in (str(source),str(target)) for r in values):
                raise HTTPException(409,'Объединённая история требует отдельного исправления')
            continue
        if name=='supplier_team_members':
            if any(r.get('supplier_id')==source for r in values):
                raise HTTPException(409,'У исходной карточки есть команда. Требуется отдельная проверка')
            continue
        for row in values:
            related=used_by_target(row,refs.get(name,set()),source,target,owner['id'])
            if name=='supplier_contract_versions' and str((row.get('snapshot_json') or {}).get('supplier',{}).get('supplierId'))==str(target):related=True
            if related and not (rfq and correction_rfqs.allowed(rfq,name,row)):
                raise HTTPException(409,'Кабинет уже получил документы, заявки или назначения. Требуется отдельное исправление адресатов')
            if (name not in POLICY_TABLES and 'company_id' not in columns and values) or (
                    'company_id' in columns and row.get('company_id') is None):
                raise HTTPException(409,'Принадлежность части истории не подтверждена. Требуется отдельная проверка')
        if name in names:retained[names[name]]=sum(r.get('supplier_id')==source for r in values)
    # A legacy array can address the connected card without a recipient or quote.
    # Work addressed to another owned card is independent of this new link.
    for row in fingerprints['supply_requests']:
        if target in (row.get('selected_suppliers') or []) and not (rfq and correction_rfqs.allowed(rfq,'supply_requests',row)):
            raise HTTPException(409,'Кабинету уже адресована заявка этой компании. Сначала проверьте её получателей')
    cur.execute('SELECT to_jsonb(s) AS row FROM suppliers s WHERE id=ANY(%s) ORDER BY id',([source,target],))
    fingerprints['suppliers']=[r['row'] for r in cur.fetchall()]
    flags={key:os.getenv(key,'0') for key in POLICY_FLAGS}
    payload=dict(rows=fingerprints,schema={n:sorted(schema[n]) for n in inspected},refs={n:sorted(refs.get(n,set())) for n in inspected},flags=flags,ownerIds=sorted(owner_ids))
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result=dict(digest=digest,tables=sorted(set(locked)|(correction_rfqs.EXTRA_TABLES|set(rfq['referenceTables']) if mode!='disconnect_unused' else set())),retainedDocuments=retained,flags=flags)
    if rfq:result['rfq']=rfq
    return result
