"""Create/retry manual contracts using explicit commands, never a person's name."""
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException


def manual_request_id(reference, legacy_id=None):
    if not isinstance(reference, dict) or set(reference) != {'type', 'requestId'} or reference['type'] != 'manual':
        raise HTTPException(400, 'Некорректная команда создания бригады без аккаунта')
    if legacy_id not in (None, ''):
        raise HTTPException(400, 'Для бригады без аккаунта нельзя указывать пользователя')
    try:
        value = reference['requestId']
        parsed = UUID(value) if isinstance(value, str) else None
        if parsed is None or parsed.version != 4 or str(parsed) != value:
            raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'Некорректный ключ создания бригады')


def command_evidence(reference, *, company_id, project_id, actor_id, command, payload):
    request_id = manual_request_id(reference)
    if 'expectedCompanyId' in payload or 'expectedActorId' in payload:
        if (type(payload.get('expectedCompanyId')) is not int or payload['expectedCompanyId'] != company_id
                or type(payload.get('expectedActorId')) is not int or payload['expectedActorId'] != actor_id):
            raise HTTPException(403, 'Пользователь или компания изменились. Откройте сохранённую отправку под исходным пользователем')
    try:
        encoded = json.dumps({'command': command, 'companyId': company_id, 'projectId': project_id,
            'actorId': actor_id, 'payload': payload}, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError):
        raise HTTPException(400, 'Некорректные данные создания бригады')
    return request_id, hashlib.sha256(encoded.encode()).hexdigest()


def find_manual_retry(cur, company_id, project_id, work_package, request_id, command_hash):
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('manual-brigade:'+str(company_id)+':'+request_id,))
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (company_id, project_id))
    cur.execute('''SELECT o.contract_id,o.command_hash,bc.project_id,
            COALESCE(NULLIF(bc.work_package,''),'Основная') AS package,bc.contractor_id,bc.status,
            bc.party_snapshot_json,bc.party_snapshot_hash
        FROM manual_brigade_contract_origins o JOIN brigade_contracts bc ON bc.id=o.contract_id
        WHERE o.company_id=%s AND o.request_id=%s AND bc.company_id=o.company_id
        FOR UPDATE OF bc''', (company_id, request_id))
    row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        # These callers use ordinary cursors; keep the API explicit for dict cursors too.
        row = (row['contract_id'], row['command_hash'], row['project_id'], row['package'],
               row['contractor_id'], row['status'], row['party_snapshot_json'], row['party_snapshot_hash'])
    if (row[1] != command_hash or row[2] != project_id or row[3] != work_package
            or row[4] is not None or row[5] in ('Подписан', 'Аннулирован', 'Удалён', 'Удален')
            or row[6] is not None or row[7] is not None):
        raise HTTPException(409, 'Предыдущая команда создания бригады отличается. Обновите список договоров')
    return row[0]


def record_manual_origin(cur, contract_id, company_id, project_id, request_id, command_hash, actor_id):
    cur.execute('''INSERT INTO manual_brigade_contract_origins
        (contract_id,company_id,project_id,request_id,command_hash,created_by)
        VALUES(%s,%s,%s,%s,%s,%s)''', (contract_id, company_id, project_id, request_id, command_hash, actor_id))


def require_manual_contract(cur, company_id, project_id, contract_id, work_package):
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (company_id, project_id))
    cur.execute('''SELECT bc.id FROM brigade_contracts bc
        JOIN manual_brigade_contract_origins o ON o.contract_id=bc.id
            AND o.company_id=bc.company_id AND o.project_id=bc.project_id
        JOIN projects p ON p.id=bc.project_id AND p.company_id=bc.company_id
        WHERE bc.id=%s AND bc.company_id=%s AND bc.project_id=%s
            AND COALESCE(NULLIF(bc.work_package,''),'Основная')=%s
            AND bc.contractor_id IS NULL AND bc.party_snapshot_json IS NULL AND bc.party_snapshot_hash IS NULL
            AND COALESCE(bc.status,'') NOT IN ('Подписан','Аннулирован','Удалён','Удален')
        FOR UPDATE OF bc''', (contract_id, company_id, project_id, work_package))
    if not cur.fetchone():
        raise HTTPException(409, 'Бригада без аккаунта не подтверждена для выбранного договора')
