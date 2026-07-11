import re

from fastapi import HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def require_document_upload_actor(company_actors):
    """Require one concrete active company membership for a new file write."""
    actors = [
        dict(actor)
        for actor in company_actors or []
        if _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
    ]
    if len(actors) != 1:
        raise HTTPException(
            status_code=409,
            detail="Для загрузки файла выберите одну конкретную компанию",
        )
    actor = actors[0]
    company_id = _positive_int(actor.get("companyId") or actor.get("company_id"))
    actor["companyId"] = company_id
    actor["company_id"] = company_id
    return actor


def require_document_parent_company(document_company_id, parent_company_id):
    document_company_id = _positive_int(document_company_id)
    parent_company_id = _positive_int(parent_company_id)
    if not document_company_id or not parent_company_id or document_company_id != parent_company_id:
        raise HTTPException(status_code=409, detail="Документ относится к другой компании")
    return parent_company_id


def document_storage_namespace(company_id, project_id=None, project_name="", context="general"):
    """Build a stable tenant namespace without trusting names as ownership proof."""
    company_id = _positive_int(company_id)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания файла не определена")
    project_id = _positive_int(project_id)
    context_key = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(context or "general")).strip("-")[:40] or "general"
    if project_id:
        return f"company-{company_id}-project-{project_id}-{context_key}"
    return f"company-{company_id}-common-{context_key}"
