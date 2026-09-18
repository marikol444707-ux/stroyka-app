"""Company-scoped customer archives and private supplier documents.

Unassigned legacy rows remain supplier-private; ownership is never guessed.
This module does not grant cross-company access to protected file contents.
"""
import re
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException


ARCHIVE_ROLES = {"директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер"}


def _positive_id(value, field):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value or "")):
        raise HTTPException(status_code=400, detail=f"{field}: требуется положительный целый идентификатор")
    return int(value)


def register_supplier_documents_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    current_supplier_ids = deps["current_supplier_ids"]
    supplier_related_ids = deps["supplier_related_ids"]
    resolve_context = deps["resolve_work_company_context"]
    effective_actors = deps["effective_company_actors"]

    def company_actors(cur, user, action, claimed, header_id, header_mode):
        context = resolve_context(cur, user, claimed, action,
                                  x_company_id=header_id, x_company_mode=header_mode)
        actors = [actor for actor in effective_actors(user, context)
                  if actor.get("role") in ARCHIVE_ROLES and actor.get("companyId")]
        if action != "read":
            if context.get("mode") != "company" or len(actors) != 1:
                raise HTTPException(status_code=403, detail="Нет права изменять документы выбранной компании")
            if claimed is not None and _positive_id(claimed, "companyId") != actors[0]["companyId"]:
                raise HTTPException(status_code=409, detail="Компания документа не совпадает с выбранной компанией")
        return actors

    def validate_company_file(cur, file_url, company_id):
        if not file_url:
            return
        match = re.fullmatch(r"/tenant-files/([1-9][0-9]*)/content", file_url)
        if not match:
            raise HTTPException(status_code=409, detail="Загрузите документ в защищённое хранилище выбранной компании")
        cur.execute("""SELECT company_id, project_id FROM file_ownership
                       WHERE id=%s AND COALESCE(deletion_status,'active')='active'""",
                    (int(match.group(1)),))
        row = cur.fetchone()
        if not row or row[0] != company_id:
            raise HTTPException(status_code=403, detail="Нет доступа к файлу документа")
        if row[1]:
            raise HTTPException(status_code=409, detail="Документ объекта нельзя публиковать в общем архиве компании")

    @app.get("/supplier-documents")
    def list_supplier_documents(
        supplier_id: int = None,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None,
    ):
        conn = get_db()
        cur = conn.cursor()
        try:
            if supplier_id is not None:
                supplier_id = _positive_id(supplier_id, "supplier_id")
            if current_user.get("role") == "поставщик":
                own_ids = current_supplier_ids(cur, current_user)
                if not own_ids:
                    return []
                if supplier_id and supplier_id not in own_ids:
                    raise HTTPException(status_code=403, detail="Нет доступа к документам этого поставщика")
                where, params = "supplier_id = ANY(%s) AND company_id IS NULL", [own_ids]
            else:
                actors = company_actors(cur, current_user, "read", None, x_company_id, x_company_mode)
                if not actors:
                    return []
                where = "company_id = ANY(%s)"
                params = [[actor["companyId"] for actor in actors]]
                if supplier_id:
                    where += " AND supplier_id = ANY(%s)"
                    params.append(supplier_related_ids(cur, supplier_id) or [supplier_id])
            cur.execute("""SELECT id,supplier_id,doc_type,title,file_url,status,signed_at,
                                  expires_at,notes,uploaded_by,created_at,company_id
                           FROM supplier_documents WHERE """ + where +
                        " AND archived_at IS NULL ORDER BY created_at DESC", tuple(params))
            return [{
                "id": r[0], "supplierId": r[1], "docType": r[2] or "", "title": r[3] or "",
                "fileUrl": r[4] or "", "status": r[5] or "",
                "signedAt": str(r[6]) if r[6] else "", "expiresAt": str(r[7]) if r[7] else "",
                "notes": r[8] or "", "uploadedBy": r[9] or "", "createdAt": str(r[10]),
                "companyId": r[11], "visibility": "customer" if r[11] else "supplier_private",
            } for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    @app.post("/supplier-documents")
    def create_supplier_document(
        data: dict,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None,
    ):
        supplier_id = _positive_id(data.get("supplierId"), "supplierId")
        conn = get_db()
        cur = conn.cursor()
        try:
            claimed = data.get("companyId") if "companyId" in data else data.get("company_id")
            if current_user.get("role") == "поставщик":
                if supplier_id not in current_supplier_ids(cur, current_user):
                    raise HTTPException(status_code=403, detail="Нет доступа к документам этого поставщика")
                if claimed is not None:
                    raise HTTPException(status_code=409, detail="Публикация поставщиком в архив заказчика требует привязки к сделке; пока доступен личный архив")
                company_id, actor = None, current_user
            else:
                actors = company_actors(cur, current_user, "create", claimed, x_company_id, x_company_mode)
                actor = actors[0]
                company_id = actor["companyId"]
                cur.execute("SELECT id FROM suppliers WHERE id=%s", (supplier_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Поставщик не найден")
                validate_company_file(cur, str(data.get("fileUrl") or ""), company_id)
            cur.execute(
                """INSERT INTO supplier_documents
                   (supplier_id,doc_type,title,file_url,status,signed_at,expires_at,notes,uploaded_by,company_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (supplier_id, data.get("docType") or "Другое", data.get("title") or "",
                 data.get("fileUrl") or "", data.get("status") or "На проверке",
                 data.get("signedAt") or None, data.get("expiresAt") or None,
                 data.get("notes") or "", actor.get("name") or actor.get("email") or "", company_id))
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, "ok": True, "companyId": company_id}
        finally:
            cur.close()
            conn.close()

    @app.delete("/supplier-documents/{id}")
    def delete_supplier_document(
        id: int,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias="X-Company-Id")] = None,
        x_company_mode: Annotated[Optional[str], Header(alias="X-Company-Mode")] = None,
    ):
        id = _positive_id(id, "id")
        conn = get_db()
        cur = conn.cursor()
        try:
            supplier = current_user.get("role") == "поставщик"
            actors = [] if supplier else company_actors(
                cur, current_user, "delete", None, x_company_id, x_company_mode)
            own_ids = current_supplier_ids(cur, current_user) if supplier else []
            cur.execute("SELECT supplier_id,company_id FROM supplier_documents WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Документ не найден")
            if supplier:
                # A supplier cannot remove the customer's archive entry.
                allowed = row[0] in own_ids and row[1] is None
            else:
                allowed = row[1] == actors[0]["companyId"]
            if not allowed:
                raise HTTPException(status_code=403, detail="Нет доступа к изменению документа")
            cur.execute("""UPDATE supplier_documents SET archived_at=NOW()
                           WHERE id=%s AND supplier_id=%s AND company_id IS NOT DISTINCT FROM %s
                             AND archived_at IS NULL""", (id, row[0], row[1]))
            conn.commit()
            return {"ok": True, "archived": True}
        finally:
            cur.close()
            conn.close()
