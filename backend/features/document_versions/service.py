import json
from datetime import datetime


def save_document_version(
    get_db,
    document_type,
    document_id,
    snapshot_json,
    changed_by="",
    change_reason="",
):
    """Save a document snapshot and return its generated version label."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM document_versions WHERE document_type=%s AND document_id=%s",
            (document_type, document_id),
        )
        count = cur.fetchone()[0]
        label = "v" + str(count + 1) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot = (
            snapshot_json
            if isinstance(snapshot_json, str)
            else json.dumps(snapshot_json, ensure_ascii=False, default=str)
        )
        cur.execute(
            """INSERT INTO document_versions
               (document_type, document_id, version_label, snapshot_json, changed_by, change_reason)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (document_type, document_id, label, snapshot, changed_by, change_reason),
        )
        conn.commit()
        cur.close()
        conn.close()
        return label
    except Exception as exc:
        print("VERSION SAVE ERROR:", str(exc))
        return None
