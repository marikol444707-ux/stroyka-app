"""Customer files enter the existing owned project correspondence, without posting acts."""
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class CustomerFile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    projectId: int = Field(strict=True, gt=0)
    fileId: int = Field(strict=True, gt=0)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(default='', max_length=10000)


def register_customer_file_submission(app, scope, get_current_user):
    @app.post('/project-letters/customer-files')
    def send(data: CustomerFile, request: Request, user: dict = Depends(get_current_user)):
        with scope.transaction(user, request, ('заказчик',), write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, {'projectId': data.projectId}, ('заказчик',))
            # This row lock serializes retries and file deletion with publication.
            cur.execute('''SELECT id FROM file_ownership WHERE id=%s AND company_id=%s
                AND project_id=%s AND uploaded_by_id=%s AND context='customer-request'
                AND COALESCE(deletion_status,'active')='active' FOR UPDATE''',
                (data.fileId, parent['companyId'], parent['id'], actor['id']))
            if not cur.fetchone():
                raise HTTPException(403, 'Можно отправить только свой файл, загруженный для этого объекта')
            url = f'/tenant-files/{data.fileId}/content'
            cur.execute('''SELECT id,subject,body,status FROM project_letters WHERE company_id=%s
                AND project_id=%s AND created_by_user_id=%s AND file_url=%s
                AND side='customer' AND direction='incoming' ORDER BY id LIMIT 1''',
                (parent['companyId'], parent['id'], actor['id'], url))
            previous = cur.fetchone()
            if previous:
                if previous[1] != data.subject or (previous[2] or '') != data.body or previous[3] == 'Аннулировано':
                    raise HTTPException(409, 'Этот файл уже отправлен. Откройте его в переписке объекта')
                return {'ok': True, 'id': previous[0], 'companyId': parent['companyId'], 'projectId': parent['id']}
            cur.execute('''INSERT INTO project_letters
                (project_name,company_id,project_id,created_by_user_id,side,direction,subject,body,
                 counterparty,letter_date,file_url,author,status)
                VALUES (%s,%s,%s,%s,'customer','incoming',%s,%s,%s,CURRENT_DATE,%s,%s,'Получено') RETURNING id''',
                (parent['name'], parent['companyId'], parent['id'], actor['id'], data.subject,
                 data.body, actor.get('name') or '', url, actor.get('name') or 'Заказчик'))
            record_id = cur.fetchone()[0]
            cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s', (data.fileId,))
        return {'ok': True, 'id': record_id, 'companyId': parent['companyId'], 'projectId': parent['id']}
