import json
from decimal import Decimal

from fastapi import HTTPException

from . import records


def require_capacity(cur, work, project, accepted, deps):
    cur.execute('''SELECT i.quantity FROM brigade_contract_items i JOIN brigade_contracts c ON c.id=i.contract_id
        WHERE i.id=%s AND c.company_id=%s AND c.project_id=%s FOR UPDATE OF i''',
        (work['contract_item_id'], project['companyId'], project['id']))
    contract = cur.fetchone()
    if not contract:
        raise HTTPException(409, 'Договорная позиция больше не относится к объекту')
    if accepted:
        cur.execute("SELECT COALESCE(SUM(quantity::numeric(14,6)),0) AS done FROM work_journal WHERE contract_item_id=%s AND status='Подтверждено'",
                    (work['contract_item_id'],))
        if Decimal(str(cur.fetchone()['done'])) + accepted > Decimal(str(contract['quantity'] or 0)):
            raise HTTPException(409, 'Принятый объём превысит объём договорной позиции')
    if not work['estimate_id']:
        return
    cur.execute('SELECT sections_json FROM estimates WHERE id=%s AND company_id=%s FOR UPDATE', (work['estimate_id'], project['companyId']))
    estimate = cur.fetchone()
    if not estimate:
        raise HTTPException(409, 'Смета работы не найдена в компании')
    sections = estimate['sections_json']
    sections = json.loads(sections) if isinstance(sections, str) else sections
    target_key = work.get('estimate_item_key') or ''
    matches = [item for si, section in enumerate(sections or []) for ii, item in enumerate(section.get('items') or [])
               if target_key in deps['estimate_keys'](item, work['estimate_id'], si, ii)] if target_key else []
    if len(matches) != 1:
        raise HTTPException(409, 'Для приёмки нужна точная действующая позиция сметы')
    cur.execute("SELECT COALESCE(SUM(quantity::numeric(14,6)),0) AS done FROM work_journal WHERE estimate_id=%s AND estimate_item_key=%s AND status='Подтверждено'",
                (work['estimate_id'], target_key))
    if Decimal(str(cur.fetchone()['done'])) + accepted > Decimal(str(matches[0].get('quantity') or 0)):
        raise HTTPException(409, 'Принятый объём превысит объём сметы')


def room(cur, journal_id, project, deps):
    # All ancestors/descendants are immutable links; only this family may share a room/work key.
    cur.execute('''WITH RECURSIVE ancestors(id) AS (
        SELECT %s::int UNION ALL SELECT l.parent_journal_id FROM work_rework_links l JOIN ancestors a
        ON l.journal_id=a.id WHERE l.company_id=%s), family(id) AS (
        SELECT id FROM ancestors WHERE NOT EXISTS(SELECT 1 FROM work_rework_links WHERE journal_id=ancestors.id)
        UNION ALL SELECT l.journal_id FROM work_rework_links l JOIN family f ON l.parent_journal_id=f.id WHERE l.company_id=%s)
        SELECT id FROM family''', (journal_id, project['companyId'], project['companyId']))
    family = [row['id'] for row in cur.fetchall()]
    work = records.load(cur, journal_id, project['companyId'])
    deps['sync_room'](cur, work, family_journal_ids=family)
    return work


def related(cur, journal_id, project, deps, accepted=False):
    work = room(cur, journal_id, project, deps)
    deps['recalculate_contract'](cur, work['contract_item_id'])
    deps['recalculate_estimate'](cur, work, strict_key=True)
    if work['status'] != 'Отклонено':
        deps['sync_hidden'](cur, work, exact_journal_only=True)
    if accepted:
        from .daily_acts import sync_daily
        sync_daily(cur, work, project, deps['locked_act_statuses'])
