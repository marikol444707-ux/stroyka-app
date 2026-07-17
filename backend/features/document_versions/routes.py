import json

from fastapi import Depends


def register_document_versions_module(app, deps):
    get_db = deps["get_db"]
    require_roles = deps["require_roles"]
    project_document_roles = tuple(deps["project_document_roles"])

    @app.get("/document-versions")
    def list_document_versions(
        document_type: str = None,
        document_id: int = None,
        _current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        columns = "id, document_type, document_id, version_label, changed_by, change_reason, created_at"
        if document_type and document_id is not None:
            cur.execute(
                f"SELECT {columns} FROM document_versions WHERE document_type=%s AND document_id=%s ORDER BY created_at DESC",
                (document_type, document_id),
            )
        elif document_type:
            cur.execute(
                f"SELECT {columns} FROM document_versions WHERE document_type=%s ORDER BY created_at DESC LIMIT 200",
                (document_type,),
            )
        else:
            cur.execute(f"SELECT {columns} FROM document_versions ORDER BY created_at DESC LIMIT 200")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "id": row[0],
                "documentType": row[1],
                "documentId": row[2],
                "versionLabel": row[3],
                "changedBy": row[4] or "",
                "changeReason": row[5] or "",
                "createdAt": str(row[6]),
            }
            for row in rows
        ]

    @app.get("/document-versions/{vid}")
    def get_document_version(
        vid: int,
        _current_user: dict = Depends(require_roles(*project_document_roles)),
    ):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, document_type, document_id, version_label, snapshot_json,
                      changed_by, change_reason, created_at
               FROM document_versions WHERE id=%s""",
            (vid,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"error": "not found"}
        try:
            snapshot = json.loads(row[4]) if row[4] else {}
        except Exception:
            snapshot = {}
        return {
            "id": row[0],
            "documentType": row[1],
            "documentId": row[2],
            "versionLabel": row[3],
            "snapshot": snapshot,
            "changedBy": row[5] or "",
            "changeReason": row[6] or "",
            "createdAt": str(row[7]),
        }
