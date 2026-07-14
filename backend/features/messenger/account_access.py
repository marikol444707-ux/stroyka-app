from fastapi import HTTPException


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def resolve_account_company_ids(company_context, actors, *, leadership_roles=(), write=False):
    context = dict(company_context or {})
    actors = [dict(actor or {}) for actor in actors or []]
    allowed_roles = {str(role or "").strip() for role in leadership_roles}
    allowed_company_ids = sorted({
        company_id
        for actor in actors
        for company_id in [_positive_int(actor.get("companyId") or actor.get("company_id"))]
        if company_id and (actor.get("role") or "") in allowed_roles
    })

    if context.get("mode") == "company":
        company_id = _positive_int(context.get("companyId") or context.get("company_id"))
        matching = [
            actor
            for actor in actors
            if _positive_int(actor.get("companyId") or actor.get("company_id")) == company_id
        ]
        if not company_id or len(matching) != 1:
            raise HTTPException(status_code=409, detail="Компания MAX-связки определяется неоднозначно")
        if company_id not in allowed_company_ids:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет управлять MAX-связками",
            )
        return [company_id]

    if write:
        raise HTTPException(status_code=400, detail="Для изменения MAX-связки выберите одну компанию")
    if context.get("mode") == "all_companies" and allowed_company_ids:
        return allowed_company_ids
    raise HTTPException(status_code=403, detail="Нет доступа к MAX-связкам выбранных компаний")


def require_account_target_company(target_company_ids, selected_company_id):
    company_id = _positive_int(selected_company_id)
    allowed = {
        value
        for raw in target_company_ids or []
        for value in [_positive_int(raw)]
        if value
    }
    if not company_id or company_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Сотрудник не принадлежит выбранной компании",
        )
    return company_id


def account_identity_lock_keys(provider, *, external_user_id="", chat_id="", user_id=None, staff_id=None):
    clean_provider = str(provider or "").strip().lower()
    values = {
        f"messenger-account:{clean_provider}:external:{str(external_user_id).strip()}"
        if str(external_user_id or "").strip() else "",
        f"messenger-account:{clean_provider}:chat:{str(chat_id).strip()}"
        if str(chat_id or "").strip() else "",
        f"messenger-account:{clean_provider}:user:{_positive_int(user_id)}"
        if _positive_int(user_id) else "",
        f"messenger-account:{clean_provider}:staff:{_positive_int(staff_id)}"
        if _positive_int(staff_id) else "",
    }
    return sorted(value for value in values if value)


def resolve_existing_account(rows, *, user_id=None, staff_id=None):
    matches = [dict(row or {}) for row in rows or []]
    if not matches:
        return None
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Найдено несколько пересекающихся MAX-связок; требуется ручная проверка",
        )
    existing = matches[0]
    requested_user_id = _positive_int(user_id)
    requested_staff_id = _positive_int(staff_id)
    existing_user_id = _positive_int(existing.get("user_id"))
    existing_staff_id = _positive_int(existing.get("staff_id"))
    if existing_user_id != requested_user_id or existing_staff_id != requested_staff_id:
        raise HTTPException(
            status_code=409,
            detail="MAX-идентичность уже привязана к другому сотруднику",
        )
    return existing
