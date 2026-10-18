"""Pin receipt evidence in the same transaction as stock/accounting changes."""
import re
from fastapi import HTTPException


def retain_originals(cur, urls, company_id, *, target_project=None):
    if not isinstance(urls, list) or not urls or len(urls) > 30:
        raise HTTPException(400, 'Загрузите оригинал документа')
    project_id = None
    if target_project:
        cur.execute('SELECT id FROM projects WHERE company_id=%s AND name=%s', (company_id, target_project))
        projects = cur.fetchall()
        if len(projects) != 1:
            raise HTTPException(409, 'Объект приёмки не определён однозначно')
        project_id = projects[0]['id']
    ids = set()
    for url in urls:
        match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', url) if isinstance(url, str) else None
        if not match:
            raise HTTPException(400, 'Требуется оригинал в защищённом хранилище')
        ids.add(int(match.group(1)))
    # Same row lock as tenant-file deletion. A deletion that won the race leaves
    # non-active metadata and blocks posting; a successful receipt pins the bytes.
    for identity in sorted(ids):
        cur.execute("""SELECT company_id,project_id,COALESCE(deletion_status,'active') AS status
                       FROM file_ownership WHERE id=%s FOR UPDATE""", (identity,))
        row = cur.fetchone()
        if not row or row['company_id'] != company_id or row['status'] != 'active':
            raise HTTPException(409, 'Оригинал удалён или недоступен; загрузите документ заново')
        if target_project is not None and row.get('project_id') != project_id:
            raise HTTPException(409, 'Оригинал относится к другому месту приёмки')
        cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s AND company_id=%s',
                    (identity, company_id))
        if cur.rowcount != 1:
            raise HTTPException(409, 'Не удалось сохранить оригинал документа')
