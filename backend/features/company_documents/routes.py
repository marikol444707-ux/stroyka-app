"""Company document routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 18):
GET/POST /company-documents and DELETE /company-documents/{id} keep
their URLs, finance role guard and payload fields.
"""

from fastapi import Depends


def register_company_documents_module(app, deps):
    get_db = deps["get_db"]
    get_current_user = deps["get_current_user"]
    require_roles = deps["require_roles"]
    finance_roles = tuple(deps.get("finance_roles") or ())

    @app.get("/company-documents")
    def get_company_documents(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in finance_roles:
            return []
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id,company_id,name,doc_type,file_url,expires_at,uploaded_by FROM company_documents ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"companyId":r[1],"name":r[2],"docType":r[3],"fileUrl":r[4],"expiresAt":r[5],"uploadedBy":r[6]} for r in rows]

    @app.post("/company-documents")
    def create_company_document(data: dict, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO company_documents (company_id,name,doc_type,file_url,expires_at,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("companyId"),data.get("name",""),data.get("docType",""),data.get("fileUrl",""),data.get("expiresAt",""),data.get("uploadedBy","")))
        conn.commit()
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"id":row[0],"ok":True}

    @app.delete("/company-documents/{id}")
    def delete_company_document(id: int, _current_user: dict = Depends(require_roles(*finance_roles))):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM company_documents WHERE id=%s",(id,))
        conn.commit()
        cur.close(); conn.close()
        return {"ok":True}
