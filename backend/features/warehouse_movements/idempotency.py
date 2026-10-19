"""Durable legacy movement commands. Caller owns authorization and transaction."""
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

SCHEMA_SQL = """
CREATE TABLE warehouse_movement_commands (
    company_id integer NOT NULL REFERENCES companies(id),
    command_id uuid NOT NULL,
    payload_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, command_id)
)
"""


def command_identity(model):
    try:
        command_id = str(UUID(str(getattr(model, 'commandId', '') or '')))
    except ValueError:
        raise HTTPException(422, 'Обновите страницу: для перемещения нужен идентификатор команды. Повторяйте незавершённую операцию с тем же идентификатором.')
    fields = ('materialName', 'fromLocation', 'toLocation', 'quantity', 'unit',
              'workPackage', 'date', 'createdBy', 'notes', 'invoiceId', 'invoiceLineIndex')
    payload = {field: getattr(model, field, None) for field in fields}
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Некорректные данные перемещения')
    return command_id, hashlib.sha256(encoded.encode()).hexdigest()


def replay_command(cur, company_id, command_id, payload_hash):
    # Same key waits for commit/rollback, including when no ledger row exists yet.
    # Advisory collisions only serialize unrelated commands; the PK is authoritative.
    lock = int.from_bytes(hashlib.sha256(f'warehouse-movement:{company_id}:{command_id}'.encode()).digest()[:8], 'big', signed=True)
    cur.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
    cur.execute('SELECT payload_hash,response FROM warehouse_movement_commands WHERE company_id=%s AND command_id=%s',
                (company_id, command_id))
    previous = cur.fetchone()
    if previous is None:
        return None
    if previous['payload_hash'] != payload_hash:
        raise HTTPException(409, 'Эта команда уже выполнена с другими данными. Проверьте результат исходного перемещения; не повторяйте его как новое.')
    return previous['response']


def save_command(cur, company_id, command_id, payload_hash, result):
    response = jsonable_encoder(result)
    cur.execute('INSERT INTO warehouse_movement_commands (company_id,command_id,payload_hash,response) VALUES (%s,%s,%s,%s)',
                (company_id, command_id, payload_hash, Json(response)))
    return response
