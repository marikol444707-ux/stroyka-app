import os
from typing import Optional

from fastapi import Depends, Header, HTTPException

from .service import document_local_path


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
    )
    return {field: row[index] if len(row) > index else None for index, field in enumerate(fields)}


def register_document_access_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    resolve_resource_company_actor = deps["resolve_resource_company_actor"]
    resolve_project_parent = deps["resolve_project_parent"]
    require_project_access = deps["require_project_access"]
    leadership_roles = set(deps.get("leadership_roles") or ())
    platform_staff_roles = deps.get("platform_staff_roles") or ()
    client_account_roles = deps.get("client_account_roles") or ()
    upload_dir = deps["upload_dir"]
    s3_enabled = deps["s3_enabled"]
    delete_s3_object = deps["delete_s3_object"]

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
            require_project_access(actor, project["name"])
        return actor

    def load_file(cur, file_id, *, for_update=False):
        lock_sql = " FOR UPDATE" if for_update else ""
        cur.execute(
            """SELECT id,company_id,project_id,file_url,storage_key,context,original_name,content_type,
                      uploaded_by_id,uploaded_by,created_at
                 FROM file_ownership WHERE id=%s""" + lock_sql,
            (file_id,),
        )
        row = _file_record(cur.fetchone())
        if not row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        return row

    @app.get("/tenant-files/{file_id}")
    def get_tenant_file_metadata(
        file_id: int,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(get_current_user),
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            row = load_file(cur, file_id)
            authorize_file(cur, current_user, row, "read", x_company_id, x_company_mode)
            return {
                "id": row["id"],
                "companyId": row["company_id"],
                "projectId": row.get("project_id"),
                "url": row["file_url"],
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
        cur = conn.cursor()
        try:
            row = load_file(cur, file_id, for_update=True)
            actor = authorize_file(cur, current_user, row, "delete", x_company_id, x_company_mode)
            is_owner = _positive_int(row.get("uploaded_by_id")) == _positive_int(current_user.get("id"))
            if actor.get("role") not in leadership_roles and not is_owner:
                raise HTTPException(
                    status_code=403,
                    detail="Удалить файл может загрузивший его сотрудник или руководитель",
                )

            storage_key = str(row.get("storage_key") or "").strip()
            if storage_key:
                if not s3_enabled():
                    raise HTTPException(
                        status_code=409,
                        detail="S3-хранилище недоступно: запись файла не удалена",
                    )
                delete_s3_object(storage_key)
            else:
                local_path = document_local_path(upload_dir, row.get("file_url"))
                if not local_path.is_file():
                    raise HTTPException(
                        status_code=409,
                        detail="Локальный файл отсутствует: запись владельца не удалена",
                    )
                os.remove(local_path)

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
