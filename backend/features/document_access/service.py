import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException


_INLINE_DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def require_document_upload_actor(company_actors):
    """Require one concrete active company membership for a new file write."""
    actors = [
        dict(actor)
        for actor in company_actors or []
        if _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
    ]
    if len(actors) != 1:
        raise HTTPException(
            status_code=409,
            detail="Для загрузки файла выберите одну конкретную компанию",
        )
    actor = actors[0]
    company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
    actor["companyId"] = company_id
    actor["company_id"] = company_id
    return actor


def require_document_parent_company(document_company_id, parent_company_id):
    document_company_id = _positive_int(document_company_id)
    parent_company_id = _positive_int(parent_company_id)
    if not document_company_id or not parent_company_id or document_company_id != parent_company_id:
        raise HTTPException(status_code=409, detail="Документ относится к другой компании")
    return parent_company_id


def document_project_reference(project_id, project_name=""):
    """Use a project name only as a consistency hint when an exact ID is present."""
    normalized_project_id = _positive_int(project_id)
    if project_id not in (None, "") and not normalized_project_id:
        raise HTTPException(status_code=400, detail="projectId должен быть положительным целым числом")
    if not normalized_project_id:
        return None, ""
    return normalized_project_id, str(project_name or "").strip()


def document_storage_namespace(company_id, project_id=None, project_name="", context="general"):
    """Build a stable tenant namespace without trusting names as ownership proof."""
    company_id = _positive_int(company_id)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания файла не определена")
    project_id = _positive_int(project_id)
    context_key = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(context or "general")).strip("-")[:40] or "general"
    if project_id:
        return f"company-{company_id}-project-{project_id}-{context_key}"
    return f"company-{company_id}-common-{context_key}"


def document_local_path(upload_dir, file_url):
    """Resolve a registered local upload without allowing it to escape the upload root."""
    parsed = urlsplit(str(file_url or ""))
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/uploads/"):
        raise HTTPException(status_code=409, detail="Файл не относится к локальному хранилищу")
    relative_path = unquote(parsed.path[len("/uploads/"):])
    if not relative_path or relative_path.startswith(("/", "\\")) or "\\" in relative_path or "\x00" in relative_path:
        raise HTTPException(status_code=409, detail="Некорректный путь локального файла")
    root_path = Path(upload_dir).resolve()
    try:
        local_path = (root_path / relative_path).resolve()
        local_path.relative_to(root_path)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(status_code=409, detail="Некорректный путь локального файла")
    if local_path == root_path:
        raise HTTPException(status_code=409, detail="Некорректный путь локального файла")
    return local_path


def document_response_policy(original_name):
    """Allow inline display only for passive file types selected from a safe extension."""
    filename = str(original_name or "file").replace("\\", "/").split("/")[-1]
    filename = "".join(ch for ch in filename if ch >= " " and ch != "\x7f").strip()[:255]
    if not filename or filename in (".", ".."):
        filename = "file"
    media_type = _INLINE_DOCUMENT_TYPES.get(Path(filename).suffix.lower())
    if media_type:
        return filename, media_type, "inline"
    return filename, "application/octet-stream", "attachment"
