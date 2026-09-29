"""An approved count creates separate stock history, never rewrites receipts."""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from psycopg2.extras import Json

from . import policy
from ..warehouse_distribution.models import MAIN
from ..warehouse_distribution.service import lock_sources
from ..work_material_accounting.quantities import quantity


def allocations(rows, counts, submitted):
    if not isinstance(submitted, list):
        raise HTTPException(400, 'Укажите распределение недостачи по партиям')
    needed = {r['key']: r for r in rows if r['kind'] == 'material' and r['stockTable'] == 'warehouse_main'
              and Decimal(policy.difference(r, counts[r['key']])) < 0}
    result = {}
    for data in submitted:
        if not isinstance(data, dict) or set(data) != {'key', 'untrackedQuantity', 'lots'}:
            raise HTTPException(400, 'Некорректное распределение недостачи')
        key = data['key']
        if not isinstance(key, str) or key not in needed or key in result:
            raise HTTPException(400, 'Распределение относится к другой позиции или повторяется')
        row = needed[key]
        untracked = quantity(data['untrackedQuantity'], zero=True)
        if untracked > Decimal(row['untrackedQuantity']):
            raise HTTPException(409, 'Недостаточно остатка без привязки к партии')
        if not isinstance(data['lots'], list):
            raise HTTPException(400, 'Нужен список партий')
        allowed = {l['lotId']: l for l in row['lots']}
        used = {}
        seen = set()
        for lot in data['lots']:
            if not isinstance(lot, dict) or set(lot) != {'lotId', 'quantity'} or type(lot['lotId']) is not int:
                raise HTTPException(400, 'Некорректная партия недостачи')
            lot_id = lot['lotId']
            if lot_id not in allowed or lot_id in seen:
                raise HTTPException(400, 'Партия отсутствует в снимке или повторяется')
            seen.add(lot_id)
            amount = quantity(lot['quantity'], zero=True)
            if amount > Decimal(allowed[lot_id]['quantity']):
                raise HTTPException(409, 'Недостача превышает доступное количество партии')
            if amount:
                used[lot_id] = policy.decimal_text(amount)
        expected = -Decimal(policy.difference(row, counts[key]))
        if untracked + sum((Decimal(v) for v in used.values()), Decimal(0)) != expected:
            raise HTTPException(400, 'Сумма по партиям и остатку без партии должна совпадать с недостачей')
        result[key] = {'untrackedQuantity': policy.decimal_text(untracked), 'lots': used}
    if set(result) != set(needed):
        raise HTTPException(400, 'Распределите каждую недостачу основного склада')
    return result


def apply(cur, session, actor, event_id, deductions):
    company_id = actor['companyId']
    location = session['snapshot']['project']
    for row in session['snapshot']['rows']:
        if row['kind'] != 'material':
            continue
        count = session['counts'][row['key']]
        delta = Decimal(policy.difference(row, count))
        if not delta:
            continue
        amount = abs(delta)
        reason = count['reason']
        changes = deductions.get(row['key'], {'untrackedQuantity': '0', 'lots': {}})
        if changes['lots']:
            lots, _ = lock_sources(cur, company_id, [int(k) for k in changes['lots']], validate=True)
            for lot_id, raw in changes['lots'].items():
                lot = lots[int(lot_id)]
                if Decimal(lot['available_quantity']) < Decimal(raw):
                    raise HTTPException(409, 'Остаток партии изменился; требуется новая сверка')
                cur.execute('UPDATE warehouse_receipt_lots SET available_quantity=available_quantity-%s WHERE id=%s', (raw, lot_id))
        table = row['stockTable']
        assert table in ('materials', 'warehouse_main')
        cur.execute(f'UPDATE {table} SET quantity=%s WHERE id=%s AND company_id=%s RETURNING quantity',
                    (count['actual'], row['stockId'], company_id))
        updated = cur.fetchone()
        if not updated or Decimal(str(updated['quantity'])) != Decimal(count['actual']):
            raise HTTPException(409, 'Склад не может сохранить точное количество')
        source, target = (location, 'Инвентаризация') if delta < 0 else ('Инвентаризация', location)
        cur.execute('''INSERT INTO warehouse_movements(company_id,material_name,from_location,to_location,
            quantity,unit,work_package,date,created_by,notes)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (company_id, row['name'], source, target, amount, row['unit'], row['package'],
             date.today().isoformat(), actor.get('name') or '', f'Инвентаризация №{session["inventory_id"]}: {reason}'))
        movement_id = cur.fetchone()['id']
        for lot_id, raw in changes['lots'].items():
            cur.execute('''INSERT INTO warehouse_lot_movements(lot_id,company_id,warehouse_movement_id,
                operation_type,quantity,unit,from_location,to_location,created_by)
                VALUES(%s,%s,%s,'inventory_shortage',%s,%s,%s,%s,%s)''',
                (lot_id, company_id, movement_id, raw, row['unit'], MAIN, 'Инвентаризация', actor.get('name') or ''))
        cur.execute('''INSERT INTO warehouse_history(company_id,material,type,quantity,unit,date,project,
            issued_to,issued_by,work_package,source_type,source_id)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'inventory_reconciliation',%s) RETURNING id''',
            (company_id, row['name'], 'инвентаризация: недостача' if delta < 0 else 'инвентаризация: излишек',
             amount, row['unit'], date.today().isoformat(), location, '', actor.get('name') or '',
             row['package'], session['inventory_id']))
        history_id = cur.fetchone()['id']
        cur.execute('''INSERT INTO inventory_stock_adjustments(inventory_id,company_id,event_id,row_key,
            stock_table,stock_id,before_quantity,after_quantity,reason,lot_changes,history_id,movement_id)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (session['inventory_id'], company_id, event_id, row['key'], table, row['stockId'],
             row['expected'], count['actual'], reason, Json(changes), history_id, movement_id))
