import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from ..work_material_accounting import service as materials
from ..work_material_accounting.documents import owned_document_url
from ..work_material_accounting.settlement_guards import require_unacted_work
from ..work_material_accounting.quantities import validate_items
from . import records, sync
from .policy import review_quantities

COMMON_FIELDS = {'requestId', 'expectedState', 'expectedCompanyId', 'expectedActorId', 'materialAccountingVersion'}


def evidence(cur, value, project, required=False):
    if not isinstance(value, list) or len(value) > 20 or (required and not value):
        raise HTTPException(400, 'Приложите фотографии выполненной работы (не более 20)')
    result = []
    for url in value:
        if not isinstance(url, str) or not url.startswith('/tenant-files/'):
            raise HTTPException(400, 'Загрузите фотографии в программу')
        url = owned_document_url(cur, url, project['companyId'], project['id'], require_upload=True)
        cur.execute('SELECT content_type FROM file_ownership WHERE id=%s', (int(url.split('/')[2]),))
        if not (cur.fetchone()['content_type'] or '').startswith('image/'):
            raise HTTPException(400, 'Для приёмки приложите фотографию, а не документ')
        if url not in result:
            result.append(url)
    return result


def text_field(data, name, maximum=4000):
    value = data.get(name, '')
    if not isinstance(value, str) or len(value) > maximum:
        raise HTTPException(400, 'Некорректный текст замечаний или комментария')
    return value.strip()


def scaled_totals(work, qty):
    # Allocate the saved totals, including a final cent, without using today's contract price.
    return {field: (Decimal(str(work[field] or 0)) * qty / Decimal(str(work['quantity']))).quantize(
        Decimal('.01'), rounding=ROUND_HALF_UP) for field in ('total', 'execution_total', 'customer_total')}


def create_rework(cur, work, project, review_id, remaining, accepted_totals):
    fields = ('company_id', 'master_id', 'master_name', 'project', 'description', 'unit', 'price_per_unit',
              'date', 'estimate_id', 'section_name', 'responsible_itr', 'hidden_work', 'normatives',
              'project_docs', 'work_package', 'room_id', 'room_name', 'surface', 'estimate_item_name',
              'estimate_item_key', 'contract_item_id', 'customer_price_per_unit', 'execution_price_per_unit',
              'execution_price_mode')
    child = {field: work[field] for field in fields}
    child.update(quantity=remaining, status='На доработке', material_accounting_version=2,
                 photo_url='', materials_used='[]', comment='')
    child.update({field: Decimal(str(work[field] or 0)) - accepted_totals[field] for field in accepted_totals})
    cur.execute('INSERT INTO work_journal (' + ','.join(child) + ') VALUES (' + ','.join(['%s'] * len(child)) + ') RETURNING id', tuple(child.values()))
    child_id = cur.fetchone()['id']
    cur.execute('''INSERT INTO work_rework_links(journal_id,company_id,project_id,parent_journal_id,review_id,quantity)
        VALUES(%s,%s,%s,%s,%s,%s)''', (child_id, project['companyId'], project['id'], work['id'], review_id, remaining))
    return child_id


def review(cur, work, project, actor, operation_id, data, deps):
    if work['status'] != 'На проверке':
        raise HTTPException(409, 'По этой работе уже принято решение или она ещё не сдана')
    require_unacted_work(cur, work['id'])
    reason = text_field(data, 'reason')
    accepted, remaining = review_quantities(work['quantity'], data.get('acceptedQuantity'), data.get('decision'), reason)
    photos = evidence(cur, data.get('photos', []), project)
    if accepted and work.get('hidden_work'):
        evidence(cur, records.photos(work['photo_url']), project, required=True)
    if remaining:
        cur.execute("SELECT id,status FROM hidden_works_acts WHERE company_id=%s AND work_journal_id=%s FOR UPDATE",
                    (project['companyId'], work['id']))
        if any(row['status'] == 'Подписан' for row in cur.fetchall()):
            raise HTTPException(409, 'По работе подписан АОСР. Сначала оформите его корректировку')
    sync.require_capacity(cur, work, project, accepted, deps)
    cur.execute('''INSERT INTO work_acceptance_reviews(company_id,project_id,journal_id,operation_id,
        actor_id,actor_name,decision,submitted_quantity,accepted_quantity,reason,photos,work_snapshot)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (project['companyId'], project['id'], work['id'], operation_id, actor['id'], actor.get('name') or '',
         data['decision'], work['quantity'], accepted, reason, Json(photos), Json(jsonable_encoder(work))))
    review_id = cur.fetchone()['id']
    totals = scaled_totals(work, accepted)
    # Create lineage while the parent still contains its original submitted volume.
    child_id = create_rework(cur, work, project, review_id, remaining, totals) if remaining else None
    if accepted:
        cur.execute('''UPDATE work_journal SET quantity=%s,total=%s,execution_total=%s,customer_total=%s,
            status='Подтверждено',confirmed_by=%s,confirmed_at=%s WHERE id=%s''',
            (accepted, totals['total'], totals['execution_total'], totals['customer_total'],
             actor.get('name') or '', date.today().isoformat(), work['id']))
    else:
        cur.execute("UPDATE work_journal SET status='Отклонено',confirmed_by=%s,confirmed_at=%s WHERE id=%s",
                    (actor.get('name') or '', date.today().isoformat(), work['id']))
        cur.execute("UPDATE hidden_works_acts SET status='Аннулирован' WHERE company_id=%s AND work_journal_id=%s AND status<>'Подписан'",
                    (project['companyId'], work['id']))
    sync.related(cur, work['id'], project, deps, accepted=bool(accepted))
    if child_id:
        sync.room(cur, child_id, project, deps)
    return {'ok': True, 'journalId': work['id'], 'reviewId': review_id, 'reworkJournalId': child_id}


def resubmit(cur, work, project, actor, operation_id, data, deps):
    cur.execute('SELECT quantity FROM work_rework_links WHERE journal_id=%s AND company_id=%s', (work['id'], project['companyId']))
    link = cur.fetchone()
    if not link or work['status'] != 'На доработке' or Decimal(str(work['quantity'])) != link['quantity']:
        raise HTTPException(409, 'Доработка уже сдана или её состояние изменилось')
    if actor['id'] != work['master_id']:
        raise HTTPException(403, 'Повторно сдаёт работу назначенный исполнитель')
    comment = text_field(data, 'comment')
    if not comment:
        raise HTTPException(400, 'Опишите, как устранены замечания')
    photos = evidence(cur, data.get('photos', []), project, required=True)
    items = data.get('materialsUsed', [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise HTTPException(400, 'Материалы работы должны быть списком')
    validate_items(items)
    if any(item.get('work_package') is not None and not isinstance(item['work_package'], str) for item in items):
        raise HTTPException(400, 'Некорректный пакет материала')
    items = deps['force_material_package'](items, work['work_package'])
    if not isinstance(items, list) or any(not isinstance(item, dict) or not deps['has_package_access'](actor, item.get('workPackage') or 'Основная') for item in items):
        raise HTTPException(400, 'Проверьте материалы и доступ к пакету работ')
    prepared = materials.prepare(cur, project, actor, items, material_key=deps['material_key'],
                                 personal_balance=deps['personal_balance'], norm_unit=deps['norm_unit'])
    work_date = date.today().isoformat()
    cur.execute("UPDATE work_journal SET status='На проверке',comment=%s,photo_url=%s,date=%s WHERE id=%s",
                (comment, ','.join(photos), work_date, work['id']))
    materials.post(cur, project, actor, work['id'], operation_id, prepared, work_date)
    cur.execute('''INSERT INTO work_rework_submissions(journal_id,company_id,operation_id,actor_id,comment,photos)
        VALUES(%s,%s,%s,%s,%s,%s)''', (work['id'], project['companyId'], operation_id, actor['id'], comment, Json(photos)))
    sync.related(cur, work['id'], project, deps)
    return {'ok': True, 'journalId': work['id']}


def execute(cur, work, project, actor, operation_id, action, data, deps):
    allowed = {'decision', 'acceptedQuantity', 'reason', 'photos'} if action == 'acceptance' else {'comment', 'photos', 'materialsUsed'}
    if set(data) - allowed - COMMON_FIELDS:
        raise HTTPException(400, 'В отправке есть неподдерживаемые поля')
    if data.get('expectedState') != records.state(work):
        raise HTTPException(409, 'Работа изменилась. Обновите её перед сохранением решения')
    handler = review if action == 'acceptance' else resubmit
    return handler(cur, work, project, actor, operation_id, data, deps)
