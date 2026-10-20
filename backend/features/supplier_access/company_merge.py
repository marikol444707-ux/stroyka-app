"""Company-confirmed grouping, preserving original documents and bank snapshots."""
import hashlib
import json

from fastapi import HTTPException
from .legal_identity import canonical_legal
from psycopg2.extras import Json
from psycopg2 import sql


def group_rows(rows):
    by_id = {row['id']: row for row in rows}
    groups = {}
    for row in rows:
        target = row.pop('mergedIntoSupplierId', None) or row['id']
        if target not in by_id:
            target = row['id']
        groups.setdefault(target, []).append(row['id'])
    for target, ids in groups.items():
        for sid in ids:
            by_id[sid].update(canonicalSupplierId=target, relatedSupplierIds=sorted(ids))
    return rows


def owned_metadata(cur, rows):
    ids = [row['id'] for row in rows]
    cur.execute("SELECT supplier_id,to_jsonb(l)->'profile'->>'mergedIntoSupplierId' AS target FROM company_supplier_links l WHERE supplier_id=ANY(%s)", (ids,))
    targets = {r['supplier_id']: int(r['target']) for r in cur.fetchall() if r.get('target') and r['target'].isdigit()}
    grouped = group_rows([dict(id=sid, mergedIntoSupplierId=targets.get(sid)) for sid in ids])
    return {row['id']: row for row in grouped}


def check_company_documents(cur, source_id, company_id):
    cur.execute('''SELECT DISTINCT a.table_name FROM information_schema.columns a
        JOIN information_schema.columns b ON b.table_schema=a.table_schema AND b.table_name=a.table_name
        WHERE a.table_schema='public' AND a.column_name='supplier_id' AND b.column_name='company_id'
        ORDER BY a.table_name''')
    tables = [r['table_name'] for r in cur.fetchall()]
    for table in tables:
        cur.execute(sql.SQL('SELECT 1 FROM {} WHERE supplier_id=%s AND company_id IS DISTINCT FROM %s LIMIT 1')
                    .format(sql.Identifier(table)), (source_id, company_id))
        if cur.fetchone():
            raise HTTPException(409, 'История карточки требует проверки компании-владельца')


def pair(cur, company, target_id, source_id):
    if type(source_id) is not int or source_id <= 0 or source_id == target_id:
        raise HTTPException(422, 'Выберите другую карточку поставщика')
    cur.execute('''SELECT s.*,l.id AS link_id,l.version AS link_version,l.profile
        FROM suppliers s JOIN company_supplier_links l ON l.supplier_id=s.id
        WHERE l.company_id=%s AND l.platform_account_id=%s AND s.id=ANY(%s)
        ORDER BY s.id FOR UPDATE OF s,l''',
        (company['id'], company['platform_account_id'], sorted([target_id, source_id])))
    rows = {r['id']: r for r in cur.fetchall()}
    if len(rows) != 2:
        raise HTTPException(404, 'Обе карточки должны быть в каталоге выбранной компании')
    target, source = rows[target_id], rows[source_id]
    if any((r['profile'] or {}).get('mergedIntoSupplierId') for r in rows.values()):
        raise HTTPException(409, 'Карточка уже объединена. Обновите каталог')
    if source.get('user_id'):
        raise HTTPException(409, 'Основной должна быть карточка с кабинетом поставщика')
    cur.execute("SELECT 1 FROM company_supplier_links WHERE company_id=%s AND profile->>'mergedIntoSupplierId'=%s LIMIT 1",
                (company['id'], str(source_id)))
    if cur.fetchone():
        raise HTTPException(409, 'Вторая карточка уже содержит объединённую историю. Выберите её основной')
    for key in ('inn', 'ogrn'):
        lengths = (10, 12) if key == 'inn' else (13, 15)
        left, right = canonical_legal(target.get(key), lengths), canonical_legal(source.get(key), lengths)
        if left is None or right is None or (left and right and left != right):
            raise HTTPException(409, 'Реквизиты карточек различаются. Объединение недоступно')
    # Attaching a provisional identity to an account must never share another
    # buyer's legacy records. Check every persisted company-scoped supplier FK.
    cur.execute('SELECT company_id,platform_account_id FROM company_supplier_links WHERE supplier_id=%s', (source_id,))
    if any(r['company_id'] != company['id'] or r['platform_account_id'] != company['platform_account_id'] for r in cur.fetchall()):
        raise HTTPException(409, 'Карточка используется другой компанией. Нужна проверка платформы')
    cur.execute('SELECT 1 FROM supplier_team_members WHERE supplier_id=%s LIMIT 1', (source_id,))
    if cur.fetchone():
        raise HTTPException(409, 'У второй карточки уже есть команда поставщика')
    check_company_documents(cur, source_id, company['id'])
    return target, source


def preview_for_pair(cur, company, target, source):
    counts, documents = {}, {}
    for table in ('supplier_invoices', 'warehouse_invoices', 'supplier_offers'):
        # Include exact current rows, not just counts: replacing/changing a
        # document between preview and confirm must invalidate the review.
        cur.execute(sql.SQL('SELECT id,md5(to_jsonb(d)::text) AS fingerprint FROM {} d WHERE supplier_id=%s AND company_id=%s ORDER BY id')
                    .format(sql.Identifier(table)), (source['id'], company['id']))
        documents[table] = [dict(row) for row in cur.fetchall()]
        counts[table] = len(documents[table])
    review = dict(targetId=target['id'], sourceId=source['id'], targetName=target['name'], sourceName=source['name'],
                  targetVersion=target['link_version'], sourceVersion=source['link_version'],
                  hasSupplierAccount=bool(target.get('user_id')), documents=counts)
    evidence = dict(companyId=company['id'], platformAccountId=company['platform_account_id'],
                    review=review, documents=documents,
                    identities=[{key: row.get(key) for key in ('id', 'inn', 'ogrn', 'user_id', 'profile')}
                                for row in (target, source)])
    review['reviewVersion'] = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
    return review


def preview(cur, company, target_id, source_id):
    target, source = pair(cur, company, target_id, source_id)
    return preview_for_pair(cur, company, target, source)


def confirm(directory, data, user, headers, target_id):
    if data.get('confirmed') is not True:
        raise HTTPException(422, 'Сначала проверьте карточки и подтвердите объединение')
    with directory.transaction(user, headers, write=True, claimed_company_id=data.get('companyId')) as (cur, company, actor):
        if actor.get('role') not in ('директор', 'зам_директора', 'бухгалтер'):
            raise HTTPException(403, 'Объединять карточки может руководитель или бухгалтер')
        target, source = pair(cur, company, target_id, data.get('sourceId'))
        if target.get('user_id'):
            raise HTTPException(409, 'Объединение с кабинетом открывает старую историю. Выполните проверку в Администратор → Организации → Участники и доступ → Поставщики.')
        if any(type(data.get(key)) is not int or data[key] != row['link_version']
               for key, row in (('targetVersion', target), ('sourceVersion', source))):
            raise HTTPException(409, 'Карточки изменились. Проверьте объединение ещё раз')
        review = preview_for_pair(cur, company, target, source)
        if data.get('expectedReview') != review['reviewVersion']:
            raise HTTPException(409, 'Карточки или документы изменились. Проверьте последствия объединения ещё раз')
        apply_pair(cur,target,source)
        directory.audit(cur, actor, company, source['link_id'], 'supplier_cards_merged')
        return dict(ok=True, targetId=target_id, sourceId=source['id'])


def apply_pair(cur,target,source):
    """Caller must lock/revalidate the pair and authorize historical disclosure."""
    profile={**(source['profile'] or {}),'mergedIntoSupplierId':target['id']}
    cur.execute('UPDATE company_supplier_links SET profile=%s,version=version+1 WHERE id=%s',
                (Json(profile),source['link_id']))
    cur.execute('UPDATE company_supplier_links SET version=version+1 WHERE id=%s',(target['link_id'],))
    if target.get('user_id'):
        cur.execute('UPDATE suppliers SET user_id=%s WHERE id=%s',(target['user_id'],source['id']))


def document_relationship(cur, supplier_id, company_id):
    """Catalog provenance comes from the caller's locked, company-owned receipt."""
    if not supplier_id:
        return
    cur.execute('SELECT platform_account_id FROM companies WHERE id=%s FOR SHARE', (company_id,))
    company = cur.fetchone()
    if not company or not company.get('platform_account_id'):
        raise HTTPException(409, 'Компания накладной не привязана к аккаунту платформы')
    cur.execute("""INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id,source_type,source_detail)
        VALUES(%s,%s,%s,'warehouse_invoice','Из накладной компании')
        ON CONFLICT(company_id,supplier_id) DO NOTHING""",
        (company_id, supplier_id, company['platform_account_id']))
    cur.execute('SELECT platform_account_id FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',
                (company_id, supplier_id))
    if cur.fetchone()['platform_account_id'] != company['platform_account_id']:
        raise HTTPException(409, 'Связь поставщика с аккаунтом компании требует проверки')
