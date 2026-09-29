from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from psycopg2.extras import Json

from .quantities import quantity, money
from . import records
from .documents import owned_document_url


def text_field(data, field, message, maximum=4000):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise HTTPException(400, message)
    return value.strip()


def create(cur, owner, actor, operation_id, data):
    reason = text_field(data, 'reason', 'Укажите причину брака')
    photos = data.get('photos')
    if not isinstance(photos, list) or not 1 <= len(photos) <= 20:
        raise HTTPException(400, 'Приложите фотографии брака')
    photos = [owned_document_url(cur, photo, owner['company_id'], owner['project_id']) for photo in photos]
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        raise HTTPException(400, 'Выберите испорченные материалы и количество')
    available = {row['id']: row['current_quantity'] for row in records.entries(cur, owner['journal_id'], owner['company_id'])}
    reserved = records.reserved_quantities(cur, owner['journal_id'], owner['company_id'])
    selected = {}
    for item in items:
        if not isinstance(item, dict) or type(item.get('entryId')) is not int or item['entryId'] <= 0:
            raise HTTPException(400, 'Выберите запись фактического расхода')
        entry_id = item['entryId']
        if entry_id not in available:
            raise HTTPException(404, 'Материал расхода этой работы не найден')
        selected[entry_id] = quantity(selected.get(entry_id, 0) + quantity(item.get('quantity')))
        if selected[entry_id] + reserved.get(entry_id, 0) > available[entry_id]:
            raise HTTPException(400, 'Количество брака превышает расход, свободный от других актов брака')
    cur.execute('''INSERT INTO work_material_defects(company_id,journal_id,operation_id,reported_by,reason,photos)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',
        (owner['company_id'], owner['journal_id'], operation_id, actor['id'], reason, Json(photos)))
    defect_id = cur.fetchone()['id']
    for entry_id, amount in selected.items():
        cur.execute('''INSERT INTO work_material_defect_items(defect_id,company_id,entry_id,quantity)
            VALUES(%s,%s,%s,%s)''', (defect_id, owner['company_id'], entry_id, amount))
    return next(records.defect_response(row) for row in records.defects(cur, owner['journal_id'], owner['company_id'])
                if row['id'] == defect_id)


def decide(cur, owner, actor, operation_id, defect_id, data):
    defect = next((row for row in records.defects(cur, owner['journal_id'], owner['company_id'])
                   if row['id'] == defect_id), None)
    if not defect:
        raise HTTPException(404, 'Акт брака этой работы не найден')
    cur.execute('SELECT 1 FROM work_contract_fine_allocations WHERE defect_id=%s LIMIT 1', (defect_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Штраф уже включён в акт. Пересмотр требует отдельного акта корректировки')
    decision = data.get('decision')
    if decision not in ('confirmed', 'disputed', 'cancelled'):
        raise HTTPException(400, 'Выберите решение по акту брака')
    if defect['status'] == 'cancelled' or defect['status'] == decision:
        raise HTTPException(409, 'Решение уже зафиксировано. Обновите акт брака')
    reason = text_field(data, 'reason', 'Укажите основание решения')
    amount, contract_evidence, valuations = Decimal('0.00'), '', []
    if decision == 'confirmed':
        allowed_types = {'Субподрядчик', 'ГПХ', 'Самозанятый', 'ИП', 'ООО', 'Своя бригада'}
        if owner['contractor_type'] not in allowed_types or owner['contract_status'] != 'Подписан':
            raise HTTPException(409, 'Штраф за материалы возможен только по подписанному договору подряда; уточните вид договора')
        contract_evidence = text_field(data, 'contractEvidence', 'Укажите договорное основание ответственности за материал')
        source = data.get('valuations')
        if not isinstance(source, list) or len(source) != len(defect['items']):
            raise HTTPException(400, 'Подтвердите стоимость каждого испорченного материала')
        values = {}
        for value in source:
            if not isinstance(value, dict) or type(value.get('entryId')) is not int or value['entryId'] in values:
                raise HTTPException(400, 'Для каждой строки нужна одна подтверждённая стоимость')
            values[value['entryId']] = value
        if set(values) != {item['entry_id'] for item in defect['items']}:
            raise HTTPException(400, 'Стоимость должна относиться к материалам этого акта брака')
        for item in defect['items']:
            value = values[item['entry_id']]
            price = money(value.get('unitPrice'), zero=False)
            evidence = text_field(value, 'priceEvidence', 'Укажите документ, подтверждающий стоимость материала')
            line_amount = (price * item['quantity']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            amount = money(amount + line_amount)
            valuations.append({'entryId': item['entry_id'], 'unitPrice': str(price),
                'name': item['material_name'], 'unit': item['unit'],
                'quantity': str(item['quantity']), 'amount': str(line_amount), 'priceEvidence': evidence})
        if not amount:
            raise HTTPException(400, 'Подтверждённая стоимость испорченного материала должна быть больше нуля')
        cur.execute('UPDATE brigade_contracts SET settlement_version=2 WHERE id=%s', (owner['contract_id'],))
    cur.execute('''INSERT INTO work_material_defect_decisions(company_id,defect_id,operation_id,actor_id,
        decision,reason,amount,contract_evidence,valuations) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (owner['company_id'], defect_id, operation_id, actor['id'], decision, reason, amount, contract_evidence, Json(valuations)))
    return next(records.defect_response(row) for row in records.defects(cur, owner['journal_id'], owner['company_id'])
                if row['id'] == defect_id)
