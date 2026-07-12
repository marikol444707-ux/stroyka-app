from fastapi import HTTPException

try:
    from backend.features.ai_findings.service import resolve_project_owner
except ModuleNotFoundError:
    from features.ai_findings.service import resolve_project_owner


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def resolve_task_owner(cur, data, *, system_project_name="Система", project_owner=None):
    payload = dict(data or {})
    project_name = str(payload.get("projectName") or payload.get("project_name") or "")
    finding_id = _positive_int(payload.get("findingId") or payload.get("finding_id"))
    if project_name == system_project_name:
        if finding_id:
            raise HTTPException(status_code=409, detail="Platform-задача не может ссылаться на находку объекта")
        return {"scope": "platform", "companyId": None, "projectId": None, "projectName": system_project_name}
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="projectName required")

    if finding_id:
        cur.execute(
            "SELECT company_id,project_id,project_name FROM ai_findings WHERE id=%s",
            (finding_id,),
        )
        finding = cur.fetchone()
        if not finding:
            raise HTTPException(status_code=404, detail="Находка ИИ не найдена")
        company_id = _positive_int(_row_value(finding, "company_id", 0))
        project_id = _positive_int(_row_value(finding, "project_id", 1))
        finding_project_name = str(_row_value(finding, "project_name", 2) or "")
        if not company_id or not project_id:
            raise HTTPException(status_code=409, detail="Владелец находки ИИ не определён")
        if finding_project_name.strip() != project_name.strip():
            raise HTTPException(status_code=409, detail="Задача и находка относятся к разным объектам")
        project = resolve_project_owner(
            cur, finding_project_name, company_id=company_id, project_id=project_id,
        )
    else:
        project = project_owner or resolve_project_owner(cur, project_name)
        if project["name"].strip() != project_name.strip():
            raise HTTPException(status_code=409, detail="Название объекта задачи не совпадает с owner")
    return {
        "scope": "company",
        "companyId": project["companyId"],
        "projectId": project["id"],
        "projectName": project["name"],
    }


def task_owner_filter(owner, *, alias=""):
    prefix = (alias + ".") if alias else ""
    if (owner or {}).get("scope") == "platform":
        return f"{prefix}owner_scope='platform' AND {prefix}company_id IS NULL AND {prefix}project_id IS NULL", []
    company_id = _positive_int((owner or {}).get("companyId"))
    project_id = _positive_int((owner or {}).get("projectId"))
    if not company_id or not project_id:
        raise HTTPException(status_code=409, detail="Владелец задачи не определён")
    return f"{prefix}owner_scope='company' AND {prefix}company_id=%s AND {prefix}project_id=%s", [company_id, project_id]
