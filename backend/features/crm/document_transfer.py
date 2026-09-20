"""Resolve CRM document destination without guessing between same-name projects."""
from fastapi import HTTPException
from ..project_access.service import resolve_project_parent
from ..customer_cabinet.record_scope import positive_id


def document_transfer_project(cur, owner, lead, data):
    bound_id = positive_id(owner.get('projectId') or lead.get('projectId'))
    requested = data.get('projectId')
    requested_id = positive_id(requested)
    if requested not in (None, '') and not requested_id:
        raise HTTPException(status_code=422, detail='Некорректный идентификатор объекта')
    if bound_id and requested_id and bound_id != requested_id:
        raise HTTPException(status_code=409, detail='Документы CRM закреплены за другим объектом')
    return resolve_project_parent(cur, {'companyId':owner['companyId']},
        project_id=bound_id or requested_id, project_name=data.get('projectName') or '', for_update=True)
