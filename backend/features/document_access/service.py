import os
import re
import stat
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


def require_document_storage_identity(
    company_id,
    project_id,
    context,
    file_url,
    storage_key="",
    *,
    s3_prefix="uploads",
    expected_s3_urls=(),
):
    """Reject a registered storage pointer outside its canonical tenant namespace."""
    namespace = document_storage_namespace(company_id, project_id, context=context)
    raw_key = str(storage_key or "").strip()
    normalized_key = raw_key.strip("/")
    if normalized_key:
        if raw_key != normalized_key:
            raise HTTPException(status_code=409, detail="Некорректный путь S3-файла")
        key_parts = normalized_key.split("/")
        if any(part in ("", ".", "..") or "\\" in part or "\x00" in part for part in key_parts):
            raise HTTPException(status_code=409, detail="Некорректный путь S3-файла")
        raw_prefixes = s3_prefix if isinstance(s3_prefix, (list, tuple, set)) else (s3_prefix,)
        prefix_options = []
        for raw_prefix in raw_prefixes:
            prefix_parts = [part for part in str(raw_prefix or "").strip("/").split("/") if part]
            if any(part in (".", "..") or "\\" in part or "\x00" in part for part in prefix_parts):
                raise HTTPException(status_code=503, detail="Префикс S3-хранилища настроен некорректно")
            prefix_options.append([*prefix_parts, namespace])
        if not any(
            key_parts[:len(expected_root)] == expected_root and len(key_parts) > len(expected_root)
            for expected_root in prefix_options
        ):
            raise HTTPException(status_code=409, detail="S3-файл не соответствует компании или объекту")
        allowed_urls = {str(value or "").strip() for value in expected_s3_urls or () if str(value or "").strip()}
        if str(file_url or "").strip() not in allowed_urls:
            raise HTTPException(status_code=409, detail="Публичный URL не соответствует S3-файлу")
        return namespace

    parsed = urlsplit(str(file_url or ""))
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not parsed.path.startswith("/uploads/"):
        raise HTTPException(status_code=409, detail="Локальный файл не соответствует хранилищу компании")
    relative_path = unquote(parsed.path[len("/uploads/"):])
    path_parts = relative_path.split("/")
    if (
        any(part in ("", ".", "..") or "\\" in part or "\x00" in part for part in path_parts)
        or not path_parts
        or path_parts[0] != namespace
    ):
        raise HTTPException(status_code=409, detail="Локальный файл не соответствует компании или объекту")
    return namespace


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


def _local_file_parts(file_url):
    parsed = urlsplit(str(file_url or ""))
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not parsed.path.startswith("/uploads/"):
        raise HTTPException(status_code=409, detail="Файл не относится к локальному хранилищу")
    relative_path = unquote(parsed.path[len("/uploads/"):])
    parts = relative_path.split("/")
    if (
        not relative_path
        or any(part in ("", ".", "..") for part in parts)
        or any("\\" in part or "\x00" in part for part in parts)
    ):
        raise HTTPException(status_code=409, detail="Некорректный путь локального файла")
    return parts


def _open_local_parent_directories(upload_dir, parts):
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise HTTPException(status_code=503, detail="Безопасное локальное хранилище недоступно")
    directory_fds = [os.open(str(Path(upload_dir).resolve()), os.O_RDONLY | directory | nofollow)]
    try:
        for part in parts[:-1]:
            directory_fds.append(
                os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=directory_fds[-1])
            )
        return directory_fds, nofollow
    except Exception:
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)
        raise


def open_document_local_file(upload_dir, file_url, max_bytes):
    """Open a local upload through no-follow directory descriptors and return its size."""
    parts = _local_file_parts(file_url)

    max_bytes = int(max_bytes or 0)
    if max_bytes <= 0:
        raise HTTPException(status_code=503, detail="Лимит размера файла не настроен")

    directory_fds = []
    file_fd = None
    try:
        directory_fds, nofollow = _open_local_parent_directories(upload_dir, parts)
        file_fd = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=directory_fds[-1])
        file_stat = os.fstat(file_fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise HTTPException(status_code=409, detail="Локальный объект не является файлом")
        if file_stat.st_size > max_bytes:
            raise HTTPException(status_code=413, detail="Файл превышает допустимый размер защищенной выдачи")
        stream = os.fdopen(file_fd, "rb", closefd=True)
        file_fd = None
        return stream, int(file_stat.st_size)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл отсутствует в хранилище") from None
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(status_code=409, detail="Небезопасный путь локального файла") from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def delete_document_local_file(upload_dir, file_url, missing_ok=False):
    """Unlink a local upload relative to a no-follow parent descriptor."""
    parts = _local_file_parts(file_url)
    directory_fds = []
    try:
        directory_fds, _nofollow = _open_local_parent_directories(upload_dir, parts)
        os.unlink(parts[-1], dir_fd=directory_fds[-1])
        return True
    except FileNotFoundError:
        if missing_ok:
            return False
        raise HTTPException(status_code=409, detail="Локальный файл отсутствует: запись владельца не удалена") from None
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(status_code=409, detail="Небезопасный путь локального файла") from None
    finally:
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


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
