"""Reusable company sets; no request, stock or notification side effects."""
import json
import os

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from ..work_material_accounting.quantities import quantity

DIRECTORS = ('директор', 'зам_директора')
WRITERS = (*DIRECTORS, 'главный_инженер', 'снабженец', 'кладовщик', 'прораб', 'мастер', 'субподрядчик', 'бригадир')
READERS = (*WRITERS, 'бухгалтер')
ENVELOPE = {'requestId', 'expectedCompanyId', 'expectedActorId', 'materialAccountingVersion'}
COLUMNS = '''id,company_id AS "companyId",name,category,items_json,
    created_by AS "createdBy",created_by_id AS "createdById",created_at AS "createdAt",archived,version'''


def enabled():
    return os.environ.get('SUPPLY_TEMPLATES_ENABLED') == '1'


def text(value, maximum, required=False):
    if not isinstance(value, str) or '\x00' in value or len(value) > maximum or (required and not value.strip()):
        raise HTTPException(400, 'Проверьте название, единицы и длину текстовых полей шаблона')
    return value.strip()


def validate(data):
    if set(data) - (ENVELOPE | {'name', 'category', 'items'}):
        raise HTTPException(400, 'Переданы неизвестные поля шаблона')
    name = ' '.join(text(data.get('name'), 255, True).split())
    category = text(data.get('category', ''), 100)
    rows = data.get('items')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise HTTPException(400, 'Шаблон должен содержать от 1 до 200 строк')
    items = []
    for item in rows:
        if not isinstance(item, dict) or set(item) - {'materialName', 'quantity', 'unit', 'workPackage'}:
            raise HTTPException(400, 'Некорректная строка шаблона')
        items.append({'materialName': text(item.get('materialName'), 500, True),
                      'quantity': float(quantity(item.get('quantity'))),
                      'unit': text(item.get('unit'), 40, True),
                      'workPackage': text(item.get('workPackage', ''), 255)})
    return name, category, items


def card(row):
    result = dict(row)
    result['items'] = json.loads(result.pop('items_json'))
    return result


def load(cur, template_id, company_id):
    cur.execute('SELECT ' + COLUMNS + ' FROM supply_request_templates WHERE id=%s AND company_id=%s FOR UPDATE',
                (template_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Шаблон не найден в выбранной компании')
    return card(row)


def listing(cur, actor, legacy):
    cur.execute('SELECT ' + COLUMNS + ''' FROM supply_request_templates
        WHERE company_id=%s AND NOT archived ORDER BY name_key,id LIMIT 1001''', (actor['companyId'],))
    rows = [card(row) for row in cur.fetchall()]
    if legacy:
        return rows[:1000]
    return {'items': rows[:1000], 'truncated': len(rows) > 1000,
            'canCreate': enabled() and actor['role'] in WRITERS,
            'canArchive': enabled() and actor['role'] in DIRECTORS}


def command(cur, actor, template_id, data, operation_id):
    before = None
    if template_id is None:
        name, category, items = validate(data)
        cur.execute('''INSERT INTO supply_request_templates(company_id,name,name_key,category,items_json,created_by,created_by_id)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (actor['companyId'], name, name.casefold(), category, json.dumps(items, ensure_ascii=False), actor.get('name') or '', actor['id']))
        template_id = cur.fetchone()['id']
    else:
        if actor['role'] not in DIRECTORS:
            raise HTTPException(403, 'Архивировать шаблоны может руководитель компании')
        if set(data) - (ENVELOPE | {'expectedVersion'}):
            raise HTTPException(400, 'Переданы неизвестные поля архивирования')
        before = load(cur, template_id, actor['companyId'])
        if type(data.get('expectedVersion')) is not int or data['expectedVersion'] != before['version'] or before['archived']:
            raise HTTPException(409, 'Шаблон изменён или уже в архиве. Обновите список')
        cur.execute('''UPDATE supply_request_templates SET archived=TRUE,version=version+1,updated_at=now()
            WHERE id=%s AND company_id=%s''', (template_id, actor['companyId']))
    after = load(cur, template_id, actor['companyId'])
    cur.execute('''INSERT INTO supply_template_events(template_id,company_id,operation_id,actor_id,actor_name,
        action,reason,before_template,after_template) VALUES(%s,%s,%s,%s,%s,%s,'',%s,%s) RETURNING id''',
        (template_id, actor['companyId'], operation_id, actor['id'], actor.get('name') or '', 'archive' if before else 'create',
         Json(jsonable_encoder(before)) if before else None, Json(jsonable_encoder(after))))
    return {'ok': True, 'id': template_id, 'eventId': cur.fetchone()['id']}
