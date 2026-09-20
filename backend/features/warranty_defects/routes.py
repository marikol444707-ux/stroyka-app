"""Warranty requests with exact company/project ownership."""
from fastapi import Depends, HTTPException, Request


def register_warranty_defects_module(app, deps):
    authenticated = deps['get_current_user']
    read_roles = tuple(deps.get('read_roles') or ())
    write_roles = tuple(deps.get('write_roles') or ())
    delete_roles = (*tuple(deps.get('leadership_roles') or ()), 'прораб', 'главный_инженер')
    scope = deps['record_scope']

    @app.get('/warranty-defects')
    def list_warranty_defects(project_name: str = None, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            clauses, params = [], []
            for actor in actors:
                where, values = scope.visible([actor], read_roles)
                if actor.get('role') == 'заказчик':
                    where += ' AND r.created_by_user_id=%s'; values.append(actor.get('id'))
                clauses.append('(' + where + ')'); params.extend(values)
            where = '(' + (' OR '.join(clauses) or 'FALSE') + ')'
            if project_name:
                where += ' AND p.name=%s'; params.append(project_name)
            cur.execute('SELECT r.id,p.name,r.description,r.found_at,r.reported_by,r.reporter_phone,'
                        'r.status,r.assigned_to,r.fix_notes,r.fixed_at,r.photo_url,r.severity,r.created_at,'
                        'r.company_id,r.project_id,r.created_by_user_id FROM warranty_defects r '
                        'JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                        'WHERE ' + where + ' ORDER BY r.id DESC', params)
            rows = cur.fetchall()
        return [{'id':r[0],'projectName':r[1] or '', 'description':r[2] or '',
                 'foundAt':str(r[3]) if r[3] else '', 'reportedBy':r[4] or '',
                 'reporterPhone':r[5] or '', 'status':r[6] or 'Открыт','assignedTo':r[7] or '',
                 'fixNotes':r[8] or '', 'fixedAt':str(r[9]) if r[9] else '',
                 'photoUrl':r[10] or '', 'severity':r[11] or '',
                 'createdAt':str(r[12]) if r[12] else '',
                 'companyId':r[13],'projectId':r[14],'createdByUserId':r[15]} for r in rows]

    @app.post('/warranty-defects')
    def create_warranty_defect(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        text = data.get('description')
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise HTTPException(status_code=422, detail='Опишите дефект: до 10000 символов')
        with scope.transaction(current_user, request, read_roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, data, read_roles)
            customer = actor.get('role') == 'заказчик'
            cur.execute('INSERT INTO warranty_defects '
                        '(project_name,description,found_at,reported_by,reporter_phone,status,assigned_to,'
                        'photo_url,severity,company_id,project_id,created_by_user_id) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                        (parent['name'],text.strip(),data.get('foundAt') or None,actor.get('name',''),
                         data.get('reporterPhone',''),'Открыт' if customer else data.get('status','Открыт'),
                         '' if customer else data.get('assignedTo',''),data.get('photoUrl',''),
                         '' if customer else data.get('severity',''),parent['companyId'],parent['id'],actor['id']))
            record_id = cur.fetchone()[0]
        return {'id':record_id,'ok':True}

    @app.put('/warranty-defects/{id}')
    def update_warranty_defect(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], 'warranty_defects', id, write_roles)
            fields = {'status':'status','assignedTo':'assigned_to','fixNotes':'fix_notes',
                      'fixedAt':'fixed_at','severity':'severity','photoUrl':'photo_url'}
            selected = [(column, (data[key] or None) if key == 'fixedAt' else data[key])
                        for key,column in fields.items() if key in data]
            if selected:
                cur.execute('UPDATE warranty_defects SET ' + ','.join(column+'=%s' for column,_ in selected)
                            + ' WHERE id=%s', [value for _,value in selected]+[id])
        return {'ok':True}

    @app.delete('/warranty-defects/{id}')
    def delete_warranty_defect(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, delete_roles, write=True) as (cur, actors):
            scope.record(cur, actors[0], 'warranty_defects', id, delete_roles)
            cur.execute('DELETE FROM warranty_defects WHERE id=%s', (id,))
        return {'ok':True}
