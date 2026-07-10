import json
import re
from typing import List

from fastapi import HTTPException


_REQUEST_COMPANY_MODES = {"company", "all_companies"}
_WRITE_ACTION_MODES = {"write", "mutate", "create", "update", "delete"}


def _as_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def _json_list(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item or "").strip()]
        except Exception:
            return []
    return []


def _strict_header_company_id(value):
    if value in (None, ""):
        return None
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="X-Company-Id должен быть положительным целым числом")
    if result <= 0:
        raise HTTPException(status_code=400, detail="X-Company-Id должен быть положительным целым числом")
    return result


def _assert_platform_account_boundary(user: dict, context: dict):
    expected_account_id = _as_int(user.get("platformAccountId") or user.get("platform_account_id"))
    if not expected_account_id:
        return
    contexts = context.get("companies") if context.get("mode") == "all_companies" else [context]
    for item in contexts or []:
        actual_account_id = _as_int(item.get("platformAccountId") or item.get("platform_account_id"))
        if actual_account_id and actual_account_id != expected_account_id:
            raise HTTPException(status_code=403, detail="Компания относится к другому клиентскому аккаунту")


def company_ids_for_context(context: dict) -> List[int]:
    if (context or {}).get("mode") == "company":
        company_id = _as_int((context or {}).get("companyId") or (context or {}).get("company_id"))
        return [company_id] if company_id and company_id > 0 else []
    if (context or {}).get("mode") != "all_companies":
        return []
    company_ids = {
        company_id
        for item in (context or {}).get("companies") or []
        for company_id in [_as_int((item or {}).get("companyId") or (item or {}).get("company_id"))]
        if company_id and company_id > 0
    }
    return sorted(company_ids)


def company_id_scope_filter(context: dict, column: str = "company_id"):
    column = str(column or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", column):
        raise ValueError("Invalid company scope column")
    company_ids = {
        company_id
        for value in (context or {}).get("companyIds") or company_ids_for_context(context or {})
        for company_id in [_as_int(value)]
        if company_id and company_id > 0
    }
    normalized_ids = sorted(company_ids)
    if (context or {}).get("mode") == "company":
        return (f" AND {column}=%s", [normalized_ids[0]]) if normalized_ids else (" AND FALSE", [])
    if (context or {}).get("mode") == "all_companies":
        return (f" AND {column} = ANY(%s)", [normalized_ids]) if normalized_ids else (" AND FALSE", [])
    return " AND FALSE", []


def assert_rows_company_scope(rows, expected_company_id, resource_label="связанные данные"):
    expected_id = _as_int(expected_company_id)
    if not expected_id or expected_id <= 0:
        raise HTTPException(status_code=409, detail="Компания документа не определена")
    for row in rows or []:
        actual_id = _as_int((row or {}).get("company_id") or (row or {}).get("companyId"))
        if actual_id != expected_id:
            raise HTTPException(
                status_code=409,
                detail=str(resource_label or "Связанные данные") + " относятся к другой компании",
            )
    return rows


def effective_company_user(user: dict, context: dict) -> dict:
    """Overlay the authenticated identity with the selected membership scope."""
    actor = dict(user or {})
    company_id = _as_int((context or {}).get("companyId") or (context or {}).get("company_id"))
    platform_account_id = _as_int(
        (context or {}).get("platformAccountId")
        or (context or {}).get("platform_account_id")
        or actor.get("platformAccountId")
        or actor.get("platform_account_id")
    )
    assigned_projects = _json_list((context or {}).get("assignedProjects"))
    assigned_packages = _json_list((context or {}).get("assignedPackages"))
    legacy_project_name = str(actor.get("projectName") or actor.get("project_name") or "").strip()
    default_legacy_project = (
        legacy_project_name
        if (context or {}).get("isDefault") and not assigned_projects
        else ""
    )
    actor.update({
        "role": (context or {}).get("effectiveRole") or (context or {}).get("role") or actor.get("role") or "",
        "companyId": company_id,
        "company_id": company_id,
        "platformAccountId": platform_account_id,
        "platform_account_id": platform_account_id,
        "projectName": default_legacy_project,
        "project_name": default_legacy_project,
        "assignedProjects": assigned_projects,
        "assigned_projects": assigned_projects,
        "assignedPackages": assigned_packages,
        "assigned_packages": assigned_packages,
    })
    return actor


def effective_company_actors(user: dict, context: dict) -> List[dict]:
    """Return one effective actor per company allowed by a resolved read context."""
    context = context or {}
    company_ids = {
        company_id
        for value in context.get("companyIds") or company_ids_for_context(context)
        for company_id in [_as_int(value)]
        if company_id and company_id > 0
    }
    if context.get("mode") == "company":
        candidates = [context]
    elif context.get("mode") == "all_companies":
        candidates = context.get("companies") or []
    else:
        candidates = []

    actors = []
    seen_company_ids = set()
    for candidate in candidates:
        company_id = _as_int((candidate or {}).get("companyId") or (candidate or {}).get("company_id"))
        if not company_id or company_id not in company_ids or company_id in seen_company_ids:
            continue
        actors.append(effective_company_user(user, candidate or {}))
        seen_company_ids.add(company_id)
    return actors


def _company_context_row(
    row: dict,
    *,
    client_account_roles=(),
    source: str = "membership",
    read_only: bool = False,
) -> dict:
    item = dict(row or {})
    role = item.get("role") or ""
    company_id = item.get("company_id") or item.get("id")
    platform_account_id = item.get("platform_account_id")
    return {
        "membershipId": item.get("membership_id"),
        "companyId": company_id,
        "company_id": company_id,
        "companyName": item.get("company_name") or item.get("name") or "",
        "company_name": item.get("company_name") or item.get("name") or "",
        "shortName": item.get("short_name") or item.get("shortName") or "",
        "platformAccountId": platform_account_id,
        "platform_account_id": platform_account_id,
        "role": role,
        "active": item.get("active") is not False,
        "companyActive": item.get("company_active") is not False,
        "isDefault": bool(item.get("is_default")),
        "assignedProjects": _json_list(item.get("assigned_projects")),
        "assignedPackages": _json_list(item.get("assigned_packages")),
        "accountLevel": role in client_account_roles,
        "readOnly": bool(read_only),
        "source": source,
    }


def user_company_memberships(
    cur,
    user: dict,
    *,
    include_inactive: bool = False,
    platform_staff_roles=(),
    client_account_roles=(),
) -> List[dict]:
    user_id = _as_int(user.get("id"))
    if not user_id:
        return []
    where = ["m.user_id=%s"]
    values = [user_id]
    if not include_inactive:
        where.append("COALESCE(m.active,TRUE)=TRUE")
        where.append("COALESCE(c.active,TRUE)=TRUE")
    cur.execute(f"""
        SELECT m.id AS membership_id, m.user_id, m.company_id,
               COALESCE(m.platform_account_id,c.platform_account_id) AS platform_account_id,
               m.role, m.assigned_projects, m.assigned_packages,
               COALESCE(m.active,TRUE) AS active, COALESCE(m.is_default,FALSE) AS is_default,
               c.name AS company_name, c.short_name, COALESCE(c.active,TRUE) AS company_active
        FROM user_company_roles m
        LEFT JOIN companies c ON c.id=m.company_id
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(m.is_default,FALSE) DESC, c.name NULLS LAST, m.company_id
    """, tuple(values))
    rows = [
        _company_context_row(row, client_account_roles=client_account_roles)
        for row in cur.fetchall()
    ]
    if rows:
        return rows
    legacy_company_id = _as_int(user.get("companyId") or user.get("company_id"))
    if not legacy_company_id or user.get("role") in platform_staff_roles:
        return []
    cur.execute("""SELECT c.id AS company_id, c.platform_account_id, c.name AS company_name,
                          c.short_name, COALESCE(c.active,TRUE) AS company_active
                   FROM companies c
                   WHERE c.id=%s""", (legacy_company_id,))
    company = cur.fetchone()
    if not company:
        return []
    legacy = dict(company)
    legacy.update({
        "membership_id": None,
        "role": user.get("role") or "",
        "assigned_projects": user.get("assignedProjects") or user.get("assigned_projects") or [],
        "assigned_packages": user.get("assignedPackages") or user.get("assigned_packages") or [],
        "active": True,
        "is_default": True,
    })
    return [_company_context_row(legacy, client_account_roles=client_account_roles, source="legacy")]


def account_company_contexts(cur, user: dict, *, client_account_roles=()) -> List[dict]:
    account_id = _as_int(user.get("platformAccountId") or user.get("platform_account_id"))
    company_id = _as_int(user.get("companyId") or user.get("company_id"))
    if not account_id and company_id:
        cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
        company = cur.fetchone()
        account_id = _as_int((company or {}).get("platform_account_id"))
    if not account_id:
        return []
    cur.execute("""SELECT c.id AS company_id, c.platform_account_id, c.name AS company_name,
                          c.short_name, COALESCE(c.active,TRUE) AS company_active
                   FROM companies c
                   WHERE c.platform_account_id=%s AND COALESCE(c.active,TRUE)=TRUE
                   ORDER BY c.name NULLS LAST, c.id""", (account_id,))
    rows = []
    for row in cur.fetchall():
        item = dict(row)
        item.update({
            "membership_id": None,
            "role": user.get("role") or "",
            "assigned_projects": [],
            "assigned_packages": [],
            "active": True,
            "is_default": _as_int(row.get("company_id")) == company_id,
        })
        rows.append(_company_context_row(
            item,
            client_account_roles=client_account_roles,
            source="account",
            read_only=True,
        ))
    return rows


def resolve_company_context(
    cur,
    user: dict,
    requested_company_id=None,
    action_mode: str = "read",
    *,
    platform_staff_roles=(),
    client_account_roles=(),
) -> dict:
    """Resolve SaaS company context without mutating legacy user.company_id flows."""
    mode = (action_mode or "read").strip().lower()
    requested_id = _as_int(requested_company_id)
    role = user.get("role") or ""
    if role in platform_staff_roles:
        if mode == "summary":
            return {"mode": "all_companies", "companyId": None, "role": role, "readOnly": True}
        raise HTTPException(status_code=403, detail="Платформенная роль не может выполнять рабочее действие без support-сессии компании")
    memberships = user_company_memberships(
        cur,
        user,
        platform_staff_roles=platform_staff_roles,
        client_account_roles=client_account_roles,
    )
    if role in client_account_roles and not memberships:
        account_companies = account_company_contexts(cur, user, client_account_roles=client_account_roles)
        if requested_id:
            selected = next((row for row in account_companies if _as_int(row.get("companyId")) == requested_id), None)
            if selected:
                if mode in ("write", "mutate", "create", "update", "delete"):
                    raise HTTPException(status_code=403, detail="Роль уровня аккаунта пока имеет только обзор. Для рабочих действий назначьте роль в компании.")
                return {**selected, "mode": "company"}
        if mode == "summary":
            return {"mode": "all_companies", "companyId": None, "role": role, "readOnly": True, "companies": account_companies}
        raise HTTPException(status_code=400, detail="Выберите компанию и рабочую роль для действия")
    if requested_id:
        selected = next((row for row in memberships if _as_int(row.get("companyId")) == requested_id), None)
        if not selected:
            raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")
        return {**selected, "mode": "company"}
    if memberships and mode == "summary":
        return {"mode": "all_companies", "companyId": None, "role": role, "readOnly": True, "companies": memberships}
    default_company = next((row for row in memberships if row.get("isDefault")), None)
    if default_company:
        return {**default_company, "mode": "company"}
    if len(memberships) == 1:
        return {**memberships[0], "mode": "company"}
    if memberships:
        raise HTTPException(status_code=400, detail="Выберите компанию для рабочего действия")
    raise HTTPException(status_code=403, detail="Компания пользователя не назначена")


def resolve_request_company_context(
    cur,
    user: dict,
    requested_company_id=None,
    action_mode: str = "read",
    *,
    x_company_id=None,
    x_company_mode=None,
    platform_staff_roles=(),
    client_account_roles=(),
) -> dict:
    """Resolve untrusted request headers through the existing membership rules."""
    action = (action_mode or "read").strip().lower()
    raw_mode = str(x_company_mode or "").strip().lower()
    if raw_mode and raw_mode not in _REQUEST_COMPANY_MODES:
        raise HTTPException(status_code=400, detail="X-Company-Mode должен быть company или all_companies")

    header_company_id = _strict_header_company_id(x_company_id)
    if not raw_mode and header_company_id:
        raw_mode = "company"
    if raw_mode == "company" and not header_company_id:
        raise HTTPException(status_code=400, detail="Для режима company требуется X-Company-Id")
    if raw_mode == "all_companies" and header_company_id:
        raise HTTPException(status_code=400, detail="В режиме all_companies нельзя передавать X-Company-Id")
    if raw_mode == "all_companies" and action in _WRITE_ACTION_MODES:
        raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")

    resource_company_id = _as_int(requested_company_id)
    if header_company_id and resource_company_id and header_company_id != resource_company_id:
        raise HTTPException(status_code=409, detail="Выбранная компания не совпадает с компанией объекта или документа")

    requested_mode = raw_mode or "legacy"
    resolved_company_id = header_company_id or resource_company_id
    resolved_action = "summary" if raw_mode == "all_companies" else action
    context = resolve_company_context(
        cur,
        user,
        resolved_company_id,
        resolved_action,
        platform_staff_roles=platform_staff_roles,
        client_account_roles=client_account_roles,
    )
    _assert_platform_account_boundary(user, context)
    return {
        **context,
        "companyIds": company_ids_for_context(context),
        "effectiveRole": context.get("role") or user.get("role") or "",
        "requestedMode": requested_mode,
    }


def resolve_resource_company_actor(
    cur,
    user: dict,
    resource_company_id,
    action_mode: str = "update",
    *,
    claimed_company_id=None,
    x_company_id=None,
    x_company_mode=None,
    allowed_roles=(),
    forbidden_detail="Роль в выбранной компании не позволяет выполнить действие",
    platform_staff_roles=(),
    client_account_roles=(),
):
    """Resolve a mutation actor against the company already stored on a resource."""
    company_id = _as_int(resource_company_id)
    if not company_id or company_id <= 0:
        raise HTTPException(
            status_code=409,
            detail="Документ не привязан к компании. Сначала назначьте компанию безопасным переносом данных.",
        )
    if claimed_company_id not in (None, ""):
        claimed_id = _as_int(claimed_company_id)
        if not claimed_id or claimed_id <= 0:
            raise HTTPException(status_code=400, detail="companyId должен быть положительным целым числом")
        if claimed_id != company_id:
            raise HTTPException(status_code=409, detail="companyId не совпадает с компанией документа")
    context = resolve_request_company_context(
        cur,
        user,
        company_id,
        action_mode,
        x_company_id=x_company_id,
        x_company_mode=x_company_mode,
        platform_staff_roles=platform_staff_roles,
        client_account_roles=client_account_roles,
    )
    resolved_company_id = _as_int(context.get("companyId") or context.get("company_id"))
    if context.get("mode") != "company" or resolved_company_id != company_id:
        raise HTTPException(status_code=409, detail="Выбранная компания не совпадает с компанией документа")
    actor = effective_company_user(user, context)
    normalized_roles = {str(role or "").strip() for role in allowed_roles or [] if str(role or "").strip()}
    if normalized_roles and (actor.get("role") or "") not in normalized_roles:
        raise HTTPException(status_code=403, detail=forbidden_detail)
    return context, actor


def build_company_context_response(
    cur,
    current_user: dict,
    *,
    platform_staff_roles=(),
    client_account_roles=(),
) -> dict:
    role = current_user.get("role") or ""
    companies = []
    if role in platform_staff_roles:
        cur.execute("""SELECT c.id AS company_id, c.platform_account_id, c.name AS company_name,
                              c.short_name, COALESCE(c.active,TRUE) AS company_active
                       FROM companies c
                       WHERE COALESCE(c.active,TRUE)=TRUE
                       ORDER BY c.platform_account_id NULLS LAST, c.name NULLS LAST, c.id""")
        for row in cur.fetchall():
            item = dict(row)
            item.update({
                "membership_id": None,
                "role": role,
                "assigned_projects": [],
                "assigned_packages": [],
                "active": True,
                "is_default": False,
            })
            companies.append(_company_context_row(
                item,
                client_account_roles=client_account_roles,
                source="platform",
                read_only=True,
            ))
    else:
        companies = user_company_memberships(
            cur,
            current_user,
            platform_staff_roles=platform_staff_roles,
            client_account_roles=client_account_roles,
        )
        if role in client_account_roles:
            known_ids = {_as_int(item.get("companyId")) for item in companies}
            for item in account_company_contexts(cur, current_user, client_account_roles=client_account_roles):
                if _as_int(item.get("companyId")) not in known_ids:
                    companies.append(item)
    default_company = next((item for item in companies if item.get("isDefault")), None)
    if not default_company and len(companies) == 1:
        default_company = companies[0]
    platform_account_id = (
        current_user.get("platformAccountId")
        or current_user.get("platform_account_id")
        or (default_company or {}).get("platformAccountId")
    )
    if not platform_account_id and companies:
        platform_account_id = companies[0].get("platformAccountId")
    return {
        "ok": True,
        "user": {
            "id": current_user.get("id"),
            "name": current_user.get("name") or "",
            "email": current_user.get("email") or "",
            "role": role,
            "companyId": current_user.get("companyId") or current_user.get("company_id"),
            "platformAccountId": platform_account_id,
        },
        "platformAccountId": platform_account_id,
        "defaultCompanyId": (default_company or {}).get("companyId"),
        "companies": companies,
        "canUseAllCompanies": len(companies) > 1 or role in platform_staff_roles or role in client_account_roles,
        "modeRules": {
            "allCompaniesReadOnly": True,
            "writeRequiresConcreteCompany": True,
            "legacyCompanyIdStillSupported": True,
        },
    }
