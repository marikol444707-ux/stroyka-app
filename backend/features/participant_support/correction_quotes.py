"""Received quotes may be rejected; never alter prices, originals or snapshots."""
import re
from fastapi import HTTPException

MODE='reject_received_quotes'


def validate_offer(offer):
    if offer['status']!='Получено' or not offer.get('responded_at'):
        raise HTTPException(409,'КП уже выбрано или его состояние не подтверждено. Нужна отдельная проверка')


def originals(cur,company,offers,schema):
    required={'file_ownership':{'id','company_id','file_url','deletion_status'},
        'supplier_offers':{'id','pdf_url'},'supplier_invoices':{'file_url','photo_url'},
        'supplier_contract_versions':{'source_file_id','snapshot_json'}}
    if any(not columns<=schema.get(table,set()) for table,columns in required.items()):
        raise HTTPException(503,'Проверка КП требует полного реестра оригиналов')
    offer_ids=[o['id'] for o in offers]
    checked=set()
    for offer in offers:
        url=offer.get('pdf_url')
        if not url:continue
        match=re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content',str(url))
        if match:
            cur.execute('SELECT id,company_id,file_url,deletion_status FROM file_ownership WHERE id=%s',(int(match[1]),))
        else:
            cur.execute('SELECT id,company_id,file_url,deletion_status FROM file_ownership WHERE file_url=%s',(url,))
        files=cur.fetchall()
        if len(files)!=1 or files[0]['company_id']!=company or files[0]['deletion_status'] not in (None,'','active'):
            raise HTTPException(409,'Оригинал КП отсутствует в архиве компании, удалён или имеет другого владельца')
        original=files[0];urls=[url,original['file_url'],f"/tenant-files/{original['id']}/content"]
        cur.execute('''SELECT 1 FROM supplier_offers WHERE NOT (id=ANY(%s)) AND pdf_url=ANY(%s)
            UNION ALL SELECT 1 FROM supplier_invoices WHERE file_url=ANY(%s) OR photo_url=ANY(%s)
            UNION ALL SELECT 1 FROM supplier_contract_versions WHERE source_file_id=%s
                OR EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(snapshot_json->'addenda','[]'::jsonb)) a
                    WHERE a->>'sourceFileId'=%s) LIMIT 1''',
            (offer_ids,urls,urls,urls,original['id'],str(original['id'])))
        if cur.fetchone():
            raise HTTPException(409,'Оригинал КП используется в другом документе. Нужна отдельная проверка доступа')
        checked.add(original['id'])
    return len(checked)
