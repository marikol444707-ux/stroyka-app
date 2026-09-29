"""Physical tool states are separate from monetary responsibility."""
import hashlib
import json
import os

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

DIRECTORS = ('директор', 'зам_директора')
MANAGERS = (*DIRECTORS, 'прораб', 'главный_инженер', 'кладовщик', 'снабженец')
WORKERS = ('мастер', 'бригадир', 'субподрядчик')
READERS = (*MANAGERS, *WORKERS, 'бухгалтер', 'сметчик')


def enabled():
    return os.environ.get('TOOL_CUSTODY_ENABLED') == '1'


def schema_present(cur):
    cur.execute("SELECT to_regclass('public.tool_custody_events') IS NOT NULL AS present")
    row = cur.fetchone()
    return row['present'] if isinstance(row, dict) else row[0]


def state(tool):
    return hashlib.sha256(json.dumps(jsonable_encoder(tool), sort_keys=True,
                                    ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def identifier(value, label):
    if type(value) is not int or value <= 0:
        raise HTTPException(400, 'Выберите ' + label)
    return value


def text(data, field='reason', required=True):
    value = data.get(field, '')
    if not isinstance(value, str) or len(value) > 4000 or (required and not value.strip()):
        raise HTTPException(400, 'Заполните основание, причину и подтверждающие документы')
    return value.strip()


def needs_reconciliation(tool):
    return not tool.get('custody_version') and (tool['status'] == 'На объекте' or
        (tool['status'] == 'У мастера' and (not tool.get('master_id') or not tool.get('project_id'))))


def next_status(tool, action, condition, role, reconciled_status=None):
    status = tool['status']
    if action in ('write_off', 'archive', 'reconcile') and role not in DIRECTORS:
        raise HTTPException(403, 'Списание и архивирование подтверждает директор')
    if action == 'reconcile' and needs_reconciliation(tool) and reconciled_status in ('На складе', 'У мастера'):
        return reconciled_status
    if action == 'issue' and status == 'На складе' and not tool.get('master_id') and not tool.get('master_name'):
        return 'У мастера'
    if action == 'return' and status == 'У мастера':
        if condition in ('good', 'damaged', 'lost'):
            return {'good': 'На складе', 'damaged': 'На ремонте', 'lost': 'Утерян'}[condition]
        raise HTTPException(400, 'Укажите состояние при возврате')
    if action == 'repair' and status == 'На ремонте':
        return 'На складе'
    if action == 'recover' and status == 'Утерян' and condition in ('good', 'damaged'):
        return 'На складе' if condition == 'good' else 'На ремонте'
    if action == 'write_off' and status in ('На складе', 'На ремонте', 'Утерян'):
        return 'Списан'
    if action == 'archive' and status in ('На складе', 'Списан'):
        return 'В архиве'
    raise HTTPException(409, 'Операция недоступна в текущем состоянии инструмента. Обновите карточку')
