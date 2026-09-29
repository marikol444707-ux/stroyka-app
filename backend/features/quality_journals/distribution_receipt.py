"""Exact allocation-owned quality writes. Caller owns authorization and transaction.

No DDL, legacy adoption, source-invoice owner changes, commits or external calls.
Immutable operation results retain proof IDs so flag-off cannot weaken existing
owned return/replay checks. Journal quantities describe the original acceptance.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import os

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .ownership import positive_id

MAIN = 'Основной склад'


def distribution_quality_enabled():
    return os.getenv('OWNED_DISTRIBUTION_QUALITY_ENABLED') == '1'


def reject():
    raise HTTPException(409, 'Не подтверждена точная принадлежность или точность журнала распределения')


def quantity(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0:
            reject()
        return result
    except (InvalidOperation, ValueError, TypeError):
        reject()


def quality_spec(allocation, deps):
    if not all(positive_id(allocation.get(key)) for key in ('id', 'company_id', 'project_id')):
        reject()
    name, unit = allocation.get('material_name'), allocation.get('unit')
    if not isinstance(name, str) or not name.strip() or not isinstance(unit, str) or not unit.strip():
        reject()
    detector = deps.get('detect_cable_info')
    if not callable(detector):
        reject()
    cable = detector(name)
    if not isinstance(cable, dict) or type(cable.get('isCable')) is not bool:
        reject()
    qty = quantity(allocation.get('quantity'))
    if qty >= Decimal('10000000000') or qty != qty.quantize(Decimal('0.0001')):
        reject()
    if cable['isCable']:
        normalizer = deps.get('normalize_unit')
        unit = normalizer(unit) if callable(normalizer) else unit
        if unit != 'м' or qty >= Decimal('100000000') or qty != qty.quantize(Decimal('0.01')):
            reject()
    return dict(quantity=qty, unit=unit, cable=cable)


@contextmanager
def scope(cur):
    if cur.connection.autocommit:
        reject()
    with cur.connection.cursor(cursor_factory=RealDictCursor) as owned:
        owned.execute('SHOW transaction_isolation')
        if owned.fetchone()['transaction_isolation'] != 'read committed':
            reject()
        yield owned


def load_allocation(cur, allocation_id, company_id):
    if not positive_id(allocation_id) or not positive_id(company_id):
        reject()
    cur.execute('''SELECT * FROM warehouse_distribution_allocations
        WHERE id=%s AND company_id=%s FOR UPDATE''', (allocation_id, company_id))
    row = cur.fetchone()
    if not row:
        reject()
    return row


def trace_history(cur, allocation, *, event=None, creating=False, owned=True):
    """Check persisted stock lineage, then select only the object's history leg."""
    a = allocation
    cur.execute('SELECT name FROM projects WHERE id=%s AND company_id=%s FOR SHARE',
                (a['project_id'], a['company_id']))
    project = cur.fetchone()
    cur.execute('SELECT * FROM warehouse_receipt_lots WHERE id=%s AND company_id=%s FOR UPDATE',
                (a['lot_id'], a['company_id']))
    lot = cur.fetchone()
    cur.execute('SELECT * FROM warehouse_invoices WHERE id=%s AND company_id=%s FOR SHARE',
                (a['receipt_id'], a['company_id']))
    receipt = cur.fetchone()
    if (not project or project['name'] != a['project_name'] or not lot or not receipt
            or receipt.get('project_id') is not None or lot.get('project_id') is not None
            or lot['warehouse_invoice_id'] != a['receipt_id']
            or lot['invoice_line_index'] != a['invoice_line_index']
            or lot['material_name'] != a['material_name'] or lot['unit'] != a['unit']
            or lot['warehouse_target'] != 'main' or lot['warehouse_location'] != MAIN
            or quantity(lot['received_quantity']) < quantity(a['quantity'])):
        reject()
    if event and (event['allocation_id'] != a['id'] or event['company_id'] != a['company_id']
                  or quantity(event['quantity']) > quantity(a['quantity'])):
        reject()
    # A child is accepted from transit, not issued a second time from MAIN.
    # Snapshot discriminator is stored by the immutable allocation writer.
    snapshot = a.get('movement_snapshot') or {}
    if not event and isinstance(snapshot, dict) and 'transferId' in snapshot:
        from ..warehouse_distribution.transfers import child_history
        return child_history(cur, a, creating=creating or not owned), receipt
    movement_id = event['movement_id'] if event else a['movement_id']
    amount = quantity(event['quantity'] if event else a['quantity'])
    origin, destination = (a['project_name'], MAIN) if event else (MAIN, a['project_name'])
    cur.execute('SELECT * FROM warehouse_movements WHERE id=%s AND company_id=%s FOR UPDATE',
                (movement_id, a['company_id']))
    movement = cur.fetchone()
    if (not movement or movement['material_name'] != a['material_name'] or movement['unit'] != a['unit']
            or quantity(movement['quantity']) != amount or movement['from_location'] != origin
            or movement['to_location'] != destination or movement['work_package'] != a['work_package']
            or movement['source_invoice_id'] != a['receipt_id']
            or movement['source_invoice_line_index'] != a['invoice_line_index']):
        reject()
    cur.execute('SELECT * FROM warehouse_lot_movements WHERE id=%s FOR UPDATE',
                (event['lot_movement_id'] if event else a['lot_movement_id'],))
    journal = cur.fetchone()
    if (not journal or journal['lot_id'] != a['lot_id'] or journal['company_id'] != a['company_id']
            or journal['warehouse_movement_id'] != movement_id or quantity(journal['quantity']) != amount
            or journal['unit'] != a['unit'] or journal['from_location'] != origin
            or journal['to_location'] != destination
            or journal['operation_type'] != ('distribution_return' if event else 'warehouse_movement_out')
            or journal['reversal_of_id'] != (a['lot_movement_id'] if event else None)):
        reject()
    cur.execute('''SELECT * FROM warehouse_history WHERE source_type='warehouse_movement'
        AND source_id=%s ORDER BY id FOR UPDATE''', (movement_id,))
    histories = cur.fetchall()
    if len(histories) != 2:
        reject()
    by_type = {row['type']: row for row in histories}
    if set(by_type) != {'перемещение: списание', 'перемещение: приход'}:
        reject()
    for kind, location, other in (('перемещение: списание', origin, destination),
                                   ('перемещение: приход', destination, origin)):
        h = by_type[kind]
        if (h['company_id'] != a['company_id'] or h['material'] != a['material_name']
                or h['unit'] != a['unit'] or quantity(h['quantity']) != amount
                or h['project'] != location or h['issued_to'] != other or h['work_package'] != a['work_package']
                or h['source_invoice_id'] != a['receipt_id'] or h['source_invoice_line_index'] != a['invoice_line_index']):
            reject()
        expected_project = None if location == MAIN or creating or not owned else a['project_id']
        if h.get('project_id') != expected_project:
            reject()
    owned = by_type['перемещение: списание' if event else 'перемещение: приход']
    return owned, receipt


def journal_records(cur, a, history, spec, *, proof=None, creating=False):
    """Never adopt an existing row, including an unowned historical lookalike."""
    key = 'allocation:' + str(a['id'])
    result = dict(allocationId=a['id'], historyId=history['id'], inspectionId=None, cableId=None)
    for table, name_col, qty_col, id_key in (
        ('material_inspection_journal', 'material_name', 'quantity', 'inspectionId'),
        ('cable_journal', 'cable_brand', 'length_received', 'cableId'),
    ):
        required = id_key == 'inspectionId' or spec['cable']['isCable']
        # Search all owners to detect conflicting provenance rather than hiding it.
        cur.execute(f'''SELECT * FROM {table} WHERE source_item_key=%s OR warehouse_history_id=%s
            OR (source_type='warehouse_history' AND source_id=%s) ORDER BY id FOR UPDATE''',
            (key, history['id'], history['id']))
        rows = cur.fetchall()
        if creating:
            if rows:
                reject()
            continue
        if not required:
            if rows or proof.get(id_key) is not None:
                reject()
            continue
        if len(rows) != 1:
            reject()
        row = rows[0]
        if (row['id'] != proof.get(id_key) or row['company_id'] != a['company_id']
                or row['project_id'] != a['project_id'] or row['project_name'] != a['project_name']
                or row['invoice_id'] is not None or row['delivery_id'] is not None
                or row['warehouse_history_id'] != history['id'] or row['source_type'] != 'warehouse_history'
                or row['source_id'] != history['id'] or row['source_item_key'] != key
                or row[name_col] != a['material_name'] or quantity(row[qty_col]) != spec['quantity']
                or row['work_package'] != a['work_package']
                or (id_key == 'inspectionId' and row['unit'] != spec['unit'])):
            reject()
        result[id_key] = row['id']
    return result


def stamp(cur, history, allocation):
    cur.execute('''UPDATE warehouse_history SET project_id=%s
        WHERE id=%s AND company_id=%s AND project_id IS NULL RETURNING project_id''',
        (allocation['project_id'], history['id'], allocation['company_id']))
    row = cur.fetchone()
    if not row or row['project_id'] != allocation['project_id']:
        reject()


def create_distribution_quality(cur, deps, allocation, *, force=False):
    if not distribution_quality_enabled() and not force:
        return None
    quality_spec(allocation, deps)
    with scope(cur) as owned:
        a = load_allocation(owned, allocation['id'], allocation['company_id'])
        owned.execute('''SELECT result,kind FROM warehouse_distribution_operations
            WHERE id=%s AND company_id=%s FOR UPDATE''', (a['operation_id'], a['company_id']))
        operation = owned.fetchone()
        snapshot = a.get('movement_snapshot') or {}
        expected_kind = 'receipt' if isinstance(snapshot, dict) and 'transferId' in snapshot else 'issue'
        if not operation or operation['result'] is not None or operation['kind'] != expected_kind:
            reject()
        spec = quality_spec(a, deps)
        history, receipt = trace_history(owned, a, creating=True)
        proof = journal_records(owned, a, history, spec, creating=True)
        stamp(owned, history, a)
        for table, name_col, qty_col, id_key in (
            ('material_inspection_journal', 'material_name', 'quantity', 'inspectionId'),
            ('cable_journal', 'cable_brand', 'length_received', 'cableId'),
        ):
            if id_key == 'cableId' and not spec['cable']['isCable']:
                continue
            columns = ['company_id','project_id','project_name','warehouse_history_id','source_type','source_id',
                       'source_item_key',name_col,qty_col,'work_package','supplier','received_at']
            values = [a['company_id'],a['project_id'],a['project_name'],history['id'],'warehouse_history',history['id'],
                      'allocation:'+str(a['id']),a['material_name'],spec['quantity'],a['work_package'],
                      receipt.get('supplier_name') or '', history.get('date') or None]
            if id_key == 'inspectionId':
                columns.append('unit')
                values.append(spec['unit'])
            else:
                columns.extend(['cable_type','cross_section','cores_count'])
                values.extend([spec['cable'].get('cableType') or '',spec['cable'].get('section'),spec['cable'].get('cores')])
            owned.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s']*len(values))}) RETURNING id",
                          values)
            proof[id_key] = owned.fetchone()['id']
        # Read-back catches precision-changing triggers or an unexpected schema.
        verify_quality(owned, deps, a, proof)
        return proof


def verify_quality(cur, deps, allocation, proof):
    if not isinstance(proof, dict) or proof.get('allocationId') != allocation['id']:
        reject()
    history, _ = trace_history(cur, allocation)
    if proof.get('historyId') != history['id']:
        reject()
    journal_records(cur, allocation, history, quality_spec(allocation, deps), proof=proof)
    snapshot = allocation.get('movement_snapshot') or {}
    if isinstance(snapshot,dict) and 'transferId' in snapshot:
        from ..warehouse_distribution.transfers import verify_ancestors
        verify_ancestors(cur,deps,allocation)


def prepare_distribution_return(cur, deps, allocation):
    # The operation result is authoritative opt-in evidence, not current flags.
    cur.execute('SELECT result FROM warehouse_distribution_operations WHERE id=%s AND company_id=%s',
                (allocation['operation_id'], allocation['company_id']))
    operation = cur.fetchone()
    result = operation['result'] if operation else None
    if not isinstance(result, dict):
        reject()
    has_proof = 'ownedQuality' in result
    proofs = result.get('ownedQuality', [])
    if not distribution_quality_enabled() and not has_proof:
        # Flag-off removes journal requirements, never physical custody evidence.
        # No new tables are touched for an ordinary 0012 root allocation.
        from ..warehouse_distribution.transfers import verify_ancestors
        trace_history(cur, allocation, owned=False)
        verify_ancestors(cur, deps, allocation, require_owned=False)
        return None
    if not isinstance(proofs, list) or any(not isinstance(p, dict) for p in proofs):
        reject()
    candidates = [p for p in proofs if p.get('allocationId') == allocation['id']]
    if len(candidates) != 1:
        reject()
    with scope(cur) as owned:
        verify_quality(owned, deps, allocation, candidates[0])
    return candidates[0]


def create_distribution_return_quality(cur, deps, allocation, event, proof):
    if proof is None:
        return None
    with scope(cur) as owned:
        verify_quality(owned, deps, allocation, proof)
        history, _ = trace_history(owned, allocation, event=event, creating=True)
        stamp(owned, history, allocation)
        return {**proof, 'returnId': event['id'], 'returnHistoryId': history['id']}


def verify_distribution_replay(cur, deps, operation_id, company_id, replay, allocation_id=None):
    proofs = replay.get('ownedQuality')
    if not distribution_quality_enabled() and 'ownedQuality' not in replay:
        if allocation_id is not None:
            cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
            allocation = load_allocation(cur, allocation_id, company_id)
            if prepare_distribution_return(cur, deps, allocation) is not None:
                reject()
            cur.execute('''SELECT * FROM warehouse_distribution_returns
                WHERE operation_id=%s AND company_id=%s AND allocation_id=%s FOR UPDATE''',
                (operation_id, company_id, allocation_id))
            events = cur.fetchall()
            if len(events) != 1:
                reject()
            trace_history(cur, allocation, event=events[0], owned=False)
        return
    if not isinstance(proofs, list) or not proofs:
        reject()
    # Match lock order of new writes before acquiring any lineage row locks.
    cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')
    with scope(cur) as owned:
        if allocation_id is None:
            owned.execute('''SELECT * FROM warehouse_distribution_allocations
                WHERE operation_id=%s AND company_id=%s ORDER BY id FOR UPDATE''', (operation_id, company_id))
            allocations = owned.fetchall()
        else:
            allocations = [load_allocation(owned, allocation_id, company_id)]
        if len(allocations) != len(proofs):
            reject()
        for a, proof in zip(allocations, proofs):
            verify_quality(owned, deps, a, proof)
            if allocation_id is not None:
                owned.execute('''SELECT * FROM warehouse_distribution_returns
                    WHERE operation_id=%s AND company_id=%s AND allocation_id=%s FOR UPDATE''',
                    (operation_id, company_id, allocation_id))
                events = owned.fetchall()
                if len(events) != 1 or proof.get('returnId') != events[0]['id']:
                    reject()
                history, _ = trace_history(owned, a, event=events[0])
                if proof.get('returnHistoryId') != history['id']:
                    reject()
