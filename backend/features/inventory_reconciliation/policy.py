import hashlib
import json
import os
from decimal import Decimal

from fastapi import HTTPException

from ..work_material_accounting.quantities import quantity

DIRECTORS = ('директор', 'зам_директора')
COUNTERS = (*DIRECTORS, 'кладовщик', 'прораб', 'главный_инженер')
READERS = (*COUNTERS, 'снабженец', 'бухгалтер')
STATUSES = {'draft': 'Черновик', 'submitted': 'На проверке', 'approved': 'Утверждена', 'cancelled': 'Отменена'}


def enabled():
    return os.environ.get('INVENTORY_RECONCILIATION_ENABLED') == '1'


def schema_present(cur):
    cur.execute("SELECT to_regclass('inventory_reconciliations') AS name")
    row = cur.fetchone()
    return bool(row.get('name') if isinstance(row, dict) else row[0])


def legacy_write_guard(cur, inventory_id=None):
    if enabled():
        raise HTTPException(409, 'Используйте новую сверку во вкладке «Инвентаризация»')
    if inventory_id and schema_present(cur):
        cur.execute('SELECT 1 FROM inventory_reconciliations WHERE inventory_id=%s', (inventory_id,))
        if cur.fetchone():
            raise HTTPException(409, 'Сохранённая сверка изменяется только через её операции')


def text(value, *, required=False):
    if value is None:
        value = ''
    if not isinstance(value, str) or len(value) > 4000 or (required and not value.strip()):
        raise HTTPException(400, 'Укажите причину длиной до 4000 символов')
    return value.strip()


def decimal_text(value):
    return format(Decimal(value).normalize(), 'f')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str, allow_nan=False).encode()).hexdigest()


def difference(row, count):
    actual = count.get('actual')
    return None if actual is None else decimal_text(Decimal(actual) - Decimal(row['expected']))


def validate_counts(rows, submitted):
    if not isinstance(submitted, list) or len(submitted) > len(rows):
        raise HTTPException(400, 'Нужен список строк пересчёта')
    available = {r['key']: r for r in rows}
    result = {}
    for value in submitted:
        if not isinstance(value, dict) or not isinstance(value.get('key'), str):
            raise HTTPException(400, 'Некорректная строка пересчёта')
        key = value['key']
        row = available.get(key)
        if row is None or key in result:
            raise HTTPException(400, 'Позиция отсутствует в снимке или повторяется')
        field = 'actual' if row['kind'] == 'material' else 'condition'
        if set(value) - {'key', field, 'reason'}:
            raise HTTPException(400, 'Учётные данные строки определяются сервером')
        count = {'reason': text(value.get('reason'))}
        if field == 'actual':
            raw = value.get('actual')
            count[field] = None if raw is None or raw == '' else decimal_text(quantity(raw, zero=True))
        else:
            condition = value.get('condition')
            if condition not in (None, '', 'as_recorded', 'missing', 'damaged', 'found'):
                raise HTTPException(400, 'Выберите результат проверки инструмента')
            count[field] = condition or None
        result[key] = count
    return result


def require_complete(rows, counts):
    for row in rows:
        count = counts.get(row['key'], {})
        if row['kind'] == 'material':
            if count.get('actual') is None:
                raise HTTPException(400, 'Укажите факт по каждой позиции; ноль вводится явно')
            changed = difference(row, count) != '0'
        else:
            if not count.get('condition'):
                raise HTTPException(400, 'Проверьте каждый инструмент')
            changed = count['condition'] != 'as_recorded'
        if changed:
            text(count.get('reason'), required=True)
