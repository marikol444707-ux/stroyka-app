"""Runtime ownership helpers for API error writes and reads."""

from fastapi import HTTPException


PLATFORM_STAFF_ROLES = {
    "system_owner",
    "platform_admin",
    "platform_support",
    "billing_admin",
}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _platform_owner():
    return {"ownerScope": "platform", "companyId": None, "projectId": None}


def resolve_api_error_write_owner(
    cur,
    user,
    resolve_company_context,
    *,
    x_company_id=None,
    x_company_mode=None,
):
    """Resolve one safe owner without allowing error logging to break a request."""
    actor = dict(user or {})
    if not _positive_int(actor.get("id")) or actor.get("role") in PLATFORM_STAFF_ROLES:
        return _platform_owner()
    try:
        context = resolve_company_context(
            cur,
            actor,
            None,
            "read",
            x_company_id=x_company_id,
            x_company_mode=x_company_mode,
        )
    except HTTPException:
        return _platform_owner()
    company_id = _positive_int((context or {}).get("companyId") or (context or {}).get("company_id"))
    if (context or {}).get("mode") != "company" or not company_id:
        return _platform_owner()
    return {"ownerScope": "company", "companyId": company_id, "projectId": None}


def resolve_api_error_read_scope(
    cur,
    user,
    resolve_company_context,
    effective_company_actors,
    *,
    allowed_roles=(),
    x_company_id=None,
    x_company_mode=None,
):
    """Return a parameterized owner predicate for /system-status."""
    actor = dict(user or {})
    if actor.get("role") in PLATFORM_STAFF_ROLES:
        return {"where": "owner_scope='platform'", "params": ()}
    context = resolve_company_context(
        cur,
        actor,
        None,
        "read",
        x_company_id=x_company_id,
        x_company_mode=x_company_mode,
    )
    roles = {str(role or "").strip() for role in allowed_roles or ()}
    company_ids = sorted({
        company_id
        for item in effective_company_actors(actor, context) or []
        for company_id in [_positive_int((item or {}).get("companyId") or (item or {}).get("company_id"))]
        if company_id and str((item or {}).get("role") or "").strip() in roles
    })
    if not company_ids:
        raise HTTPException(status_code=403, detail="Роль не позволяет просматривать ошибки системы")
    return {
        "where": "owner_scope='company' AND company_id = ANY(%s)",
        "params": (company_ids,),
    }


def scoped_api_error_filter(scope, where="", params=()):
    scope_where = str((scope or {}).get("where") or "").strip()
    if not scope_where:
        raise ValueError("API error owner scope is required")
    extra_where = str(where or "").strip()
    combined = f"({scope_where})"
    if extra_where:
        combined += f" AND ({extra_where})"
    return combined, tuple((scope or {}).get("params") or ()) + tuple(params or ())


def insert_api_error(
    cur,
    *,
    method,
    path,
    status_code,
    error_type,
    error_message,
    user_id=None,
    user_name="",
    user_role="",
    owner=None,
):
    owner = dict(owner or _platform_owner())
    cur.execute(
        """INSERT INTO api_errors
           (method, path, status_code, error_type, error_message, user_id, user_name, user_role,
            owner_scope, company_id, project_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            method,
            path,
            status_code,
            error_type,
            error_message,
            _positive_int(user_id),
            str(user_name or ""),
            str(user_role or ""),
            owner.get("ownerScope") or "platform",
            _positive_int(owner.get("companyId")),
            _positive_int(owner.get("projectId")),
        ),
    )
