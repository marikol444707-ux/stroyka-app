from fastapi import HTTPException


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def resolve_marketing_outbox_owners(channels, publication_project=None) -> dict:
    channels = [dict(channel or {}) for channel in channels or []]
    project = dict(publication_project or {})
    project_id = _positive_int(project.get("id"))
    project_company_id = _positive_int(project.get("company_id") or project.get("companyId"))
    owners = {}
    company_ids = set()

    for channel in channels:
        channel_id = _positive_int(channel.get("id"))
        company_id = _positive_int(channel.get("company_id") or channel.get("companyId"))
        channel_project_id = _positive_int(channel.get("project_id") or channel.get("projectId"))
        if not channel_id or not company_id:
            raise HTTPException(status_code=409, detail="Маркетинговый MAX-канал не привязан к компании")
        if project_id and not project_company_id:
            raise HTTPException(status_code=409, detail="Объект публикации не привязан к компании")
        if project_company_id and project_company_id != company_id:
            raise HTTPException(status_code=409, detail="Объект публикации принадлежит другой компании")
        if project_id and channel_project_id and channel_project_id != project_id:
            raise HTTPException(status_code=409, detail="Маркетинговый MAX-канал привязан к другому объекту")
        company_ids.add(company_id)
        owners[channel_id] = {
            "scope": "company",
            "companyId": company_id,
            "projectId": project_id or channel_project_id,
        }

    if len(company_ids) > 1:
        raise HTTPException(status_code=409, detail="Нельзя публиковать одновременно в каналы разных компаний")
    return owners


def resolve_supply_outbox_owner(request_context, recipient) -> dict:
    request_context = dict(request_context or {})
    recipient = dict(recipient or {})
    company_id = _positive_int(request_context.get("companyId") or request_context.get("company_id"))
    recipient_company_id = _positive_int(recipient.get("company_id") or recipient.get("companyId"))
    project_id = _positive_int(request_context.get("projectId") or request_context.get("project_id"))
    if not company_id:
        raise HTTPException(status_code=409, detail="Заявка снабжения не привязана к компании")
    if not recipient_company_id:
        raise HTTPException(status_code=409, detail="Получатель КП не привязан к компании")
    if recipient_company_id != company_id:
        raise HTTPException(status_code=409, detail="Получатель КП принадлежит другой компании")
    return {"scope": "company", "companyId": company_id, "projectId": project_id}


def resolve_channel_write_owner(company_context, actors, project_rows=None, *, project_required=False, leadership_roles=()) -> dict:
    context = dict(company_context or {})
    actors = [dict(actor or {}) for actor in actors or []]
    if len(actors) != 1:
        raise HTTPException(status_code=409, detail="Компания MAX-канала определяется неоднозначно")
    allowed_roles = {str(role or "").strip() for role in (*leadership_roles, "менеджер_crm")}
    if (actors[0].get("role") or "") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Роль в выбранной компании не позволяет менять MAX-каналы")
    company_id = _positive_int(context.get("companyId") or context.get("company_id"))
    if not company_id:
        raise HTTPException(status_code=409, detail="MAX-канал не привязан к компании")

    project_id = None
    if project_required:
        projects = [dict(row or {}) for row in project_rows or []]
        if len(projects) != 1:
            raise HTTPException(status_code=409, detail="Объект MAX-канала определяется неоднозначно")
        project_id = _positive_int(projects[0].get("id"))
        project_company_id = _positive_int(projects[0].get("company_id") or projects[0].get("companyId"))
        if not project_id or project_company_id != company_id:
            raise HTTPException(status_code=409, detail="Объект MAX-канала принадлежит другой компании")
    return {"companyId": company_id, "projectId": project_id}
