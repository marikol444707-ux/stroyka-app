from fastapi import HTTPException


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def resolve_authenticated_lead_owner(company_context, actors, *, allowed_roles=()) -> dict:
    context = dict(company_context or {})
    actors = [dict(actor or {}) for actor in actors or []]
    company_id = _positive_int(context.get("companyId") or context.get("company_id"))
    if context.get("mode") != "company" or not company_id or len(actors) != 1:
        raise HTTPException(status_code=409, detail="Для CRM-действия выберите одну конкретную компанию")
    normalized_roles = {str(role or "").strip() for role in allowed_roles or () if str(role or "").strip()}
    if normalized_roles and (actors[0].get("role") or "") not in normalized_roles:
        raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет менять CRM")
    actor_company_id = _positive_int(actors[0].get("companyId") or actors[0].get("company_id"))
    if actor_company_id != company_id:
        raise HTTPException(status_code=409, detail="Рабочая роль не совпадает с выбранной компанией")
    return {"companyId": company_id, "actor": actors[0]}


def resolve_public_lead_owner(public_site_company_id) -> dict:
    company_id = _positive_int(public_site_company_id)
    if not company_id:
        raise HTTPException(status_code=503, detail="Компания публичного сайта не настроена")
    return {"companyId": company_id}


def resolve_marketing_lead_owner(channel) -> dict:
    channel = dict(channel or {})
    company_id = _positive_int(channel.get("company_id") or channel.get("companyId"))
    if not company_id:
        raise HTTPException(status_code=409, detail="Маркетинговый MAX-канал не привязан к компании")
    return {"companyId": company_id}


def resolve_lead_child_owner(lead) -> dict:
    lead = dict(lead or {})
    company_id = _positive_int(lead.get("company_id") or lead.get("companyId"))
    if not company_id:
        raise HTTPException(
            status_code=409,
            detail="CRM-заявка не привязана к компании. Сначала завершите безопасный перенос данных.",
        )
    return {
        "companyId": company_id,
        "projectId": _positive_int(lead.get("project_id") or lead.get("projectId")),
    }
