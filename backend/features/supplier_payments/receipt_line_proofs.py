"""Internal receipt registration, no HTTP, authority grants, stock or money writes.

Caller authorizes the current warehouse actor and owns the entire receipt
transaction, including stock locks before the company lock. Never call after
committing receipt/stock creation. Only immutable exact source lines are supported;
VAT requires the separate schema/runtime adapter. Ambiguous or historical
invoices without a specification fail closed.
"""
from fastapi import HTTPException
from psycopg2.errors import CheckViolation


def register_receipt_line(cur, *, company_id, invoice_id, warehouse_id):
    if cur.connection.autocommit:
        raise RuntimeError('Receipt proof requires caller-owned transaction')
    if any(type(value) is not int or value <= 0 for value in (company_id, invoice_id, warehouse_id)):
        raise HTTPException(409, 'Не определены документы приёмки')
    cur.execute('SELECT public.supplier_allocation_lock(%s)', (company_id,))
    cur.execute('''SELECT id FROM supplier_payment_documents
        WHERE company_id=%s AND document_kind='invoice' AND document_id=%s''', (company_id, invoice_id))
    record = cur.fetchone()
    if not record:
        raise HTTPException(409, 'Счёт не зарегистрирован в журнале оплат')
    cur.execute('''SELECT l.id,l.unit_price,d.received_quantity,d.id AS delivery_id
        FROM supplier_invoice_line_specs s JOIN supplier_invoice_lines l ON l.spec_id=s.id
        JOIN supply_deliveries d ON d.source_supplier_invoice_id=s.invoice_id
            AND d.company_id=s.company_id AND d.material_name=l.material_name
            AND d.unit=l.unit AND COALESCE(d.work_package,'')=l.work_package AND d.price_per_unit=l.unit_price
        JOIN warehouse_invoices w ON w.supply_delivery_id=d.id AND w.company_id=s.company_id
        WHERE s.invoice_id=%s AND s.company_id=%s AND w.id=%s FOR UPDATE OF l''',
        (invoice_id, company_id, warehouse_id))
    lines = cur.fetchall()
    if len(lines) != 1:
        raise HTTPException(409, 'Приёмка не соответствует единственной строке сохранённого счёта')
    line = lines[0]
    cur.execute('''SELECT id FROM supplier_payment_allocation_groups
        WHERE company_id=%s AND invoice_record_id=%s''', (company_id, record['id']))
    group = cur.fetchone()
    if not group:
        cur.execute('''INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id)
            VALUES(%s,%s) RETURNING id''', (company_id, record['id']))
        group = cur.fetchone()
    cur.execute('''SELECT id,group_id,company_id FROM supplier_payment_receipt_relations
        WHERE warehouse_invoice_id=%s''', (warehouse_id,))
    relation = cur.fetchone()
    if relation and (relation['group_id'], relation['company_id']) != (group['id'], company_id):
        raise HTTPException(409, 'Приёмка уже относится к другому счёту')
    try:
        if not relation:
            cur.execute('''INSERT INTO supplier_payment_receipt_relations
                (company_id,group_id,warehouse_invoice_id,amount,provenance)
                SELECT %s,%s,id,total_with_vat,NULL FROM warehouse_invoices WHERE id=%s RETURNING id''',
                (company_id, group['id'], warehouse_id))
            relation = cur.fetchone()
        cur.execute('SELECT * FROM supplier_receipt_line_proofs WHERE receipt_relation_id=%s', (relation['id'],))
        proof = cur.fetchone()
        if proof:
            if proof['invoice_line_id'] != line['id'] or proof['company_id'] != company_id:
                raise HTTPException(409, 'Сохранённая связь строки приёмки требует сверки')
        else:
            cur.execute("SELECT to_regclass('supplier_vat_guard_versions') AS ready")
            tax_ready=bool(cur.fetchone()['ready'])
            cur.execute('''INSERT INTO supplier_receipt_line_proofs
                (receipt_relation_id,invoice_line_id,company_id,quantity,amount''' + (',vat_amount' if tax_ready else '') + ''')
                SELECT %s,%s,%s,received_quantity,received_quantity*price_per_unit''' +
                (', (SELECT total_vat FROM warehouse_invoices WHERE supply_delivery_id=supply_deliveries.id)' if tax_ready else '') + '''
                FROM supply_deliveries WHERE id=%s''',
                (relation['id'], line['id'], company_id, line['delivery_id']))
    except CheckViolation:
        raise HTTPException(409, 'Количество, стоимость или состав приёмки не соответствуют счёту') from None
    return dict(groupId=group['id'], receiptRelationId=relation['id'], invoiceLineId=line['id'])
