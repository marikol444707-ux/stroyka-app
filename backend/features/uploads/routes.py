"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, Request, UploadFile
from typing import Optional
import psycopg2

def register_uploads_module(app, deps):
    BRIGADE_FULL_VIEW_ROLES = deps['BRIGADE_FULL_VIEW_ROLES']
    _resolve_work_company_context = deps['_resolve_work_company_context']
    _row_get = deps['_row_get']
    effective_company_actors = deps['effective_company_actors']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    require_roles = deps['require_roles']
    save_upload_file = deps['save_upload_file']
    router = APIRouter()

    @router.post("/upload-photo")
    async def upload_photo(
        request: Request,
        file: UploadFile = File(...),
        projectName: str = Form(default=""),
        project_name: str = Form(default=""),
        projectId: Optional[int] = Form(default=None),
        context: str = Form(default="general"),
        supplierOfferId: Optional[int] = Form(default=None),
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        _current_user: dict = Depends(get_current_user),
    ):
        try:
            from backend.features.document_access.service import (
                build_document_upload_response,
                document_project_reference,
                document_storage_namespace,
                require_document_upload_actor,
            )
            from backend.features.project_access.service import resolve_project_parent
            from backend.features.project_access.service import require_project_parent_access
        except ModuleNotFoundError:
            from features.document_access.service import (
                build_document_upload_response,
                document_project_reference,
                document_storage_namespace,
                require_document_upload_actor,
            )
            from features.project_access.service import resolve_project_parent
            from features.project_access.service import require_project_parent_access
        conn = get_db()
        conn.autocommit = False
        access_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if _current_user.get("role") == "поставщик":
                try:
                    from backend.features.document_access.supplier_files import upload_scope
                except ModuleNotFoundError:
                    from features.document_access.supplier_files import upload_scope
                if request.url.path.rstrip("/") == "/upload-photo":
                    raise HTTPException(403, "Загрузите файл через карточку КП")
                company_id, context, project = upload_scope(access_cur, _current_user, supplierOfferId)
                requested_project_name = ""
            else:
                company_context = _resolve_work_company_context(
                    access_cur,
                    _current_user,
                    None,
                    "write",
                    x_company_id=x_company_id,
                    x_company_mode=x_company_mode,
                )
                actor = require_document_upload_actor(effective_company_actors(_current_user, company_context))
                company_id = int(actor["companyId"])
                requested_project_name = (projectName or project_name or "").strip()
                bound_project_id, bound_project_name = document_project_reference(projectId, requested_project_name)
                project = None
                if bound_project_id:
                    project = resolve_project_parent(
                        access_cur,
                        actor,
                        project_id=bound_project_id,
                        project_name=bound_project_name,
                    )
                    require_project_parent_access(access_cur, actor, project, BRIGADE_FULL_VIEW_ROLES)
                if actor.get("role") == "заказчик":
                    if not project:
                        raise HTTPException(400, "Для вложения заказчика выберите объект")
                    context = "customer-request"
            namespace = document_storage_namespace(
                company_id,
                (project or {}).get("id"),
                (project or {}).get("name") or requested_project_name,
                context,
            )
            uploaded = save_upload_file(file, namespace, context)
            access_cur.execute(
                """INSERT INTO file_ownership
                          (company_id,project_id,file_url,storage_key,context,original_name,content_type,
                           uploaded_by_id,uploaded_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (file_url) DO UPDATE
                           SET company_id=EXCLUDED.company_id,
                               project_id=EXCLUDED.project_id,
                               storage_key=EXCLUDED.storage_key,
                               context=EXCLUDED.context,
                               original_name=EXCLUDED.original_name,
                               content_type=EXCLUDED.content_type,
                               uploaded_by_id=EXCLUDED.uploaded_by_id,
                               uploaded_by=EXCLUDED.uploaded_by
                   RETURNING id""",
                (
                    company_id,
                    (project or {}).get("id"),
                    uploaded.get("url"),
                    uploaded.get("key") or "",
                    context or "general",
                    file.filename or "file",
                    file.content_type or "",
                    _current_user.get("id"),
                    _current_user.get("name") or "",
                ),
            )
            ownership_row = access_cur.fetchone()
            file_id = _row_get(ownership_row, "id", 0)
            conn.commit()
            return build_document_upload_response(
                uploaded,
                file_id=file_id,
                company_id=company_id,
                project_id=(project or {}).get("id"),
                project_name=(project or {}).get("name") or "",
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            access_cur.close()
            conn.close()

    @router.post("/supplier-offers/{offer_id}/files")
    async def upload_supplier_offer_file(
        offer_id: int, request: Request, file: UploadFile = File(...),
        user: dict = Depends(require_roles("поставщик")),
    ):
        return await upload_photo(request=request, file=file, projectName="", project_name="",
                                  projectId=None, context="supplier-offers", supplierOfferId=offer_id,
                                  x_company_id=None, x_company_mode=None, _current_user=user)

    app.include_router(router)

