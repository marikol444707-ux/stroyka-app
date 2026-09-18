"""Opt-in invoice quality writes inside the already-authorized receipt transaction."""
from decimal import Decimal, InvalidOperation
import os

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .ownership import positive_id


def invoice_quality_enabled():
    return os.getenv('OWNED_INVOICE_QUALITY_ENABLED') == '1'


def create_invoice_quality(cur, *, company_id, project_id, invoice_id, line_index,
                           name, quantity, unit, work_package='', cable_info=None):
    """No auth bypass/legacy reconstruction. Caller owns transaction and permissions.

    Parent row lock serializes retries for this invoice; a stable line ordinal
    identifies the source, not a material name/quantity fingerprint. The SQL role
    must not bypass this service to write owned journal rows concurrently.
    """
    if (not all(positive_id(value) for value in (company_id, project_id, invoice_id))
            or type(line_index) is not int or not 0 <= line_index <= 2147483647):
        raise HTTPException(409, 'Не определён точный владелец строки накладной')
    if cur.connection.autocommit:
        raise HTTPException(409, 'Журнал должен сохраняться в транзакции приёмки')
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, ValueError):
        raise HTTPException(400, 'Некорректное количество для журнала')
    if not qty.is_finite() or qty <= 0 or not isinstance(name, str) or not name.strip():
        raise HTTPException(400, 'Некорректная строка журнала')
    if cable_info and cable_info.get('isCable') and unit != 'м':
        raise HTTPException(409, 'Для кабельного журнала требуется подтверждённое количество в метрах')
    is_cable = bool(cable_info and cable_info.get('isCable'))
    scale, limit = (2, Decimal('100000000')) if is_cable else (4, Decimal('10000000000'))
    if qty >= limit or qty != qty.quantize(Decimal(1).scaleb(-scale)):
        raise HTTPException(400, 'Количество не помещается в журнал без округления')
    key = 'invoice-line:' + str(line_index)
    with cur.connection.cursor(cursor_factory=RealDictCursor) as scope:
        scope.execute('SHOW transaction_isolation')
        if scope.fetchone()['transaction_isolation'] != 'read committed':
            raise HTTPException(409, 'Журнал требует транзакцию READ COMMITTED')
        scope.execute('''SELECT i.company_id,i.project_id,i.supplier_name,i.date,p.name AS project_name
            FROM warehouse_invoices i JOIN projects p ON p.id=i.project_id AND p.company_id=i.company_id
            WHERE i.id=%s AND i.company_id=%s AND i.project_id=%s FOR UPDATE OF i''',
            (invoice_id, company_id, project_id))
        parent = scope.fetchone()
        if not parent:
            raise HTTPException(409, 'Владелец накладной не совпадает с владельцем журнала')
        added = {'inspections': 0, 'cables': 0}
        tables = [('material_inspection_journal', 'material_name', 'quantity', 'inspections')]
        if cable_info and cable_info.get('isCable'):
            tables.append(('cable_journal', 'cable_brand', 'length_received', 'cables'))
        for table, name_field, quantity_field, counter in tables:
            unit_expression = 'unit' if counter == 'inspections' else "'м'"
            scope.execute(f'''SELECT company_id,project_id,{name_field} AS name,{quantity_field} AS quantity,
                work_package, source_type, source_id, {unit_expression} AS unit
                FROM {table} WHERE invoice_id=%s AND source_item_key=%s ORDER BY id''', (invoice_id, key))
            existing = scope.fetchall()
            if existing:
                if (len(existing) != 1 or existing[0]['company_id'] != company_id
                        or existing[0]['project_id'] != project_id or existing[0]['name'] != name
                        or existing[0]['quantity'] != qty or existing[0]['unit'] != unit
                        or existing[0]['source_type'] != 'warehouse_invoice'
                        or existing[0]['source_id'] != invoice_id
                        or existing[0]['work_package'] != work_package):
                    raise HTTPException(409, 'Конфликт существующей строки журнала')
                continue
            columns = f'company_id,project_id,project_name,invoice_id,source_type,source_id,source_item_key,{name_field},{quantity_field},supplier,received_at,work_package'
            values = [company_id, project_id, parent['project_name'], invoice_id,
                      'warehouse_invoice', invoice_id, key, name, qty, parent['supplier_name'] or '', parent['date'] or None, work_package]
            if counter == 'inspections':
                columns += ',unit'
                values.append(unit)
            else:
                columns += ',cable_type,cross_section,cores_count'
                values.extend([cable_info.get('cableType') or '', cable_info.get('section'), cable_info.get('cores')])
            scope.execute(f'INSERT INTO {table} ({columns}) VALUES (' + ','.join(['%s'] * len(values)) + ')', values)
            added[counter] += 1
        return added
