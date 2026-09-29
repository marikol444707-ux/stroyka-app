"""Append-only explicit grouping; historical snapshots and invoice links stay intact."""
from fastapi import HTTPException


def attach_registry(cur, contract, parties, source=None):
    company_id = contract['company_id']
    identity = (parties['supplier_id'], parties['buyer_company_id'], parties['payer_company_id'])
    registry = None
    if source is not None:
        snapshot = source['snapshot_json']
        if source['company_id'] != company_id or (
            snapshot.get('supplier', {}).get('supplierId'),
            snapshot.get('buyer', {}).get('companyId'),
            snapshot.get('payer', {}).get('companyId')) != identity:
            raise HTTPException(422, 'Стороны отличаются от сохранённого договора. Оформите отдельный договор')
        cur.execute('''SELECT r.* FROM supplier_contract_registry r
            JOIN supplier_contract_registry_versions m
              ON m.registry_id=r.id AND m.company_id=r.company_id
            WHERE m.contract_version_id=%s AND r.company_id=%s FOR UPDATE OF r''',
                    (source['id'], company_id))
        registry = cur.fetchone()
        if registry:
            if registry['archived']:
                raise HTTPException(422, 'Договор в архиве. Сначала восстановите его в архиве документов')
            if (registry['supplier_id'],registry['buyer_company_id'],registry['payer_company_id']) != identity:
                raise HTTPException(422, 'Договор относится к другим сторонам')
            cur.execute('''SELECT MAX(contract_version_id) AS latest
                FROM supplier_contract_registry_versions WHERE registry_id=%s AND company_id=%s''',
                        (registry['id'],company_id))
            if cur.fetchone()['latest'] != source['id']:
                raise HTTPException(422, 'У договора появилась новая версия. Обновите список договоров')
    if registry is None:
        cur.execute('''INSERT INTO supplier_contract_registry
            (company_id,supplier_id,buyer_company_id,payer_company_id)
            VALUES (%s,%s,%s,%s) RETURNING *''', (company_id,*identity))
        registry = cur.fetchone()
        if source is not None:
            cur.execute('''INSERT INTO supplier_contract_registry_versions
                (contract_version_id,registry_id,company_id) VALUES (%s,%s,%s)''',
                        (source['id'],registry['id'],company_id))
    cur.execute('''INSERT INTO supplier_contract_registry_versions
        (contract_version_id,registry_id,company_id) VALUES (%s,%s,%s)''',
                (contract['id'],registry['id'],company_id))
    return registry['id']
