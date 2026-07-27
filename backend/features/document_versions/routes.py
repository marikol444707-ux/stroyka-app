"""Document version read routes.

Extracted verbatim from backend/main.py (Task 13.1, slice 2):
GET /document-versions and GET /document-versions/{vid} keep their
URLs, role guard and response fields. The write helper
save_doc_version stays in main.py where its callers live.
"""

from fastapi import Depends


def register_document_versions_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    project_document_roles = tuple(deps.get("project_document_roles") or ())

    @app.get("/document-versions")
    def list_document_versions(document_type: str = None, document_id: int = None, _current_user: dict = Depends(require_roles(*project_document_roles))):
        conn = get_db()
        cur = conn.cursor()
        cols = "id, document_type, document_id, version_label, changed_by, change_reason, created_at"
        if document_type and document_id is not None:
            cur.execute(f"SELECT {cols} FROM document_versions WHERE document_type=%s AND document_id=%s ORDER BY created_at DESC",
                        (document_type, document_id))
        elif document_type:
            cur.execute(f"SELECT {cols} FROM document_versions WHERE document_type=%s ORDER BY created_at DESC LIMIT 200",
                        (document_type,))
        else:
            cur.execute(f"SELECT {cols} FROM document_versions ORDER BY created_at DESC LIMIT 200")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id":r[0],"documentType":r[1],"documentId":r[2],"versionLabel":r[3],
                 "changedBy":r[4] or "","changeReason":r[5] or "","createdAt":str(r[6])} for r in rows]

    @app.get("/document-versions/{vid}")
    def get_document_version(vid: int, _current_user: dict = Depends(require_roles(*project_document_roles))):
        import json as _j
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""SELECT id, document_type, document_id, version_label, snapshot_json,
                              changed_by, change_reason, created_at
                       FROM document_versions WHERE id=%s""", (vid,))
        r = cur.fetchone()
        cur.close(); conn.close()
        if not r:
            return {"error": "not found"}
        try: snap = _j.loads(r[4]) if r[4] else {}
        except: snap = {}
        return {"id":r[0],"documentType":r[1],"documentId":r[2],"versionLabel":r[3],
                "snapshot":snap,"changedBy":r[5] or "","changeReason":r[6] or "",
                "createdAt":str(r[7])}
