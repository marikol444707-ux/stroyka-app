"""Warehouse address cards; these commands never adjust material balances."""
import os

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

DIRECTORS = ('директор', 'зам_директора')
WRITERS = (*DIRECTORS, 'главный_инженер', 'кладовщик', 'снабженец')
READERS = (*WRITERS, 'бухгалтер')
FIELDS = {'name': 255, 'city': 255, 'address': 2000, 'notes': 4000}
COLUMNS = '''id,company_id AS "companyId",name,city,address,notes,archived,version,updated_at AS "updatedAt"'''


def enabled():
    return os.environ.get('WAREHOUSE_DIRECTORY_ENABLED') == '1'


def text(value, maximum, required=False):
    if not isinstance(value, str) or '\x00' in value or len(value) > maximum:
        raise HTTPException(400, 'Проверьте тип и длину текстовых полей')
    value = value.strip()
    if required and not value:
        raise HTTPException(400, 'Укажите название склада или основание действия')
    return value


def capabilities(actor):
    return {'canManage': enabled() and actor['role'] in WRITERS,
            'canArchive': enabled() and actor['role'] in DIRECTORS}


def load(cur, warehouse_id, company_id):
    cur.execute('SELECT ' + COLUMNS + ' FROM warehouses WHERE id=%s AND company_id=%s FOR UPDATE',
                (warehouse_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Склад не найден в выбранной компании')
    return dict(row)


def listing(cur, actor, legacy=False):
    cur.execute('SELECT ' + COLUMNS + ' FROM warehouses WHERE company_id=%s'
                + (' AND NOT archived' if legacy else '') + ' ORDER BY archived,lower(name),id LIMIT 1001',
                (actor['companyId'],))
    rows = [dict(r) for r in cur.fetchall()]
    if legacy:
        return rows[:1000]
    return {'items': rows[:1000], 'truncated': len(rows) > 1000, **capabilities(actor)}


def detail(cur, card, actor):
    cur.execute('''SELECT id,action,reason,actor_name AS "actorName",created_at AS "createdAt",
        before_card AS "before",after_card AS "after" FROM warehouse_directory_events
        WHERE warehouse_id=%s AND company_id=%s ORDER BY id DESC LIMIT 201''',
                (card['id'], actor['companyId']))
    rows = [dict(r) for r in cur.fetchall()]
    return {'warehouse': card, 'history': rows[:200], 'historyTruncated': len(rows) > 200, **capabilities(actor)}


def command(cur, actor, card, data, operation_id):
    action = data.get('action')
    allowed = {'action', 'requestId', 'expectedCompanyId', 'expectedActorId', 'materialAccountingVersion'}
    if card is None:
        if action != 'create':
            raise HTTPException(400, 'Для новой карточки нужно действие создания')
        allowed |= FIELDS.keys()
    else:
        allowed |= {'expectedVersion', 'reason'}
        if action == 'update':
            allowed |= FIELDS.keys()
        elif action not in ('archive', 'restore'):
            raise HTTPException(400, 'Неизвестное действие с карточкой склада')
        if type(data.get('expectedVersion')) is not int or data['expectedVersion'] != card['version']:
            raise HTTPException(409, 'Карточка изменена другим пользователем. Сохраните нужный текст, закройте форму, обновите каталог и откройте карточку заново')
    if set(data) - allowed:
        raise HTTPException(400, 'Переданы неизвестные поля карточки склада')
    reason = text(data.get('reason', ''), 2000, required=action in ('archive', 'restore'))
    if action in ('archive', 'restore') and actor['role'] not in DIRECTORS:
        raise HTTPException(403, 'Архивом складов управляет директор')
    if action in ('create', 'update'):
        if card and card['archived']:
            raise HTTPException(409, 'Сначала восстановите склад из архива')
        if card and not FIELDS.keys() <= data.keys():
            raise HTTPException(400, 'Передайте название, город, адрес и заметки полностью')
        values = {key: text(data.get(key, ''), maximum, required=key == 'name') for key, maximum in FIELDS.items()}
        values['name'] = ' '.join(values['name'].split())
        # PostgreSQL lower() may leave Cyrillic unchanged in C-locale databases.
        name_key = values['name'].casefold()
        if card is None:
            cur.execute('''INSERT INTO warehouses(company_id,name,city,address,notes,name_key)
                VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''', (actor['companyId'], *values.values(), name_key))
            warehouse_id = cur.fetchone()['id']
        else:
            warehouse_id = card['id']
            cur.execute('''UPDATE warehouses SET name=%s,city=%s,address=%s,notes=%s,name_key=%s,
                version=version+1,updated_at=now() WHERE id=%s AND company_id=%s''',
                        (*values.values(), name_key, warehouse_id, actor['companyId']))
    else:
        archive = action == 'archive'
        if card['archived'] == archive:
            raise HTTPException(409, 'Склад уже находится в этом состоянии')
        warehouse_id = card['id']
        cur.execute('''UPDATE warehouses SET archived=%s,version=version+1,updated_at=now()
            WHERE id=%s AND company_id=%s''', (archive, warehouse_id, actor['companyId']))
    after = load(cur, warehouse_id, actor['companyId'])
    cur.execute('''INSERT INTO warehouse_directory_events(warehouse_id,company_id,operation_id,
        actor_id,actor_name,action,reason,before_card,after_card) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (warehouse_id, actor['companyId'], operation_id, actor['id'], actor.get('name') or '', action, reason,
         Json(jsonable_encoder(card)) if card else None, Json(jsonable_encoder(after))))
    return {'ok': True, 'warehouseId': warehouse_id, 'eventId': cur.fetchone()['id']}
