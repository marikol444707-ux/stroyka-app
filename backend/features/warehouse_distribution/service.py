"""Transaction-scoped distribution commands. No connection, commit, DDL or supplier writes."""
from datetime import date
from decimal import Decimal
import json

from fastapi import HTTPException
from psycopg2.extras import Json

from .models import MAIN, conflict, decimal_text, payload_hash, validate_source
from ..quality_journals import distribution_receipt as owned_quality


def json_value(value):
    """Stable JSON persisted for idempotent replay, without float quantity loss."""
    return json.loads(json.dumps(value, default=lambda x: decimal_text(x) if isinstance(x, Decimal) else str(x)))


def begin_operation(cur, data, actor, allocation_id=None, *, kind=None, identity=None):
    kind = kind or ('issue' if allocation_id is None else 'return')
    digest = payload_hash(data, identity or (kind if allocation_id is None else f'return:{allocation_id}'))
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1464095564, data.companyId))
    cur.execute('''SELECT id,payload_hash,result FROM warehouse_distribution_operations
        WHERE company_id=%s AND request_id=%s''', (data.companyId, str(data.requestId)))
    previous = cur.fetchone()
    if previous:
        if previous['payload_hash'] != digest:
            conflict('requestId уже использован с другим содержимым')
        if previous['result'] is None:
            conflict('Операция не завершена; повторите запрос с тем же requestId')
        return previous['id'], previous['result']
    # Coarse by design: legacy INSERT/UPDATE acquire conflicting RowExclusive locks.
    # This protects missing-target insertion as well as duplicate-row validation.
    cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
    cur.execute('''INSERT INTO warehouse_distribution_operations
        (company_id,request_id,kind,payload_hash,reason,created_by_id,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (data.companyId, str(data.requestId), kind, digest, data.reason,
         actor.get('id'), actor.get('name') or ''))
    return cur.fetchone()['id'], None


def finish_operation(cur, operation_id, result):
    result = json_value(result)
    cur.execute('UPDATE warehouse_distribution_operations SET result=%s WHERE id=%s',
                (Json(result), operation_id))
    return result


def lock_sources(cur, company_id, lot_ids, *, validate=True):
    ids = sorted(set(lot_ids))
    cur.execute('''SELECT id,warehouse_invoice_id FROM warehouse_receipt_lots
        WHERE company_id=%s AND id=ANY(%s) ORDER BY id''', (company_id, ids))
    references = cur.fetchall()
    if len(references) != len(ids):
        raise HTTPException(404, 'Партия не найдена в выбранной компании')
    receipt_ids = sorted({r['warehouse_invoice_id'] for r in references})
    cur.execute('''SELECT * FROM warehouse_invoices WHERE company_id=%s AND id=ANY(%s)
        ORDER BY id FOR UPDATE''', (company_id, receipt_ids))
    receipts = {r['id']: r for r in cur.fetchall()}
    cur.execute('''SELECT * FROM warehouse_receipt_lots WHERE company_id=%s AND id=ANY(%s)
        ORDER BY id FOR UPDATE''', (company_id, ids))
    lots = {r['id']: r for r in cur.fetchall()}
    if len(lots) != len(ids):
        conflict('Партия изменена; повторите запрос')
    for lot in lots.values():
        receipt = receipts.get(lot['warehouse_invoice_id'])
        if receipt is None:
            conflict('Исходная накладная партии недоступна')
        if validate:
            validate_source(lot, receipt)
    return lots, receipts


def lock_projects(cur, company_id, project_ids):
    ids = sorted(set(project_ids))
    cur.execute('''SELECT id,name FROM projects WHERE company_id=%s AND id=ANY(%s)
        ORDER BY id FOR UPDATE''', (company_id, ids))
    projects = {r['id']: r['name'] for r in cur.fetchall()}
    if len(projects) != len(ids):
        raise HTTPException(404, 'Объект не найден в выбранной компании')
    for name in projects.values():
        if not name or name != name.strip() or name == MAIN:
            conflict('Неоднозначное имя объекта')
        cur.execute('''SELECT id FROM projects WHERE company_id=%s AND lower(btrim(name))=lower(btrim(%s))
            ORDER BY id''', (company_id, name))
        if len(cur.fetchall()) != 1:
            conflict('В компании есть объекты с одинаковыми именами')
    return projects


def normalized_unit_sql(column='unit'):
    # Matches the shared movement helper's SQL key, not a guessed conversion.
    assert column in ('unit', 'a.unit', 'OLD.unit', '%s')
    return f"lower(replace(replace(replace(replace(trim(coalesce({column},'')),'²','2'),'³','3'),'.',''),' ',''))"


def check_stock_keys(cur, company_id, material, unit, project, package):
    for table, extra, values in (
        ('warehouse_main', '', []),
        ('materials', " AND project=%s AND coalesce(nullif(work_package,''),'Основная')=%s", [project, package]),
    ):
        cur.execute(f'''SELECT id FROM {table} WHERE company_id=%s AND lower(name)=lower(%s)
            AND {normalized_unit_sql()}={normalized_unit_sql('%s')} {extra} ORDER BY id FOR UPDATE''',
            [company_id, material, unit, *values])
        if len(cur.fetchall()) > 1:
            conflict('Неоднозначные строки агрегированного складского остатка')


def stock_snapshot(cur, company_id, lot, project):
    """Table locks are held. Capture quantities before the float-based helper runs."""
    result = {}
    for table, extra, args in (
        ('warehouse_main', '', []), ('materials', ' AND project=%s', [project]),
    ):
        package = "coalesce(nullif(work_package,''),'Основная')" if table == 'materials' else "''"
        cur.execute(f'''SELECT id,quantity,{package} AS package FROM {table}
            WHERE company_id=%s AND lower(name)=lower(%s)
              AND {normalized_unit_sql()}={normalized_unit_sql('%s')} {extra}
            ORDER BY id FOR UPDATE''', [company_id, lot['material_name'], lot['unit'], *args])
        result[table] = cur.fetchall()
    return result


def exact_stock_quantity(raw):
    """Reject legacy drift, never round it away. Only exact six-place values enter."""
    value = Decimal(str(raw if raw is not None else 0))
    if (not value.is_finite() or value < 0 or value >= Decimal('100000000')
            or value != value.quantize(Decimal('0.000001'))
            or Decimal(str(float(value))) != value):
        conflict('Остаток агрегированного склада требует сверки точности; автоматическое округление запрещено')
    return value


def project_stock_delta(cur, before, after, package, quantity, returning):
    """Project the known exact delta, not rounded float results, onto legacy stock."""
    for table in ('warehouse_main', 'materials'):
        old = [r for r in before[table] if table == 'warehouse_main' or r['package'] == package]
        new = [r for r in after[table] if table == 'warehouse_main' or r['package'] == package]
        if len(old) > 1 or len(new) != 1:
            conflict('Неоднозначный остаток при точном обновлении склада')
        base = exact_stock_quantity(old[0]['quantity']) if old else Decimal(0)
        delta = quantity if (table == 'warehouse_main') == returning else -quantity
        projected = exact_stock_quantity(base + delta)
        if old and old[0]['id'] != new[0]['id']:
            conflict('Строка складского остатка изменена')
        cur.execute(f'UPDATE {table} SET quantity=%s WHERE id=%s RETURNING quantity', (projected, new[0]['id']))
        stored = cur.fetchone()
        if not stored or Decimal(str(stored['quantity'])) != projected:
            conflict('Тип складского остатка не сохраняет точность операции')


def apply(cur, deps, company_id, actor, lot, receipt, project_name, quantity, reason, package='Основная', returning=False):
    source, target = (project_name, MAIN) if returning else (MAIN, project_name)
    check_stock_keys(cur, company_id, lot['material_name'], lot['unit'], project_name, package)
    before = stock_snapshot(cur, company_id, lot, project_name)
    source_table = 'materials' if returning else 'warehouse_main'
    for row in before[source_table]:
        if source_table == 'warehouse_main' or row['package'] == package:
            exact_stock_quantity(row['quantity'])
    model = deps['movement_model'](
        materialName=lot['material_name'], fromLocation=source, toLocation=target,
        quantity=float(quantity), unit=lot['unit'], workPackage=package,
        date=date.today().isoformat(), createdBy=actor.get('name') or '', notes=reason,
        invoiceId=None, invoiceLineIndex=None)
    movement = deps['apply_movement'](cur, model, company_id, actor)
    resolved_package = movement.get('workPackage') or 'Основная'
    # The helper can resolve the estimate package during issue. A conflict here
    # rolls back its stock changes too, including any duplicate target update.
    check_stock_keys(cur, company_id, lot['material_name'], lot['unit'], project_name, resolved_package)
    if returning and resolved_package != package:
        conflict('Раздел склада объекта изменён')
    if (movement.get('unit') != lot['unit'] or movement.get('materialName') != lot['material_name']
            or Decimal(str(movement['quantity'])) != quantity):
        conflict('Нормализация перемещения не совпадает с партией')
    after = stock_snapshot(cur, company_id, lot, project_name)
    project_stock_delta(cur, before, after, resolved_package, quantity, returning)
    cur.execute('''UPDATE warehouse_movements SET source_invoice_id=%s,source_invoice_line_index=%s
        WHERE id=%s AND company_id=%s''',
        (receipt['id'], lot['invoice_line_index'], movement['id'], company_id))
    if cur.rowcount != 1:
        conflict('Движение не найдено в выбранной компании')
    cur.execute('''UPDATE warehouse_history SET source_invoice_id=%s,source_invoice_line_index=%s
        WHERE source_type='warehouse_movement' AND source_id=%s AND company_id=%s''',
        (receipt['id'], lot['invoice_line_index'], movement['id'], company_id))
    if cur.rowcount != 2:
        conflict('Неполная история перемещения')
    movement.update(sourceInvoiceId=receipt['id'], sourceInvoiceLineIndex=lot['invoice_line_index'])
    return movement


def journal(cur, company_id, actor, lot, movement, quantity, original=None):
    returning = original is not None
    delta = quantity if returning else -quantity
    cur.execute('''UPDATE warehouse_receipt_lots SET available_quantity=available_quantity+%s
        WHERE id=%s AND company_id=%s AND status='active'
          AND available_quantity+%s BETWEEN 0 AND received_quantity RETURNING available_quantity''',
        (delta, lot['id'], company_id, delta))
    remaining = cur.fetchone()
    if not remaining:
        conflict('Недостаточный или изменённый остаток партии')
    lot['available_quantity'] = remaining['available_quantity']
    cur.execute('''INSERT INTO warehouse_lot_movements
        (lot_id,company_id,warehouse_movement_id,operation_type,quantity,unit,
         from_location,to_location,created_by,reversal_of_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (lot['id'], company_id, movement['id'],
         'distribution_return' if returning else 'warehouse_movement_out', quantity,
         lot['unit'], movement['fromLocation'], movement['toLocation'], actor.get('name') or '', original))
    return cur.fetchone()['id']


def allocation_views(cur, rows):
    if not rows:
        return []
    cur.execute('''SELECT id,allocation_id,quantity,movement_id,reason,created_by,created_at
        FROM warehouse_distribution_returns WHERE company_id=%s AND allocation_id=ANY(%s) ORDER BY id''',
        (rows[0]['company_id'], [row['id'] for row in rows]))
    histories = {}
    for r in cur.fetchall():
        histories.setdefault(r['allocation_id'], []).append(dict(
            id=r['id'], quantity=decimal_text(r['quantity']), movementId=r['movement_id'],
            reason=r['reason'], createdBy=r['created_by'], createdAt=str(r['created_at'])))
    return [serialize_allocation(row, histories.get(row['id'], [])) for row in rows]


def allocation_view(cur, row):
    return allocation_views(cur, [row])[0]


def serialize_allocation(row, history):
    return dict(id=row['id'], companyId=row['company_id'], warehouseInvoiceId=row['receipt_id'],
                invoiceNumber=row['receipt_number'], lotId=row['lot_id'], invoiceLineIndex=row['invoice_line_index'],
                projectId=row['project_id'], projectName=row['project_name'], materialName=row['material_name'],
                unit=row['unit'], workPackage=row['work_package'], quantity=decimal_text(row['quantity']),
                returnedQuantity=decimal_text(row['returned_quantity']),
                transferredQuantity=decimal_text(row.get('transferred_quantity', 0)),
                netQuantity=decimal_text(remaining_entitlement(row)), movementId=row['movement_id'],
                reason=row['reason'], createdBy=row['created_by'], createdAt=str(row['created_at']), returns=history)


def remaining_entitlement(allocation):
    return allocation['quantity'] - allocation['returned_quantity'] - allocation.get('transferred_quantity', 0)


def issue(cur, deps, data, actor):
    operation_id, replay = begin_operation(cur, data, actor)
    if replay is not None:
        owned_quality.verify_distribution_replay(cur, deps, operation_id, data.companyId, replay)
        return replay
    lots, receipts = lock_sources(cur, data.companyId, [r.lotId for r in data.rows])
    projects = lock_projects(cur, data.companyId, [r.projectId for r in data.rows])
    totals = {}
    for row in data.rows:
        totals[row.lotId] = totals.get(row.lotId, Decimal(0)) + row.quantity
    for lot_id, quantity in totals.items():
        if quantity > lots[lot_id]['available_quantity']:
            conflict('Недостаточный остаток партии для всех строк запроса')
    allocations = []
    quality_proofs = []
    for row in data.rows:
        lot = lots[row.lotId]
        receipt = receipts[lot['warehouse_invoice_id']]
        movement = apply(cur, deps, data.companyId, actor, lot, receipt,
                         projects[row.projectId], row.quantity, data.reason)
        lot_movement_id = journal(cur, data.companyId, actor, lot, movement, row.quantity)
        cur.execute('''INSERT INTO warehouse_distribution_allocations
            (company_id,operation_id,lot_id,receipt_id,receipt_number,invoice_line_index,project_id,
             project_name,material_name,unit,work_package,quantity,movement_id,lot_movement_id,
             movement_snapshot,reason,created_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (data.companyId, operation_id, lot['id'], receipt['id'], str(receipt.get('number') or ''),
             lot['invoice_line_index'], row.projectId, projects[row.projectId], lot['material_name'], lot['unit'],
             movement.get('workPackage') or 'Основная', row.quantity, movement['id'], lot_movement_id,
             Json(json_value(movement)), data.reason, actor.get('name') or ''))
        allocation = cur.fetchone()
        proof = owned_quality.create_distribution_quality(cur, deps, allocation)
        if proof is not None:
            quality_proofs.append(proof)
        allocations.append(allocation_view(cur, allocation))
    result = dict(ok=True, operationId=operation_id, requestId=str(data.requestId), items=allocations)
    if quality_proofs:
        result['ownedQuality'] = quality_proofs
    return finish_operation(cur, operation_id, result)


def physical_return(cur, deps, allocation_id, data, actor):
    operation_id, replay = begin_operation(cur, data, actor, allocation_id)
    if replay is not None:
        owned_quality.verify_distribution_replay(cur, deps, operation_id, data.companyId, replay, allocation_id)
        return replay
    cur.execute('''SELECT * FROM warehouse_distribution_allocations WHERE id=%s AND company_id=%s''',
                (allocation_id, data.companyId))
    allocation = cur.fetchone()
    if not allocation:
        raise HTTPException(404, 'Распределение не найдено в выбранной компании')
    lots, receipts = lock_sources(cur, data.companyId, [allocation['lot_id']])
    projects = lock_projects(cur, data.companyId, [allocation['project_id']])
    cur.execute('''SELECT * FROM warehouse_distribution_allocations WHERE id=%s AND company_id=%s FOR UPDATE''',
                (allocation_id, data.companyId))
    allocation = cur.fetchone()
    if projects[allocation['project_id']] != allocation['project_name']:
        conflict('Объект переименован; возврат по старому складскому имени запрещён')
    if data.quantity > remaining_entitlement(allocation):
        conflict('Возврат превышает невозвращённое распределение')
    lot = lots[allocation['lot_id']]
    if (lot['warehouse_invoice_id'] != allocation['receipt_id']
            or lot['invoice_line_index'] != allocation['invoice_line_index']
            or lot['material_name'] != allocation['material_name'] or lot['unit'] != allocation['unit']):
        conflict('Идентичность исходной партии изменена')
    quality_proof = owned_quality.prepare_distribution_return(cur, deps, allocation)
    movement = apply(cur, deps, data.companyId, actor, lot, receipts[allocation['receipt_id']],
                     allocation['project_name'], data.quantity, data.reason,
                     package=allocation['work_package'], returning=True)
    journal_id = journal(cur, data.companyId, actor, lot, movement, data.quantity, allocation['lot_movement_id'])
    cur.execute('''INSERT INTO warehouse_distribution_returns
        (company_id,allocation_id,operation_id,quantity,movement_id,lot_movement_id,movement_snapshot,reason,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (data.companyId, allocation_id, operation_id, data.quantity, movement['id'], journal_id,
         Json(json_value(movement)), data.reason, actor.get('name') or ''))
    event = cur.fetchone()
    quality_proof = owned_quality.create_distribution_return_quality(cur, deps, allocation, event, quality_proof)
    cur.execute('''UPDATE warehouse_distribution_allocations SET returned_quantity=returned_quantity+%s
        WHERE id=%s AND company_id=%s RETURNING *''', (data.quantity, allocation_id, data.companyId))
    result = allocation_view(cur, cur.fetchone())
    response = dict(ok=True, operationId=operation_id, requestId=str(data.requestId), item=result)
    if quality_proof is not None:
        response['ownedQuality'] = [quality_proof]
    return finish_operation(cur, operation_id, response)
