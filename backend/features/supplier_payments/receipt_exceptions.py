"""Caller-owned transaction: rejected/zero delivery evidence, never a payable receipt."""
from fastapi import HTTPException
from psycopg2.errors import CheckViolation


def register_receipt_exception(cur, *, company_id, invoice_id, delivery_id, warehouse_id):
    if cur.connection.autocommit:
        raise RuntimeError('Receipt exception requires caller-owned transaction')
    cur.execute('SELECT public.supplier_allocation_lock(%s)', (company_id,))
    cur.execute('SELECT * FROM supplier_receipt_exceptions WHERE delivery_id=%s', (delivery_id,))
    existing = cur.fetchone()
    if existing:
        if (existing['company_id'],existing['invoice_id'],existing['warehouse_invoice_id']) != (company_id,invoice_id,warehouse_id):
            raise HTTPException(409, 'Результат приёмки относится к другим документам')
        return dict(deliveryId=delivery_id,acceptedQuantity=0,rejectedQuantity=existing['rejected_quantity'])
    cur.execute('''SELECT l.id FROM supplier_invoice_lines l JOIN supplier_invoice_line_specs s ON s.id=l.spec_id
        JOIN supply_deliveries d ON d.source_supplier_invoice_id=s.invoice_id AND d.company_id=s.company_id
        WHERE s.invoice_id=%s AND s.company_id=%s AND d.id=%s
            AND (l.material_name,l.unit,l.work_package,l.unit_price)=
                (d.material_name,d.unit,COALESCE(d.work_package,''),d.price_per_unit) FOR UPDATE OF l''',
        (invoice_id,company_id,delivery_id))
    lines=cur.fetchall()
    if len(lines)!=1:
        raise HTTPException(409, 'Приёмка не соответствует единственной строке счёта')
    try:
        cur.execute('''INSERT INTO supplier_receipt_exceptions
            (delivery_id,company_id,invoice_id,invoice_line_id,warehouse_invoice_id,claim_id,
             received_quantity,rejected_quantity,shortage_quantity,quality_status,provenance)
            SELECT id,%s,%s,%s,%s,claim_id,received_quantity,received_quantity,shortage_quantity,quality_status,'{}'::jsonb
            FROM supply_deliveries WHERE id=%s RETURNING rejected_quantity''',
            (company_id,invoice_id,lines[0]['id'],warehouse_id,delivery_id))
        result=cur.fetchone()
    except CheckViolation:
        raise HTTPException(409, 'Документы, количество или претензия по непринятой поставке требуют сверки') from None
    return dict(deliveryId=delivery_id,acceptedQuantity=0,rejectedQuantity=result['rejected_quantity'])


def assert_stock_source(cur, *, company_id, warehouse_id):
    """Called after authorization/source lookup, inside the stock transaction."""
    cur.execute('''SELECT to_jsonb(w)->>'supply_delivery_id' AS delivery_id,
            d.company_id AS delivery_company,d.received_at,d.received_quantity,d.quality_status
        FROM warehouse_invoices w LEFT JOIN supply_deliveries d
            ON d.id=(to_jsonb(w)->>'supply_delivery_id')::int
        WHERE w.id=%s AND w.company_id=%s''', (warehouse_id,company_id))
    source=cur.fetchone()
    if not source:
        raise HTTPException(404, 'Накладная выбранной компании не найдена')
    if source['delivery_id'] and (source['delivery_company'] != company_id or not source['received_at']
            or (source['received_quantity'] or 0)<=0 or source['quality_status'] in ('Брак','Несоответствие')):
        raise HTTPException(409, 'Материал по этой поставке не принят на склад. Выдача и перемещение недоступны')
