from fastapi import HTTPException


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def resolve_outbox_read_company_ids(company_context, actors, *, leadership_roles=()) -> list[int]:
    context = dict(company_context or {})
    actors = [dict(actor or {}) for actor in actors or []]
    allowed_roles = {str(role or "").strip() for role in leadership_roles}
    context_company_ids = {
        company_id
        for value in (
            context.get("companyIds")
            or [context.get("companyId") or context.get("company_id")]
        )
        for company_id in [_positive_int(value)]
        if company_id
    }
    allowed_company_ids = sorted({
        company_id
        for actor in actors
        for company_id in [_positive_int(actor.get("companyId") or actor.get("company_id"))]
        if company_id in context_company_ids and (actor.get("role") or "") in allowed_roles
    })

    if context.get("mode") == "company":
        company_id = _positive_int(context.get("companyId") or context.get("company_id"))
        matching_actors = [
            actor
            for actor in actors
            if _positive_int(actor.get("companyId") or actor.get("company_id")) == company_id
        ]
        if not company_id or len(matching_actors) != 1:
            raise HTTPException(status_code=409, detail="Компания очереди MAX определяется неоднозначно")
        if company_id not in allowed_company_ids:
            raise HTTPException(
                status_code=403,
                detail="Роль в выбранной компании не позволяет читать очередь MAX",
            )
        return [company_id]

    if context.get("mode") == "all_companies" and allowed_company_ids:
        return allowed_company_ids
    raise HTTPException(status_code=403, detail="У пользователя нет доступа к очереди MAX выбранных компаний")
