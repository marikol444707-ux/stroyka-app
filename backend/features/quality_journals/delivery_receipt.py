"""Owned delivery journals inside the authorized automatic receipt transaction."""
import os
from decimal import Decimal

from fastapi import HTTPException

from .invoice_receipt import create_invoice_quality
from .ownership import positive_id


def delivery_quality_enabled():
    return os.getenv('OWNED_DELIVERY_QUALITY_ENABLED') == '1'


def create_delivery_quality(cur, *, delivery_id, company_id, project_id, invoice_id, normalize_unit,
                            replay=False, cable_info=None, expected_quantity=None):
    """Caller owns authorization and transaction; replay validates, never repairs."""
    if not all(positive_id(value) for value in (delivery_id, company_id, project_id)):
        raise HTTPException(409, 'Не определена принадлежность поставки')
    if cur.connection.autocommit:
        raise HTTPException(409, 'Журнал требует транзакцию приёмки')
    cur.execute('SHOW transaction_isolation')
    if cur.fetchone()['transaction_isolation'] != 'read committed':
        raise HTTPException(409, 'Журнал требует транзакцию READ COMMITTED')
    cur.execute('''SELECT * FROM supply_deliveries WHERE id=%s AND company_id=%s
                   AND project_id=%s FOR UPDATE''', (delivery_id, company_id, project_id))
    delivery = cur.fetchone()
    if not delivery or not delivery['received_at'] or delivery['status'] not in ('Принято', 'Проблема'):
        raise HTTPException(409, 'Не подтверждена приёмка поставки')
    quantity = delivery['received_quantity']
    if quantity is None or not Decimal(str(quantity)).is_finite() or quantity < 0:
        raise HTTPException(409, 'Не подтверждено количество поставки')
    if not replay and (expected_quantity is None or Decimal(str(expected_quantity)) != quantity):
        raise HTTPException(400, 'Количество приёмки не должно округляться при сохранении')
    if quantity > 0:
        if not positive_id(invoice_id):
            raise HTTPException(409, 'Не определена накладная приёмки')
        cur.execute('''SELECT id FROM warehouse_invoices WHERE id=%s AND company_id=%s
            AND project_id=%s AND supply_delivery_id=%s AND source_type='supply_delivery'
            AND source_id=%s AND status='Принята' FOR UPDATE''',
            (invoice_id, company_id, project_id, delivery_id, str(delivery_id)))
        if not cur.fetchone():
            raise HTTPException(409, 'Накладная не соответствует принятой поставке')
    elif invoice_id is not None:
        raise HTTPException(409, 'Нулевая приёмка не должна иметь накладную')

    is_cable = bool(cable_info and cable_info.get('isCable'))
    for table, expected in (('material_inspection_journal', quantity > 0),
                            ('cable_journal', quantity > 0 and is_cable)):
        # Inspect all references, including contradictory legacy/generic links.
        cur.execute(f'''SELECT company_id,project_id,delivery_id,invoice_id,source_type,
            source_id,source_item_key,warehouse_history_id FROM {table}
            WHERE delivery_id=%s OR invoice_id=%s
               OR (source_type='supply_delivery' AND source_id=%s)
               OR (source_type='warehouse_invoice' AND source_id=%s) FOR UPDATE''',
            (delivery_id, invoice_id, delivery_id, invoice_id))
        rows = cur.fetchall()
        if len(rows) != int(replay and expected):
            raise HTTPException(409, 'Журнал требует отдельной проверки: запись отсутствует или уже существует')
        for row in rows:
            if (row['company_id'] != company_id or row['project_id'] != project_id
                    or row['delivery_id'] != delivery_id or row['invoice_id'] != invoice_id
                    or row['source_type'] != 'warehouse_invoice' or row['source_id'] != invoice_id
                    or row['source_item_key'] != 'invoice-line:0' or row['warehouse_history_id'] is not None):
                raise HTTPException(409, 'Связи журнала противоречат поставке')
    if quantity == 0:
        return {'inspections': 0, 'cables': 0}
    result = create_invoice_quality(cur, company_id=company_id, project_id=project_id,
        invoice_id=invoice_id, line_index=0, name=(delivery['material_name'] or '').strip(),
        quantity=quantity, unit=normalize_unit(delivery['unit'] or 'шт') or 'шт',
        work_package=(delivery['work_package'] or '').strip() or 'Основная', cable_info=cable_info)
    if not replay:
        cur.execute('''UPDATE material_inspection_journal SET delivery_id=%s,inspected=TRUE,
            visual_inspection_result=%s,remarks=%s WHERE invoice_id=%s AND source_item_key='invoice-line:0'
            AND company_id=%s AND project_id=%s''',
            (delivery_id, delivery['quality_status'] or 'Принято', delivery['quality_notes'] or '',
             invoice_id, company_id, project_id))
        if is_cable:
            cur.execute('''UPDATE cable_journal SET delivery_id=%s WHERE invoice_id=%s
                AND source_item_key='invoice-line:0' AND company_id=%s AND project_id=%s''',
                (delivery_id, invoice_id, company_id, project_id))
    return result
