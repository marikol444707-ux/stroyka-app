"""Tax amount adapter for authorized, locked, invoice-owned receipt transactions."""
import os
from decimal import Decimal
from fastapi import HTTPException
from .receipt_tax import receipt_tax_slice


def require_vat_schema(cur):
    cur.execute("SELECT to_regclass('supplier_vat_guard_versions') IS NOT NULL AS ready")
    if not cur.fetchone()['ready']:
        raise HTTPException(503,'Не установлена схема НДС по строкам поступления')


def receipt_vat(cur, delivery, quantity):
    """Return None for legacy/no-tax receipts; never infer tax or a payer."""
    if os.getenv('SUPPLIER_PARTIAL_RECEIPTS_ENABLED')!='1':
        return None
    invoice_id=delivery.get('source_supplier_invoice_id')
    if not invoice_id:
        return None
    cur.execute('''SELECT i.vat_amount,EXISTS(SELECT 1 FROM supplier_invoice_line_specs s
        WHERE s.invoice_id=i.id AND s.company_id=i.company_id AND s.source_payload->>'vatIncluded'='true') AS declared_tax
        FROM supplier_invoices i WHERE i.id=%s AND i.company_id=%s''',
                (invoice_id,delivery['company_id']))
    invoice=cur.fetchone()
    if not invoice or (not invoice['vat_amount'] and not invoice['declared_tax']):
        return None
    if os.getenv('SUPPLIER_VAT_RECEIPTS_ENABLED')!='1':
        raise HTTPException(409,'Приёмка с НДС по строкам пока отключена')
    require_vat_schema(cur)
    cur.execute('SELECT supplier_allocation_lock(%s)',(delivery['company_id'],))
    cur.execute('''SELECT l.id,l.amount,l.vat_amount,l.unit_price FROM supplier_invoice_lines l
        JOIN supplier_invoice_line_specs s ON s.id=l.spec_id AND s.company_id=l.company_id
        JOIN supplier_payment_documents d ON d.document_kind='invoice' AND d.document_id=s.invoice_id AND d.company_id=s.company_id
        WHERE s.invoice_id=%s AND s.company_id=%s AND l.material_name=%s AND l.unit=%s
          AND l.work_package=%s AND l.unit_price=%s FOR UPDATE OF l''',
        (invoice_id,delivery['company_id'],delivery['material_name'],delivery['unit'],
         delivery.get('work_package') or '',delivery['price_per_unit']))
    lines=cur.fetchall()
    if len(lines)!=1:
        raise HTTPException(409,'Для приёмки НДС нужна подтверждённая строка нового счёта')
    line=lines[0]
    cur.execute('SELECT COALESCE(sum(amount),0) AS amount FROM supplier_receipt_line_proofs WHERE invoice_line_id=%s', (line['id'],))
    previous=cur.fetchone()['amount']
    if delivery.get('quality_status') in ('Брак','Несоответствие'):
        previous=Decimal(0)
    try:
        return receipt_tax_slice(line_amount=line['amount'],line_vat_amount=line['vat_amount'],
            previous_amount=previous,received_amount=Decimal(str(quantity))*line['unit_price'])
    except ValueError:
        raise HTTPException(409,'НДС и сумма поступления не соответствуют строке счёта') from None
