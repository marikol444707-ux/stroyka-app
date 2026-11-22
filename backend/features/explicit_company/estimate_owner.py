"""The company stored on a new estimate is the caller's selected company."""

from fastapi import HTTPException


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def explicit_estimate_company_id(actor_company_id, project_company_id=None):
    """Return the actor company, and reject a project that belongs elsewhere."""
    actor_company = _positive(actor_company_id)
    if not actor_company:
        raise HTTPException(status_code=409, detail="Компания сметы не назначена")
    if project_company_id in (None, ""):
        return actor_company
    project_company = _positive(project_company_id)
    if project_company != actor_company:
        raise HTTPException(status_code=409, detail="Объект относится к другой компании")
    return actor_company
