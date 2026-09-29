"""Persist an RFQ MAX claim before network I/O; ambiguous claims never retry."""
from psycopg2.extras import RealDictCursor


SUPPLIER_MESSAGE_ELIGIBLE_SQL = """EXISTS (
                    SELECT 1 FROM supply_request_recipients r
                    JOIN supply_requests q ON q.id=r.request_id AND q.company_id=r.company_id
                    JOIN users u ON u.id=r.supplier_user_id AND u.role='поставщик'
                        AND COALESCE(u.active,TRUE)
                    JOIN suppliers s ON s.id=r.target_supplier_id AND s.user_id=u.id
                    WHERE r.max_outbox_id=o.id AND r.company_id=o.company_id
                      AND r.request_id=o.entity_id AND r.supplier_user_id=o.user_id
                      AND r.visible_to_supplier=TRUE
                      AND EXISTS (SELECT 1 FROM messenger_accounts a
                        WHERE a.id=o.messenger_account_id AND a.provider='max' AND COALESCE(a.enabled,TRUE)
                          AND a.user_id=r.supplier_user_id
                          AND COALESCE(a.external_user_id,'')=COALESCE(o.external_user_id,'')
                          AND COALESCE(a.chat_id,'')=COALESCE(o.chat_id,''))
                      AND q.prorab_confirmed_at IS NOT NULL AND q.director_approved_at IS NOT NULL
                      AND q.status IN ('Утверждена','КП запрошены')
                      AND EXISTS (SELECT 1 FROM supplier_offers f WHERE f.request_id=r.request_id
                        AND f.company_id=r.company_id AND f.supplier_id IN (r.supplier_id,r.target_supplier_id)
                        AND COALESCE(f.status,'') NOT IN ('Отклонено','Отозвано')))"""


def dispatch_supplier_message(get_db, message_id, send):
    conn = get_db()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""SELECT entity_id,company_id FROM messenger_outbox WHERE id=%s
                AND provider='max' AND owner_scope='company' AND event_type='supplier_kp_requested'
                AND entity_type='supply_request' AND status='queued'""",(message_id,))
            candidate=cur.fetchone()
            if not candidate:
                return None
            cur.execute("SELECT id FROM supply_requests WHERE id=%s AND company_id=%s FOR UPDATE",
                (candidate['entity_id'],candidate['company_id']))
            if not cur.fetchone():
                return None
            cur.execute("""SELECT supplier_user_id,target_supplier_id FROM supply_request_recipients
                WHERE max_outbox_id=%s AND request_id=%s AND company_id=%s FOR UPDATE""",
                (message_id,candidate['entity_id'],candidate['company_id']))
            recipient=cur.fetchone()
            if not recipient:
                return None
            cur.execute("""SELECT u.id FROM users u JOIN suppliers s ON s.user_id=u.id AND s.id=%s
                JOIN messenger_accounts a ON a.user_id=u.id
                JOIN messenger_outbox o ON o.messenger_account_id=a.id AND o.id=%s
                WHERE u.id=%s FOR SHARE OF u,s,a""",
                (recipient['target_supplier_id'],message_id,recipient['supplier_user_id']))
            if not cur.fetchone():
                return None
            cur.execute(f"""UPDATE messenger_outbox o SET status='sending',updated_at=NOW(),
                    last_error='',next_attempt_at=NULL
                WHERE o.id=%s AND o.provider='max' AND o.owner_scope='company'
                  AND o.company_id IS NOT NULL AND o.event_type='supplier_kp_requested'
                  AND o.entity_type='supply_request' AND o.status='queued'
                  AND (o.next_attempt_at IS NULL OR o.next_attempt_at<=NOW())
                  AND {SUPPLIER_MESSAGE_ELIGIBLE_SQL}
                RETURNING o.*""", (message_id,))
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if not row:
        return None
    try:
        _, provider_id, _ = send(dict(row))
        if not str(provider_id or '').strip():
            return {'id': message_id, 'status': 'unconfirmed'}
    except Exception:
        # Sending is durable even when the process dies or persistence fails.
        return {'id': message_id, 'status': 'unconfirmed'}
    conn = get_db()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""UPDATE messenger_outbox SET status='sent',provider_message_id=%s,
                sent_at=NOW(),updated_at=NOW(),last_error='',next_attempt_at=NULL
                WHERE id=%s AND company_id=%s AND provider='max' AND owner_scope='company'
                  AND event_type='supplier_kp_requested' AND status='sending' RETURNING *""",
                (provider_id, message_id, row['company_id']))
            updated = cur.fetchone()
        conn.commit()
        return {'id': message_id, 'status': 'sent' if updated else 'unconfirmed',
                'providerMessageId': provider_id, 'item': dict(updated) if updated else None}
    except Exception:
        conn.rollback()
        return {'id': message_id, 'status': 'unconfirmed'}
    finally:
        conn.close()
