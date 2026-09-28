"""Opt-in bridge for proven invoice-only receipts; caller owns locks and authority."""
import os
from fastapi import HTTPException
from psycopg2.errors import CheckViolation


def managed_receipts_enabled():
    return os.getenv('SUPPLIER_PARTIAL_RECEIPTS_ENABLED') == '1'


def supports_managed_receipts(cur, company_id, invoice_id):
    if not managed_receipts_enabled() or not invoice_id:
        return False
    cur.execute("SELECT to_regclass('public.supplier_receipt_line_proofs') AS ready")
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Не установлена схема частичной приёмки')
    cur.execute('''SELECT d.id FROM supplier_payment_documents d
        JOIN supplier_invoice_line_specs s ON s.invoice_id=d.document_id AND s.company_id=d.company_id
        WHERE d.company_id=%s AND d.document_kind='invoice' AND d.document_id=%s''',
        (company_id, invoice_id))
    root = cur.fetchone()
    if not root:
        return False
    try:
        cur.execute('SELECT public.supplier_allocation_root(%s,%s)', (root['id'], company_id))
    except CheckViolation:
        raise HTTPException(409, 'Связи счёта требуют сверки перед частичной приёмкой') from None
    return True


def verify_existing_receipt(cur, company_id, invoice_id, warehouse_id):
    cur.execute('''SELECT r.id FROM supplier_payment_receipt_relations r
        JOIN supplier_payment_allocation_groups g ON g.id=r.group_id AND g.company_id=r.company_id
        JOIN supplier_payment_documents d ON d.id=g.invoice_record_id AND d.company_id=g.company_id
        JOIN supplier_receipt_line_proofs p ON p.receipt_relation_id=r.id AND p.company_id=r.company_id
        WHERE r.warehouse_invoice_id=%s AND r.company_id=%s AND d.document_kind='invoice'
            AND d.document_id=%s''', (warehouse_id, company_id, invoice_id))
    if not cur.fetchone():
        raise HTTPException(409, 'Накладная не имеет подтверждённой связи со счётом')


def finalize_receipt(cur, delivery, warehouse_id):
    invoice_id = delivery.get('source_supplier_invoice_id')
    if supports_managed_receipts(cur, delivery.get('company_id'), invoice_id):
        from .receipt_line_proofs import register_receipt_line
        # Run after stock, ownership and quality writes: the proof freezes the source.
        return register_receipt_line(cur, company_id=delivery['company_id'],
                                     invoice_id=invoice_id, warehouse_id=warehouse_id)


def receipt_settlement_ids(cur, warehouse_ids):
    """Project only invoice identity for already authorized warehouse rows (tuple cursor)."""
    if not warehouse_ids:
        return {}
    cur.execute("SELECT to_regclass('public.supplier_payment_receipt_relations')")
    if not cur.fetchone()[0]:
        return {}
    cur.execute('''SELECT w.id,d.document_id FROM warehouse_invoices w
        JOIN supplier_payment_receipt_relations r ON r.warehouse_invoice_id=w.id AND r.company_id=w.company_id
        JOIN supplier_payment_allocation_groups g ON g.id=r.group_id AND g.company_id=r.company_id
        JOIN supplier_payment_documents d ON d.id=g.invoice_record_id AND d.company_id=g.company_id
        WHERE w.id=ANY(%s) AND d.document_kind='invoice' ''', (warehouse_ids,))
    return dict(cur.fetchall())
