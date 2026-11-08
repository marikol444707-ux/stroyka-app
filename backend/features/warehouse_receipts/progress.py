"""Read-only accepted/remaining quantities from existing immutable line proofs."""
import os
from decimal import Decimal


def invoice_progress(cur, batch):
    # Never activate or register a ledger baseline from a preview.
    if os.getenv('SUPPLIER_PARTIAL_RECEIPTS_ENABLED') != '1':
        return {}
    source = batch.get('documentParties', {}).get('sourceInvoiceId')
    if type(source) is not int or source <= 0:
        return {}
    cur.execute("SELECT to_regclass('public.supplier_receipt_line_proofs') IS NOT NULL AND to_regclass('public.supplier_invoice_line_specs') IS NOT NULL AS ready")
    if not (cur.fetchone() or {}).get('ready'):
        return {}
    # Only lines proved by the already authorized deliveries are exposed; no
    # invoice-wide totals that could reveal another package's purchases.
    cur.execute('''SELECT d.id AS delivery_id,l.id AS line_id,l.quantity,
        COALESCE((SELECT SUM(p.quantity) FROM supplier_receipt_line_proofs p
                  WHERE p.invoice_line_id=l.id AND p.company_id=l.company_id),0) AS accepted
        FROM supply_deliveries d
        JOIN supplier_invoice_line_specs s ON s.invoice_id=d.source_supplier_invoice_id
          AND s.company_id=d.company_id
        JOIN supplier_invoice_lines l ON l.spec_id=s.id AND l.company_id=s.company_id
          AND l.material_name=d.material_name AND l.unit=d.unit
          AND l.work_package=COALESCE(d.work_package,'') AND l.unit_price=d.price_per_unit
        WHERE d.company_id=%s AND d.source_supplier_invoice_id=%s AND d.id=ANY(%s)
          AND EXISTS(SELECT 1 FROM supplier_payment_documents pd
            WHERE pd.company_id=s.company_id AND pd.document_kind='invoice' AND pd.document_id=s.invoice_id)
        ORDER BY d.id,l.id''', (batch['companyId'],source,[line['id'] for line in batch['lines']]))
    result, ambiguous = {}, set()
    for row in cur.fetchall():
        identity=row['delivery_id']
        if identity in result:
            ambiguous.add(identity)
            continue
        ordered, accepted=Decimal(str(row['quantity'])),Decimal(str(row['accepted']))
        if not ordered.is_finite() or not accepted.is_finite() or ordered <= 0 or accepted < 0 or accepted > ordered:
            ambiguous.add(identity)
            continue
        result[identity]={'sourceInvoiceId':source,'orderedQuantity':str(ordered),
                          'acceptedQuantity':str(accepted),'remainingQuantity':str(ordered-accepted)}
    return {key:value for key,value in result.items() if key not in ambiguous}
