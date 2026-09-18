"""Opt-in ownership for new automatic receipt sources, not historical repair."""
import os

from fastapi import HTTPException

from ..project_access.service import resolve_project_parent


def delivery_sources_enabled():
    return os.getenv('OWNED_DELIVERY_SOURCES_ENABLED') == '1'


def prepare_delivery_sources(cur, actor, delivery):
    """Caller holds stock/delivery locks and has checked membership and chain access."""
    # Stock is still name-based, so even a stored ID must not bypass ambiguity.
    project = resolve_project_parent(cur, actor, project_name=delivery.get('project'), for_update=True)
    project_id = project['id']
    if delivery.get('project_id') not in (None, project_id):
        raise HTTPException(409, 'Поставка связана с другим объектом')
    received = delivery.get('status') in ('Принято', 'Проблема') or bool(delivery.get('received_at'))
    cur.execute('SELECT id,company_id,project_id,source_type,source_id FROM warehouse_invoices WHERE supply_delivery_id=%s FOR UPDATE',
                (delivery['id'],))
    invoices = cur.fetchall()
    cur.execute("SELECT company_id,project_id,source_invoice_id FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s FOR UPDATE",
                (delivery['id'],))
    movements = cur.fetchall()
    if received:
        if delivery.get('project_id') != project_id:
            raise HTTPException(409, 'Историческая приёмка требует отдельной проверки принадлежности')
        positive = (delivery.get('received_quantity') or 0) > 0
        if len(invoices) != int(positive):
            raise HTTPException(409, 'Нарушена связь приёмки с накладной')
        for invoice in invoices:
            if (invoice['company_id'] != delivery['company_id'] or invoice['project_id'] != project_id
                    or invoice['source_type'] != 'supply_delivery' or str(invoice['source_id']) != str(delivery['id'])):
                raise HTTPException(409, 'Принадлежность накладной поставки не подтверждена')
        expected_movement = positive and delivery.get('quality_status') != 'Брак'
        if len(movements) != int(expected_movement):
            raise HTTPException(409, 'Нарушена связь приёмки со складом')
        for movement in movements:
            if (movement['company_id'] != delivery['company_id'] or movement['project_id'] != project_id
                    or movement['source_invoice_id'] != invoices[0]['id']):
                raise HTTPException(409, 'Принадлежность складского движения не подтверждена')
    else:
        if invoices or movements:
            raise HTTPException(409, 'До приёмки уже существуют складские документы: нужна проверка')
        cur.execute('UPDATE supply_deliveries SET project_id=%s WHERE id=%s AND company_id=%s',
                    (project_id, delivery['id'], delivery['company_id']))
    return project_id


def bind_new_delivery_sources(cur, delivery, project_id, invoice_id):
    """Bind only records created in this same acceptance transaction."""
    if invoice_id is None:
        return
    cur.execute("""UPDATE warehouse_invoices SET project_id=%s
        WHERE id=%s AND company_id=%s AND supply_delivery_id=%s
          AND source_type='supply_delivery' AND source_id=%s AND project_id IS NULL""",
        (project_id, invoice_id, delivery['company_id'], delivery['id'], str(delivery['id'])))
    if cur.rowcount != 1:
        raise HTTPException(409, 'Не удалось подтвердить принадлежность новой накладной')
    cur.execute("""UPDATE warehouse_history SET project_id=%s
        WHERE company_id=%s AND source_type='supply_delivery' AND source_id=%s
          AND source_invoice_id=%s AND project_id IS NULL""",
        (project_id, delivery['company_id'], delivery['id'], invoice_id))
    expected = (delivery.get('received_quantity') or 0) > 0 and delivery.get('quality_status') != 'Брак'
    if cur.rowcount != int(expected):
        raise HTTPException(409, 'Не удалось подтвердить принадлежность складского движения')
