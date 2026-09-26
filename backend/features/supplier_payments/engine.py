"""Internal, unregistered transaction engine.

RELEASE GATE: real authorization/locking and new-operation policy adapters plus
legacy-writer guards are required before exposing this to any runtime route.
Callbacks use the supplied cursor and must neither commit nor open connections.
"""
from decimal import Decimal

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .commands import normalize_command, command_fingerprint, positive_id
from .attachment_projection import attachments_available, balance_source, canonical_records
from .statuses import payment_status_eligible
from .cancellations import require_uncancelled
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


def _documents(context, company_id, command):
    documents = context.get('documents', [])
    if not context.get('actorName') or not 1 <= len(documents) <= 2:
        raise HTTPException(409, 'Не определены сотрудник и документы оплаты')
    keys = {(d['kind'], d['id']) for d in documents}
    if len(keys) != len(documents) or (command['documentKind'], command['documentId']) not in keys:
        raise HTTPException(409, 'Изменился состав документов оплаты')
    identities = set()
    for doc in documents:
        if doc['kind'] not in ('invoice', 'warehouse') or doc['companyId'] != company_id:
            raise HTTPException(409, 'Документ принадлежит другой компании')
        positive_id(doc['id']); positive_id(doc['payerCompanyId']); positive_id(doc['supplierId'])
        if not doc['projectName']:
            raise HTTPException(409, 'Не определён объект оплаты')
        try:
            doc['amount'] = schedule_paid_amount(doc['amount'])
            doc['paidAmount'] = schedule_paid_amount(doc['paidAmount'])
        except ValueError:
            raise HTTPException(409, 'Суммы документа требуют проверки')
        if doc['amount'] <= 0 or doc['paidAmount'] > doc['amount']:
            raise HTTPException(409, 'Суммы документа требуют проверки')
        identities.add((doc['payerCompanyId'], doc['supplierId'], doc['projectName'], doc['workPackage']))
    if len(identities) != 1 or len({d['paidAmount'] for d in documents}) != 1:
        raise HTTPException(409, 'Связанные документы требуют сверки')
    if len(documents) == 2 and {d['kind'] for d in documents} != {'invoice', 'warehouse'}:
        raise HTTPException(409, 'Операция не поддерживает несколько счетов')
    return sorted(documents, key=lambda d: (d['kind'], d['id']))


def _baseline(cur, doc, company_id):
    cur.execute('''SELECT * FROM supplier_payment_documents
        WHERE company_id=%s AND document_kind=%s AND document_id=%s''', (company_id, doc['kind'], doc['id']))
    record = cur.fetchone()
    identity = (doc['payerCompanyId'], doc['supplierId'], doc['projectName'], doc['workPackage'], doc['amount'])
    if record is None:
        cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (company_id, doc['kind'], doc['id'], *identity, doc['paidAmount']))
        record = cur.fetchone()
    elif tuple(record[key] for key in ('payer_company_id','supplier_id','project_name','work_package','amount')) != identity:
        raise HTTPException(409, 'Реквизиты учтённого документа изменились')
    source = balance_source(cur, record, company_id)
    cur.execute('''SELECT COALESCE(SUM(delta),0) AS total FROM supplier_payment_impacts
                   WHERE document_record_id=%s AND company_id=%s''', (source['id'], company_id))
    expected = source['opening_paid'] + cur.fetchone()['total']
    if expected != doc['paidAmount']:
        raise HTTPException(409, 'Сумма документа не совпадает с журналом оплат')
    return record


def _result(operation):
    return dict(operationId=operation['id'], projectPaymentId=operation['project_payment_id'],
                kind=operation['kind'], amount=format(operation['amount'], '.2f'))


def _require_same_document_group(cur, records, company_id):
    """An established payment group cannot silently gain or lose documents."""
    record_ids = sorted(record['id'] for record in records)
    cur.execute('''SELECT 1 FROM supplier_payment_impacts
        WHERE company_id=%s AND operation_id IN (
            SELECT operation_id FROM supplier_payment_impacts
            WHERE company_id=%s AND document_record_id=ANY(%s::bigint[]))
        GROUP BY operation_id
        HAVING array_agg(document_record_id ORDER BY document_record_id) <> %s::bigint[]
        LIMIT 1''', (company_id, company_id, record_ids, record_ids))
    if cur.fetchone():
        raise HTTPException(409, 'Изменился состав связанных документов оплаты')


def execute(get_db, authorize_and_lock, actor_id, company_id, body, *, validate_new):
    """Own one transaction; current auth precedes replay, payment rules follow it.

    authorize_and_lock(cur, actor_id, company_id, command) supplies trusted live
    actorName and locked document snapshots. validate_new(cur,context,command,
    signed_amount) must check live identity/status for a NEW operation. Actual
    payments have no schedule/acceptance cap; exact remaining-balance bounds
    stay in this engine. Canonical payer authority belongs to the resolver.
    Neither callback is supplied by this module or accepted from an HTTP body.
    """
    positive_id(actor_id); positive_id(company_id)
    if not callable(authorize_and_lock) or not callable(validate_new):
        raise TypeError('Both authorization and payment policy adapters are required')
    command = normalize_command(body)
    fingerprint = command_fingerprint(company_id, actor_id, command)
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Serializes this engine only. Other writers are NOT safe until they
            # adopt the same policy/lock protocol or are blocked for managed rows.
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
            context = authorize_and_lock(cur, actor_id, company_id, command)
            cur.execute('SELECT * FROM supplier_payment_operations WHERE company_id=%s AND request_id=%s',
                        (company_id, command['requestId']))
            replay = cur.fetchone()
            if replay:
                if replay['fingerprint'] != fingerprint:
                    raise HTTPException(409, 'UUID операции уже использован с другими данными')
                return _result(replay)
            require_uncancelled(cur, company_id, command['requestId'], fingerprint)
            if attachments_available(cur):
                cur.execute('SELECT id FROM supplier_payment_attachments WHERE company_id=%s AND request_id=%s',
                            (company_id, command['requestId']))
                if cur.fetchone():
                    raise HTTPException(409, 'UUID операции уже использован для присоединения накладной')
            documents = _documents(context, company_id, command)
            original = None
            if command['kind'] == 'reversal':
                cur.execute('SELECT * FROM supplier_payment_operations WHERE id=%s AND company_id=%s',
                            (command['reversesId'], company_id))
                original = cur.fetchone()
                if not original or original['kind'] != 'payment':
                    raise HTTPException(409, 'Исходный платёж не найден')
                if (original['document_kind'], original['document_id']) != (command['documentKind'], command['documentId']):
                    raise HTTPException(409, 'Сторно относится к другому документу')
                cur.execute('SELECT id FROM supplier_payment_operations WHERE reverses_id=%s', (original['id'],))
                if cur.fetchone():
                    raise HTTPException(409, 'Платёж уже сторнирован')
                amount = original['amount']
            else:
                amount = Decimal(command['amount'])
            signed = -amount if original else amount
            validate_new(cur, context, command, signed)
            records = [_baseline(cur, doc, company_id) for doc in documents]
            records = canonical_records(cur, records, company_id, command)
            _require_same_document_group(cur, records, company_id)
            if original:
                cur.execute('SELECT document_record_id FROM supplier_payment_impacts WHERE operation_id=%s', (original['id'],))
                if {r['document_record_id'] for r in cur.fetchall()} != {r['id'] for r in records}:
                    raise HTTPException(409, 'Изменился состав документов исходной оплаты')
            for doc in documents:
                if not 0 <= doc['paidAmount'] + signed <= doc['amount']:
                    raise HTTPException(400, 'Сумма выходит за пределы долга документа')
            reversal_statuses = {}
            recalculate_statuses = True
            if original:
                # Callbacks need not carry status metadata. Re-read the already
                # locked physical group: undoing money must not approve a held,
                # pending or cancelled document (or reopen its financial mirror).
                for doc in documents:
                    table, columns = ('supplier_invoices', 'status') if doc['kind'] == 'invoice' else (
                        'warehouse_invoices', 'status,accounting_status')
                    cur.execute(f'SELECT {columns} FROM {table} WHERE id=%s AND company_id=%s FOR UPDATE',
                                (doc['id'], company_id))
                    live = cur.fetchone()
                    if not live:
                        raise HTTPException(409, 'Документ сторно больше не существует')
                    reversal_statuses[(doc['kind'], doc['id'])] = live[
                        'status' if doc['kind'] == 'invoice' else 'accounting_status']
                    recalculate_statuses = recalculate_statuses and payment_status_eligible(doc['kind'], live)
            first = documents[0]
            cur.execute('''INSERT INTO project_payments
                (company_id,project_name,work_package,amount,note,date,added_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (company_id,first['projectName'],first['workPackage'],signed,command['reason'],
                 command['paidAt'],context['actorName']))
            payment_id = cur.fetchone()['id']
            cur.execute('''INSERT INTO supplier_payment_operations
                (company_id,request_id,fingerprint,document_kind,document_id,kind,amount,
                 payer_company_id,supplier_id,project_payment_id,reverses_id,actor_id,actor_name,reason,payment_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (company_id,command['requestId'],fingerprint,command['documentKind'],command['documentId'],
                 command['kind'],amount,first['payerCompanyId'],first['supplierId'],payment_id,
                 command['reversesId'],actor_id,context['actorName'],command['reason'],command['paidAt']))
            operation = cur.fetchone()
            for record in records:
                cur.execute('''INSERT INTO supplier_payment_impacts
                    (operation_id,document_record_id,company_id,delta) VALUES (%s,%s,%s,%s)''',
                    (operation['id'],record['id'],company_id,signed))
            # Derived mirrors update physically but never receive a second impact.
            for doc in documents:
                paid = doc['paidAmount'] + signed
                if doc['kind'] == 'invoice':
                    status = 'Оплачен' if paid == doc['amount'] else 'Частично оплачен' if paid > 0 else 'Утверждён'
                    if not recalculate_statuses:
                        status = reversal_statuses[(doc['kind'], doc['id'])]
                    cur.execute('''UPDATE supplier_invoices SET paid_amount=%s,status=%s,paid_by=%s,paid_at=%s
                                   WHERE id=%s AND company_id=%s''',
                                (paid,status,context['actorName'],command['paidAt'],doc['id'],company_id))
                else:
                    status = 'Оплачена' if paid == doc['amount'] else 'Частично оплачена' if paid > 0 else 'К оплате'
                    if not recalculate_statuses:
                        status = reversal_statuses[(doc['kind'], doc['id'])]
                    cur.execute('''UPDATE warehouse_invoices SET paid_amount=%s,accounting_status=%s,paid_by=%s,paid_at=%s
                                   WHERE id=%s AND company_id=%s''',
                                (paid,status,context['actorName'],command['paidAt'],doc['id'],company_id))
                if cur.rowcount != 1:
                    raise HTTPException(409, 'Документ изменился во время оплаты')
        conn.commit()
        return _result(operation)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
