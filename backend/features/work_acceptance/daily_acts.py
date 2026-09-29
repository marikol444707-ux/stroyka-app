"""Append newly accepted IDs without changing a signed daily control act."""
import json
from decimal import Decimal

from .records import photos


def sync_daily(cur, work, project, locked_statuses):
    if not work.get('room_id') and not work.get('room_name'):
        return
    scope = (project['companyId'], work['project'], work['work_package'] or 'Основная', work['date'], work['date'], work['master_id'])
    cur.execute('''SELECT id,status,work_journal_ids FROM interim_acts WHERE company_id=%s AND project=%s
        AND COALESCE(NULLIF(work_package,''),'Основная')=%s AND period_start=%s AND period_end=%s
        AND master_id=%s AND source_type='daily_work' AND status<>'Аннулирован' ORDER BY id DESC FOR UPDATE''', scope)
    acts = cur.fetchall()
    draft = next((row for row in acts if row['status'] not in locked_statuses), None)
    draft_id = draft['id'] if draft else 0
    cur.execute('''SELECT w.id,w.execution_total,w.photo_url FROM work_journal w
        WHERE w.company_id=%s AND w.project=%s AND COALESCE(NULLIF(w.work_package,''),'Основная')=%s
          AND w.date=%s AND w.status='Подтверждено' AND w.master_id=%s
          AND (w.room_id IS NOT NULL OR COALESCE(w.room_name,'')<>'')
          AND NOT EXISTS(SELECT 1 FROM interim_acts a WHERE a.status<>'Аннулирован' AND a.id<>%s
            AND (COALESCE(NULLIF(a.work_journal_ids,''),'[]')::jsonb @> jsonb_build_array(w.id)
                 OR COALESCE(NULLIF(a.work_journal_ids,''),'[]')::jsonb ? w.id::text)) ORDER BY w.id''',
        (scope[0], scope[1], scope[2], scope[3], scope[5], draft_id))
    rows = cur.fetchall()
    if not rows:
        return
    ids = json.dumps([row['id'] for row in rows])
    total = sum((Decimal(str(row['execution_total'] or 0)) for row in rows), Decimal(0))
    pictures = json.dumps(list(dict.fromkeys(url for row in rows for url in photos(row['photo_url']))))
    if draft:
        cur.execute('UPDATE interim_acts SET total_amount=%s,work_journal_ids=%s,photo_urls=%s WHERE id=%s', (total, ids, pictures, draft_id))
    else:
        cur.execute('''INSERT INTO interim_acts(company_id,master_id,master_name,project,work_package,
            period_start,period_end,total_amount,paid_amount,status,work_journal_ids,source_type,photo_urls)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,0,'Новый',%s,'daily_work',%s)''',
            (scope[0], scope[5], work['master_name'], scope[1], scope[2], scope[3], scope[4], total, ids, pictures))
