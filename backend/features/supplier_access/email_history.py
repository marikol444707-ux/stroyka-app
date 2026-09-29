"""Scoped evidence and explicit, versioned retry after a proven SMTP rejection."""
from fastapi import HTTPException
from .email_attempts import EMAIL_QUEUED, EMAIL_REJECTED


def attach_email_history(cur, request, rows):
    ids=[row['id'] for row in rows if int(row.get('id') or 0)>0]
    if not ids:
        return rows
    cur.execute('''SELECT * FROM (
        SELECT id,recipient_id,outcome,code,started_at,finished_at,
            row_number() OVER (PARTITION BY recipient_id ORDER BY id DESC) AS position
        FROM supplier_email_attempts WHERE company_id=%s AND request_id=%s AND recipient_id=ANY(%s)
        ) a WHERE position<=20 ORDER BY id DESC''', (request['company_id'],request['id'],ids))
    attempts={}
    for item in cur.fetchall():
        attempts.setdefault(item['recipient_id'],[]).append({
            'id':item['id'],'outcome':item['outcome'],'code':item['code'],
            'startedAt':item['started_at'],'finishedAt':item['finished_at']})
    for row in rows:
        history=attempts.get(row['id'],[])
        row['emailAttempts']=history
        row['emailRetryAttemptId']=(history[0]['id'] if history and history[0]['outcome']=='rejected'
            and row.get('emailNotificationStatus')==EMAIL_REJECTED and row.get('visibleToSupplier') else None)
    return rows


def queue_rejected_email(cur, request_id, company_id, recipient_id, attempt_id):
    if type(attempt_id) is not int or attempt_id<=0:
        raise HTTPException(400,'Обновите сведения о последней попытке')
    cur.execute('''SELECT id FROM supply_requests WHERE id=%s AND company_id=%s
        AND prorab_confirmed_at IS NOT NULL AND director_approved_at IS NOT NULL
        AND status IN ('Утверждена','КП запрошены') FOR UPDATE''',(request_id,company_id))
    if not cur.fetchone():
        raise HTTPException(409,'Заявка больше не допускает отправку КП')
    cur.execute('''SELECT email_notification_status FROM supply_request_recipients
        WHERE id=%s AND request_id=%s AND company_id=%s AND visible_to_supplier=TRUE FOR UPDATE''',
        (recipient_id,request_id,company_id))
    row=cur.fetchone()
    if not row:
        raise HTTPException(404,'Получатель недоступен')
    cur.execute('''SELECT id,outcome FROM supplier_email_attempts
        WHERE company_id=%s AND request_id=%s AND recipient_id=%s ORDER BY id DESC LIMIT 1''',
        (company_id,request_id,recipient_id))
    attempt=cur.fetchone()
    if not attempt or attempt['id']!=attempt_id or attempt['outcome']!='rejected':
        raise HTTPException(409,'Повтор не разрешён: обновите состояние уведомления')
    if row['email_notification_status']==EMAIL_QUEUED:
        return
    if row['email_notification_status']!=EMAIL_REJECTED:
        raise HTTPException(409,'Повтор этой попытки уже обработан')
    cur.execute('''UPDATE supply_request_recipients SET email_notification_status=%s
        WHERE id=%s AND request_id=%s AND company_id=%s''',
        (EMAIL_QUEUED,recipient_id,request_id,company_id))
