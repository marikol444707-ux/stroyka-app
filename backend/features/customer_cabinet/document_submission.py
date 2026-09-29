"""Customer files enter the existing owned project correspondence, without posting acts."""
from typing import Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class CustomerFile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    projectId: int = Field(strict=True, gt=0)
    fileId: int = Field(strict=True, gt=0)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(default='', max_length=10000)
    replacesLetterId: Optional[int] = Field(default=None, strict=True, gt=0)


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=2000)


def register_customer_file_submission(app, scope, get_current_user, correction_roles):
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
            original_id = None
            if data.replacesLetterId:
                cur.execute('''SELECT id FROM project_letters WHERE id=%s AND company_id=%s AND project_id=%s
                    AND created_by_user_id=%s AND side='customer' AND direction='incoming'
                    AND correction_requested_at IS NOT NULL AND corrected_by_letter_id IS NULL FOR UPDATE''',
                    (data.replacesLetterId, parent['companyId'], parent['id'], actor['id']))
                original = cur.fetchone()
                if not original:
                    raise HTTPException(409, 'Запрос на исправление не найден или уже выполнен')
                original_id = original[0]
            cur.execute('''INSERT INTO project_letters
                (project_name,company_id,project_id,created_by_user_id,side,direction,subject,body,
                 counterparty,letter_date,file_url,author,status,replaces_letter_id)
                VALUES (%s,%s,%s,%s,'customer','incoming',%s,%s,%s,CURRENT_DATE,%s,%s,'Получено',%s) RETURNING id''',
                (parent['name'], parent['companyId'], parent['id'], actor['id'], data.subject,
                 data.body, actor.get('name') or '', url, actor.get('name') or 'Заказчик', original_id))
            record_id = cur.fetchone()[0]
            if original_id:
                cur.execute('UPDATE project_letters SET corrected_by_letter_id=%s WHERE id=%s',
                    (record_id, original_id))
            cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s', (data.fileId,))
        return {'ok': True, 'id': record_id, 'companyId': parent['companyId'], 'projectId': parent['id']}

    @app.post('/project-letters/{letter_id}/request-correction')
    def request_correction(letter_id: int, data: CorrectionRequest, request: Request,
                           user: dict = Depends(get_current_user)):
        with scope.transaction(user, request, correction_roles, write=True) as (cur, actors):
            actor = actors[0]
            owned = scope.record(cur, actor, 'project_letters', letter_id, correction_roles)
            cur.execute('''SELECT side,direction,file_url,correction_reason,corrected_by_letter_id
                FROM project_letters WHERE id=%s AND company_id=%s AND project_id=%s FOR UPDATE''',
                (letter_id, owned[1], owned[0]))
            row = cur.fetchone()
            if not row or row[0] != 'customer' or row[1] != 'incoming' or not row[2]:
                raise HTTPException(409, 'Исправление можно запросить только для входящего файла заказчика')
            if row[4]:
                raise HTTPException(409, 'Исправленная версия уже получена')
            if row[3]:
                if row[3] != data.reason:
                    raise HTTPException(409, 'Запрос уже отправлен. Обновите документы')
                return {'ok': True, 'letterId': letter_id}
            cur.execute('''UPDATE project_letters SET correction_reason=%s,correction_requested_at=NOW(),
                correction_requested_by_id=%s,correction_requested_by_name=%s WHERE id=%s''',
                (data.reason, actor.get('id'), actor.get('name') or actor.get('role') or '', letter_id))
        return {'ok': True, 'letterId': letter_id}
