"""Exact ownership for legacy project records; names never establish stored ownership."""
from fastapi import HTTPException

TABLES = frozenset(('inspection_orders', 'supervisor_acts', 'contracts', 'project_chat', 'tb_journal', 'interim_acts', 'room_works'))


def owned_query(scope, actors, roles, table, columns, *, record_id=None, project_name=None, lock=False):
    if table not in TABLES:
        raise ValueError('Unsupported owned table')
    where, params = scope.visible(actors, roles)
    params = list(params)
    query = (f'SELECT {columns} FROM {table} r JOIN projects p '
             'ON p.id=r.project_id AND p.company_id=r.company_id WHERE ' + where)
    if record_id is not None:
        query += ' AND r.id=%s'; params.append(record_id)
    if project_name:
        query += ' AND p.name=%s'; params.append(project_name)
    if lock:
        query += ' FOR UPDATE OF r,p'
    return query, params


def require_record(cur, scope, actors, roles, table, record_id):
    query, params = owned_query(scope, actors, roles, table, 'r.id', record_id=record_id, lock=True)
    cur.execute(query, params)
    if not cur.fetchone():
        raise HTTPException(404, 'Запись не найдена в доступном объекте')
