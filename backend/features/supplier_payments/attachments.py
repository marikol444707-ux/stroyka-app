"""Internal full-invoice mirror attachment; no runtime route or policy supplied."""
from uuid import UUID

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .attachment_projection import attachments_available
from .commands import command_fingerprint, positive_id
from .cancellations import require_uncancelled
from .engine import _baseline, _documents
from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


def normalize_attachment(body):
    allowed = {'requestId', 'invoiceId', 'warehouseId', 'reason'}
    if not isinstance(body, dict) or set(body) != allowed:
        raise HTTPException(422, 'Нужны UUID, счёт, накладная и основание присоединения')
    try:
        request_id = str(UUID(body['requestId']))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Некорректный UUID присоединения')
    reason = body['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise HTTPException(422, 'Укажите основание, до 1000 символов')
    return dict(requestId=request_id, kind='attachment', documentKind='invoice',
                documentId=positive_id(body['invoiceId']), warehouseId=positive_id(body['warehouseId']),
                reason=reason.strip())


def _result(row, command):
    return dict(attachmentId=row['id'], invoiceId=command['documentId'],
                warehouseId=command['warehouseId'], mirroredPaid=format(row['mirrored_paid'], '.2f'))


def attach_receipt_in_transaction(cur, authorize_and_lock, actor_id, company_id, body, *, validate_new):
    """Attach using the caller's explicit transaction and RealDict cursor.

    Caller owns commit/rollback and must take any required stock locks BEFORE
    calling this company-serialized worker. No connections, DDL or lifecycle
    operations here. Both trusted callbacks are required on the same cursor:
    authorize_and_lock checks current actor/scope and locks both documents even
    on replay; validate_new proves exact receipt provenance, full coverage and
    canonical payer/contract identity for a new attachment.

    This internal worker grants no financial permission and creates no payment
    or expense. Runtime receipt authorization and response filtering belong to
    a separate server adapter; do not expose mirroredPaid to a receipt actor
    without financial-read access.
    """
    if cur.connection.autocommit:
        raise RuntimeError('Receipt attachment requires an explicit transaction')
    positive_id(actor_id); positive_id(company_id)
    if not callable(authorize_and_lock) or not callable(validate_new):
        raise TypeError('Authorization and attachment policy adapters are required')
    command = normalize_attachment(body)
    fingerprint = command_fingerprint(company_id, actor_id, command)
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
    context = authorize_and_lock(cur, actor_id, company_id, command)
    if not attachments_available(cur):
        raise HTTPException(409, 'Схема присоединения накладных не установлена')
    cur.execute('''SELECT * FROM supplier_payment_attachments
                   WHERE company_id=%s AND request_id=%s''', (company_id, command['requestId']))
    replay = cur.fetchone()
    if replay:
        if replay['fingerprint'] != fingerprint:
            raise HTTPException(409, 'UUID операции уже использован с другими данными')
        return _result(replay, command)
    require_uncancelled(cur, company_id, command['requestId'], fingerprint)
    cur.execute('''SELECT id FROM supplier_payment_operations WHERE company_id=%s AND request_id=%s''',
                (company_id, command['requestId']))
    if cur.fetchone():
        raise HTTPException(409, 'UUID уже использован для платежа')
    raw = context.get('documents', [])
    if len(raw) != 2 or {(d['kind'], d['id']) for d in raw} != {
            ('invoice', command['documentId']), ('warehouse', command['warehouseId'])}:
        raise HTTPException(409, 'Не определена точная пара счёт–накладная')
    invoice = dict(next(d for d in raw if d['kind'] == 'invoice'))
    warehouse = dict(next(d for d in raw if d['kind'] == 'warehouse'))
    try:
        source_paid = schedule_paid_amount(invoice['paidAmount'])
        target_paid = schedule_paid_amount(warehouse['paidAmount'])
    except ValueError:
        raise HTTPException(409, 'Суммы документа требуют проверки')
    if target_paid not in (0, source_paid):
        raise HTTPException(409, 'Оплата накладной требует отдельной сверки')
    # Only validation sees aligned balances. The target baseline below
    # keeps its actual pre-attachment opening, never a fabricated payment.
    documents = _documents({**context, 'documents': [invoice, {**warehouse, 'paidAmount': source_paid}]},
                           company_id, command)
    if documents[0]['amount'] != documents[1]['amount']:
        raise HTTPException(409, 'Частичная накладная требует отдельной разноски')
    warehouse = {**documents[1], 'paidAmount': target_paid}
    invoice = documents[0]
    validate_new(cur, context, command)
    cur.execute('''SELECT d.id FROM supplier_payment_documents d
        WHERE d.company_id=%s AND d.document_kind='invoice' AND d.document_id=%s
          AND EXISTS (SELECT 1 FROM supplier_payment_impacts i WHERE i.document_record_id=d.id)''',
        (company_id, invoice['id']))
    if not cur.fetchone():
        raise HTTPException(409, 'У счёта нет операций в журнале оплат: нужна отдельная сверка')
    cur.execute('''SELECT id FROM supplier_payment_documents
        WHERE company_id=%s AND document_kind='warehouse' AND document_id=%s''',
        (company_id, warehouse['id']))
    if cur.fetchone():
        raise HTTPException(409, 'Накладная уже зарегистрирована: нужна отдельная сверка')
    source = _baseline(cur, invoice, company_id)
    target = _baseline(cur, warehouse, company_id)
    cur.execute('''INSERT INTO supplier_payment_attachments
        (company_id,request_id,fingerprint,invoice_record_id,warehouse_record_id,
         mirrored_paid,actor_id,actor_name,reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (company_id,command['requestId'],fingerprint,source['id'],target['id'],source_paid,
         actor_id,context['actorName'],command['reason']))
    attachment = cur.fetchone()
    status = 'Оплачена' if source_paid == invoice['amount'] else 'Частично оплачена' if source_paid > 0 else 'К оплате'
    cur.execute('''UPDATE warehouse_invoices w SET paid_amount=%s,accounting_status=%s,
        paid_by=i.paid_by,paid_at=i.paid_at FROM supplier_invoices i
        WHERE w.id=%s AND w.company_id=%s AND i.id=%s AND i.company_id=%s''',
        (source_paid,status,warehouse['id'],company_id,invoice['id'],company_id))
    if cur.rowcount != 1:
        raise HTTPException(409, 'Документ изменился во время присоединения')
    return _result(attachment, command)


def attach_receipt(get_db, authorize_and_lock, actor_id, company_id, body, *, validate_new):
    """Own a transaction for standalone internal callers; API is unchanged."""
    # Keep invalid input/callback rejection before opening a connection.
    positive_id(actor_id); positive_id(company_id)
    if not callable(authorize_and_lock) or not callable(validate_new):
        raise TypeError('Authorization and attachment policy adapters are required')
    normalize_attachment(body)
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            result = attach_receipt_in_transaction(
                cur, authorize_and_lock, actor_id, company_id, body, validate_new=validate_new)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
