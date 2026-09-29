import re
from urllib.parse import urlsplit

from fastapi import HTTPException


def document_url(value):
    if not isinstance(value, str) or len(value) > 2000:
        raise HTTPException(400, 'Приложите документ или фотографию')
    value = value.strip()
    parsed = urlsplit(value)
    local = re.fullmatch(r'/tenant-files/[1-9][0-9]*/content', value) or value.startswith('/uploads/')
    remote = parsed.scheme in ('http', 'https') and parsed.netloc
    if not (local or remote) or any(ord(char) < 32 for char in value):
        raise HTTPException(400, 'Некорректная ссылка на документ или фотографию')
    return value


def owned_document_url(cur, value, company_id, project_id, *, require_upload=False):
    value = document_url(value)
    match = re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content', value)
    if not match:
        if require_upload:
            raise HTTPException(400, 'Загрузите подписанный акт в программу')
        return value
    file_id = int(match.group(1))
    if file_id > 9223372036854775807:
        raise HTTPException(404, 'Документ этого объекта не найден')
    cur.execute('''SELECT id FROM file_ownership WHERE id=%s AND company_id=%s
        AND project_id=%s AND deletion_status='active' FOR SHARE''',
        (file_id, company_id, project_id))
    if not cur.fetchone():
        raise HTTPException(404, 'Документ этого объекта не найден')
    return value
