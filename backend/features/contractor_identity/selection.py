"""Resolve an explicit user/staff selection using persisted company links only."""
import re

from fastapi import HTTPException

from .identity import PERFORMER_ROLES, positive_id


def _id(value):
    if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,9}', value):
        value = int(value)
    try:
        return positive_id(value)
    except ValueError:
        raise HTTPException(400, 'Некорректный идентификатор исполнителя')


def resolve_selected_user(cur, company_id, reference, legacy_id=None):
    company_id = _id(company_id)
    if (not isinstance(reference, dict) or set(reference) != {'type', 'id'}
            or reference.get('type') not in ('user', 'staff')):
        raise HTTPException(400, 'Выберите точную карточку исполнителя')
    selected_id = _id(reference['id'])
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
