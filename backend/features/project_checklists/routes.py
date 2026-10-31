"""Checklists authorized through their exact project, in the selected company."""
from fastapi import Depends, HTTPException, Request


def require_checklist(cur, scope, actors, checklist_id, roles, *, lock=False):
    where, params = scope.visible(actors, roles)
    cur.execute('SELECT c.id FROM project_checklists c JOIN projects p ON p.id=c.project_id '
                'WHERE c.id=%s AND ' + where + (' FOR UPDATE OF c,p' if lock else ''),
                (checklist_id, *params))
    if not cur.fetchone():
        raise HTTPException(404, 'Чек-лист не найден в доступном объекте')


def register_project_checklists_module(app, deps):
    scope = deps['record_scope']
    authenticated = deps['get_current_user']
    read_roles = tuple(deps['read_roles'])
    write_roles = tuple(deps['write_roles'])

    @app.get('/project-checklists')
    def get_project_checklists(request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = scope.visible(actors, read_roles)
            cur.execute('SELECT c.id,c.project_id,p.name,c.name,c.template,c.status,c.created_by,c.created_at '
                        'FROM project_checklists c JOIN projects p ON p.id=c.project_id WHERE ' + where + ' ORDER BY c.id', params)
            rows = cur.fetchall()
        return [dict(zip(('id','projectId','projectName','name','template','status','createdBy','createdAt'),
                         (*row[:7], str(row[7])))) for row in rows]

    @app.post('/project-checklists')
    def create_project_checklist(data: dict, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], data, write_roles)
            cur.execute('INSERT INTO project_checklists (project_id,project_name,name,template,status,created_by,created_at) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                        (parent['id'],parent['name'],data.get('name',''),data.get('template',''),
                         data.get('status','В работе'),data.get('createdBy',''),data.get('createdAt','')))
            record_id = cur.fetchone()[0]
        return {'id': record_id, 'ok': True}

    @app.delete('/project-checklists/{id}')
    def delete_project_checklist(id: int, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_checklist(cur, scope, actors, id, write_roles, lock=True)
            cur.execute('DELETE FROM checklist_items WHERE checklist_id=%s', (id,))
            cur.execute('DELETE FROM project_checklists WHERE id=%s', (id,))
        return {'ok': True}
