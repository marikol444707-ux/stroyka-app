import json
from decimal import Decimal

from fastapi import HTTPException
from psycopg2.extras import Json

from .quantities import quantity
from . import records


def correct(cur, owner, project, actor, operation_id, data, personal_balance):
    reason = data.get('reason')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise HTTPException(400, 'Укажите причину исправления расхода')
    entry_id = data.get('entryId')
    if type(entry_id) is not int or entry_id <= 0:
        raise HTTPException(400, 'Выберите исходную запись расхода')
    target, expected = quantity(data.get('quantity'), zero=True), quantity(data.get('expectedQuantity'), zero=True)
    originals = records.entries(cur, owner['journal_id'], owner['company_id'])
    entry = next((row for row in originals if row['id'] == entry_id), None)
    if not entry:
        raise HTTPException(404, 'Запись расхода этой работы не найдена')
    if entry['current_quantity'] != expected:
        raise HTTPException(409, 'Расход уже исправлен. Обновите данные перед корректировкой')
    reserved = records.reserved_quantities(cur, owner['journal_id'], owner['company_id'])
    if target < reserved.get(entry_id, 0):
        raise HTTPException(409, 'Расход не может быть меньше материала, указанного в действующих актах брака')
    delta = target - expected
    if not delta:
        raise HTTPException(400, 'Укажите новое фактическое количество')
    if entry['source'] == 'personal' and delta > 0:
        balance = personal_balance(cur, project['name'], owner['actor_id'], owner['actor_name'],
            entry['material_name'], entry['work_package'], entry['unit'], company_id=owner['company_id'])
        if Decimal(str(balance['available'])) < delta:
            raise HTTPException(400, 'Недостаточно подтверждённого материала у исполнителя')
    if entry['source'] == 'warehouse':
        cur.execute('''SELECT quantity FROM materials WHERE id=%s AND company_id=%s AND project=%s FOR UPDATE''',
                    (entry['warehouse_material_id'], owner['company_id'], project['name']))
        stock = cur.fetchone()
        if not stock:
            raise HTTPException(409, 'Исходный складской остаток изменился. Требуется сверка')
        available = quantity(stock['quantity'], zero=True)
        if available < delta:
            raise HTTPException(400, 'Недостаточно материала на складе объекта')
        after = quantity(available - delta, zero=True)
        cur.execute('UPDATE materials SET quantity=%s WHERE id=%s RETURNING quantity', (after, entry['warehouse_material_id']))
        if Decimal(str(cur.fetchone()['quantity'])) != after:
            raise HTTPException(409, 'Склад не может сохранить исправленное количество с требуемой точностью')
    cur.execute('''INSERT INTO work_material_entries(company_id,journal_id,operation_id,corrects_entry_id,
        source,warehouse_material_id,material_name,unit,work_package,quantity,identity_snapshot,unit_price,reason)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (owner['company_id'], owner['journal_id'], operation_id, entry_id, entry['source'], entry['warehouse_material_id'],
         entry['material_name'], entry['unit'], entry['work_package'], delta, Json(entry['identity_snapshot']),
         entry['unit_price'], reason.strip()))
    correction_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO warehouse_history(company_id,material,type,quantity,unit,date,project,
        issued_to,issued_by,work_package,source_type,source_id)
        VALUES(%s,%s,'корректировка расхода по работе',%s,%s,CURRENT_DATE,%s,%s,%s,%s,'work_material_entry',%s)''',
        (owner['company_id'], entry['material_name'], delta, entry['unit'], project['name'], owner['actor_name'],
         actor.get('name') or '', entry['work_package'], correction_id))
    # Projection for old readers; immutable original/delta entries remain the evidence.
    cur.execute('SELECT materials_used FROM work_journal WHERE id=%s', (owner['journal_id'],))
    raw = cur.fetchone()['materials_used']
    prior = json.loads(raw) if isinstance(raw, str) else raw or []
    grouped = {}
    for row in records.entries(cur, owner['journal_id'], owner['company_id']):
        if row['current_quantity'] <= 0:
            continue
        key = (tuple(row['identity_snapshot']['key']), row['work_package'])
        if key not in grouped:
            template = next((item for item in prior if tuple((item.get('identitySnapshot') or {}).get('key', [])) == key[0]
                             and item.get('workPackage') == key[1]), {})
            grouped[key] = {**template, 'name': row['material_name'], 'unit': row['unit'], 'workPackage': row['work_package'],
                            'identitySnapshot': row['identity_snapshot'], 'personalQuantity': 0, 'warehouseQuantity': 0,
                            'warehouseMaterialId': None}
        item = grouped[key]
        field = 'personalQuantity' if row['source'] == 'personal' else 'warehouseQuantity'
        item[field] = float(row['current_quantity'])
        if row['source'] == 'warehouse':
            item['warehouseMaterialId'] = row['warehouse_material_id']
        item['quantity'] = round(item['personalQuantity'] + item['warehouseQuantity'], 6)
    cur.execute('UPDATE work_journal SET materials_used=%s WHERE id=%s',
                (json.dumps(list(grouped.values()), ensure_ascii=False), owner['journal_id']))
    return {'ok': True, 'correctionId': correction_id, 'entryId': entry_id, 'quantity': target}
