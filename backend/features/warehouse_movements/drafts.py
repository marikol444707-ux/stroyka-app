"""Immutable movement intent; callers own authorization and transactions.

Every operation uses the same actor/company lock. History and cancelled command
bindings are retained, so delayed requests can never revive cancelled work.
"""
import hashlib
import json
from uuid import UUID
from fastapi import HTTPException
from psycopg2.extras import Json
from .idempotency import command_identity

SCHEMA_SQL = """
CREATE TABLE warehouse_movement_drafts (
 company_id integer NOT NULL REFERENCES companies(id),
 actor_user_id integer NOT NULL,
 draft_id uuid NOT NULL,
 commands jsonb NOT NULL,
 complete boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz,
 PRIMARY KEY(company_id,actor_user_id,draft_id)
);
CREATE UNIQUE INDEX warehouse_movement_drafts_one_pending
 ON warehouse_movement_drafts(company_id,actor_user_id) WHERE NOT complete;
CREATE TABLE warehouse_movement_draft_commands (
 company_id integer NOT NULL,
 actor_user_id integer NOT NULL,
 draft_id uuid NOT NULL,
 command_id uuid NOT NULL,
 payload_hash text NOT NULL,
 cancelled boolean NOT NULL DEFAULT false,
 cancelled_at timestamptz,
 PRIMARY KEY(company_id,command_id),
 FOREIGN KEY(company_id,actor_user_id,draft_id)
 REFERENCES warehouse_movement_drafts(company_id,actor_user_id,draft_id)
);
"""


def uuid_value(value, label):
    try:
        return str(UUID(str(value or '')))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, f'Некорректный {label}')


def actor_identity(user, expected):
    try:
        actor, expected = int(user.get('id') or 0), int(expected or 0)
    except (ValueError, TypeError):
        raise HTTPException(403, 'Не удалось подтвердить пользователя черновика')
    if actor <= 0 or actor != expected:
        raise HTTPException(403, 'Пользователь изменился. Обновите страницу.')
    return actor


def lock_actor(cur, company, actor):
    lock = int.from_bytes(hashlib.sha256(f'movement-draft:{company}:{actor}'.encode()).digest()[:8], 'big', signed=True)
    cur.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))


def command_payload(model, draft_id, actor):
    command_id, digest = command_identity(model)
    if getattr(model, 'draftId', None) is not None and uuid_value(model.draftId, 'draftId') != draft_id:
        raise HTTPException(409, 'Команда относится к другому черновику')
    if getattr(model, 'expectedActorUserId', None) is not None and model.expectedActorUserId != actor:
        raise HTTPException(403, 'Пользователь команды изменился')
    fields = ('materialName', 'fromLocation', 'toLocation', 'quantity', 'unit', 'workPackage',
              'date', 'createdBy', 'notes', 'invoiceId', 'invoiceLineIndex')
    command = {field: getattr(model, field, None) for field in fields}
    command.update(commandId=command_id, draftId=draft_id, expectedActorUserId=actor)
    return command, digest


def get_draft(cur, company, actor, draft_id):
    cur.execute('SELECT draft_id,commands,complete FROM warehouse_movement_drafts WHERE company_id=%s AND actor_user_id=%s AND draft_id=%s', (company, actor, draft_id))
    return cur.fetchone()


def pending_drafts(cur, company, actor):
    cur.execute('SELECT draft_id,commands,complete FROM warehouse_movement_drafts WHERE company_id=%s AND actor_user_id=%s AND NOT complete ORDER BY created_at', (company, actor))
    return cur.fetchall()


def reconcile(cur, company, actor, draft):
    commands = []
    for command in draft['commands']:
        cur.execute('SELECT c.payload_hash,c.response,b.payload_hash AS expected_hash,b.cancelled FROM warehouse_movement_draft_commands b LEFT JOIN warehouse_movement_commands c ON c.company_id=b.company_id AND c.command_id=b.command_id WHERE b.company_id=%s AND b.actor_user_id=%s AND b.draft_id=%s AND b.command_id=%s',
                    (company, actor, str(draft['draft_id']), command['commandId']))
        row = cur.fetchone()
        if row is None or (row['payload_hash'] is not None and row['payload_hash'] != row['expected_hash']):
            raise HTTPException(409, 'Не удалось подтвердить результат команды')
        committed = row['payload_hash'] is not None
        commands.append({'command': command, 'status': 'committed' if committed else ('cancelled' if row['cancelled'] else 'pending'), 'response': row['response'] if committed else None})
    complete = bool(commands) and all(item['status'] in ('committed', 'cancelled') for item in commands)
    if complete and not draft['complete']:
        cur.execute('UPDATE warehouse_movement_drafts SET complete=true,completed_at=now() WHERE company_id=%s AND actor_user_id=%s AND draft_id=%s', (company, actor, str(draft['draft_id'])))
    return {'draftId': str(draft['draft_id']), 'companyId': company, 'actorUserId': actor, 'commands': commands, 'complete': complete}


def prepare(cur, company, actor, draft_id, models):
    if not 1 <= len(models) <= 100:
        raise HTTPException(422, 'Черновик должен содержать от 1 до 100 команд')
    pairs = [command_payload(model, draft_id, actor) for model in models]
    commands = [pair[0] for pair in pairs]
    if len({c['commandId'] for c in commands}) != len(commands):
        raise HTTPException(422, 'Идентификаторы команд должны быть уникальны')
    if len(json.dumps(commands, ensure_ascii=False, allow_nan=False).encode()) > 262144:
        raise HTTPException(422, 'Черновик слишком большой')
    existing = get_draft(cur, company, actor, draft_id)
    if existing:
        if existing['commands'] != commands:
            raise HTTPException(409, 'Сохранённый черновик нельзя изменить')
        return existing
    if pending_drafts(cur, company, actor):
        raise HTTPException(409, 'Сначала завершите сохранённое перемещение')
    for command, _ in pairs:
        cur.execute('SELECT 1 FROM warehouse_movement_draft_commands WHERE company_id=%s AND command_id=%s UNION ALL SELECT 1 FROM warehouse_movement_commands WHERE company_id=%s AND command_id=%s',
                    (company, command['commandId'], company, command['commandId']))
        if cur.fetchone():
            raise HTTPException(409, 'Идентификатор команды уже используется')
    cur.execute('INSERT INTO warehouse_movement_drafts(company_id,actor_user_id,draft_id,commands) VALUES(%s,%s,%s,%s)', (company, actor, draft_id, Json(commands)))
    for command, digest in pairs:
        cur.execute('INSERT INTO warehouse_movement_draft_commands(company_id,actor_user_id,draft_id,command_id,payload_hash) VALUES(%s,%s,%s,%s,%s)', (company, actor, draft_id, command['commandId'], digest))
    return {'draft_id': draft_id, 'commands': commands, 'complete': False}


def verify_prepared(cur, company, actor, model):
    draft_id = uuid_value(getattr(model, 'draftId', None), 'draftId')
    command_id, digest = command_identity(model)
    cur.execute('SELECT payload_hash,cancelled FROM warehouse_movement_draft_commands WHERE company_id=%s AND actor_user_id=%s AND draft_id=%s AND command_id=%s', (company, actor, draft_id, command_id))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(409, 'Сначала сохраните черновик перемещения')
    if row['cancelled']:
        raise HTTPException(409, 'Команда отменена и больше не может быть выполнена')
    if row['payload_hash'] != digest:
        raise HTTPException(409, 'Сохранённую команду нельзя изменить')


def cancel_pending(cur, company, actor, draft):
    # Caller holds the writer lock: an in-flight write has committed or rolled back.
    # Only then does ledger absence establish that a command was not executed.
    state = reconcile(cur, company, actor, draft)
    for item in state['commands']:
        if item['status'] == 'pending':
            cur.execute('UPDATE warehouse_movement_draft_commands SET cancelled=true,cancelled_at=now() WHERE company_id=%s AND actor_user_id=%s AND draft_id=%s AND command_id=%s AND NOT cancelled',
                        (company, actor, str(draft['draft_id']), item['command']['commandId']))
    return reconcile(cur, company, actor, draft)
