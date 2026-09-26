"""Live allocation authority; caller owns the transaction and its lifetime.

No registration, DDL, business writes, repair, or transaction-control commands.
The selected company is a trusted route argument, not a field in allocation rows.
Receipt admission/schema readiness remain separate dependencies. Finance roles
and project/package policy are reused unchanged from build_payment_access.
"""
import json

from fastapi import HTTPException

from .access import build_payment_access
from .commands import positive_id
from .documents import build_document_resolver


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Принадлежность или приёмки распределения требуют сверки')


def _package(raw):
    # Do not run a SQL parser on potentially corrupt items: a domain conflict
    # must leave the caller's transaction usable without a savepoint/rollback.
    class PackageObject(dict):
        duplicate_package_key = False

    def package_object(pairs):
        result = PackageObject()
        for key, value in pairs:
            if key in ('workPackage', 'work_package') and key in result:
                result.duplicate_package_key = True
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('Invalid JSON constant')

    try:
        rows = json.loads(raw, object_pairs_hook=package_object, parse_constant=invalid_constant)
    except (TypeError, ValueError):
        raise HTTPException(409, 'Пакет приёмки требует сверки') from None
    _require(isinstance(rows, list) and bool(rows))
    packages = set()
    for row in rows:
        # Match 0019: only top-level item package keys must be unique;
        # unrelated/nested metadata is not part of package identity.
        _require(isinstance(row, PackageObject) and not row.duplicate_package_key)
        values = [row[key] for key in ('workPackage', 'work_package') if key in row]
        _require(values and all(isinstance(value, str) and value == value.strip(' \t\r\n') for value in values))
        _require(len(set(values)) == 1)
        packages.add(values[0])
    _require(len(packages) == 1)
    return packages.pop()


def build_allocation_access(deps, operation='update'):
    access = build_payment_access(deps, operation=operation)
    resolve_invoice = build_document_resolver(access)

    def authorize(cur, actor_id, company_id, command):
        positive_id(actor_id)
        positive_id(company_id)
        if not isinstance(command, dict):
            raise HTTPException(422, 'Нужен идентификатор группы распределения')
        group_id = positive_id(command.get('groupId'), 9223372036854775807)
        if cur.connection.autocommit:
            raise RuntimeError('Allocation authority requires a caller-owned transaction')
        cur.execute('SHOW transaction_isolation')
        _require(cur.fetchone()['transaction_isolation'] == 'read committed')
        # Reentrant with allocation_store._enter; safe for direct internal use.
        cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
        # Current selected-company authority precedes even schema discovery.
        # Its user/company/membership locks pin this actor until caller exit.
        actor = access(cur, actor_id, company_id, '', '')

        def scope_access(project, package):
            deps['require_project_access'](actor, project)
            if not deps['has_package_access'](actor, package or 'Основная'):
                raise HTTPException(403, 'Нет доступа к пакету документа')

        cur.execute('''SELECT d.* FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_documents d ON d.id=g.invoice_record_id AND d.company_id=g.company_id
            WHERE g.id=%s AND g.company_id=%s''', (group_id, company_id))
        baseline = cur.fetchone()
        if not baseline:
            raise HTTPException(404, 'Группа выбранной компании не найдена')
        cur.execute('SELECT * FROM supplier_invoices WHERE id=%s', (baseline['document_id'],))
        invoice = cur.fetchone()
        owned = invoice and invoice['company_id'] == company_id
        project = invoice['project_name'] or '' if owned else ''
        package = invoice['work_package'] or '' if owned else ''
        # Stored payer is only a preliminary denial boundary. Canonical payer
        # is independently resolved from the live bound contract below.
        if baseline['payer_company_id'] != company_id:
            actor = access(cur, actor_id, company_id, project, package,
                           payer_company_id=baseline['payer_company_id'])
        else:
            scope_access(project, package)
        _require(owned and baseline['document_kind'] == 'invoice')

        # Preserve canonical invoice -> warehouse lock order. Refresh scopes
        # after waiting, before inspecting any receipt integrity details.
        cur.execute('SELECT * FROM supplier_invoices WHERE id=%s FOR UPDATE', (invoice['id'],))
        invoice = cur.fetchone()
        _require(invoice is not None and invoice['company_id'] == company_id)
        project, package = invoice['project_name'] or '', invoice['work_package'] or ''
        scope_access(project, package)

        cur.execute('''SELECT * FROM supplier_payment_receipt_relations
            WHERE group_id=%s ORDER BY warehouse_invoice_id,id LIMIT 10001''', (group_id,))
        relations = cur.fetchall()
        _require(len(relations) <= 10000)
        warehouse_ids = [row['warehouse_invoice_id'] for row in relations]
        cur.execute('''SELECT w.*,to_jsonb(w) AS frozen FROM warehouse_invoices w
            WHERE id=ANY(%s::int[]) ORDER BY id FOR UPDATE''', (warehouse_ids,))
        warehouses = {row['id']: row for row in cur.fetchall()}
        delivery_ids = [row['supply_delivery_id'] for row in warehouses.values() if row['supply_delivery_id'] is not None]
        cur.execute('''SELECT d.*,to_jsonb(d) AS frozen FROM supply_deliveries d
            WHERE id=ANY(%s::int[]) ORDER BY id FOR SHARE''', (delivery_ids,))
        deliveries = {row['id']: row for row in cur.fetchall()}
        # ALL live raw scopes first, including omitted receipts. Malformed JSON
        # on one receipt must not mask denial on another receipt's live project.
        for row in warehouses.values():
            if row['company_id'] == company_id:
                scope_access(row['project'] or row['location'] or '', package)
        for row in deliveries.values():
            if row['company_id'] == company_id:
                scope_access(row['project'] or '', row['work_package'] or '')
        packages, malformed = {}, False
        for wid, row in warehouses.items():
            if row['company_id'] != company_id:
                continue
            try:
                packages[wid] = _package(row['items'])
            except HTTPException:
                malformed = True
                continue
            scope_access(row['project'] or row['location'] or '', packages[wid])
        _require(not malformed)

        # Reject any legacy pair before the general resolver could parse that
        # warehouse or invoke its SQL package/savepoint helper.
        cur.execute('''SELECT EXISTS(SELECT 1 FROM warehouse_invoices WHERE supplier_invoice_id=%s)
            OR EXISTS(SELECT 1 FROM supplier_payment_attachments WHERE invoice_record_id=%s) AS linked''',
            (invoice['id'], baseline['id']))
        _require(invoice['warehouse_invoice_id'] is None and not cur.fetchone()['linked'])
        context = resolve_invoice(cur, actor_id, company_id, dict(documentKind='invoice', documentId=invoice['id']))
        _require(len(context['documents']) == 1)
        doc = context['documents'][0]
        _require(doc['kind'] == 'invoice' and doc['id'] == invoice['id'] and all(
            baseline[stored] == doc[live] for stored, live in (
                ('company_id', 'companyId'), ('payer_company_id', 'payerCompanyId'), ('supplier_id', 'supplierId'),
                ('project_name', 'projectName'), ('work_package', 'workPackage'), ('amount', 'amount'))))
        cur.execute('''SELECT COALESCE(SUM(delta),0) AS total FROM supplier_payment_impacts
            WHERE document_record_id=%s AND company_id=%s''', (baseline['id'], company_id))
        _require(baseline['opening_paid'] + cur.fetchone()['total'] == doc['paidAmount'])
        cur.execute('''SELECT EXISTS(SELECT 1 FROM supplier_invoices WHERE warehouse_invoice_id=ANY(%s::int[]))
            OR EXISTS(SELECT 1 FROM supplier_payment_documents
                      WHERE document_kind='warehouse' AND document_id=ANY(%s::int[])) AS linked''',
            (warehouse_ids, warehouse_ids))
        _require(not cur.fetchone()['linked'])
        _require(sum(row['amount'] for row in relations) <= doc['amount'])
        for relation in relations:
            row = warehouses.get(relation['warehouse_invoice_id'])
            _require(relation['company_id'] == company_id and row is not None and row['company_id'] == company_id)
            delivery = deliveries.get(row['supply_delivery_id'])
            _require(delivery is not None and delivery['company_id'] == company_id)
            _require(relation['source_delivery_id'] == delivery['id'])
            _require(row['supplier_id'] == doc['supplierId'] and delivery['supplier_id'] == doc['supplierId']
                     and (row['project'] or row['location'] or '') == doc['projectName']
                     and (delivery['project'] or '') == doc['projectName']
                     and packages[row['id']] == doc['workPackage']
                     and (delivery['work_package'] or '') == doc['workPackage'])
            _require(relation['amount'] > 0 and row['total_base'] == relation['amount']
                     and row['total_with_vat'] == relation['amount'] and row['total_vat'] == 0
                     and (row['paid_amount'] or 0) == 0 and row['supplier_invoice_id'] is None
                     and row['status'] == 'Принята' and delivery['status'] == 'Принято'
                     and delivery['quality_status'] == 'Принято' and delivery['received_at'] is not None)
            _require(context['contract'] is not None and delivery['source_supplier_invoice_id'] == invoice['id']
                     and delivery['contract_version_id'] == context['contract']['contractVersionId']
                     and delivery['offer_id'] == invoice['offer_id'] and delivery['request_id'] == invoice['request_id']
                     and row['source_type'] == 'supply_delivery' and row['source_id'] == str(delivery['id'])
                     and row['supply_request_id'] == delivery['request_id'])
            _require(relation['provenance'] == dict(deliveryId=delivery['id'], sourceSupplierInvoiceId=invoice['id'],
                warehouseInvoiceId=row['id'], warehouse=row['frozen'], delivery=delivery['frozen']))
        return context

    return authorize
