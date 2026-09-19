"""At-most-once SMTP invocation for each persisted RFQ recipient.

A lost acknowledgement is deliberately not retryable. The existing SMTP adapter
cannot distinguish a rejected message from one accepted before the connection
failed. Commit the conservative state BEFORE crossing that boundary.
"""
import logging

from psycopg2.extras import RealDictCursor

EMAIL_QUEUED = 'В очереди email'
EMAIL_UNCONFIRMED = 'Передача email: результат не подтверждён'
_RECHECKABLE = {'', EMAIL_QUEUED, 'Нет email', 'SMTP не настроен', 'Пропущено: тестовый email'}
logger = logging.getLogger(__name__)


def prepare_email_status(current, email, configured, skip):
    current = (current or '').strip()
    if current not in _RECHECKABLE:
        return current
    if not email:
        return 'Нет email'
    if skip:
        return 'Пропущено: тестовый email'
    if not configured:
        return 'SMTP не настроен'
    return EMAIL_QUEUED


def dispatch_recipient_email(get_db, request_id, company_id, recipient_id, *,
                             configured, skip_email, context, text, send):
    """Called only after RFQ commit. Never raise into the already saved response."""
    conn = None
    try:
        conn = get_db()
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Same lock order as RFQ: request, then recipient. Concurrent workers
            # re-read the committed claim after the first releases these locks.
            cur.execute('''SELECT id FROM supply_requests
                WHERE id=%s AND company_id=%s
                  AND prorab_confirmed_at IS NOT NULL AND director_approved_at IS NOT NULL
                  AND status IN ('Утверждена','КП запрошены') FOR UPDATE''', (request_id, company_id))
            if not cur.fetchone():
                return
            cur.execute('''SELECT id FROM supply_request_recipients
                WHERE id=%s AND request_id=%s AND company_id=%s
                  AND email_notification_status=%s FOR UPDATE''',
                (recipient_id, request_id, company_id, EMAIL_QUEUED))
            if not cur.fetchone():
                return
            # Fresh READ COMMITTED snapshot after waiting for the recipient.
            # Hold identity/contact rows stable until the claim is committed.
            cur.execute('''SELECT r.id, r.email_notification_status,
                       COALESCE(s.name,'') AS supplier_name,
                       COALESCE(NULLIF(s.email,''),NULLIF(u.email,''),'') AS email
                FROM supply_request_recipients r
                JOIN users u ON u.id=r.supplier_user_id
                    AND u.role='поставщик' AND COALESCE(u.active,TRUE)
                JOIN suppliers s ON s.id=r.target_supplier_id AND s.user_id=u.id
                WHERE r.id=%s AND r.request_id=%s AND r.company_id=%s
                  AND r.visible_to_supplier=TRUE
                  AND EXISTS (SELECT 1 FROM supplier_offers o
                    WHERE o.request_id=r.request_id AND o.company_id=r.company_id
                      AND o.supplier_id IN (r.target_supplier_id,r.supplier_id)
                      AND COALESCE(o.status,'') NOT IN ('Отклонено','Отозвано'))
                FOR SHARE OF u,s''', (recipient_id, request_id, company_id))
            recipient = cur.fetchone()
            if not recipient or recipient['email_notification_status'] != EMAIL_QUEUED:
                return
            email = recipient['email'].strip()
            status = prepare_email_status(EMAIL_QUEUED, email, configured(), skip_email(email))
            message = None
            if status == EMAIL_QUEUED:
                request_context = context(cur, request_id)
                if not request_context or request_context.get('companyId') != company_id:
                    return
                message = text(request_context, recipient['supplier_name'])
                status = EMAIL_UNCONFIRMED
            cur.execute('''UPDATE supply_request_recipients SET email_notification_status=%s
                WHERE id=%s AND request_id=%s AND company_id=%s''',
                (status, recipient_id, request_id, company_id))
        conn.commit()
        conn.close()
        conn = None
        if message is None:
            return
        if send(email, *message) is not True:
            return
        conn = get_db()
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute('''UPDATE supply_request_recipients
                SET email_notification_status='Отправлено', email_sent_at=COALESCE(email_sent_at,NOW())
                WHERE id=%s AND request_id=%s AND company_id=%s AND email_notification_status=%s''',
                (recipient_id, request_id, company_id, EMAIL_UNCONFIRMED))
        conn.commit()
    except Exception:
        # No addresses, message bodies, credentials or raw provider exceptions.
        logger.warning('supplier_email_attempt_unconfirmed request_id=%s recipient_id=%s', request_id, recipient_id)
    finally:
        if conn is not None:
            conn.close()
