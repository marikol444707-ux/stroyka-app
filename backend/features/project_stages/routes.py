"""Project stages use their canonical project and current company membership."""
from fastapi import Depends, HTTPException, Request


FIELDS = {
    'name': 'name', 'status': 'status', 'startDate': 'start_date',
    'endDate': 'end_date', 'progress': 'progress', 'responsible': 'responsible',
    'notes': 'notes', 'orderNum': 'order_num',
}


def stage_values(data):
    values = {column: data[key] for key, column in FIELDS.items() if key in data}
    for column in ('progress', 'order_num'):
        if column not in values:
            continue
        value = values[column]
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise HTTPException(422, 'Некорректное числовое значение этапа')
        try:
            values[column] = int(value)
        except ValueError:
            raise HTTPException(422, 'Некорректное числовое значение этапа')
        if not 0 <= values[column] <= (100 if column == 'progress' else 2147483647):
            raise HTTPException(422, 'Некорректное числовое значение этапа')
    limits = {'name': 255, 'status': 50, 'start_date': 50, 'end_date': 50, 'responsible': 255, 'notes': 10000}
    for column in set(values) - {'progress', 'order_num'}:
        if not isinstance(values[column], str) or len(values[column]) > limits[column]:
            raise HTTPException(422, 'Некорректный текст этапа')
    return values


def register_project_stages_module(app, deps):
    authenticated = deps['get_current_user']
    read_roles = tuple(deps.get('read_roles') or ())
    write_roles = tuple(deps.get('write_roles') or ())
    scope = deps['record_scope']

    def require_stage(cur, actor, stage_id):
        where, params = scope.visible([actor], write_roles)
        cur.execute('SELECT s.id FROM project_stages s JOIN projects p ON p.id=s.project_id '
                    'WHERE s.id=%s AND ' + where + ' FOR UPDATE OF s,p', (stage_id, *params))
        if not cur.fetchone():
            raise HTTPException(404, 'Этап не найден в доступном объекте')

    @app.get('/project-stages')
    def get_project_stages(current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = scope.visible(actors, read_roles)
            cur.execute('SELECT s.id,s.project_id,p.name,s.name,s.status,s.start_date,s.end_date,'
                        's.progress,s.responsible,s.notes,s.order_num,p.company_id '
                        'FROM project_stages s JOIN projects p ON p.id=s.project_id WHERE '
                        + where + ' ORDER BY s.order_num,s.id', params)
            rows = cur.fetchall()
        roles = {int(actor.get('companyId') or actor.get('company_id')): actor['role'] for actor in actors}
        keys = ('id', 'projectId', 'projectName', 'name', 'status', 'startDate', 'endDate',
                'progress', 'responsible', 'notes', 'orderNum', 'companyId')
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            if roles.get(item['companyId']) == 'заказчик':
                item.pop('responsible', None)
                item.pop('notes', None)
            result.append(item)
        return result

    @app.post('/project-stages')
    def create_project_stage(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        values = {
            'name': '', 'status': 'Не начат', 'start_date': '', 'end_date': '',
            'progress': 0, 'responsible': '', 'notes': '', 'order_num': 0,
            **stage_values(data),
        }
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], data, write_roles)
            values = {'project_id': parent['id'], 'project_name': parent['name'], **values}
            columns = ','.join(values)
            placeholders = ','.join(['%s'] * len(values))
            cur.execute(f'INSERT INTO project_stages ({columns}) VALUES ({placeholders}) RETURNING id', list(values.values()))
            stage_id = cur.fetchone()[0]
        return {'id': stage_id, 'ok': True}

    @app.put('/project-stages/{id}')
    def update_project_stage(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        values = stage_values(data)
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_stage(cur, actors[0], id)
            if values:
                cur.execute('UPDATE project_stages SET ' + ','.join(column+'=%s' for column in values)
                            + ' WHERE id=%s', [*values.values(), id])
        return {'ok': True}

    @app.delete('/project-stages/{id}')
    def delete_project_stage(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_stage(cur, actors[0], id)
            cur.execute('DELETE FROM project_stages WHERE id=%s', (id,))
        return {'ok': True}
