"""Company-owned alias storage used by the opt-in reader and separate HTTP editor.

Operators use membership-verified AliasAccess. Business readers must pass owner
IDs from an already authorized document. All writes use the caller's transaction.
"""
from dataclasses import dataclass
import re

from fastapi import HTTPException

from ..company_context.service import resolve_request_company_context, effective_company_actors
from ..project_access.service import resolve_project_parent, require_project_parent_access


def normalize_alias(value):
    return re.sub(r'\s+', ' ', re.sub(r'[.,;:()«»"\'`/\\]+', ' ', str(value or '').lower())).strip()


def _id(value, maximum=2147483647):
    if type(value) is not int or not 0 < value <= maximum:
        raise HTTPException(400, 'Требуется положительный идентификатор')
    return value


@dataclass(frozen=True)
class AliasAccess:
    actor: dict
    writable: bool
    full_project_roles: tuple


def require_alias_actor(cur, user, *, allowed_roles, company_id=None,
                        x_company_id=None, x_company_mode=None, write=False,
                        full_project_roles=(), platform_staff_roles=(), client_account_roles=()):
    if company_id is not None:
        _id(company_id)
    context = resolve_request_company_context(cur, user, company_id,
        'write' if write else 'read', x_company_id=x_company_id, x_company_mode=x_company_mode,
        platform_staff_roles=platform_staff_roles, client_account_roles=client_account_roles)
    if (context.get('mode') != 'company' or context.get('source') != 'membership'
            or not context.get('membershipId') or not context.get('active') or not context.get('companyActive')):
        raise HTTPException(403, 'Требуется активная роль в одной выбранной компании')
    # Hold authorization stable through the caller's transaction, including
    # time spent waiting for an alias writer. Recheck after pending revocations.
    cur.execute('SELECT id FROM users WHERE id=%s AND active=TRUE FOR SHARE', (user['id'],))
    if not cur.fetchone():
        raise HTTPException(403, 'Пользователь отключён')
    cur.execute('SELECT id FROM companies WHERE id=%s FOR SHARE', (context['companyId'],))
    cur.fetchone()
    membership_id = context['membershipId']
    cur.execute('SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE',
                (membership_id, user['id'], context['companyId']))
    if not cur.fetchone():
        raise HTTPException(403, 'Членство больше не действует')
    context = resolve_request_company_context(cur, user, context['companyId'], 'write' if write else 'read',
        platform_staff_roles=platform_staff_roles, client_account_roles=client_account_roles)
    if (context.get('source') != 'membership' or not context.get('active') or not context.get('companyActive')
            or context.get('membershipId') != membership_id):
        raise HTTPException(403, 'Членство больше не действует')
    actors = effective_company_actors(user, context)
    if len(actors) != 1 or actors[0].get('role') not in allowed_roles:
        raise HTTPException(403, 'Роль в компании не позволяет работать с соответствиями')
    actor = dict(actors[0])
    actor['projectName'] = actor['project_name'] = ''
    return AliasAccess(actor, write, tuple(full_project_roles))


def _write_scope(cur, access):
    if cur.connection.autocommit:
        raise RuntimeError('Alias mutations require an explicit transaction')
    if not isinstance(access, AliasAccess) or not access.writable:
        raise HTTPException(403, 'Нет права изменения соответствий')
    cur.execute('SHOW transaction_isolation')
    if cur.fetchone()['transaction_isolation'] != 'read committed':
        raise RuntimeError('Alias mutations require READ COMMITTED isolation')
    company_id, user_id = _id(access.actor.get('companyId')), _id(access.actor.get('id'))
    # Serialize all alias replacements/deactivations for this tenant, including
    # the absent-row case. Unrelated companies have independent advisory locks.
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (913041, company_id))
    return company_id, user_id


def _project(cur, access, project_id):
    if project_id is not None:
        parent = resolve_project_parent(cur, access.actor, project_id=_id(project_id))
        require_project_parent_access(cur, access.actor, parent, access.full_project_roles)


_UNCONDITIONAL = object()


def save_alias(cur, access, *, alias_name, canonical_name, canonical_unit='', project_id=None,
               expected_previous_id=_UNCONDITIONAL):
    company_id, user_id = _write_scope(cur, access)
    _project(cur, access, project_id)
    for value, maximum in ((alias_name, 500), (canonical_name, 500), (canonical_unit, 50)):
        if not isinstance(value, str) or len(value.strip()) > maximum:
            raise HTTPException(400, 'Недопустимое название или единица материала')
    alias_name, canonical_name, canonical_unit = alias_name.strip(), canonical_name.strip(), canonical_unit.strip()
    key = normalize_alias(alias_name)
    if not key or len(key) > 500 or not canonical_name:
        raise HTTPException(400, 'Укажите исходное и сметное название материала')
    if expected_previous_id is not _UNCONDITIONAL:
        if expected_previous_id is not None:
            _id(expected_previous_id, 9223372036854775807)
        cur.execute('''SELECT id FROM company_material_aliases
            WHERE company_id=%s AND project_id IS NOT DISTINCT FROM %s
              AND alias_key=%s AND active''', (company_id, project_id, key))
        current = cur.fetchone()
        if (current['id'] if current else None) != expected_previous_id:
            raise HTTPException(409, 'Соответствие изменилось. Обновите список перед сохранением')
    cur.execute('''UPDATE company_material_aliases SET active=FALSE,
        deactivated_by_id=%s,deactivated_at=now()
        WHERE company_id=%s AND project_id IS NOT DISTINCT FROM %s
          AND alias_key=%s AND active RETURNING id''', (user_id, company_id, project_id, key))
    old = cur.fetchone()
    cur.execute('''INSERT INTO company_material_aliases
        (company_id,project_id,alias_name,alias_key,canonical_name,canonical_unit,created_by_id,previous_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (company_id, project_id, alias_name, key, canonical_name, canonical_unit, user_id,
         old['id'] if old else None))
    return dict(cur.fetchone())


def deactivate_alias(cur, access, alias_id):
    company_id, user_id = _write_scope(cur, access)
    cur.execute('SELECT project_id FROM company_material_aliases WHERE id=%s AND company_id=%s FOR UPDATE',
                (_id(alias_id, 9223372036854775807), company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Соответствие не найдено')
    _project(cur, access, row['project_id'])
    cur.execute('''UPDATE company_material_aliases SET active=FALSE,
        deactivated_by_id=%s,deactivated_at=now() WHERE id=%s AND company_id=%s AND active''',
        (user_id, alias_id, company_id))


def list_aliases(cur, access, *, project_id=None, limit=100, offset=0):
    if not isinstance(access, AliasAccess):
        raise HTTPException(403, 'Требуется проверенный доступ к компании')
    if type(limit) is not int or not 1 <= limit <= 500 or type(offset) is not int or offset < 0:
        raise HTTPException(400, 'Недопустимые параметры страницы')
    _project(cur, access, project_id)
    # A project view includes company-wide mappings; no project means only the
    # company-wide scope, not all projects (which could expose assigned objects).
    cur.execute('''SELECT * FROM company_material_aliases WHERE company_id=%s AND active
        AND (project_id IS NULL OR project_id=%s) ORDER BY project_id NULLS LAST,alias_key,id
        LIMIT %s OFFSET %s''', (_id(access.actor.get('companyId')), project_id, limit, offset))
    return [dict(row) for row in cur.fetchall()]


def resolve_alias(cur, *, company_id, project_id=None, name):
    """Internal reader: owner IDs must come from a previously authorized resource.

    No legacy table fallback. Missing schema is a hard error, not silent matching.
    """
    company_id = _id(company_id)
    if project_id is not None:
        resolve_project_parent(cur, {'companyId': company_id}, project_id=_id(project_id))
    key = normalize_alias(name)
    if not key:
        return None
    cur.execute('''SELECT * FROM company_material_aliases WHERE company_id=%s AND active
        AND alias_key=%s AND (project_id IS NULL OR project_id=%s)
        ORDER BY project_id NULLS LAST LIMIT 1''', (company_id, key, project_id))
    row = cur.fetchone()
    return dict(row) if row else None
