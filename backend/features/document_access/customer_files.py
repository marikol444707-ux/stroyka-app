"""Customer file access follows published records, not merely object membership."""
import re

from fastapi import HTTPException

from ..customer_cabinet.record_scope import positive_id

CUSTOMER_UPLOAD_CONTEXT = 'customer-request'


def _scope(actor, row):
    company_id = positive_id(row.get('company_id'))
    project_id = positive_id(row.get('project_id'))
    user_id = positive_id(actor.get('id'))
    if (not company_id or not project_id or not user_id
            or company_id != positive_id(actor.get('companyId') or actor.get('company_id'))):
        raise HTTPException(403, 'Вложение недоступно заказчику')
    return company_id, project_id, user_id


def authorize_customer_read(cur, actor, row):
    company_id, project_id, user_id = _scope(actor, row)
    # A newly uploaded request attachment can be previewed before the form is sent.
    if row.get('context') == CUSTOMER_UPLOAD_CONTEXT and positive_id(row.get('uploaded_by_id')) == user_id:
        return
    file_id = positive_id(row.get('id'))
    if not file_id:
        raise HTTPException(403, 'Вложение недоступно заказчику')
    urls = [str(row.get('file_url') or ''), f'/tenant-files/{file_id}/content']
    urls = [url for url in urls if url]
    sources = (
        ('project_documents', "side='customer' AND COALESCE(sign_status,'')<>'Аннулирован' AND scan_url=ANY(%s)", [urls]),
        ('project_letters', "side='customer' AND COALESCE(status,'')<>'Аннулировано' AND file_url=ANY(%s)", [urls]),
        ('prescriptions', "created_by_user_id=%s AND COALESCE(status,'')<>'Аннулировано' AND (photo_url=ANY(%s) OR fix_photo_url=ANY(%s))", [user_id,urls,urls]),
        ('warranty_defects', 'created_by_user_id=%s AND photo_url=ANY(%s)', [user_id,urls]),
    )
    for table, predicate, params in sources:
        cur.execute(f'SELECT 1 FROM {table} WHERE company_id=%s AND project_id=%s AND '+predicate+' LIMIT 1',
                    [company_id,project_id,*params])
        if cur.fetchone():
            return
    # Journal records currently have a company/name parent; only an unambiguous
    # canonical project and confirmed work may publish their progress photographs.
    cur.execute('''SELECT 1 FROM work_journal w JOIN projects p
                     ON p.company_id=w.company_id AND p.name=w.project
                   WHERE p.company_id=%s AND p.id=%s AND w.status='Подтверждено'
                     AND w.photo_url=ANY(%s)
                     AND NOT EXISTS (SELECT 1 FROM projects other WHERE
                         other.company_id=p.company_id AND other.name=p.name AND other.id<>p.id)
                   LIMIT 1''', (company_id,project_id,urls))
    if cur.fetchone():
        return
    raise HTTPException(403, 'Вложение не опубликовано для заказчика')


def customer_attachment(cur, actor, parent, value):
    """Prevent publishing a guessed internal file ID through a customer-owned record."""
    if actor.get('role') != 'заказчик':
        return value or ''
    if value in (None, ''):
        return ''
    if not isinstance(value, str) or len(value) > 2048:
        raise HTTPException(422, 'Некорректное вложение')
    match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', value)
    file_id = int(match.group(1)) if match else None
    cur.execute('''SELECT id FROM file_ownership
                   WHERE company_id=%s AND project_id=%s AND uploaded_by_id=%s AND context=%s
                     AND COALESCE(deletion_status,'active')='active'
                     AND (id=%s OR file_url=%s)''',
                (parent['companyId'],parent['id'],actor['id'],CUSTOMER_UPLOAD_CONTEXT,file_id,value))
    row = cur.fetchone()
    if not row:
        raise HTTPException(403, 'Прикрепить можно только своё вложение к обращению по этому объекту')
    saved_id = row.get('id') if isinstance(row, dict) else row[0]
    return f'/tenant-files/{saved_id}/content'
