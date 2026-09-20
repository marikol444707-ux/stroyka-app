"""Prescriptions scoped to the selected company, project and immutable author."""
from fastapi import Depends, HTTPException, Request

from ..customer_cabinet.record_scope import require_record_author


def register_prescriptions_module(app, deps):
    authenticated = deps['get_current_user']
    read_roles = tuple(deps.get('read_roles') or ())
    write_roles = tuple(deps.get('write_roles') or ())
    worker_roles = tuple(deps.get('worker_execution_roles') or ())
    scope = deps['record_scope']
    create_roles = (*write_roles, 'заказчик')

    @app.get('/prescriptions')
    def get_prescriptions(current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            # A customer sees their own remarks and replies; internal findings are not published.
            clauses, params = [], []
            for actor in actors:
                where, values = scope.visible([actor], read_roles)
                if actor.get('role') == 'заказчик':
                    where += ' AND r.created_by_user_id=%s'; values.append(actor.get('id'))
                clauses.append('(' + where + ')'); params.extend(values)
            where = ' OR '.join(clauses) or 'FALSE'
            cur.execute('SELECT r.id,p.name,r.number,r.issued_by,r.issued_by_role,r.violation,'
                        'r.deadline,r.responsible,r.status,r.photo_url,r.fix_photo_url,r.fix_notes,'
                        'r.company_id,r.project_id,r.created_by_user_id FROM prescriptions r '
                        'JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                        "WHERE COALESCE(r.status,'') <> 'Аннулировано' AND (" + where + ') ORDER BY r.id DESC', params)
            rows = cur.fetchall()
        keys = ('id','projectName','number','issuedBy','issuedByRole','violation','deadline','responsible',
                'status','photoUrl','fixPhotoUrl','fixNotes','companyId','projectId','createdByUserId')
        return [dict(zip(keys, row)) for row in rows]

    @app.post('/prescriptions')
    def create_prescription(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        text = data.get('violation')
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise HTTPException(status_code=422, detail='Укажите замечание длиной до 10000 символов')
        with scope.transaction(current_user, request, create_roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, data, create_roles)
            customer = actor.get('role') == 'заказчик'
            cur.execute('INSERT INTO prescriptions (project_name,number,issued_by,issued_by_role,violation,'
                        'deadline,responsible,status,photo_url,company_id,project_id,created_by_user_id) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                        (parent['name'], data.get('number',''), actor.get('name',''),
                         'Заказчик' if customer else data.get('issuedByRole',actor.get('role','')),
                         text.strip(), '' if customer else data.get('deadline',''),
                         '' if customer else data.get('responsible',''),
                         'Открыто' if customer else data.get('status','Открыто'), data.get('photoUrl',''),
                         parent['companyId'],parent['id'],actor['id']))
            record_id = cur.fetchone()[0]
        return {'id':record_id,'ok':True}

    @app.put('/prescriptions/{id}')
    def update_prescription(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles, write=True) as (cur, actors):
            actor = actors[0]
            owner = scope.record(cur, actor, 'prescriptions', id, read_roles)
            require_record_author(actor, owner[2])
            status = data.get('status','')
            if actor.get('role') in (*worker_roles,'кладовщик','снабженец') and status not in ('На проверке',''):
                raise HTTPException(status_code=403, detail='Можно только отправить предписание на проверку')
            if actor.get('role') == 'заказчик':
                if status not in ('Открыто','Закрыто') or any(key in data for key in ('fixPhotoUrl','fixNotes')):
                    raise HTTPException(status_code=403, detail='Заказчик может только закрыть или повторно открыть своё замечание')
                cur.execute('UPDATE prescriptions SET status=%s WHERE id=%s', (status,id))
            else:
                fields = {'status':'status','fixPhotoUrl':'fix_photo_url','fixNotes':'fix_notes'}
                selected = [(column,data[key]) for key,column in fields.items() if key in data]
                if selected:
                    cur.execute('UPDATE prescriptions SET ' + ','.join(column+'=%s' for column,_ in selected)
                                + ' WHERE id=%s', [value for _,value in selected]+[id])
        return {'ok':True}

    @app.delete('/prescriptions/{id}')
    def delete_prescription(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], 'prescriptions', id, write_roles)
            cur.execute("UPDATE prescriptions SET status='Аннулировано' WHERE id=%s", (id,))
        return {'ok':True}
