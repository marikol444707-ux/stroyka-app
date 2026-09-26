"""Run PDF text extraction outside the web process with resource/time bounds."""
import subprocess
import sys
from pathlib import Path

from fastapi import HTTPException


MAX_PDF_BYTES = 10 * 1024 * 1024


def extract_pdf_text(content):
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, 'PDF превышает 10 МБ')
    if not content.startswith(b'%PDF-'):
        raise HTTPException(422, 'Файл не является поддерживаемым PDF')
    try:
        result = subprocess.run(
            [sys.executable, '-I', str(Path(__file__).with_name('contract_pdf_worker.py'))],
            input=bytes(content), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=10, check=False, env={},
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, 'Превышено время обработки PDF') from None
    except OSError:
        raise HTTPException(503, 'Обработка PDF временно недоступна') from None
    if result.returncode == 3:
        raise HTTPException(503, 'Модуль PDF или ограничения ресурсов недоступны')
    if result.returncode == 4:
        raise HTTPException(413, 'PDF превышает лимит: 30 страниц, 64000 символов или ресурсы обработки')
    if result.returncode == 5:
        raise HTTPException(422, 'Есть страницы без извлекаемого текста. Нужен OCR или ручная проверка; частичный результат не выдан')
    if result.returncode == 6:
        raise HTTPException(422, 'Зашифрованный PDF не поддерживается')
    if result.returncode != 0:
        raise HTTPException(422, 'Не удалось безопасно извлечь текст PDF')
    try:
        text = result.stdout.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(422, 'Некорректный результат обработки PDF') from None
    if (not text.strip() or len(text) > 64000 or '\ufffd' in text
            or any(ord(ch) < 32 and ch not in '\r\n\t' for ch in text)):
        raise HTTPException(422, 'Некорректный результат обработки PDF')
    return text
