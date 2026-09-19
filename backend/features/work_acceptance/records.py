import hashlib
import json

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from .policy import REVIEWERS, WORKERS, enabled


def load(cur, journal_id, company_id):
    cur.execute('SELECT * FROM work_journal WHERE id=%s AND company_id=%s FOR UPDATE', (journal_id, company_id))
    work = cur.fetchone()
    if not work or work['material_accounting_version'] != 2:
        raise HTTPException(404, 'Новый цикл приёмки для этой записи недоступен')
    return dict(work)


def state(work):
    value = json.dumps(jsonable_encoder(work), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(value.encode()).hexdigest()


def photos(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (ValueError, TypeError):
        pass
    return [url.strip() for url in value.split(',') if url.strip()]


def report(cur, work, actor):
    journal_id, company_id = work['id'], work['company_id']
    cur.execute('''SELECT id,actor_name AS "actorName",decision,
        submitted_quantity AS "submittedQuantity",accepted_quantity AS "acceptedQuantity",
        reason,photos,created_at AS "createdAt" FROM work_acceptance_reviews
        WHERE journal_id=%s AND company_id=%s ORDER BY id''', (journal_id, company_id))
    history = [dict(row) for row in cur.fetchall()]
    cur.execute('SELECT journal_id FROM work_rework_links WHERE parent_journal_id=%s AND company_id=%s', (journal_id, company_id))
    child = cur.fetchone()
    cur.execute('SELECT l.parent_journal_id,r.reason FROM work_rework_links l JOIN work_acceptance_reviews r ON r.id=l.review_id WHERE l.journal_id=%s AND l.company_id=%s', (journal_id, company_id))
    parent = cur.fetchone()
    return {'journalId': journal_id, 'status': work['status'], 'quantity': work['quantity'],
            'description': work['description'], 'unit': work['unit'], 'roomName': work['room_name'],
            'project': work['project'], 'date': work['date'], 'masterName': work['master_name'],
            'workPackage': work['work_package'], 'comment': work['comment'], 'photos': photos(work['photo_url']),
            'expectedState': state(work), 'history': history, 'returnReason': parent['reason'] if parent else '',
            'canReview': enabled() and actor['role'] in REVIEWERS and work['status'] == 'На проверке' and not history,
            'canResubmit': enabled() and actor['role'] in WORKERS and actor['id'] == work['master_id']
                and work['status'] == 'На доработке' and bool(parent),
            'reworkJournalId': child['journal_id'] if child else None,
            'parentJournalId': parent['parent_journal_id'] if parent else None}


def guard_direct_mutation(cur, journal_id, work, data=None):
    # Older installations and isolated legacy fixtures have not applied 0028 yet.
    cur.execute("SELECT to_regclass('public.work_acceptance_reviews') AS reviews")
    if not cur.fetchone()['reviews']:
        return
    cur.execute('''SELECT 1 FROM work_acceptance_reviews WHERE journal_id=%s
        UNION ALL SELECT 1 FROM work_rework_links WHERE journal_id=%s LIMIT 1''', (journal_id, journal_id))
    if cur.fetchone():
        raise HTTPException(409, 'Для этой работы используйте историю приёмки и повторную сдачу')
    if enabled() and work.get('material_accounting_version') == 2 and (
            data is None or data.get('status') in ('Подтверждено', 'Отклонено', 'Аннулировано')):
        raise HTTPException(409, 'Откройте приёмку работы и сохраните решение')


def guard_hidden_act(cur, act_id):
    # Called under the same stock lock as acceptance, before a signature snapshot.
    cur.execute("SELECT to_regclass('public.work_acceptance_reviews')")
    if not cur.fetchone()[0]:
        return
    cur.execute('''SELECT r.decision FROM hidden_works_acts h
        JOIN work_acceptance_reviews r ON r.journal_id=h.work_journal_id AND r.company_id=h.company_id
        WHERE h.id=%s FOR UPDATE OF h''', (act_id,))
    row = cur.fetchone()
    if row and row[0] == 'return':
        raise HTTPException(409, 'Работа возвращена на доработку. Этот АОСР аннулирован; используйте акт повторно сданной работы')
