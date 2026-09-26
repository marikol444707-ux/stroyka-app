"""Optional 0018 mirrors: physical documents are not extra ledger impacts.

Call within the engine's company-serialized transaction, after current authority
and document locks. This module neither creates attachments nor authorizes them.
"""
from fastapi import HTTPException

from .documents import warehouse_payment_package


def attachments_available(cur):
    cur.execute("SELECT to_regclass('public.supplier_payment_attachments') IS NOT NULL AS available")
    return cur.fetchone()['available']


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Присоединённая накладная и исходный счёт требуют сверки')


def _identity(record):
    return tuple(record[key] for key in
                 ('company_id', 'payer_company_id', 'supplier_id', 'project_name', 'work_package', 'amount'))


def balance_source(cur, record, company_id):
    """Return the financial root, keeping the mirror's own opening immutable."""
    _require(record['company_id'] == company_id)
    if record['document_kind'] != 'warehouse' or not attachments_available(cur):
        return record
    cur.execute('''SELECT a.invoice_record_id FROM supplier_payment_attachments a
                   WHERE a.company_id=%s AND a.warehouse_record_id=%s''', (company_id, record['id']))
    attachment = cur.fetchone()
    if not attachment:
        return record
    cur.execute('SELECT * FROM supplier_payment_documents WHERE id=%s AND company_id=%s',
                (attachment['invoice_record_id'], company_id))
    source = cur.fetchone()
    _require(source and source['document_kind'] == 'invoice' and _identity(source) == _identity(record))
    return source


def canonical_records(cur, records, company_id, command):
    """Validate the complete physical pair; return invoice-only accounting keys.

    Existing 0017 pairs/standalone documents are returned unchanged. Attached
    roots must be addressed as invoices and accompanied by their exact mirror.
    Replayed operations are handled before this new-operation eligibility check.
    """
    if not attachments_available(cur):
        return records
    record_ids = [record['id'] for record in records]
    cur.execute('''SELECT * FROM supplier_payment_attachments WHERE company_id=%s
                   AND (invoice_record_id=ANY(%s::bigint[]) OR warehouse_record_id=ANY(%s::bigint[]))''',
                (company_id, record_ids, record_ids))
    attachments = cur.fetchall()
    if not attachments:
        return records
    _require(len(attachments) == 1)
    attachment = attachments[0]
    _require(len(records) == 2 and set(record_ids) ==
             {attachment['invoice_record_id'], attachment['warehouse_record_id']})
    by_id = {record['id']: record for record in records}
    source, target = by_id[attachment['invoice_record_id']], by_id[attachment['warehouse_record_id']]
    _require(source['company_id'] == company_id and target['company_id'] == company_id
             and source['document_kind'] == 'invoice' and target['document_kind'] == 'warehouse'
             and _identity(source) == _identity(target)
             and command['documentKind'] == 'invoice' and command['documentId'] == source['document_id'])

    # Recheck real rows, not only callback snapshots. Never infer ownership from
    # display names or accept a substituted mirror. Cancellation blocks new
    # payments, not undoing an existing payment; all identity checks still apply.
    cur.execute('''SELECT company_id,supplier_id,COALESCE(project_name,'') AS project_name,
                          COALESCE(work_package,'') AS work_package,amount,
                          COALESCE(paid_amount,0) AS paid_amount,warehouse_invoice_id,status
                   FROM supplier_invoices WHERE id=%s AND company_id=%s FOR UPDATE''',
                (source['document_id'], company_id))
    invoice = cur.fetchone()
    cur.execute('''SELECT company_id,supplier_id,
                          COALESCE(NULLIF(project,''),location,'') AS project_name,
                          items,COALESCE(NULLIF(total_with_vat,0),total_base) AS amount,
                          COALESCE(paid_amount,0) AS paid_amount,supplier_invoice_id,status
                   FROM warehouse_invoices WHERE id=%s AND company_id=%s FOR UPDATE''',
                (target['document_id'], company_id))
    warehouse = cur.fetchone()
    if warehouse:
        warehouse['work_package'] = warehouse_payment_package(cur, warehouse['items'], legacy_literal=True)
    _require(invoice and warehouse
             and invoice['warehouse_invoice_id'] == target['document_id']
             and warehouse['supplier_invoice_id'] == source['document_id'])
    if command['kind'] != 'reversal':
        _require(invoice['status'] != 'Аннулирован' and warehouse['status'] != 'Аннулирована')
    for live, record in ((invoice, source), (warehouse, target)):
        _require(all(live[key] == record[key] for key in
                     ('company_id', 'supplier_id', 'project_name', 'work_package', 'amount')))
    cur.execute('''SELECT COALESCE(SUM(delta),0) AS total FROM supplier_payment_impacts
                   WHERE document_record_id=%s AND company_id=%s''', (source['id'], company_id))
    expected = source['opening_paid'] + cur.fetchone()['total']
    _require(invoice['paid_amount'] == warehouse['paid_amount'] == expected)
    return [source]
