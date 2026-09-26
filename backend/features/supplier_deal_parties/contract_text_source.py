"""Bounded TXT/PDF source reader; ownership must be authorized before calling."""
import hashlib
import time
from contextlib import closing
from pathlib import PurePath

from fastapi import HTTPException

from ..document_access.service import require_document_storage_identity
from .contract_pdf import MAX_PDF_BYTES, extract_pdf_text


MAX_TEXT_BYTES = 256000
MAX_TEXT_CHARACTERS = 64000


def read_contract_text(row, deps):
    extension = PurePath(row.get('original_name') or '').suffix.lower()
    if extension not in ('.txt', '.pdf'):
        raise HTTPException(415, 'Поддерживаются TXT в UTF-8 и PDF с текстовым слоем; изображения требуют OCR')
    max_bytes = MAX_PDF_BYTES if extension == '.pdf' else MAX_TEXT_BYTES
    key = str(row.get('storage_key') or '').strip()
    require_document_storage_identity(
        row['company_id'], row.get('project_id'), row.get('context') or 'general',
        row.get('file_url'), key, s3_prefix=deps['s3_prefixes'],
        expected_s3_urls=deps['s3_urls_for_key'](key) if key else (),
    )
    started = time.monotonic()
    try:
        if key:
            if not deps['s3_enabled']():
                raise HTTPException(503, 'S3-хранилище временно недоступно')
            stream, size = deps['open_s3_object'](key)
        else:
            stream, size = deps['open_local_file'](row['file_url'])
        with closing(stream):
            if not isinstance(size, int) or size < 0 or size > max_bytes:
                raise HTTPException(413, 'Файл превышает допустимый размер')
            content = bytearray()
            while True:
                if time.monotonic() - started > 10:
                    raise HTTPException(504, 'Истекло время чтения договора')
                chunk = stream.read(min(32768, max_bytes + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise HTTPException(413, 'Файл превышает допустимый размер')
            if time.monotonic() - started > 10:
                raise HTTPException(504, 'Истекло время чтения договора')
            if len(content) != size:
                raise HTTPException(409, 'Размер файла изменился во время чтения')
    except (OSError, TimeoutError):
        raise HTTPException(503, 'Не удалось прочитать файл договора') from None
    if extension == '.pdf':
        return extract_pdf_text(content), hashlib.sha256(content).hexdigest()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise HTTPException(422, 'Требуется текстовый файл в кодировке UTF-8') from None
    if len(text) > MAX_TEXT_CHARACTERS:
        raise HTTPException(413, 'Договор превышает 64000 символов; текст не усечён')
    if not text.strip() or text.startswith('%PDF-') or any(ord(ch) < 32 and ch not in '\r\n\t' for ch in text):
        raise HTTPException(422, 'Файл не содержит поддерживаемый текст договора')
    return text, hashlib.sha256(content).hexdigest()
