"""Claim discussion and resolution; receipt, stock and money remain separate facts."""
import os

from fastapi import HTTPException
from psycopg2.extras import Json

DIRECTORS = ('директор', 'зам_директора')
WRITERS = (*DIRECTORS, 'снабженец', 'кладовщик', 'прораб')
ACTIONS = {'start': 'canStart', 'comment': 'canComment', 'reply': 'canReply',
           'resolve': 'canResolve', 'reopen': 'canReopen'}


def enabled():
    return os.environ.get('SUPPLY_CLAIMS_ENABLED') == '1'


def capabilities(role, status):
    opened = status in ('Открыта', 'В работе')
    return dict(canStart=role in WRITERS and status == 'Открыта',
                canComment=role in WRITERS and opened,
                canReply=role == 'поставщик' and opened,
                canResolve=role in DIRECTORS and opened,
                canReopen=role in DIRECTORS and status in ('Решена', 'Закрыта'))


def validate(data):
    if set(data) - {'action', 'text', 'expectedVersion', 'requestId', 'expectedCompanyId',
                    'expectedActorId', 'materialAccountingVersion'}:
        raise HTTPException(400, 'Переданы неизвестные поля претензии')
    action, text = data.get('action'), data.get('text')
    if not isinstance(action, str) or action not in ACTIONS:
        raise HTTPException(400, 'Выберите действие с претензией')
    if not isinstance(text, str) or not text.strip() or len(text) > 4000 or '\x00' in text:
        raise HTTPException(400, 'Введите сообщение от 1 до 4000 символов')
    for field in ('expectedVersion', 'expectedCompanyId', 'expectedActorId'):
        if type(data.get(field)) is not int or data[field] <= 0:
            raise HTTPException(400, 'Обновите карточку и выбранную компанию перед отправкой')
    return action, text.strip()


def command(cur, claim, actor, data, operation_id):
    action, text = validate(data)
    if not capabilities(actor['role'], claim['status'])[ACTIONS[action]]:
        raise HTTPException(403, 'Действие недоступно для вашей роли или состояния претензии')
    if data['expectedVersion'] != claim['version']:
        raise HTTPException(409, 'Претензия изменилась. Обновите карточку перед новой отправкой')
    before = {key: claim[key] for key in ('status', 'version', 'resolution')}
    status = {'start': 'В работе', 'resolve': 'Решена', 'reopen': 'Открыта'}.get(action, claim['status'])
    resolution = text if action == 'resolve' else (None if action == 'reopen' else claim['resolution'])
    cur.execute('''UPDATE supply_claims SET status=%s,resolution=%s,
        resolved_at=CASE WHEN %s='resolve' THEN now() WHEN %s='reopen' THEN NULL ELSE resolved_at END,
        version=version+1,updated_at=now() WHERE id=%s''', (status, resolution, action, action, claim['id']))
    after = dict(status=status, version=claim['version']+1, resolution=resolution)
    cur.execute('''INSERT INTO supply_claim_events(claim_id,delivery_id,company_id,operation_id,
        actor_id,actor_name,action,text,before_state,after_state)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (claim['id'], claim['deliveryId'], actor['companyId'], operation_id, actor['id'], actor.get('name') or '',
         action, text, Json(before), Json(after)))
    return {'ok': True, 'id': claim['id'], 'eventId': cur.fetchone()['id']}
