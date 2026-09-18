import hashlib
import json
import os
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json


def enabled():
    return os.environ.get('WORK_MATERIAL_ACCOUNTING_ENABLED') == '1'


def begin_operation(cur, actor, request_id, kind, payload):
    command = payload.get('data', payload)
    for field, expected in (('expectedCompanyId', actor.get('companyId')), ('expectedActorId', actor.get('id'))):
        if command.get(field) is not None and command[field] != expected:
            raise HTTPException(409, 'Компания или исполнитель изменились. Вернитесь к исходной отправке')
    try:
        key = str(UUID(str(request_id)))
        encoded = json.dumps(jsonable_encoder(payload), ensure_ascii=False,
                             sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(400, 'Нужен корректный идентификатор отправки и конечные значения')
    company_id = int(actor.get('companyId') or actor.get('company_id') or 0)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    cur.execute('''SELECT id,kind,payload_hash,result FROM work_material_operations
        WHERE company_id=%s AND actor_id=%s AND request_id=%s FOR UPDATE''',
                (company_id, actor['id'], key))
    row = cur.fetchone()
    if row:
        if not isinstance(row, dict):
            row = dict(zip(('id', 'kind', 'payload_hash', 'result'), row))
        if row['kind'] != kind or row['payload_hash'] != digest:
            raise HTTPException(409, 'Эта отправка уже использована с другим содержимым')
        if row['result'] is None:
            raise HTTPException(409, 'Отправка ещё не завершена')
        return row['id'], row['result']
    cur.execute('''INSERT INTO work_material_operations(company_id,actor_id,request_id,kind,payload_hash)
        VALUES(%s,%s,%s,%s,%s) RETURNING id''', (company_id, actor['id'], key, kind, digest))
    row = cur.fetchone()
    return (row['id'] if isinstance(row, dict) else row[0]), None


def finish_operation(cur, operation_id, result):
    cur.execute('UPDATE work_material_operations SET result=%s WHERE id=%s AND result IS NULL',
                (Json(jsonable_encoder(result)), operation_id))
