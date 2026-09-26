"""Permanent attempt tombstones, not payment reversals. No runtime registration.

All writers share the engine company advisory lock. Cancellation is terminal
only after commit; an earlier GET not_found is never evidence of cancellation.
"""
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .commands import positive_id, normalize_command, command_fingerprint
from .attachment_projection import attachments_available


def cancellations_available(cur):
    cur.execute("SELECT to_regclass('public.supplier_payment_request_cancellations') IS NOT NULL AS available")
    return cur.fetchone()['available']


def _conflict():
    raise HTTPException(409, dict(code='request_id_conflict', message='UUID уже использован с другими данными'))


def require_uncancelled(cur, company_id, request_id, fingerprint):
    """Call after current auth/replay, under the common company lock, before writes."""
    if not cancellations_available(cur):
        return
    cur.execute('SHOW transaction_isolation')
    if cur.fetchone()['transaction_isolation'] != 'read committed':
        raise HTTPException(409, 'Проверка отменённой попытки требует READ COMMITTED')
    cur.execute('''SELECT fingerprint FROM supplier_payment_request_cancellations
                   WHERE company_id=%s AND request_id=%s''', (company_id, request_id))
    row = cur.fetchone()
    if row:
        if row['fingerprint'] != fingerprint:
            _conflict()
        raise HTTPException(409, dict(code='request_cancelled', message='Попытка отменена; этот UUID закрыт'))


def _cancelled(row):
    return dict(status='cancelled', requestId=str(row['request_id']),
                cancelledAt=row['cancelled_at'].isoformat())


def cancel_request(get_db, authorize_and_lock, actor_id, company_id, body):
    """Cancel the exact normalized original payment/reversal command.

    Mandatory server callback is the current WRITE document resolver, not the
    read variant. No new-payment eligibility policy is called. A committed
    operation returns its saved result; it is never reversed or overwritten.
    """
    positive_id(actor_id); positive_id(company_id)
    if not callable(authorize_and_lock):
        raise TypeError('Current write authorization/document resolver is required')
    command = normalize_command(body)
    fingerprint = command_fingerprint(company_id, actor_id, command)
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SHOW transaction_isolation')
            if cur.fetchone()['transaction_isolation'] != 'read committed':
                raise HTTPException(409, 'Отмена попытки требует READ COMMITTED')
            cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201, company_id))
            authorize_and_lock(cur, actor_id, company_id, command)
            if not cancellations_available(cur):
                raise HTTPException(409, 'Схема отмены попыток не установлена')
            cur.execute('SELECT * FROM supplier_payment_operations WHERE company_id=%s AND request_id=%s',
                        (company_id, command['requestId']))
            operation = cur.fetchone()
            if operation:
                if operation['fingerprint'] != fingerprint:
                    _conflict()
                # Local import avoids a cycle with the engine's tombstone gate.
                from .engine import _result
                result = dict(status='confirmed', requestId=command['requestId'], result=_result(operation))
            else:
                if attachments_available(cur):
                    cur.execute('SELECT id FROM supplier_payment_attachments WHERE company_id=%s AND request_id=%s',
                                (company_id, command['requestId']))
                    if cur.fetchone():
                        _conflict()
                cur.execute('''SELECT * FROM supplier_payment_request_cancellations
                               WHERE company_id=%s AND request_id=%s''', (company_id, command['requestId']))
                row = cur.fetchone()
                if row and row['fingerprint'] != fingerprint:
                    _conflict()
                if not row:
                    cur.execute('''INSERT INTO supplier_payment_request_cancellations
                        (company_id,request_id,fingerprint,actor_id,document_kind,document_id)
                        VALUES(%s,%s,%s,%s,%s,%s) RETURNING *''',
                        (company_id, command['requestId'], fingerprint, actor_id,
                         command['documentKind'], command['documentId']))
                    row = cur.fetchone()
                result = _cancelled(row)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
