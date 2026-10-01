"""Addressed project correspondence with immutable protected file versions."""
from datetime import date
import json
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .letter_party_snapshot import capture_snapshot, snapshot_digest


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


class CustomerPublication(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    requestId: UUID
    projectId: int = Field(strict=True, gt=0)
    fileId: Optional[int] = Field(default=None, strict=True, gt=0)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(default='', max_length=10000)
    letterDate: Optional[date] = None


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
                 counterparty,letter_date,file_url,author,status,replaces_letter_id,delivery_status,
                 published_at,published_by_id,published_by_name)
                VALUES (%s,%s,%s,%s,'customer','incoming',%s,%s,%s,CURRENT_DATE,%s,%s,'Получено',%s,
                        'received',NOW(),%s,%s) RETURNING id''',
                (parent['name'], parent['companyId'], parent['id'], actor['id'], data.subject,
                 data.body, actor.get('name') or '', url, actor.get('name') or 'Заказчик', original_id,
                 actor['id'], actor.get('name') or 'Заказчик'))
            record_id = cur.fetchone()[0]
            if original_id:
                cur.execute('UPDATE project_letters SET corrected_by_letter_id=%s WHERE id=%s',
                    (record_id, original_id))
            cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s', (data.fileId,))
        return {'ok': True, 'id': record_id, 'companyId': parent['companyId'], 'projectId': parent['id']}

    @app.post('/project-letters/customer-publications')
    def publish_to_customer(data: CustomerPublication, request: Request,
                            user: dict = Depends(get_current_user)):
        """Publish one exact message/file version to customers of one authorized project."""
        with scope.transaction(user, request, correction_roles, write=True) as (cur, actors):
            actor = actors[0]
            parent = scope.parent(cur, actor, {'projectId': data.projectId}, correction_roles)
            request_id = str(data.requestId)
            cur.execute('SELECT pg_advisory_xact_lock(%s,hashtext(%s))',
                (parent['companyId'], request_id))
            file_url = ''
            if data.fileId is not None:
                cur.execute('''SELECT id FROM file_ownership WHERE id=%s AND company_id=%s
                    AND project_id=%s AND uploaded_by_id=%s AND context='project-letters'
                    AND COALESCE(deletion_status,'active')='active' FOR UPDATE''',
                    (data.fileId, parent['companyId'], parent['id'], actor['id']))
                if not cur.fetchone():
                    raise HTTPException(403, 'Можно отправить только свой файл для этого объекта')
                file_url = f'/tenant-files/{data.fileId}/content'
            cur.execute('''SELECT id,project_id,created_by_user_id,subject,body,letter_date,file_url
                FROM project_letters WHERE company_id=%s AND client_request_id=%s FOR UPDATE''',
                (parent['companyId'], request_id))
            previous = cur.fetchone()
            expected = (parent['id'], actor['id'], data.subject, data.body, data.letterDate, file_url)
            if previous:
                if tuple(previous[1:]) != expected:
                    raise HTTPException(409, 'Эта отправка уже сохранена с другими данными')
                return {'ok': True, 'id': previous[0], 'companyId': parent['companyId'],
                        'projectId': parent['id'], 'deliveryStatus': 'sent'}
            party_snapshot, customer_client_id = capture_snapshot(cur, parent, actor)
            encoded_snapshot = json.dumps(
                party_snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            cur.execute('''INSERT INTO project_letters
                (project_name,company_id,project_id,created_by_user_id,side,direction,subject,body,
                 counterparty,letter_date,file_url,author,status,delivery_status,published_at,
                 published_by_id,published_by_name,client_request_id,party_snapshot_json,
                 party_snapshot_hash,party_snapshot_frozen_at,customer_client_id)
                VALUES (%s,%s,%s,%s,'customer','outgoing',%s,%s,'Заказчик объекта',%s,%s,%s,
                        'Активно','sent',NOW(),%s,%s,%s,%s::jsonb,%s,NOW(),%s) RETURNING id''',
                (parent['name'], parent['companyId'], parent['id'], actor['id'], data.subject,
                 data.body, data.letterDate, file_url, actor.get('name') or actor.get('role') or '',
                 actor['id'], actor.get('name') or actor.get('role') or '', request_id,
                 encoded_snapshot, snapshot_digest(party_snapshot), customer_client_id))
            record_id = cur.fetchone()[0]
            if data.fileId is not None:
                cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s',
                    (data.fileId,))
        return {'ok': True, 'id': record_id, 'companyId': parent['companyId'],
                'projectId': parent['id'], 'deliveryStatus': 'sent'}

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
