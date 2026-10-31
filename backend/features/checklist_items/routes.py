"""Checklist items inherit the exact authorized parent project."""
from fastapi import Depends, HTTPException, Request
from ..project_checklists.routes import require_checklist


def register_checklist_items_module(app, deps):
    scope = deps['record_scope']
    authenticated = deps['get_current_user']
    read_roles = tuple(deps['project_document_roles'])
    write_roles = tuple(deps['project_write_roles'])
    update_roles = (*write_roles, 'технадзор', 'стройконтроль')

    @app.get('/checklist-items/{checklist_id}')
    def get_checklist_items(checklist_id: int, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            require_checklist(cur, scope, actors, checklist_id, read_roles)
            cur.execute('SELECT id,checklist_id,name,checked,checked_by,checked_at,order_num '
                        'FROM checklist_items WHERE checklist_id=%s ORDER BY order_num,id', (checklist_id,))
            rows = cur.fetchall()
        return [dict(zip(('id','checklistId','name','checked','checkedBy','checkedAt','orderNum'), row)) for row in rows]

    @app.post('/checklist-items')
    def create_checklist_item(data: dict, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            require_checklist(cur, scope, actors, int(data.get('checklistId') or 0), write_roles, lock=True)
            cur.execute('INSERT INTO checklist_items (checklist_id,name,checked,checked_by,checked_at,order_num) '
                        'VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                        (data.get('checklistId'),data.get('name',''),data.get('checked',False),
                         data.get('checkedBy',''),data.get('checkedAt',''),int(data.get('orderNum',0))))
            record_id = cur.fetchone()[0]
        return {'id': record_id, 'ok': True}

    @app.put('/checklist-items/{id}')
    def update_checklist_item(id: int, data: dict, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, update_roles, write=True) as (cur, actors):
            where, params = scope.visible(actors, update_roles)
            cur.execute('SELECT i.id FROM checklist_items i JOIN project_checklists c ON c.id=i.checklist_id '
                        'JOIN projects p ON p.id=c.project_id WHERE i.id=%s AND ' + where + ' FOR UPDATE OF i,c,p', (id,*params))
            if not cur.fetchone():
                raise HTTPException(404, 'Пункт чек-листа не найден в доступном объекте')
            cur.execute('UPDATE checklist_items SET checked=%s,checked_by=%s,checked_at=%s WHERE id=%s',
                        (data.get('checked',False),data.get('checkedBy',''),data.get('checkedAt',''),id))
        return {'ok': True}
