"""Register platform financial documents in transaction-owned file storage."""
from fastapi import HTTPException


def register_platform_document_file(
    cur,
    uploaded,
    *,
    company_id,
    context,
    original_name,
    current_user,
):
    if not isinstance(uploaded, dict) or not str(uploaded.get("url") or "").strip():
        raise HTTPException(
            status_code=502,
            detail="Хранилище не вернуло ссылку на сохранённый договор.",
        )
    cur.execute(
        """INSERT INTO file_ownership
                  (company_id, project_id, file_url, storage_key, context,
                   original_name, content_type, uploaded_by_id, uploaded_by)
           VALUES (%s, NULL, %s, %s, %s, %s, 'application/pdf', %s, %s)
           RETURNING id""",
        (
            company_id,
            uploaded.get("url"),
            uploaded.get("key") or "",
            context,
            original_name,
            current_user.get("id") if isinstance(current_user, dict) else None,
            (current_user.get("name") or current_user.get("email") or str(current_user.get("id") or "system")) if isinstance(current_user, dict) else "system",
        ),
    )
    row = cur.fetchone()
    file_id = row.get("id") if isinstance(row, dict) else row[0]
    return "/tenant-files/{}/content".format(file_id)

