from fastapi import HTTPException


WORKER_OUTBOX_SCOPE_SQL = "owner_scope='company' AND company_id IS NOT NULL"


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def assert_worker_outbox_owner(row) -> dict:
    item = dict(row or {})
    company_id = _positive_int(item.get("company_id") or item.get("companyId"))
    project_id = _positive_int(item.get("project_id") or item.get("projectId"))
    if item.get("owner_scope") != "company" or not company_id:
        raise HTTPException(status_code=409, detail="Очередь MAX не привязана к компании")
    return {"companyId": company_id, "projectId": project_id}


def dispatch_outbox_lock_clause(*, dry_run: bool) -> str:
    return "" if dry_run else " FOR UPDATE SKIP LOCKED"
