import os

from fastapi import HTTPException


MAX_PUBLIC_LEAD_FILE_BYTES = 10 * 1024 * 1024
MAX_PUBLIC_LEAD_FILES = 5
MAX_PUBLIC_UPLOADS_PER_HOUR = 10

_TYPE_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}


def public_upload_rate_exceeded(recent_uploads: int) -> bool:
    try:
        return int(recent_uploads or 0) >= MAX_PUBLIC_UPLOADS_PER_HOUR
    except (TypeError, ValueError):
        return True


def _detected_content_type(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return ""


def validate_public_lead_file(filename: str, content_type: str, content: bytes) -> dict:
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(content) > MAX_PUBLIC_LEAD_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ")

    safe_name = os.path.basename(str(filename or "file").replace("\\", "/"))[:120]
    extension = os.path.splitext(safe_name)[1].lower()
    detected_type = _detected_content_type(content)
    if not detected_type or extension not in _TYPE_EXTENSIONS.get(detected_type, set()):
        raise HTTPException(status_code=415, detail="Разрешены только PDF, JPEG, PNG и WebP")

    declared_type = str(content_type or "").lower().split(";", 1)[0].strip()
    if declared_type not in ("", "application/octet-stream", detected_type):
        raise HTTPException(status_code=415, detail="Тип файла не совпадает с содержимым")

    return {
        "filename": safe_name,
        "contentType": detected_type,
        "size": len(content),
    }
