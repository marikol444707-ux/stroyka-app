"""Read-only invoice deadlines; visibility is established by the caller."""
import datetime as dt
from zoneinfo import ZoneInfo

from .payment_schedule import schedule_projection, schedule_paid_amount


def business_today():
    return dt.datetime.now(ZoneInfo('Europe/Moscow')).date()


def payment_deadline(invoice, today=None):
    today = today or business_today()
    result = {'schemaVersion': 1, 'asOf': today.isoformat(),
              'invoiceId': invoice['invoice_id'], 'status': 'review_required', 'stages': []}
    try:
        projection = schedule_projection(invoice['snapshot_json'], invoice['amount'],
                                         invoice.get('invoice_date'), invoice.get('accepted_at'))
        if projection is None:
            return None
        paid = schedule_paid_amount(invoice.get('paid_amount') or 0)
        total = schedule_paid_amount(invoice['amount'])
        if paid > total or (invoice['status'] == 'Оплачен' and paid < total):
            return result
        for index, stage in enumerate(projection['stages']):
            if stage['event'] != 'after_acceptance':
                continue
            remaining = (dt.date.fromisoformat(stage['dueDate']) - today).days if stage['dueDate'] else None
            result['stages'].append({**stage, 'stageIndex': index, 'remainingDays': remaining})
        result['status'] = ('cancelled' if invoice['status'] == 'Аннулирован' else
                            'paid' if paid >= total else
                            'active' if invoice.get('accepted_at') else 'waiting_acceptance')
        return result if result['stages'] else None
    except (ValueError, TypeError, KeyError):
        return result


# Exact parent identities prevent cross-company/offer projections on corrupt rows.
INVOICE_DEADLINE_SELECT = '''
 SELECT i.id AS invoice_id,i.company_id,i.contract_version_id,i.offer_id,i.request_id,i.supplier_id,
        i.project_name,COALESCE(NULLIF(i.work_package,''),'Основная') AS package_name,i.amount,i.paid_amount,
        i.status,i.invoice_number,COALESCE(i.invoice_date,i.created_at::date) AS invoice_date,
        v.snapshot_json,
        receipt.accepted_at
 FROM supplier_invoices i
 JOIN supplier_contract_versions v ON v.id=i.contract_version_id
   AND v.company_id=i.company_id AND v.offer_id=i.offer_id
 JOIN supplier_offers o ON o.id=i.offer_id AND o.company_id=i.company_id
   AND o.supplier_id=i.supplier_id AND o.request_id=i.request_id
 JOIN supply_requests r ON r.id=o.request_id AND r.company_id=o.company_id AND i.project_name=r.project
 LEFT JOIN LATERAL (
   SELECT CASE WHEN COUNT(*)>0 AND BOOL_AND(d.received_at IS NOT NULL
     AND COALESCE(d.status IN ('Принято','Проблема'),FALSE)) THEN MAX(d.received_at) END AS accepted_at
   FROM supply_deliveries d WHERE d.source_supplier_invoice_id=i.id
     AND d.company_id=i.company_id AND d.contract_version_id=i.contract_version_id
     AND d.offer_id=i.offer_id AND d.supplier_id=i.supplier_id AND d.request_id=i.request_id
     AND d.project=i.project_name AND COALESCE(NULLIF(d.work_package,''),'Основная')=COALESCE(NULLIF(i.work_package,''),'Основная')
 ) receipt ON TRUE
'''


def enrich_invoice_deadlines(cur, invoices):
    """Enrich already-authorized invoice rows; never use heuristic receipt links."""
    if not invoices:
        return
    cur.execute('''SELECT source.id AS source_id,source.company_id AS source_company_id,
        source.contract_version_id AS saved_contract_id,invoice.* FROM supplier_invoices source
        LEFT JOIN (''' + INVOICE_DEADLINE_SELECT + ''') invoice ON invoice.invoice_id=source.id
        WHERE source.id=ANY(%s)''', ([row['id'] for row in invoices],))
    rows = {(row['source_id'], row['source_company_id']): row for row in cur.fetchall()}
    today = business_today()
    for invoice in invoices:
        row = rows.get((invoice['id'], invoice['company_id']))
        invoice['paymentDeadline'] = None
        if row and row['invoice_id'] and row['company_id'] == invoice['company_id']:
            invoice['paymentDeadline'] = payment_deadline(row, today)
        elif row and row['saved_contract_id']:
            invoice['paymentDeadline'] = {'schemaVersion': 1, 'asOf': today.isoformat(),
                'invoiceId': invoice['id'], 'status': 'review_required', 'stages': []}


def enrich_warehouse_deadlines(cur, invoices):
    """Project deadlines only through the persisted, exact incoming-document link."""
    if not invoices:
        return
    cur.execute('''SELECT w.id AS warehouse_id,w.company_id AS warehouse_company_id,
        w.project AS warehouse_project,w.location AS warehouse_location,w.supplier_id AS warehouse_supplier_id,
        w.supply_delivery_id AS warehouse_delivery_id,w.supply_request_id AS warehouse_request_id,
        w.supplier_invoice_id AS linked_invoice_id,invoice.* FROM warehouse_invoices w
        LEFT JOIN (''' + INVOICE_DEADLINE_SELECT + ''') invoice
          ON invoice.invoice_id=w.supplier_invoice_id AND invoice.company_id=w.company_id
         AND invoice.supplier_id=w.supplier_id
         AND invoice.project_name=COALESCE(NULLIF(w.project,''),
             CASE WHEN w.location<>'Основной склад' THEN w.location END,'')
         AND (w.supply_request_id IS NULL OR w.supply_request_id=invoice.request_id)
         AND ((w.supply_delivery_id IS NULL AND COALESCE(w.source_type,'')<>'supply_delivery')
           OR EXISTS (SELECT 1 FROM supply_deliveries d WHERE d.id=w.supply_delivery_id
             AND d.source_supplier_invoice_id=invoice.invoice_id AND d.company_id=invoice.company_id
             AND d.contract_version_id=invoice.contract_version_id AND d.offer_id=invoice.offer_id
             AND d.request_id=invoice.request_id AND d.supplier_id=invoice.supplier_id
             AND d.project=invoice.project_name
             AND COALESCE(NULLIF(d.work_package,''),'Основная')=invoice.package_name))
        WHERE w.id=ANY(%s) AND COALESCE(w.source_type,'')<>'warehouse_movement'
        ''', ([row['id'] for row in invoices],))
    rows = {(row['warehouse_id'], row['warehouse_company_id']): row for row in cur.fetchall()}
    today = business_today()
    for invoice in invoices:
        row = rows.get((invoice['id'], invoice['companyId']))
        invoice['paymentDeadline'] = None
        if invoice.get('accountingRequired') is False:
            continue
        if row and any((row.get(stored) or '') != (invoice.get(visible) or '') for stored, visible in (
                ('warehouse_project', 'project'), ('warehouse_location', 'location'),
                ('warehouse_supplier_id', 'supplierId'), ('linked_invoice_id', 'supplierInvoiceId'),
                ('warehouse_delivery_id', 'supplyDeliveryId'), ('warehouse_request_id', 'supplyRequestId'))):
            # The second read must still describe the same authorized document.
            continue
        if row and row['invoice_id'] and row['company_id'] == invoice['companyId']:
            invoice['paymentDeadline'] = payment_deadline(row, today)
        elif row and row['linked_invoice_id']:
            invoice['paymentDeadline'] = {'schemaVersion': 1, 'asOf': today.isoformat(),
                'invoiceId': None, 'status': 'review_required', 'stages': []}


def enrich_delivery_deadlines(cur, deliveries):
    if not deliveries:
        return
    cur.execute('''SELECT d.id AS delivery_id,d.company_id AS delivery_company_id,
        d.contract_version_id AS saved_contract_id,invoice.* FROM supply_deliveries d
        LEFT JOIN (''' + INVOICE_DEADLINE_SELECT + ''') invoice
          ON invoice.invoice_id=d.source_supplier_invoice_id AND invoice.company_id=d.company_id
         AND invoice.contract_version_id=d.contract_version_id
         AND invoice.offer_id=d.offer_id AND invoice.request_id=d.request_id AND invoice.supplier_id=d.supplier_id
         AND invoice.project_name=d.project AND invoice.package_name=COALESCE(NULLIF(d.work_package,''),'Основная')
        WHERE d.id=ANY(%s)''', ([row['id'] for row in deliveries],))
    rows = {row['delivery_id']: row for row in cur.fetchall()}
    today = business_today()
    for delivery in deliveries:
        row = rows.get(delivery['id'])
        # Never attach another company's data, even if an upstream row is corrupt.
        if row and row['company_id'] == delivery['companyId'] and row['invoice_id']:
            delivery['paymentDeadline'] = payment_deadline(row, today)
        elif row and row['saved_contract_id']:
            delivery['paymentDeadline'] = {'schemaVersion': 1, 'asOf': today.isoformat(),
                'invoiceId': None, 'status': 'review_required', 'stages': []}
        else:
            delivery['paymentDeadline'] = None
