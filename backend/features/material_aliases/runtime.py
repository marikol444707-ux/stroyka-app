"""Opt-in owned-alias reader. Never falls back to legacy mappings when enabled."""
import os
import psycopg2.extras
from fastapi import HTTPException

from .scoped import resolve_alias
from ..project_access.service import resolve_project_parent


def owned_aliases_enabled():
    return os.environ.get('COMPANY_MATERIAL_ALIASES_ENABLED', '').strip() == '1'


def resolve_owned_alias(cur, project, name, unit='', *, company_id=None, project_id=None):
    if type(company_id) is not int or company_id <= 0:
        raise HTTPException(409, 'Компания соответствия материала не определена')
    if project_id is not None and (type(project_id) is not int or project_id <= 0):
        raise HTTPException(409, 'Некорректный объект соответствия материала')
    project_name = (project or '').strip()
    # RealDict cursor on the SAME transaction: legacy callers also use tuples.
    with cur.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as scope_cur:
        if not cur.connection.autocommit:
            # A document may resolve many lines. Keep one directory version
            # until its transaction finishes; editors take the exclusive lock.
            scope_cur.execute('SELECT pg_advisory_xact_lock_shared(%s,%s)', (913041, company_id))
        if project_name and project_name != 'Основной склад':
            parent = resolve_project_parent(scope_cur, {'companyId': company_id},
                project_id=project_id, project_name=project_name)
            project_id, project_name = parent['id'], parent['name']
        elif project_id is not None:
            raise HTTPException(409, 'Объект соответствия не совпадает со складом')
        row = resolve_alias(scope_cur, company_id=company_id, project_id=project_id, name=name)
    if not row:
        return None
    return {'id': row['id'], 'companyId': row['company_id'], 'projectId': row['project_id'],
            'projectName': project_name if row['project_id'] else '',
            'aliasName': row['alias_name'], 'canonicalName': row['canonical_name'],
            'canonicalUnit': row['canonical_unit'] or unit, 'matchType': 'company_owned'}
