"""Read-only delivery evidence for the internal recipient diagnostics UI."""

from .supply_request_workflow import supply_request_approval_block_reason


def attach_recipient_delivery_diagnostics(cur, request, rows):
    reason = supply_request_approval_block_reason(request)
    for row in rows:
        # Preserve the historical account-link flag; it is not an acknowledgement.
        row['approvalComplete'] = not bool(reason)
        row['approvalBlockReason'] = reason
        row['actualMaxQueueStatus'] = 'unknown' if row.get('maxOutboxId') else None

    recipient_ids = [row['id'] for row in rows
                     if row.get('maxOutboxId') and int(row.get('id') or 0) > 0]
    if not recipient_ids:
        return rows
    # Diagnostics must also work before MAX has ever been configured.
    cur.execute("SELECT to_regclass('public.messenger_outbox') AS table_name")
    if not (cur.fetchone() or {}).get('table_name'):
        return rows
    cur.execute("""
        SELECT r.id AS recipient_id, o.status
          FROM supply_request_recipients r
          JOIN messenger_outbox o
            ON o.id=r.max_outbox_id
           AND o.company_id=r.company_id
           AND o.user_id=r.supplier_user_id
           AND o.provider='max'
           AND o.event_type='supplier_kp_requested'
           AND o.entity_type='supply_request'
           AND o.entity_id=r.request_id
         WHERE r.request_id=%s AND r.company_id=%s AND r.id=ANY(%s)
    """, (request['id'], request['company_id'], recipient_ids))
    statuses = {row['recipient_id']: row['status'] for row in cur.fetchall()}
    for row in rows:
        if row['id'] in statuses:
            row['actualMaxQueueStatus'] = statuses[row['id']] or 'unknown'
    return rows
