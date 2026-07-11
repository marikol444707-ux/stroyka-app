from typing import Optional
from urllib.parse import quote

import psycopg2.extras
from fastapi import Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from .service import (
    document_response_policy,
    require_document_storage_identity,
)


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _file_record(row):
    if not row:
        return None
    if isinstance(row, dict):
        return dict(row)
    fields = (
        "id",
        "company_id",
        "project_id",
        "file_url",
        "storage_key",
        "context",
        "original_name",
        "content_type",
        "uploaded_by_id",
        "uploaded_by",
        "created_at",
        "deletion_status",
        "deletion_error",
        "deletion_requested_at",
    )
    return {field: row[index] if len(row) > index else None for index, field in enumerate(fields)}


def _bounded_stream(stream, expected_size, max_bytes, chunk_size=64 * 1024):
    total = 0
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError("Protected file stream exceeded configured limit")
            yield chunk
        if total != expected_size:
            raise RuntimeError("Protected file stream size changed during delivery")
    finally:
        stream.close()


class OwnedStreamingResponse(StreamingResponse):
    def __init__(self, stream, expected_size, max_bytes, *, media_type, headers):
        self._owned_stream = stream
        super().__init__(
            _bounded_stream(stream, expected_size, max_bytes),
            media_type=media_type,
            headers=headers,
        )

    async def __call__(self, scope, receive, send):
        try:
            return await super().__call__(scope, receive, send)
        finally:
            self._owned_stream.close()


def register_document_access_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_resource_company_actor = deps["resolve_resource_company_actor"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_parent_access = deps["require_project_parent_access"]
    project_full_view_roles = deps.get("project_full_view_roles") or ()
    leadership_roles = set(deps.get("leadership_roles") or ())
    platform_staff_roles = deps.get("platform_staff_roles") or ()
    client_account_roles = deps.get("client_account_roles") or ()
    s3_prefix = deps.get("s3_prefixes") or deps.get("s3_prefix") or ""
    s3_urls_for_key = deps["s3_urls_for_key"]
    s3_enabled = deps["s3_enabled"]
    open_local_file = deps["open_local_file"]
    delete_local_file = deps["delete_local_file"]
    open_s3_object = deps["open_s3_object"]
    max_upload_bytes = int(deps["max_upload_bytes"])
    delete_s3_object = deps["delete_s3_object"]

    def verify_file_storage(row):
        storage_key = str(row.get("storage_key") or "").strip()
        return require_document_storage_identity(
            row["company_id"],
            row.get("project_id"),
            row.get("context") or "general",
            row.get("file_url"),
            storage_key,
            s3_prefix=s3_prefix,
            expected_s3_urls=s3_urls_for_key(storage_key) if storage_key else (),
        )

    def authorize_file(cur, current_user, row, action_mode, x_company_id, x_company_mode):
        _context, actor = resolve_resource_company_actor(
            cur,
            current_user,
            row["company_id"],
            action_mode,
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
            platform_staff_roles=platform_staff_roles,
            client_account_roles=client_account_roles,
        )
        if row.get("project_id"):
            project = resolve_project_parent(cur, actor, project_id=row["project_id"])
            require_project_parent_access(cur, actor, project, project_full_view_roles)
        return actor

    def load_file(cur, file_id, *, for_update=False):
        lock_sql = " FOR UPDATE" if for_update else ""
        cur.execute(
            """SELECT id,company_id,project_id,file_url,storage_key,context,original_name,content_type,
                      uploaded_by_id,uploaded_by,created_at,
                      COALESCE(deletion_status,'active') AS deletion_status,
                      deletion_error,deletion_requested_at
                 FROM file_ownership WHERE id=%s""" + lock_sql,
            (file_id,),
        )
        row = _file_record(cur.fetchone())
        if not row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        return row

    def require_readable_file(row):
        status = str(row.get("deletion_status") or "active").strip().lower()
        if status != "active":
            raise HTTPException(status_code=410, detail="Файл удаляется или ожидает повторного cleanup")

    @app.get("/tenant-files/{file_id}")
    def get_tenant_file_metadata(
        file_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            row = load_file(cur, file_id)
            authorize_file(cur, current_user, row, "read", x_company_id, x_company_mode)
            require_readable_file(row)
            verify_file_storage(row)
            return {
                "id": row["id"],
                "companyId": row["company_id"],
                "projectId": row.get("project_id"),
                "url": row["file_url"],
                "contentUrl": f"/tenant-files/{row['id']}/content",
                "context": row.get("context") or "general",
                "originalName": row.get("original_name") or "",
                "contentType": row.get("content_type") or "",
                "uploadedBy": row.get("uploaded_by") or "",
                "createdAt": str(row.get("created_at") or ""),
            }
        finally:
            cur.close()
            conn.close()

    @app.delete("/tenant-files/{file_id}")
    def delete_tenant_file(
        file_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            row = load_file(cur, file_id, for_update=True)
            actor = authorize_file(cur, current_user, row, "delete", x_company_id, x_company_mode)
            is_owner = _positive_int(row.get("uploaded_by_id")) == _positive_int(current_user.get("id"))
            if actor.get("role") not in leadership_roles and not is_owner:
                raise HTTPException(
                    status_code=403,
                    detail="Удалить файл может загрузивший его сотрудник или руководитель",
                )

            verify_file_storage(row)
            deletion_status = str(row.get("deletion_status") or "active").strip().lower()
            retrying_cleanup = deletion_status in ("deleting", "cleanup_failed")

            cur.execute(
                """UPDATE file_ownership
                      SET deletion_status='deleting',deletion_error=NULL,deletion_requested_at=NOW()
                    WHERE id=%s AND company_id=%s""",
                (file_id, row["company_id"]),
            )
            conn.commit()

            storage_key = str(row.get("storage_key") or "").strip()
            try:
                if storage_key:
                    if not s3_enabled():
                        raise HTTPException(
                            status_code=409,
                            detail="S3-хранилище недоступно: cleanup будет повторен позже",
                        )
                    deleted = delete_s3_object(storage_key)
                    if deleted is False and not retrying_cleanup:
                        raise HTTPException(
                            status_code=409,
                            detail="S3-файл отсутствует: запись владельца сохранена для проверки",
                        )
                else:
                    delete_local_file(
                        row.get("file_url"),
                        missing_ok=retrying_cleanup,
                    )
            except Exception as storage_error:
                conn.rollback()
                cur.execute(
                    """UPDATE file_ownership
                          SET deletion_status='cleanup_failed',deletion_error=%s
                        WHERE id=%s AND company_id=%s""",
                    ((type(storage_error).__name__ + ": " + str(storage_error))[:500], file_id, row["company_id"]),
                )
                conn.commit()
                raise

            cur.execute(
                "DELETE FROM file_ownership WHERE id=%s AND company_id=%s",
                (file_id, row["company_id"]),
            )
            conn.commit()
            return {"ok": True, "id": file_id, "companyId": row["company_id"]}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get("/tenant-files/{file_id}/content")
    def get_tenant_file_content(
        file_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            row = load_file(cur, file_id)
            authorize_file(cur, current_user, row, "read", x_company_id, x_company_mode)
            require_readable_file(row)
            headers = {
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Cross-Origin-Resource-Policy": "same-origin",
            }
            filename, media_type, disposition = document_response_policy(row.get("original_name"))
            headers["Content-Disposition"] = disposition + "; filename*=UTF-8''" + quote(filename, safe="")
            verify_file_storage(row)
            storage_key = str(row.get("storage_key") or "").strip()
            if storage_key:
                if not s3_enabled():
                    raise HTTPException(status_code=503, detail="S3-хранилище временно недоступно")
                stream, content_length = open_s3_object(storage_key)
                headers["Content-Length"] = str(content_length)
                return OwnedStreamingResponse(
                    stream,
                    content_length,
                    max_upload_bytes,
                    media_type=media_type,
                    headers=headers,
                )
            stream, content_length = open_local_file(row.get("file_url"))
            headers["Content-Length"] = str(content_length)
            return OwnedStreamingResponse(
                stream,
                content_length,
                max_upload_bytes,
                media_type=media_type,
                headers=headers,
            )
        finally:
            cur.close()
            conn.close()
