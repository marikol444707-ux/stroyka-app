"""Authenticated read-only mixed-package review; never admits a baseline write."""
import hashlib
from fastapi import HTTPException
from .commands import positive_id
from .documents import TABLES, _discover, _require
from .contract_context import load_invoice_contract
from .legacy_package_review import package_review, mixed_reconciliation_preview


def lock_authorized_pair(cur, authorize, actor_id, company_id, invoice_id):
    positive_id(actor_id); positive_id(company_id); positive_id(invoice_id)
    if cur.connection.autocommit:
        raise RuntimeError('Mixed review requires a transaction')
    cur.execute('SHOW transaction_isolation')
    _require(cur.fetchone()['transaction_isolation'] == 'read committed')
    cur.execute('SELECT company_id,project_name,work_package FROM supplier_invoices WHERE id=%s', (invoice_id,))
    root = cur.fetchone()
    if not root or root['company_id'] != company_id:
        raise HTTPException(404, 'Счёт выбранной компании не найден')
    authorize(cur, actor_id, company_id, root['project_name'], root['work_package'] or '', payer_company_id=company_id)
    discovered = _discover(cur, 'invoice', invoice_id)
    locked = {}
    for kind, (table, _) in TABLES.items():
        cur.execute(f'SELECT * FROM {table} WHERE id=ANY(%s::int[]) ORDER BY id FOR UPDATE',
                    ([row['id'] for row in discovered[kind]],))
        locked[kind] = list(cur.fetchall())
    _require(locked == _discover(cur, 'invoice', invoice_id))
    _require(all(row['company_id'] == company_id for rows in locked.values() for row in rows))
    _require(len(locked['invoice']) == 1 and len(locked['warehouse']) == 1)
    invoice, warehouse = locked['invoice'][0], locked['warehouse'][0]
    _require(invoice['warehouse_invoice_id'] == warehouse['id']
             and warehouse['supplier_invoice_id'] == invoice['id'])
    payer = company_id
    if invoice.get('contract_version_id') is not None:
        payer = load_invoice_contract(cur, invoice_id, company_id)['payerCompanyId']
    else:
        _require(invoice.get('offer_id') is None)
    actor = authorize(cur, actor_id, company_id, invoice['project_name'], invoice['work_package'] or '', payer_company_id=payer)
    cur.execute('SELECT items::text AS items FROM warehouse_invoices WHERE id=%s', (warehouse['id'],))
    raw = cur.fetchone()['items']
    try:
        packages = package_review(raw)
    except ValueError:
        raise HTTPException(409, 'Состав пакетов накладной требует сверки') from None
    for group in packages['groups']:
        authorize(cur, actor_id, company_id, warehouse['project'] or warehouse['location'] or '',
                  group['workPackage'], payer_company_id=payer)
    return invoice, warehouse, raw, payer, actor


def review(cur, authorize, actor_id, company_id, invoice_id):
    invoice, warehouse, raw, _, _ = lock_authorized_pair(
        cur, authorize, actor_id, company_id, invoice_id)
    # No amounts or package list is returned until every current scope passes.
    cur.execute('''SELECT document_kind,document_id FROM supplier_payment_documents
        WHERE (document_kind='invoice' AND document_id=%s)
           OR (document_kind='warehouse' AND document_id=%s)''', (invoice_id, warehouse['id']))
    _require(not cur.fetchall())
    cur.execute('SELECT id FROM supplier_invoice_line_specs WHERE invoice_id=%s', (invoice_id,))
    _require(not cur.fetchone())
    def common(row, project):
        return dict(id=row['id'], companyId=row['company_id'], supplierId=row['supplier_id'],
                    projectName=project, registered=False, paidAmount=row['paid_amount'])
    source = dict(common(invoice, invoice['project_name']), amount=invoice['amount'],
                  workPackage=invoice['work_package'] or '', warehouseId=invoice['warehouse_invoice_id'])
    receipt = dict(common(warehouse, warehouse['project'] or warehouse['location'] or ''),
                   amount=warehouse['total_with_vat'] or warehouse['total_base'], invoiceId=warehouse['supplier_invoice_id'])
    result = mixed_reconciliation_preview(source, [receipt], raw)
    if result['scenario'] != 'mixedPackageLegacyPair':
        raise HTTPException(409, 'Связи, реквизиты или остатки документов требуют сверки')
    evidence = source_evidence(cur, company_id, invoice_id, warehouse['id'])
    return dict(result, companyId=company_id, invoiceId=invoice_id, warehouseId=warehouse['id'],
                evidenceHash=evidence['hash'],
                readOnly=True, confirmationAvailable=False)


def source_evidence(cur, company_id, invoice_id, warehouse_id):
    """Internal locked-source serialization; never return snapshots to a client."""
    cur.execute('''SELECT to_jsonb(i)::text AS invoice, to_jsonb(w)::text AS warehouse
        FROM supplier_invoices i JOIN warehouse_invoices w ON w.id=%s
        WHERE i.id=%s AND i.company_id=%s AND w.company_id=%s''',
        (warehouse_id,invoice_id,company_id,company_id))
    row=cur.fetchone()
    _require(row is not None)
    return dict(row, hash=hashlib.sha256((row['invoice']+'\n'+row['warehouse']).encode('utf-8')).hexdigest())
