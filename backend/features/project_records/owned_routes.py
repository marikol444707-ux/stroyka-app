"""Owned documents and correspondence; measurement routes remain separate."""
from fastapi import Depends, Request


DOCUMENT_FIELDS = {
    'side':'side','docType':'doc_type','number':'number','docDate':'doc_date',
    'counterparty':'counterparty','signStatus':'sign_status','scanUrl':'scan_url',
    'amount':'amount','notes':'notes',
}
LETTER_FIELDS = {
    'side':'side','direction':'direction','subject':'subject','body':'body',
    'counterparty':'counterparty','letterDate':'letter_date','fileUrl':'file_url',
}


def register_owned_record_routes(app, deps):
    read_roles = tuple(deps['read_roles'])
    write_roles = tuple(deps['write_roles'])
    workers = tuple(deps['worker_execution_roles'])
    authenticated = deps['get_current_user']

    def register_kind(path, table, fields, actor_key, actor_column, defaults, void_column, void_value):
        @app.get(path)
        def list_records(project_name: str = None, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, read_roles) as (cur, actors):
                clauses, params = [], []
                customer_companies = set()
                for actor in actors:
                    where, values = scope.visible([actor], read_roles)
                    role = actor.get('role')
                    if role == 'заказчик':
                        where += " AND r.side='customer'"
                        customer_companies.add(int(actor.get('companyId') or actor.get('company_id')))
                    elif role in workers:
                        where += " AND r.side='contractor'"
                        if table == 'project_documents':
                            where += ' AND (r.counterparty=%s OR r.created_by_user_id=%s)'
                            values.extend([actor.get('name') or '',actor.get('id')])
                    clauses.append('(' + where + ')'); params.extend(values)
                where = '(' + (' OR '.join(clauses) or 'FALSE') + ')'
                if project_name:
                    where += ' AND p.name=%s'; params.append(project_name)
                where += f' AND COALESCE(r.{void_column},\'\')<>%s'; params.append(void_value)
                columns = ','.join('r.'+column for column in fields.values())
                cur.execute('SELECT r.id,p.name,' + columns + f',r.{actor_column},r.created_at,r.company_id,r.project_id '
                            f'FROM {table} r JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                            'WHERE ' + where + ' ORDER BY r.id DESC', params)
                rows = cur.fetchall()
            keys = ['id','projectName',*fields,actor_key,'createdAt','companyId','projectId']
            result = []
            for row in rows:
                record = dict(zip(keys,row))
                for key in ('docDate','letterDate','createdAt'):
                    if key in record:
                        record[key] = str(record[key]) if record[key] else ''
                if 'amount' in record:
                    record['amount'] = float(record['amount'] or 0)
                for key in (*fields,actor_key):
                    if record.get(key) is None:
                        record[key] = ''
                if record['companyId'] in customer_companies:
                    record.pop('notes',None)
                result.append(record)
            return result

        @app.post(path)
        def create_record(data: dict, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                actor = actors[0]
                parent = scope.parent(cur, actor, data, write_roles)
                values = [data.get(key, defaults.get(key,'')) for key in fields]
                for index,key in enumerate(fields):
                    if key in ('docDate','letterDate'):
                        values[index] = values[index] or None
                    if key == 'amount':
                        values[index] = values[index] or 0
                columns = ['project_name',*fields.values(),actor_column,'company_id','project_id','created_by_user_id']
                values = [parent['name'],*values,actor.get('name',''),parent['companyId'],parent['id'],actor['id']]
                cur.execute(f'INSERT INTO {table} (' + ','.join(columns) + ') VALUES ('
                            + ','.join(['%s']*len(values)) + ') RETURNING id',values)
                record_id = cur.fetchone()[0]
            return {'ok':True,'id':record_id}

        if table == 'project_documents':
            @app.put(path+'/{id}')
            def update_record(id: int, data: dict, _current_user: dict = Depends(authenticated), request: Request = None):
                scope = deps['record_scope']
                with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                    scope.record(cur, actors[0], table, id, write_roles)
                    selected = [(column,(data[key] or None) if key=='docDate' else data[key])
                                for key,column in fields.items() if key in data]
                    if selected:
                        cur.execute(f'UPDATE {table} SET '+','.join(column+'=%s' for column,_ in selected)
                                    +' WHERE id=%s',[value for _,value in selected]+[id])
                return {'ok':True}

        @app.delete(path+'/{id}')
        def delete_record(id: int, _current_user: dict = Depends(authenticated), request: Request = None):
            scope = deps['record_scope']
            with scope.transaction(_current_user, request, write_roles, write=True) as (cur, actors):
                scope.record(cur, actors[0], table, id, write_roles)
                cur.execute(f'UPDATE {table} SET {void_column}=%s WHERE id=%s',(void_value,id))
            return {'ok':True}

    register_kind('/project-documents','project_documents',DOCUMENT_FIELDS,'uploadedBy','uploaded_by',
                  {'side':'customer','signStatus':'Не подписан'},'sign_status','Аннулирован')
    register_kind('/project-letters','project_letters',LETTER_FIELDS,'author','author',
                  {'side':'customer','direction':'outgoing'},'status','Аннулировано')
