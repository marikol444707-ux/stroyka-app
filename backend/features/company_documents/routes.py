"""Legal documents belonging exclusively to the selected company."""
import re
from typing import Optional

from fastapi import Depends, Header, HTTPException


def register_company_documents_module(app, deps):
    get_db = deps['get_db']
    get_current_user = deps['get_current_user']
    finance_roles = tuple(deps.get('finance_roles') or ())

    def scope(cur, user, action, claimed, header_id, header_mode):
        context = deps['resolve_work_company_context'](
            cur, user, claimed, action,
            x_company_id=header_id, x_company_mode=header_mode)
        if context.get('mode') != 'company':
            if action == 'read':
                return None
            raise HTTPException(409, 'Выберите компанию для документов')
        actors = deps['effective_company_actors'](user, context)
        if len(actors) != 1 or actors[0].get('role') not in finance_roles:
            raise HTTPException(403, 'Нет доступа к документам выбранной компании')
        actor = actors[0]
        company_id = actor.get('companyId')
        if not company_id or company_id != context.get('companyId'):
            raise HTTPException(403, 'Компания документа не определена')
        if claimed is not None and (isinstance(claimed, bool) or str(claimed) != str(company_id)):
            raise HTTPException(409, 'Компания документа не совпадает с выбранной')
        return actor

    @app.get('/company-documents')
    def get_company_documents(
        current_user: dict = Depends(get_current_user),
        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            actor = scope(cur, current_user, 'read', None, x_company_id, x_company_mode)
            if actor is None:
                return []
            cur.execute('SELECT id,company_id,name,doc_type,file_url,expires_at,uploaded_by FROM company_documents WHERE company_id=%s ORDER BY id', (actor['companyId'],))
            return [dict(zip(('id', 'companyId', 'name', 'docType', 'fileUrl', 'expiresAt', 'uploadedBy'), row)) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post('/company-documents')
    def create_company_document(
        data: dict, current_user: dict = Depends(get_current_user),
        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            claimed = data.get('companyId', data.get('company_id'))
            actor = scope(cur, current_user, 'create', claimed, x_company_id, x_company_mode)
            file_url = str(data.get('fileUrl') or '')
            match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', file_url)
            if not match:
                raise HTTPException(409, 'Загрузите документ в защищённое хранилище выбранной компании')
            cur.execute("SELECT company_id,project_id FROM file_ownership WHERE id=%s AND COALESCE(deletion_status,'active')='active'", (int(match.group(1)),))
            owner = cur.fetchone()
            if not owner or owner[0] != actor['companyId']:
                raise HTTPException(403, 'Нет доступа к файлу документа')
            if owner[1] is not None:
                raise HTTPException(409, 'Документ объекта нельзя добавлять в общий архив компании')
            cur.execute('INSERT INTO company_documents (company_id,name,doc_type,file_url,expires_at,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                        (actor['companyId'], data.get('name', ''), data.get('docType', ''), file_url, data.get('expiresAt', ''), actor.get('name') or actor.get('email') or ''))
            new_id = cur.fetchone()[0]
            conn.commit()
            return {'id': new_id, 'ok': True, 'companyId': actor['companyId']}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.delete('/company-documents/{id}')
    def delete_company_document(
        id: int, current_user: dict = Depends(get_current_user),
        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            actor = scope(cur, current_user, 'delete', None, x_company_id, x_company_mode)
            cur.execute('DELETE FROM company_documents WHERE id=%s AND company_id=%s RETURNING id', (id, actor['companyId']))
            if not cur.fetchone():
                raise HTTPException(404, 'Документ не найден')
            conn.commit()
            return {'ok': True}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
