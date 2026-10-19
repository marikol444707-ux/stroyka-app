"""Tenant-authorized, read-only physical receipt preview. Never a posting proof."""
import json
import re
from typing import Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException

from ..supplier_offers.delivery_document import load_delivery_document_projections
from .duplicate_guard import normalize_invoice_date, normalize_invoice_number


def _positive(value, field):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value or '')):
        raise HTTPException(400, f'{field}: требуется положительный идентификатор')
    return int(value)


def _review():
    return {'status': 'review', 'postingAllowed': False,
            'reason': 'Документы поставки требуют сверки'}


def _originals(cur, data, company_id, actor, deps):
    urls = data.get('originalUrls')
    if not isinstance(urls, list) or not urls or len(urls) > 30:
        raise HTTPException(400, 'Загрузите оригинал документа')
    project = str(data.get('project') or '').strip()
    project_id = data.get('projectId')
    if project_id is not None:
        project_id = _positive(project_id, 'projectId')
    for url in urls:
        match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', url) if isinstance(url, str) else None
        if not match:
            raise HTTPException(400, 'Требуется оригинал в защищённом хранилище')
        cur.execute("""SELECT company_id,project_id FROM file_ownership
                       WHERE id=%s AND company_id=%s
                         AND COALESCE(deletion_status,'active')='active'""",
                    (int(match.group(1)), company_id))
        owner = cur.fetchone()
        if not owner or owner['company_id'] != company_id:
            raise HTTPException(403, 'Нет доступа к оригиналу документа')
        if owner.get('project_id') is not None:
            if project_id is not None and owner['project_id'] != project_id:
                raise HTTPException(403, 'Оригинал относится к другому объекту')
            cur.execute('SELECT name FROM projects WHERE id=%s AND company_id=%s',
                        (owner['project_id'], company_id))
            row = cur.fetchone()
            if not row or (project and row['name'] != project):
                raise HTTPException(403, 'Нет доступа к объекту оригинала')
            project = row['name']
            project_id = owner['project_id']
    if project_id is not None:
        cur.execute('SELECT name FROM projects WHERE id=%s AND company_id=%s', (project_id, company_id))
        row = cur.fetchone()
        if not row or (project and row['name'] != project):
            raise HTTPException(403, 'Нет доступа к объекту документа')
        project = row['name']
    if project:
        deps['require_project_or_warehouse_access'](actor, project)
    return project


def _standalone_receipts(cur, document, company_id, project, scope, params, *, identity_only=False):
    """Inspect whole authorized receipts; missing historical proof requires review.

    There is deliberately no join to today's company/supplier cards. Standalone
    receipts do not themselves freeze legal parties; only an exact saved upstream
    invoice and its immutable offer/contract can establish those identities.
    """
    from .matching import _inn, _lines
    from ..supplier_access.offer_party_snapshot import validate_offer_party_snapshot
    from ..supplier_offers.delivery_document import _verified_contract

    values = [company_id] + ([project] if project else []) + ([] if identity_only else list(params))
    cur.execute("""SELECT wi.id,wi.company_id,wi.number,wi.date,wi.supplier_id,
               wi.project,wi.items,wi.total_with_vat,wi.supplier_invoice_id
        FROM warehouse_invoices wi
        WHERE wi.company_id=%s AND wi.supply_delivery_id IS NULL
          AND COALESCE(wi.source_type,'') <> 'supply_delivery'
          AND COALESCE(wi.status,'Принята') IN ('Принята','Принято','accepted','received')
          """ + (' AND wi.project=%s' if project else '') + ('' if identity_only else """
          AND jsonb_typeof(wi.items::jsonb)='array'
          AND jsonb_array_length(wi.items::jsonb)>0
          AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(wi.items::jsonb) item
            CROSS JOIN LATERAL (SELECT wi.company_id,wi.project,
              COALESCE(NULLIF(BTRIM(COALESCE(item->>'workPackage',item->>'work_package')),''),
                       'Основная') AS work_package) d
            WHERE NOT COALESCE((""" + scope + """),FALSE))""") + ' ORDER BY wi.id', values)
    rows = [dict(row) for row in cur.fetchall()
            if row['company_id'] == company_id
            and (not project or row.get('project') == project)
            and normalize_invoice_number(row.get('number')) == normalize_invoice_number(document['waybillNumber'])
            and normalize_invoice_date(row.get('date')) == normalize_invoice_date(document['waybillDate'])]
    matches, incomplete = [], False
    incoming, _ = _lines(document['lines'], 'quantity')
    for row in rows:
        if not row.get('supplier_invoice_id') or not row.get('supplier_id'):
            incomplete = True
            continue
        cur.execute("""SELECT si.id,si.offer_id,si.request_id,o.party_snapshot_json,
                  (to_jsonb(si)->>'contract_version_id')::bigint AS contract_version_id
            FROM supplier_invoices si JOIN supplier_offers o
              ON o.id=si.offer_id AND o.company_id=si.company_id
             AND o.supplier_id=si.supplier_id AND o.request_id=si.request_id
            JOIN supply_requests r ON r.id=si.request_id AND r.company_id=si.company_id
            WHERE si.id=%s AND si.company_id=%s AND si.supplier_id=%s
              AND si.status IS DISTINCT FROM 'Аннулирован'
              AND r.project=%s""",
                    (row['supplier_invoice_id'], company_id, row['supplier_id'], row.get('project')))
        source = cur.fetchone()
        try:
            if not source:
                raise ValueError('missing source')
            if source.get('contract_version_id'):
                cur.execute("""SELECT snapshot_json,snapshot_hash FROM supplier_contract_versions
                    WHERE id=%s AND company_id=%s AND offer_id=%s""",
                            (source['contract_version_id'], company_id, source['offer_id']))
                contract = cur.fetchone()
                if not contract:
                    raise ValueError('missing contract')
                buyer, supplier, _ = _verified_contract(
                    contract['snapshot_json'], contract['snapshot_hash'],
                    source['contract_version_id'], company_id, row['supplier_id'])
            else:
                frozen = validate_offer_party_snapshot(source['party_snapshot_json'],
                    offer_id=source['offer_id'], request_id=source['request_id'],
                    company_id=company_id, supplier_id=row['supplier_id'])
                buyer, supplier = frozen['buyer'], frozen['supplier']
            if not _inn(buyer.get('inn')) or not _inn(supplier.get('inn')):
                raise ValueError('missing legal identity')
        except (ValueError, TypeError, KeyError, HTTPException):
            incomplete = True
            continue
        if (_inn(buyer['inn']) != _inn(document['buyerInn'])
                or _inn(supplier['inn']) != _inn(document['supplierInn'])):
            continue
        matches.append(row)
    if len(matches) > 1:
        return {'status': 'ambiguous', 'postingAllowed': False, 'reasons': ['multiple_existing_receipts']}
    if incomplete:
        return {'status': 'review', 'postingAllowed': False,
                'reasons': ['existing_receipt_missing_frozen_legal_identity'],
                'reason': 'Ранее сохранённая накладная требует сверки реквизитов'}
    if not matches:
        return {'status': 'no_match', 'postingAllowed': False, 'reasons': ['no_exact_legal_waybill_match']}
    if identity_only:
        return _review()
    row = matches[0]
    try:
        items = json.loads(row['items']) if isinstance(row['items'], str) else row['items']
        lines = [{'materialName': item.get('name'), 'unit': item.get('unit'),
                  'quantity': item.get('quantity')} for item in items]
        outgoing, error = _lines(lines, 'quantity')
    except (TypeError, ValueError, AttributeError):
        error = 'invalid_existing_receipt_lines'
    if error or incoming.keys() != outgoing.keys() or any(incoming[k][1] != outgoing[k][1] for k in incoming):
        return {'status': 'review', 'postingAllowed': False, 'reasons': ['existing_receipt_lines_mismatch']}
    return {'status': 'existing_receipt', 'postingAllowed': False,
            'warehouseInvoiceIds': [row['id']], 'receiptState': 'existing',
            'receipts': [{'id': row['id'], 'number': row['number'], 'date': str(row['date']),
                          'project': row.get('project') or '', 'lines': lines}],
            'reasons': ['exact_existing_receipt']}


def _payment_invoice_sources(cur, document, company_id, project, scope, params, source_id):
    """Read real payment invoices, verifying saved parties instead of live cards.

    These are source suggestions only. An invoice number/date is never used as a
    waybill number/date, and an offer-level relationship alone proves no shipment.
    """
    from .matching import _date, _inn
    from ..supplier_access.offer_party_snapshot import validate_offer_party_snapshot
    from ..supplier_offers.delivery_document import _verified_contract

    number = document.get('invoiceNumber')
    day = _date(document.get('invoiceDate'))
    supplier_inn, buyer_inn = _inn(document.get('supplierInn')), _inn(document.get('buyerInn'))
    if not supplier_inn or not buyer_inn:
        return {}, 'missing_legal_identity'
    if not isinstance(number, str) or not normalize_invoice_number(number) or not day:
        return {}, 'invalid_payment_invoice_identity'
    values = [company_id, day] + list(params)
    where = ''
    if project:
        where += ' AND r.project=%s'
        values.append(project)
    if source_id is not None:
        where += ' AND si.id=%s'
        values.append(source_id)
    cur.execute("""SELECT si.id,si.company_id,si.supplier_id,si.offer_id,si.request_id,
                 si.invoice_number,si.invoice_date,si.status,r.project,o.party_snapshot_json,
                 (to_jsonb(si)->>'contract_version_id')::bigint AS contract_version_id
        FROM supplier_invoices si JOIN supplier_offers o
          ON o.id=si.offer_id AND o.company_id=si.company_id
         AND o.supplier_id=si.supplier_id AND o.request_id=si.request_id
        JOIN supply_requests r ON r.id=si.request_id AND r.company_id=si.company_id
        WHERE si.company_id=%s AND si.invoice_date=%s
          AND si.status IS DISTINCT FROM 'Аннулирован'
          AND EXISTS (SELECT 1 FROM supply_deliveries d
            WHERE d.company_id=si.company_id AND d.supplier_id=si.supplier_id
              AND d.offer_id=si.offer_id AND d.request_id=si.request_id
              AND (to_jsonb(d)->>'source_supplier_invoice_id')::bigint=si.id
              AND (""" + scope + '))' + where + ' ORDER BY si.id', values)
    sources, incomplete = {}, False
    for row in list(cur.fetchall()):
        # Keep application-level assertions as defense in depth for query changes.
        if (row.get('company_id') != company_id or row.get('status') == 'Аннулирован'
                or (source_id is not None and row.get('id') != source_id)
                or (project and row.get('project') != project)
                or _date(row.get('invoice_date')) != day
                or normalize_invoice_number(row.get('invoice_number')) != normalize_invoice_number(number)):
            continue
        try:
            if row.get('contract_version_id') is not None:
                cur.execute('''SELECT snapshot_json,snapshot_hash FROM supplier_contract_versions
                    WHERE id=%s AND company_id=%s AND offer_id=%s''',
                    (row['contract_version_id'], company_id, row['offer_id']))
                contract = cur.fetchone()
                if not contract:
                    raise ValueError('missing contract')
                buyer, supplier, _ = _verified_contract(
                    contract['snapshot_json'], contract['snapshot_hash'],
                    row['contract_version_id'], company_id, row['supplier_id'])
            else:
                frozen = validate_offer_party_snapshot(row['party_snapshot_json'],
                    offer_id=row['offer_id'], request_id=row['request_id'],
                    company_id=company_id, supplier_id=row['supplier_id'])
                buyer, supplier = frozen['buyer'], frozen['supplier']
            if not _inn(buyer.get('inn')) or not _inn(supplier.get('inn')):
                raise ValueError('missing legal identity')
        except (ValueError, TypeError, KeyError, HTTPException):
            incomplete = True
            continue
        if _inn(buyer['inn']) == buyer_inn and _inn(supplier['inn']) == supplier_inn:
            sources[row['id']] = dict(row)
    return sources, 'payment_invoice_missing_frozen_legal_identity' if incomplete and not sources else None


def _candidate_view(batch):
    """Public choice shape, called only after whole-batch authorization."""
    return {key: batch.get(key) for key in (
        'id', 'companyId', 'supplierId', 'sourceSupplierInvoiceId', 'sourceInvoice',
        'project', 'waybillNumber', 'waybillDate', 'documentParties', 'lines')}


def _company_receipt_conflict(cur, document, company_id, *, exclude_ids=(), include_unreceived=False,
                              check_standalone=True):
    """Uniqueness guard, not a discovery endpoint: never return hidden records.

    Visibility and source-invoice filters cannot hide a previous posting. Saved
    frozen parties distinguish legal suppliers; missing proof fails closed.
    """
    from .matching import _date, _inn

    cur.execute('''SELECT d.id,d.waybill_number,d.waybill_date FROM supply_deliveries d
        WHERE d.company_id=%s AND d.waybill_date=%s
          AND NOT (d.id=ANY(%s::integer[]))''' + ('' if include_unreceived else '''
          AND (COALESCE(d.received_quantity,0)<>0 OR d.received_at IS NOT NULL
               OR d.status IN ('Принято','Проблема','accepted','received')
               OR EXISTS (SELECT 1 FROM warehouse_invoices wi
                          WHERE wi.company_id=d.company_id AND wi.supply_delivery_id=d.id))''') + ' ORDER BY d.id',
        (company_id, _date(document['waybillDate']), list(exclude_ids)))
    ids = [row['id'] for row in cur.fetchall()
           if row['id'] not in exclude_ids
           and normalize_invoice_number(row.get('waybill_number')) == normalize_invoice_number(document['waybillNumber'])
           and _date(row.get('waybill_date')) == _date(document['waybillDate'])]
    if ids:
        try:
            projections = load_delivery_document_projections(cur, ids, strict=True)
            for identity in ids:
                passport = projections.get(identity) or {}
                buyer, supplier = passport.get('buyer') or {}, passport.get('supplier') or {}
                if (passport.get('reviewRequired') or passport.get('companyId') != company_id
                        or not _inn(buyer.get('inn')) or not _inn(supplier.get('inn'))):
                    return True
                if (_inn(buyer['inn']) == _inn(document['buyerInn'])
                        and _inn(supplier['inn']) == _inn(document['supplierInn'])):
                    return True
        except (HTTPException, ValueError, TypeError, KeyError, AttributeError):
            return True
    if check_standalone:
        return _standalone_receipts(cur, document, company_id, '', 'TRUE', [],
                                    identity_only=True)['status'] != 'no_match'
    return False


def _standalone_or_review(cur, document, company_id, project, scope, params):
    # Even an unreceived hidden shipment prevents creating an unrelated stock
    # receipt for the same physical document through the standalone entry point.
    if _company_receipt_conflict(cur, document, company_id, include_unreceived=True,
                                check_standalone=False):
        return _review()
    result = _standalone_receipts(cur, document, company_id, project, scope, params)
    if result['status'] == 'no_match' and _standalone_receipts(
            cur, document, company_id, '', 'TRUE', [], identity_only=True)['status'] != 'no_match':
        return _review()
    return result


def resolve_receipt(cur, data, user, headers, deps):
    """Only SELECTs; caller owns transaction. Reusable under receipt writer locks."""
    from .matching import resolve_document_match, _text

    if not isinstance(data.get('document'), dict):
        raise HTTPException(400, 'Требуются данные документа')
    headers = headers or {}
    context = deps['resolve_work_company_context'](
        cur, user, data.get('companyId'), 'read',
        x_company_id=headers.get('x_company_id'), x_company_mode=headers.get('x_company_mode'))
    actors = deps['effective_company_actors'](user, context)
    if context.get('mode') != 'company' or len(actors) != 1:
        raise HTTPException(409, 'Выберите одну рабочую компанию')
    actor = actors[0]
    company_id = actor.get('companyId') or actor.get('company_id')
    if not company_id or company_id != context.get('companyId'):
        raise HTTPException(403, 'Компания не определена')
    if actor.get('role') not in deps['warehouse_roles']:
        raise HTTPException(403, 'Нет права принимать поставки в выбранной компании')
    for claimed in (data.get('companyId'), data['document'].get('companyId')):
        if claimed is not None and _positive(claimed, 'companyId') != company_id:
            raise HTTPException(409, 'Компания документа не совпадает с выбранной')
    project = _originals(cur, data, company_id, actor, deps)
    document = {**data['document'], 'companyId': company_id}
    payment_source = _text(document.get('documentType')) == 'payment_invoice'
    if not payment_source:
        preliminary = resolve_document_match(document, [])
        if preliminary['status'] == 'review':
            return preliminary
    scope, params = deps['fulfilment_visibility'](
        cur, user, 'd.company_id', 'd.project', 'd.work_package', str(company_id), 'company')
    # Explicit company restriction is retained even if the visibility helper changes.
    where = 'd.company_id=%s AND (' + scope + ')'
    values = [company_id] + list(params)
    if project:
        where += ' AND d.project=%s'
        values.append(project)
    source_id = data.get('sourceSupplierInvoiceId')
    if source_id is not None:
        source_id = _positive(source_id, 'sourceSupplierInvoiceId')
        if payment_source:
            where += " AND (to_jsonb(d)->>'source_supplier_invoice_id')::bigint=%s"
            values.append(source_id)
    sources = {}
    if payment_source:
        sources, error = _payment_invoice_sources(
            cur, document, company_id, project, scope, params, source_id)
        if error:
            return {'status': 'review', 'postingAllowed': False, 'requiresWaybill': True, 'reasons': [error]}
        if not sources:
            return {'status': 'no_match', 'postingAllowed': False, 'requiresWaybill': True,
                    'reasons': ['no_exact_payment_invoice_source']}
        where += " AND (to_jsonb(d)->>'source_supplier_invoice_id')::bigint=ANY(%s)"
        values.append(list(sources))
    cur.execute("""SELECT d.id,d.company_id AS "companyId",d.supplier_id AS "supplierId",
        d.offer_id AS "offerId",d.request_id AS "requestId",d.project,
        (to_jsonb(d)->>'source_supplier_invoice_id')::bigint AS "sourceSupplierInvoiceId",
        d.material_name AS "materialName",d.unit,d.shipped_quantity AS "shippedQuantity",
        COALESCE(d.received_quantity,0) AS "receivedQuantity",d.received_at AS "receivedAt",d.status,
        d.quality_status AS "qualityStatus",d.waybill_number AS "waybillNumber",
        d.waybill_date AS "waybillDate",to_jsonb(d)->'receipt_original_urls' AS "receiptOriginalUrls",
        CASE WHEN to_jsonb(d)->>'source_supplier_invoice_id' IS NULL THEN TRUE ELSE
          EXISTS (SELECT 1 FROM supplier_invoices si
            WHERE si.id=(to_jsonb(d)->>'source_supplier_invoice_id')::bigint
              AND si.company_id=d.company_id AND si.supplier_id=d.supplier_id
              AND si.offer_id=d.offer_id AND si.request_id=d.request_id
              AND si.status IS DISTINCT FROM 'Аннулирован'
              AND (to_jsonb(d)->>'contract_version_id')::bigint IS NOT DISTINCT FROM
                  (to_jsonb(si)->>'contract_version_id')::bigint)
        END AS "sourceInvoiceValid"
        FROM supply_deliveries d JOIN supplier_offers o
          ON o.id=d.offer_id AND o.company_id=d.company_id AND o.supplier_id=d.supplier_id
         AND o.request_id=d.request_id
        JOIN supply_requests r ON r.id=d.request_id AND r.company_id=d.company_id AND r.project=d.project
        WHERE """ + where + ' ORDER BY d.id', values)
    rows = {row['id']: dict(row) for row in cur.fetchall()}
    # Ignore unrelated complete headers before loading passports. A historical
    # shipment elsewhere must not block a fully evidenced current document.
    number = normalize_invoice_number(document.get('waybillNumber'))
    day = normalize_invoice_date(document.get('waybillDate'))
    rows = {key: row for key, row in rows.items()
            if (row.get('companyId') == company_id
                and (not project or row.get('project') == project)
                and (not payment_source or source_id is None or row.get('sourceSupplierInvoiceId') == source_id)
                and ((payment_source and row.get('sourceSupplierInvoiceId') in sources)
                     or (not payment_source
                         and normalize_invoice_number(row.get('waybillNumber')) == number
                         and normalize_invoice_date(row.get('waybillDate')) == day)))}
    if any(not row.get('sourceInvoiceValid') for row in rows.values()):
        return _review()
    if not rows:
        return _review() if source_id or payment_source or data.get('selectedBatchId') is not None else _standalone_or_review(
            cur, document, company_id, project, scope, params)
    cur.execute('''SELECT id,company_id,offer_id,delivery_ids FROM supplier_shipment_batches
                   WHERE company_id=%s AND delivery_ids && %s::integer[] ORDER BY id''',
                (company_id, list(rows)))
    batches = list(cur.fetchall())
    candidates = []
    covered = set()
    for batch in batches:
        ids = batch['delivery_ids']
        if (batch['company_id'] != company_id or not ids or len(set(ids)) != len(ids)
                or any(i not in rows for i in ids)):
            # Never disclose a partial authorized subset or hidden delivery identifiers.
            continue
        lines = [rows[i] for i in ids]
        if any(line['companyId'] != company_id or line['offerId'] != batch['offer_id'] for line in lines):
            continue
        covered.update(ids)
        first = lines[0]
        if any(any(line.get(key) != first.get(key) for key in
                   ('supplierId', 'requestId', 'project', 'sourceSupplierInvoiceId',
                    'waybillNumber', 'waybillDate')) for line in lines):
            return _review()
        projections = load_delivery_document_projections(cur, ids, strict=True)
        passports = [projections.get(i) for i in ids]
        if any(not p or p.get('reviewRequired') for p in passports):
            return _review()
        if any(p.get('companyId') != company_id or p.get('supplierId') != first['supplierId']
               for p in passports):
            return _review()
        # Different frozen parties within a batch cannot be silently collapsed.
        if any(any(p.get(k) != passports[0].get(k) for k in ('buyer', 'supplier', 'contract', 'sourceInvoiceId')) for p in passports):
            return _review()
        if passports[0].get('sourceInvoiceId') != first.get('sourceSupplierInvoiceId'):
            return _review()
        cur.execute('''SELECT id,supply_delivery_id FROM warehouse_invoices
                       WHERE company_id=%s AND supply_delivery_id=ANY(%s) ORDER BY id''', (company_id, ids))
        receipts = {}
        for receipt in cur.fetchall():
            if receipt['supply_delivery_id'] in receipts:
                return _review()
            receipts[receipt['supply_delivery_id']] = receipt['id']
        candidates.append({
            'id': batch['id'], 'companyId': company_id, 'supplierId': first['supplierId'],
            'project': first.get('project') or '',
            'sourceSupplierInvoiceId': first.get('sourceSupplierInvoiceId'),
            'waybillNumber': first['waybillNumber'], 'waybillDate': first['waybillDate'],
            'documentParties': passports[0],
            'lines': [{**line, 'documentParties': projections[line['id']],
                       'warehouseInvoiceId': receipts.get(line['id'])} for line in lines],
        })
    # Legacy rows without a complete persisted batch must never become invented batches.
    if set(rows) - covered:
        return _review()
    if payment_source:
        choices = []
        for batch in candidates:
            source = sources.get(batch['sourceSupplierInvoiceId'])
            if not source or (source['supplier_id'], source['offer_id'], source['request_id']) != (
                    batch['supplierId'], batch['lines'][0]['offerId'], batch['lines'][0]['requestId']):
                continue
            # Validate the actual saved waybill and whole shipment. Payment OCR
            # lines/number never become dispatch proof, even for a sole choice.
            shipment = {**document, 'documentType': 'waybill',
                        'waybillNumber': batch['waybillNumber'], 'waybillDate': batch['waybillDate'],
                        'lines': [{'materialName': line['materialName'], 'unit': line['unit'],
                                   'quantity': line['shippedQuantity']} for line in batch['lines']]}
            if resolve_document_match(shipment, [batch]).get('status') != 'match':
                continue
            batch['sourceInvoice'] = {'id': source['id'], 'invoiceNumber': source['invoice_number'],
                                      'invoiceDate': str(source['invoice_date'])}
            choices.append(_candidate_view(batch))
        return {'status': 'source_selection' if choices else 'review', 'postingAllowed': False,
                'requiresWaybill': True, 'candidateBatches': choices,
                'reasons': ['physical_waybill_required' if choices else 'no_eligible_linked_shipment']}
    result = resolve_document_match(document, candidates,
        selected_batch_id=data.get('selectedBatchId'),
        explicit_selection_confirmed=data.get('explicitSelectionConfirmed'),
        source_supplier_invoice_id=source_id)
    if result.get('status') == 'no_match' and not source_id and data.get('selectedBatchId') is None:
        return _standalone_or_review(cur, document, company_id, project, scope, params)
    result['postingAllowed'] = False
    if result.get('status') == 'match':
        batch_id = result.get('batchId')
        matched = next((batch for batch in candidates if batch['id'] == batch_id), None)
        if matched is None:
            return _review()
        if _company_receipt_conflict(cur, document, company_id,
                                    exclude_ids=[line['id'] for line in matched['lines']]):
            return _review()
        from .progress import invoice_progress
        progress = invoice_progress(cur, matched)
        matched['lines'] = [{**line, 'invoiceProgress': progress.get(line['id'])} for line in matched['lines']]
        result['matchedBatch'] = matched
        result['originalUrls'] = list(dict.fromkeys(data['originalUrls']))
    elif result.get('status') == 'ambiguous':
        eligible_ids = set(result.pop('candidateBatchIds', []))
        result['candidateBatches'] = [_candidate_view(batch) for batch in candidates
                                    if batch['id'] in eligible_ids]
    else:
        # Policy details must never accidentally expose arbitrary candidate IDs.
        result = {k: v for k, v in result.items() if k in ('status', 'postingAllowed', 'reason', 'reasons')}
    return result


def register_warehouse_receipt_resolver(app, deps):
    @app.post('/warehouse-receipts/resolve')
    def preview_receipt(data: dict, current_user: dict = Depends(deps['get_current_user']),
                        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
                        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode')):
        conn = deps['get_db']()
        cur = None
        try:
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("SET LOCAL statement_timeout='15s'")
            return resolve_receipt(cur, data, current_user,
                                   {'x_company_id': x_company_id, 'x_company_mode': x_company_mode}, deps)
        finally:
            try:
                conn.rollback()
            finally:
                try:
                    if cur is not None:
                        cur.close()
                finally:
                    conn.close()
