"""Append-only shipment quantities and cumulative order completion."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID
from fastapi import HTTPException

PRECISION = Decimal('0.0001')


def quantity(value, *, stored_plan=False):
    try:
        result = Decimal(str(value if value is not None else 0))
        if stored_plan and result.is_finite():
            result = result.quantize(PRECISION, rounding=ROUND_HALF_UP)
        if not result.is_finite() or result < 0 or result > Decimal('9999999999.9999') or result != result.quantize(PRECISION):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(400, 'Количество должно быть неотрицательным числом с точностью до 4 знаков')


def line_key(item):
    return (str(item.get('materialName') or item.get('material_name') or item.get('name') or '').strip().lower(),
            str(item.get('unit') or '').strip().lower(),
            str(item.get('workPackage') or item.get('work_package') or 'Основная').strip().lower() or 'основная')


def order_lines(offer):
    raw = offer.get('items_json') or []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not raw:
        raw = [dict(materialName=offer.get('material_name'), quantity=offer.get('quantity'), unit=offer.get('unit'))]
    grouped = {}
    for item in raw:
        line = dict(materialName=item.get('materialName') or item.get('name') or '',
                    quantity=quantity(item.get('quantity'), stored_plan=True), unit=item.get('unit') or offer.get('unit') or 'шт',
                    workPackage=item.get('workPackage') or item.get('work_package') or offer.get('work_package') or 'Основная')
        key = line_key(line)
        if not key[0] or not line['quantity']:
            raise HTTPException(409, 'Состав заявки требует проверки')
        if key in grouped:
            grouped[key]['quantity'] += line['quantity']
        else:
            grouped[key] = line
    return list(grouped.values())


def shipment_lines(lines, previous, data):
    ordered = {line_key(line): line for line in lines}
    chosen = {}
    if 'shippedItems' in data:
        items = data['shippedItems']
        if not isinstance(items, list):
            raise HTTPException(400, 'Укажите позиции отгрузки')
        for item in items:
            if not isinstance(item, dict):
                raise HTTPException(400, 'Некорректная позиция отгрузки')
            key = line_key(item)
            if key not in ordered or key in chosen:
                raise HTTPException(400, 'Неизвестная или повторная позиция отгрузки')
            chosen[key] = quantity(item.get('shippedQuantity', item.get('quantity')))
    elif len(lines) == 1 and data.get('shippedQuantity') not in (None, ''):
        chosen[line_key(lines[0])] = quantity(data['shippedQuantity'])
    else:
        # Compatibility for older clients: their first dispatch meant all lines.
        chosen = {key: line['quantity'] for key, line in ordered.items()}
    shipped = {}
    for row in previous:
        key = line_key(row)
        if key not in ordered:
            raise HTTPException(409, 'Состав предыдущих отгрузок требует сверки с заявкой')
        shipped[key] = shipped.get(key, Decimal(0)) + quantity(row.get('shipped_quantity'))
    result = []
    for key, amount in chosen.items():
        remaining = quantity(ordered[key]['quantity']) - shipped.get(key, Decimal(0))
        if amount > remaining:
            raise HTTPException(409, f"Превышен остаток к отгрузке: {ordered[key]['materialName']} — осталось {remaining:g} {ordered[key]['unit']}")
        if amount:
            result.append(dict(ordered[key], shippedQuantity=amount))
    if not result:
        raise HTTPException(400, 'Укажите положительное количество хотя бы для одной позиции')
    return result


def submission_identity(lines, data):
    metadata = {key: str(data.get(key) or '').strip() for key in
                ('waybillNumber', 'waybillDate', 'vehicleNumber', 'driverName', 'documentUrl', 'photoUrl')}
    normalized = {'items': sorted([list(line_key(line)) + [format(line['shippedQuantity'], '.4f')] for line in lines]), **metadata}
    fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    token = data.get('requestId')
    if token:
        try:
            token = str(UUID(str(token)))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, 'Некорректный идентификатор отгрузки')
    else:
        # Legacy retries are content-addressed. A new explicit UUID is required
        # for a second intentionally identical batch.
        token = 'legacy:' + fingerprint
    return token, fingerprint


def flow_status(lines, rows):
    if any(row.get('status') == 'Проблема' for row in rows):
        return 'Проблема поставки'
    completed = [row for row in rows if row.get('status') == 'Принято']
    if not completed:
        return 'В пути'
    received = {}
    for row in completed:
        key = line_key(row)
        received[key] = received.get(key, Decimal(0)) + quantity(row.get('received_quantity'))
    if len(completed) == len(rows) and all(received.get(line_key(line), Decimal(0)) >= line['quantity'] for line in lines):
        return 'Поставлено'
    return 'Частично поставлено'


def quote_lines(items):
    """Preserve total cost when repeated order identities are grouped."""
    grouped = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = line_key(item)
        if key not in grouped:
            grouped[key] = dict(item)
            continue
        previous = grouped[key]
        old_qty, new_qty = quantity(previous.get('quantity'), stored_plan=True), quantity(item.get('quantity'), stored_plan=True)
        if not old_qty or not new_qty:
            raise HTTPException(409, 'Повторные позиции КП без количества требуют сверки стоимости')
        def total(line, count):
            price = Decimal(str(line.get('pricePerUnit') or 0))
            value = price * count if price > 0 else Decimal(str(line.get('totalPrice') or 0))
            if not value.is_finite() or value < 0:
                raise HTTPException(409, 'Стоимость КП требует сверки')
            return value
        amount = total(previous, old_qty) + total(item, new_qty)
        grouped[key] = dict(previous, quantity=old_qty + new_qty, totalPrice=amount, pricePerUnit=amount / (old_qty + new_qty))
    return grouped
