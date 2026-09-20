"""Company membership and exact project boundaries for project records."""
from contextlib import contextmanager

import psycopg2.extras
from fastapi import HTTPException

from ..project_access.service import require_project_write_actor, resolve_project_parent

TABLES = frozenset(('prescriptions', 'warranty_defects', 'project_documents', 'project_letters'))


def positive_id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        result = int(value)
    except ValueError:
        return None
    return result if result > 0 else None


def project_visibility(actors, roles, visible_project_names):
    clauses, params = [], []
    for actor in actors:
        company_id = positive_id(actor.get('companyId') or actor.get('company_id'))
        if not company_id or actor.get('role') not in roles:
            continue
        parts = ['p.company_id=%s']
        values = [company_id]
        names = visible_project_names(actor)
        if names is not None:
            if not names:
                continue
            parts.append('p.name=ANY(%s)'); values.append(names)
            assigned = actor.get('project_id')
            if assigned is None:
                assigned = actor.get('projectId')
            if actor.get('role') == 'заказчик' and assigned not in (None, ''):
                assigned = positive_id(assigned)
                if not assigned:
                    continue
                parts.append('p.id=%s'); values.append(assigned)
            else:
                parts.append('NOT EXISTS (SELECT 1 FROM projects other WHERE '
                             'other.company_id=p.company_id AND other.name=p.name AND other.id<>p.id)')
        clauses.append('(' + ' AND '.join(parts) + ')'); params.extend(values)
    return ('(' + ' OR '.join(clauses) + ')', params) if clauses else ('FALSE', [])


def require_record_author(actor, created_by_user_id):
    if actor.get('role') == 'заказчик':
        actor_id = positive_id(actor.get('id'))
        if not actor_id or actor_id != positive_id(created_by_user_id):
            raise HTTPException(status_code=403, detail='Нет доступа к изменению чужого обращения')


class RecordScope:
    def __init__(self, get_db, resolve_context, effective_actors, visible_project_names):
        self.get_db = get_db
        self.resolve_context = resolve_context
        self.effective_actors = effective_actors
        self.visible_project_names = visible_project_names

    @contextmanager
    def transaction(self, user, request, roles, *, write=False):
        conn = self.get_db()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as context_cur:
                headers = request.headers if request is not None else {}
                context = self.resolve_context(context_cur, user, None, 'write' if write else 'read',
                    x_company_id=headers.get('x-company-id'), x_company_mode=headers.get('x-company-mode'))
                actors = self.effective_actors(user, context)
            if write:
                actors = [require_project_write_actor(actors, roles)]
            else:
                actors = [actor for actor in actors if actor.get('role') in roles]
            with conn.cursor() as cur:
                yield cur, actors
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def visible(self, actors, roles):
        return project_visibility(actors, roles, self.visible_project_names)

    def parent(self, cur, actor, data, roles):
        raw_id = data.get('projectId')
        if raw_id not in (None, '') and not positive_id(raw_id):
            raise HTTPException(status_code=422, detail='Некорректный идентификатор объекта')
        parent = resolve_project_parent(cur, actor, project_id=raw_id,
                                        project_name=data.get('projectName', ''), for_update=True)
        where, params = self.visible([actor], roles)
        cur.execute('SELECT p.id FROM projects p WHERE p.id=%s AND ' + where, (parent['id'], *params))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail='Нет доступа к объекту')
        return parent

    def record(self, cur, actor, table, record_id, roles):
        if table not in TABLES:
            raise ValueError('Unsupported owned record table')
        where, params = self.visible([actor], roles)
        cur.execute(f'SELECT r.project_id,r.company_id,r.created_by_user_id FROM {table} r '
                    'JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                    'WHERE r.id=%s AND ' + where + ' FOR UPDATE OF r,p', (record_id, *params))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Запись не найдена в доступном объекте')
        return row
