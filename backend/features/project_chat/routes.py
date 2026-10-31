"""Project chat bound to exact company/project identities."""
from fastapi import Depends, Request
from ..legacy_project_records.scope import owned_query


def register_project_chat_module(app, deps):
    scope, authenticated = deps['record_scope'], deps['get_current_user']
    roles = tuple(deps['project_document_roles'])

    @app.get('/project-chat/{project_name}')
    def get_project_chat(project_name: str, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, roles) as (cur, actors):
            columns = 'r.id,p.name,r.author_id,r.author_name,r.author_role,r.text,r.photo_url,r.created_at'
            query, params = owned_query(scope, actors, roles, 'project_chat', columns, project_name=project_name)
            cur.execute(query + ' ORDER BY r.created_at ASC LIMIT 200', params)
            rows = cur.fetchall()
        return [dict(zip(('id','projectName','authorId','authorName','authorRole','text','photoUrl','createdAt'), (*row[:7],str(row[7])))) for row in rows]

    @app.post('/project-chat')
    def create_project_chat(data: dict, request: Request = None, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, data, roles)
            cur.execute('INSERT INTO project_chat (company_id,project_id,project_name,author_id,author_name,author_role,text,photo_url) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                        (parent['companyId'],parent['id'],parent['name'],actor.get('id'),actor.get('name',''),actor.get('role',''),data.get('text',''),data.get('photoUrl','')))
            record_id = cur.fetchone()[0]
        return {'id':record_id,'ok':True}
