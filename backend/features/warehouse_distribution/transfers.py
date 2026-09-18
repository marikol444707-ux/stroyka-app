"""Two-stage attested custody. Caller owns authorization, locks and transaction.

No supplier/financial writes, root-lot balance changes or synthetic warehouse legs.
"""
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from psycopg2.extras import Json

from .models import conflict, decimal_text
from . import service
from ..quality_journals import distribution_receipt as quality

TRANSIT = 'В пути'


def require_schema(cur):
    cur.execute("SELECT to_regclass('warehouse_distribution_transfers') AS relation")
    if not cur.fetchone()['relation']:
        conflict('Межобъектная передача временно недоступна. Требуется обновление сервера.')


def load_transfer(cur, company_id, transfer_id):
    cur.execute('''SELECT * FROM warehouse_distribution_transfers
        WHERE company_id=%s AND id=%s FOR UPDATE''', (company_id, transfer_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Передача не найдена в выбранной компании')
    return row


def source(cur, company_id, allocation_id, *, historical=False):
    cur.execute('SELECT * FROM warehouse_distribution_allocations WHERE id=%s AND company_id=%s',
                (allocation_id, company_id))
    allocation = cur.fetchone()
    if not allocation:
        raise HTTPException(404, 'Распределение не найдено в выбранной компании')
    # Replays verify immutable custody evidence, not eligibility for a new write.
    # A fully returned root may legitimately be cancelled after the first command.
    lots, receipts = service.lock_sources(cur, company_id, [allocation['lot_id']], validate=not historical)
    projects = service.lock_projects(cur, company_id, [allocation['project_id']])
    allocation = quality.load_allocation(cur, allocation_id, company_id)
    lot = lots[allocation['lot_id']]
    if (projects[allocation['project_id']] != allocation['project_name']
            or lot['warehouse_invoice_id'] != allocation['receipt_id']
            or lot['invoice_line_index'] != allocation['invoice_line_index']
            or lot['material_name'] != allocation['material_name'] or lot['unit'] != allocation['unit']):
        conflict('Идентичность исходного распределения изменена')
    return allocation, receipts[allocation['receipt_id']]


def stock_leg(cur, a, project, qty, receiving, metadata=None):
    """Apply exactly one object stock delta; no estimate/package reassignment."""
    cur.execute(f'''SELECT * FROM materials WHERE company_id=%s AND project=%s
        AND lower(name)=lower(%s) AND {service.normalized_unit_sql()}={service.normalized_unit_sql('%s')}
        AND coalesce(nullif(work_package,''),'Основная')=%s ORDER BY id FOR UPDATE''',
        (a['company_id'], project, a['material_name'], a['unit'], a['work_package']))
    rows = cur.fetchall()
    if len(rows)>1 or (not receiving and not rows):
        conflict('Неоднозначный или отсутствующий остаток объекта')
    old = service.exact_stock_quantity(rows[0]['quantity']) if rows else Decimal(0)
    result = service.exact_stock_quantity(old + (qty if receiving else -qty))
    if not receiving:
        metadata = dict(price=str(rows[0].get('price') or 0),category=rows[0].get('category') or '')
    price = Decimal(metadata['price'])
    if not price.is_finite():
        conflict('Цена складской строки требует сверки')
    if rows:
        if receiving:
            cur.execute('''UPDATE materials SET quantity=%s,
                unit=%s,price=CASE WHEN %s>0 THEN %s ELSE price END,
                category=coalesce(nullif(%s,''),category) WHERE id=%s RETURNING quantity''',
                (result,a['unit'],price,price,metadata['category'],rows[0]['id']))
        else:
            cur.execute('UPDATE materials SET quantity=%s WHERE id=%s RETURNING quantity', (result, rows[0]['id']))
    else:
        cur.execute('''INSERT INTO materials(company_id,name,unit,quantity,project,work_package,price,category,min_quantity)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,0) RETURNING quantity''',
            (a['company_id'],a['material_name'],a['unit'],result,project,a['work_package'],price,metadata['category']))
    if Decimal(str(cur.fetchone()['quantity'])) != result:
        conflict('Тип складского остатка не сохраняет точность операции')
    return metadata


def check_transit_location(cur, company_id):
    cur.execute('SELECT id FROM projects WHERE company_id=%s AND lower(btrim(name))=lower(%s)',
                (company_id,TRANSIT))
    if cur.fetchone():
        conflict('Название объекта «В пути» зарезервировано для межобъектной передачи')


def movement_leg(cur, a, project, qty, actor, reason, receiving):
    origin, destination = (TRANSIT, project) if receiving else (project, TRANSIT)
    kind = 'distribution_transfer_receipt' if receiving else 'distribution_dispatch'
    today = date.today().isoformat()
    cur.execute('''INSERT INTO warehouse_movements(material_name,from_location,to_location,quantity,unit,
        work_package,date,created_by,notes,company_id,source_invoice_id,source_invoice_line_index)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,quantity''',
        (a['material_name'],origin,destination,qty,a['unit'],a['work_package'],today,
         actor.get('name') or '',reason,a['company_id'],a['receipt_id'],a['invoice_line_index']))
    movement = cur.fetchone()
    if Decimal(str(movement['quantity'])) != qty:
        conflict('История перемещения не сохраняет точность')
    cur.execute('''INSERT INTO warehouse_lot_movements(lot_id,company_id,warehouse_movement_id,operation_type,
        quantity,unit,from_location,to_location,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (a['lot_id'],a['company_id'],movement['id'],kind,qty,a['unit'],origin,destination,actor.get('name') or ''))
    lot_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO warehouse_history(company_id,material,type,quantity,unit,date,project,issued_to,
        issued_by,work_package,source_type,source_id,source_invoice_id,source_invoice_line_index)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'warehouse_movement',%s,%s,%s) RETURNING id,quantity''',
        (a['company_id'],a['material_name'],'перемещение: приход' if receiving else 'перемещение: списание',
         qty,a['unit'],today,project,TRANSIT,actor.get('name') or '',a['work_package'],
         movement['id'],a['receipt_id'],a['invoice_line_index']))
    history = cur.fetchone()
    if Decimal(str(history['quantity'])) != qty:
        conflict('История склада не сохраняет точность')
    return movement['id'], lot_id, history['id']


def views(cur, rows):
    if not rows:
        return []
    company_id = rows[0]['company_id']
    cur.execute('''SELECT * FROM warehouse_distribution_allocations
        WHERE company_id=%s AND id=ANY(%s)''', (company_id,[r['source_allocation_id'] for r in rows]))
    allocations = {r['id']:r for r in cur.fetchall()}
    cur.execute('''SELECT * FROM warehouse_distribution_transfer_receipts
        WHERE company_id=%s AND transfer_id=ANY(%s) ORDER BY id''', (company_id,[r['id'] for r in rows]))
    receipts = {}
    for event in cur.fetchall():
        receipts.setdefault(event['transfer_id'], []).append(event)
    result = []
    for t in rows:
        a = allocations[t['source_allocation_id']]
        events = receipts.get(t['id'], [])
        accepted = sum((e['quantity'] for e in events), Decimal(0))
        remaining = t['quantity']-accepted
        status = ('received' if remaining==0 else 'discrepancy' if any(
            e['quantity']<e['expected_quantity'] for e in events) else 'partial' if accepted else 'in_transit')
        result.append(dict(id=t['id'],companyId=company_id,sourceAllocationId=a['id'],
            fromProjectId=a['project_id'],fromProjectName=a['project_name'],toProjectId=t['to_project_id'],
            toProjectName=t['to_project_name'],warehouseInvoiceId=a['receipt_id'],invoiceNumber=a['receipt_number'],
            lotId=a['lot_id'],materialName=a['material_name'],unit=a['unit'],quantity=decimal_text(t['quantity']),
            receivedQuantity=decimal_text(accepted),inTransitQuantity=decimal_text(remaining),status=status,
            receipts=[dict(id=e['id'],quantity=decimal_text(e['quantity']),expectedQuantity=decimal_text(e['expected_quantity']),
                discrepancyQuantity=decimal_text(e['expected_quantity']-e['quantity']),allocationId=e['allocation_id'],
                reason=e['reason'],createdAt=str(e['created_at']),createdBy=e['created_by']) for e in events],
            reason=t['reason'],createdAt=str(t['created_at']),createdBy=t['created_by']))
    return result


def dispatch(cur, deps, data, actor):
    require_schema(cur)
    op, replay = service.begin_operation(cur,data,actor,kind='dispatch')
    if replay is not None:
        verify_replay(cur,deps,data.companyId,op,replay)
        return replay
    a, _ = source(cur,data.companyId,data.allocationId)
    check_transit_location(cur,data.companyId)
    target = service.lock_projects(cur,data.companyId,[data.toProjectId])[data.toProjectId]
    if data.toProjectId==a['project_id'] or data.quantity>service.remaining_entitlement(a):
        conflict('Передача превышает остаток распределения или объект совпадает')
    proof = quality.prepare_distribution_return(cur,deps,a)
    if proof is not None:
        # A protected dispatch must be receivable in the destination journal.
        # Existing proof keeps this preflight mandatory even with quality OFF.
        quality.quality_spec({**a, 'quantity': data.quantity}, deps)
    metadata = stock_leg(cur,a,a['project_name'],data.quantity,False)
    movement, lot_event, history = movement_leg(cur,a,a['project_name'],data.quantity,actor,data.reason,False)
    cur.execute('''INSERT INTO warehouse_distribution_transfers(company_id,operation_id,source_allocation_id,
        to_project_id,to_project_name,quantity,movement_id,lot_movement_id,history_id,reason,created_by,stock_snapshot)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (data.companyId,op,a['id'],data.toProjectId,target,data.quantity,movement,lot_event,history,data.reason,actor.get('name') or '',Json(metadata)))
    transfer = cur.fetchone()
    if proof is not None:
        quality.stamp(cur,dict(id=history),a)
    verify_leg(cur,a,movement,lot_event,data.quantity,a['project_name'],False,
               a['project_id'] if proof else None,history_id=history)
    response = dict(ok=True,requestId=str(data.requestId),item=views(cur,[transfer])[0])
    if proof is not None:
        response['sourceQuality'] = proof
    return service.finish_operation(cur,op,response)


def receive(cur,deps,transfer_id,data,actor):
    require_schema(cur)
    op,replay = service.begin_operation(cur,data,actor,kind='receipt',identity=f'receipt:{transfer_id}')
    if replay is not None:
        verify_replay(cur,deps,data.companyId,op,replay)
        return replay
    transfer = load_transfer(cur,data.companyId,transfer_id)
    check_transit_location(cur,data.companyId)
    a, _ = source(cur,data.companyId,transfer['source_allocation_id'])
    verify_dispatch(cur,deps,transfer,a)
    projects = service.lock_projects(cur,data.companyId,[transfer['to_project_id']])
    if projects[transfer['to_project_id']] != transfer['to_project_name']:
        conflict('Идентичность объекта назначения изменена')
    cur.execute('''SELECT coalesce(sum(quantity),0) AS accepted FROM warehouse_distribution_transfer_receipts
        WHERE transfer_id=%s AND company_id=%s''', (transfer_id,data.companyId))
    if data.expectedQuantity>transfer['quantity']-cur.fetchone()['accepted']:
        conflict('Приём превышает количество в пути')
    child = None
    source_proof = quality.prepare_distribution_return(cur,deps,a)
    if data.quantity:
        stock_leg(cur,a,transfer['to_project_name'],data.quantity,True,transfer['stock_snapshot'])
        movement,lot_event,_ = movement_leg(cur,a,transfer['to_project_name'],data.quantity,actor,data.reason,True)
        cur.execute('''INSERT INTO warehouse_distribution_allocations(company_id,operation_id,lot_id,receipt_id,
            receipt_number,invoice_line_index,project_id,project_name,material_name,unit,work_package,quantity,
            movement_id,lot_movement_id,movement_snapshot,reason,created_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (data.companyId,op,a['lot_id'],a['receipt_id'],a['receipt_number'],a['invoice_line_index'],
             transfer['to_project_id'],transfer['to_project_name'],a['material_name'],a['unit'],a['work_package'],
             data.quantity,movement,lot_event,Json(dict(transferId=transfer_id)),data.reason,actor.get('name') or ''))
        child = cur.fetchone()
    cur.execute('''INSERT INTO warehouse_distribution_transfer_receipts(company_id,transfer_id,operation_id,
        quantity,expected_quantity,allocation_id,reason,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (data.companyId,transfer_id,op,data.quantity,data.expectedQuantity,child['id'] if child else None,data.reason,actor.get('name') or ''))
    event_id = cur.fetchone()['id']
    proof = quality.create_distribution_quality(cur,deps,child,force=source_proof is not None) if child else None
    if child and proof is None:
        child_history(cur,child,creating=True)
    response = dict(ok=True,requestId=str(data.requestId),item=views(cur,[transfer])[0],receiptId=event_id)
    if proof is not None:
        response['ownedQuality'] = [proof]
    if source_proof is not None:
        response['sourceQuality'] = source_proof
    return service.finish_operation(cur,op,response)


def verify_dispatch(cur,deps,t,a):
    cur.execute('SELECT result FROM warehouse_distribution_operations WHERE id=%s AND company_id=%s',
                (t['operation_id'],t['company_id']))
    operation = cur.fetchone()
    if not operation or not isinstance(operation['result'],dict):
        quality.reject()
    proof = quality.prepare_distribution_return(cur,deps,a)
    if operation['result'].get('sourceQuality') != proof:
        quality.reject()
    verify_leg(cur,a,t['movement_id'],t['lot_movement_id'],t['quantity'],a['project_name'],
               False,a['project_id'] if proof else None,history_id=t['history_id'])


def verify_leg(cur,a,movement_id,lot_event_id,amount,project,receiving,owner,history_id=None):
    origin,destination = (TRANSIT,project) if receiving else (project,TRANSIT)
    kind = 'distribution_transfer_receipt' if receiving else 'distribution_dispatch'
    cur.execute('SELECT * FROM warehouse_movements WHERE id=%s AND company_id=%s FOR UPDATE',
                (movement_id,a['company_id']))
    m = cur.fetchone()
    cur.execute('SELECT * FROM warehouse_lot_movements WHERE id=%s FOR UPDATE',(lot_event_id,))
    l = cur.fetchone()
    cur.execute("SELECT * FROM warehouse_history WHERE source_type='warehouse_movement' AND source_id=%s ORDER BY id FOR UPDATE",
                (movement_id,))
    histories = cur.fetchall()
    if not m or not l or len(histories)!=1:
        quality.reject()
    h = histories[0]
    if (m['material_name']!=a['material_name'] or m['unit']!=a['unit'] or Decimal(str(m['quantity']))!=amount
            or m['from_location']!=origin or m['to_location']!=destination or m['work_package']!=a['work_package']
            or m['source_invoice_id']!=a['receipt_id'] or m['source_invoice_line_index']!=a['invoice_line_index']
            or l['company_id']!=a['company_id'] or l['lot_id']!=a['lot_id'] or l['warehouse_movement_id']!=movement_id
            or l['quantity']!=amount or l['unit']!=a['unit'] or l['operation_type']!=kind
            or l['from_location']!=origin or l['to_location']!=destination or l['reversal_of_id'] is not None
            or h['company_id']!=a['company_id'] or h.get('project_id')!=owner or h['project']!=project
            or h['issued_to']!=TRANSIT or h['material']!=a['material_name'] or h['unit']!=a['unit']
            or Decimal(str(h['quantity']))!=amount or h['work_package']!=a['work_package']
            or h['source_invoice_id']!=a['receipt_id'] or h['source_invoice_line_index']!=a['invoice_line_index']
            or h['type']!=('перемещение: приход' if receiving else 'перемещение: списание')
            or (history_id is not None and history_id!=h['id'])):
        quality.reject()
    return h


def child_history(cur,a,creating=False):
    cur.execute('''SELECT r.*,t.to_project_id,t.to_project_name,t.source_allocation_id FROM warehouse_distribution_transfer_receipts r
        JOIN warehouse_distribution_transfers t ON t.id=r.transfer_id AND t.company_id=r.company_id
        WHERE r.allocation_id=%s AND r.company_id=%s''',(a['id'],a['company_id']))
    event = cur.fetchone()
    if (not event or event['quantity']!=a['quantity'] or event['operation_id']!=a['operation_id']
            or event['transfer_id']!=a['movement_snapshot'].get('transferId')):
        quality.reject()
    cur.execute('SELECT * FROM warehouse_distribution_allocations WHERE id=%s AND company_id=%s',
                (event['source_allocation_id'],a['company_id']))
    parent = cur.fetchone()
    if (not parent or any(parent[k]!=a[k] for k in ('lot_id','receipt_id','receipt_number','invoice_line_index','material_name','unit','work_package'))
            or a['project_id']!=event['to_project_id'] or a['project_name']!=event['to_project_name']):
        quality.reject()
    return verify_leg(cur,a,a['movement_id'],a['lot_movement_id'],a['quantity'],a['project_name'],True,
                      None if creating else a['project_id'])


def verify_ancestors(cur, deps, allocation, *, require_owned=True):
    """Iterative verification avoids recursion on repeated redispatch chains."""
    child = allocation
    seen = set()
    while isinstance(child.get('movement_snapshot'),dict) and 'transferId' in child['movement_snapshot']:
        if child['id'] in seen:
            quality.reject()
        seen.add(child['id'])
        t = load_transfer(cur,child['company_id'],child['movement_snapshot']['transferId'])
        parent = quality.load_allocation(cur,t['source_allocation_id'],child['company_id'])
        cur.execute('''SELECT result FROM warehouse_distribution_operations
            WHERE id=%s AND company_id=%s''',(parent['operation_id'],child['company_id']))
        operation = cur.fetchone()
        result = operation['result'] if operation else None
        if not isinstance(result,dict):
            quality.reject()
        proof = None
        if require_owned or 'ownedQuality' in result:
            proofs = result.get('ownedQuality')
            if not isinstance(proofs,list) or any(not isinstance(p,dict) for p in proofs):
                quality.reject()
            matches = [p for p in proofs if p.get('allocationId')==parent['id']]
            if len(matches)!=1:
                quality.reject()
            proof = matches[0]
        h,_ = quality.trace_history(cur,parent,owned=proof is not None)
        if proof is not None:
            if proof.get('historyId')!=h['id']:
                quality.reject()
            quality.journal_records(cur,parent,h,quality.quality_spec(parent,deps),proof=proof)
        cur.execute('SELECT result FROM warehouse_distribution_operations WHERE id=%s AND company_id=%s',
                    (t['operation_id'],child['company_id']))
        dispatch = cur.fetchone()
        if not dispatch or not isinstance(dispatch['result'],dict) or dispatch['result'].get('sourceQuality')!=proof:
            quality.reject()
        verify_leg(cur,parent,t['movement_id'],t['lot_movement_id'],t['quantity'],parent['project_name'],False,
                   parent['project_id'] if proof is not None else None,history_id=t['history_id'])
        child = parent


def verify_replay(cur,deps,company_id,operation_id,replay):
    cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
    t = load_transfer(cur,company_id,replay['item']['id'])
    a,_ = source(cur,company_id,t['source_allocation_id'],historical=True)
    verify_dispatch(cur,deps,t,a)
    if t['operation_id']==operation_id:
        return
    cur.execute('''SELECT * FROM warehouse_distribution_transfer_receipts
        WHERE operation_id=%s AND company_id=%s AND transfer_id=%s''',(operation_id,company_id,t['id']))
    event = cur.fetchone()
    if not event or event['id']!=replay.get('receiptId'):
        quality.reject()
    if replay.get('sourceQuality') != quality.prepare_distribution_return(cur,deps,a):
        quality.reject()
    if event['allocation_id']:
        child = quality.load_allocation(cur,event['allocation_id'],company_id)
        proof = quality.prepare_distribution_return(cur,deps,child)
        if replay.get('ownedQuality',[]) != ([proof] if proof else []):
            quality.reject()
        if proof is None:
            child_history(cur,child,creating=True)
