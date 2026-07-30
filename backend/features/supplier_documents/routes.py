"""Supplier document routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 42):
the supplier documents trio keeps its URLs, per-supplier self-scope,
duplicate-group widening on read and role checks. The backfill and
dedupe admin operations stay in main.py for the dedup domain.
"""

from fastapi import Depends, HTTPException


def register_supplier_documents_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    current_supplier_ids = deps["current_supplier_ids"]
    supplier_related_ids = deps["supplier_related_ids"]

    @app.get("/supplier-documents")
    def list_supplier_documents(supplier_id: int = None, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        where = ""
        params = []
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            if not own_supplier_ids:
                cur.close(); conn.close()
                return []
            if supplier_id and supplier_id not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к документам этого поставщика")
            where = " WHERE supplier_id = ANY(%s)"
            params = [own_supplier_ids]
        elif role in ("директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер"):
            if supplier_id:
                supplier_ids = supplier_related_ids(cur, supplier_id) or [supplier_id]
                where = " WHERE supplier_id = ANY(%s)"
                params = [supplier_ids]
        else:
            cur.close(); conn.close()
            return []
        cur.execute("SELECT id, supplier_id, doc_type, title, file_url, status, signed_at, expires_at, notes, uploaded_by, created_at FROM supplier_documents" + where + " ORDER BY created_at DESC", params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"supplierId":r[1],"docType":r[2] or "","title":r[3] or "",
                 "fileUrl":r[4] or "","status":r[5] or "","signedAt":str(r[6]) if r[6] else "",
                 "expiresAt":str(r[7]) if r[7] else "","notes":r[8] or "",
                 "uploadedBy":r[9] or "","createdAt":str(r[10])} for r in rows]

    @app.post("/supplier-documents")
    def create_supplier_document(data: dict, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        supplier_id = int(data.get('supplierId') or 0)
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            if not own_supplier_ids or supplier_id not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к документам этого поставщика")
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute(
            "INSERT INTO supplier_documents (supplier_id, doc_type, title, file_url, status, signed_at, expires_at, notes, uploaded_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (supplier_id, data.get('docType') or 'Другое', data.get('title') or '',
             data.get('fileUrl') or '', data.get('status') or 'Загружен',
             data.get('signedAt') or None, data.get('expiresAt') or None,
             data.get('notes') or '', data.get('uploadedBy') or ''))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return {"id": new_id, "ok": True}

    @app.delete("/supplier-documents/{id}")
    def delete_supplier_document(id: int, current_user: dict = Depends(get_current_user)):
        conn = get_db()
        cur = conn.cursor()
        role = current_user.get("role")
        if role == "поставщик":
            own_supplier_ids = current_supplier_ids(cur, current_user)
            cur.execute("SELECT supplier_id FROM supplier_documents WHERE id=%s", (id,))
            row = cur.fetchone()
            if not row or row[0] not in own_supplier_ids:
                cur.close(); conn.close()
                raise HTTPException(status_code=403, detail="Нет доступа к документам этого поставщика")
        elif role not in ("директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер"):
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        cur.execute("DELETE FROM supplier_documents WHERE id=%s", (id,))
        cur.close(); conn.close()
        return {"ok": True}
