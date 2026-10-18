"""Resolve explicit user, staff or existing-contract selections from stored links."""
import re

from fastapi import HTTPException

from .identity import PERFORMER_ROLES, classify_reference, positive_id
from .evidence import REFERENCE_EVIDENCE_SQL


def _id(value):
    if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,9}', value):
        value = int(value)
    try:
        return positive_id(value)
    except ValueError:
        raise HTTPException(400, 'Некорректный идентификатор исполнителя')


def resolve_selected_user(cur, company_id, reference, legacy_id=None, *, project_id=None, work_package=None):
    company_id = _id(company_id)
    if (not isinstance(reference, dict) or set(reference) != {'type', 'id'}
            or reference.get('type') not in ('user', 'staff', 'contract')):
        raise HTTPException(400, 'Выберите точную карточку исполнителя')
    selected_id = _id(reference['id'])
    if reference['type'] == 'contract':
        return _resolve_contract_user(cur, company_id, selected_id, legacy_id, project_id, work_package)
    if legacy_id not in (None, '') and _id(legacy_id) != selected_id:
        raise HTTPException(400, 'Карточка и идентификатор исполнителя не совпадают')
    roles = sorted(PERFORMER_ROLES)
    if reference['type'] == 'user':
        cur.execute('''SELECT u.id FROM users u JOIN user_company_roles m ON m.user_id=u.id
            WHERE u.id=%s AND u.active IS TRUE AND u.role=ANY(%s)
                AND m.company_id=%s AND m.active IS TRUE AND m.role=ANY(%s)
            ORDER BY m.id FOR UPDATE OF m''',
            (selected_id, roles, company_id, roles))
    else:
        cur.execute('''SELECT id FROM staff WHERE id=%s AND company_id=%s
            AND company_scope_verified IS TRUE AND COALESCE(status,'Активен')='Активен' ''',
            (selected_id, company_id))
        if not cur.fetchone():
            raise HTTPException(409, 'Карточка исполнителя недоступна. Обновите список')
        cur.execute('''SELECT u.id FROM users u
            JOIN user_company_roles m ON m.user_id=u.id
            WHERE m.company_id=%s AND m.staff_id=%s AND m.active IS TRUE
                AND u.active IS TRUE AND u.role=ANY(%s) AND m.role=ANY(%s)
            ORDER BY u.id,m.id FOR UPDATE OF m''', (company_id, selected_id, roles, roles))
    rows = cur.fetchall()
    user_ids={_id(row['id'] if isinstance(row,dict) else row[0]) for row in rows}
    if len(user_ids) != 1:
        raise HTTPException(409, 'Для выбранного исполнителя нужен один действующий доступ. Проверьте карточку сотрудника')
    return user_ids.pop()


def _resolve_contract_user(cur, company_id, contract_id, legacy_id, project_id, work_package):
    project_id = _id(project_id)
    if not isinstance(work_package, str) or not work_package.strip():
        raise HTTPException(400, 'Не указан раздел работ договора')
    scope = (contract_id, company_id, project_id, work_package)
    where = ''' WHERE bc.id=%s AND bc.company_id=%s AND bc.project_id=%s
        AND COALESCE(NULLIF(bc.work_package,''),'Основная')=%s
        AND COALESCE(bc.status,'') NOT IN ('Аннулирован','Удалён','Удален')'''
    cur.execute('SELECT bc.contractor_id FROM brigade_contracts bc' + where, scope)
    row = cur.fetchone()
    owner = (row.get('contractor_id') if isinstance(row, dict) else row[0]) if row else None
    if owner is None:
        raise HTTPException(409, 'Выбранный договор недоступен или его исполнитель не подтверждён. Проверьте договор')
    # Keep the same membership -> advisory scope -> contract locking order as
    # the ordinary creation path. Recheck the evidence after obtaining the lock.
    user_id = resolve_selected_user(cur, company_id, {'type': 'user', 'id': owner}, legacy_id)
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (company_id, project_id))
    cur.execute(REFERENCE_EVIDENCE_SQL + where + ' FOR UPDATE OF bc', scope)
    row = cur.fetchone()
    if row:
        evidence = row if isinstance(row, dict) else dict(zip((column[0] for column in cur.description), row))
        reference = classify_reference(evidence)['reference']
        if reference == {'type': 'user', 'id': user_id}:
            return user_id
    raise HTTPException(409, 'Не удалось подтвердить исполнителя выбранного договора. Проверьте связь в договоре')
