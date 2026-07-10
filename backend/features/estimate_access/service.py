import json

from fastapi import HTTPException

from backend.features.project_access.service import (
    require_child_project_identity,
    resolve_project_parent,
)


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _values(value):
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item or "").strip()})
    if isinstance(value, str):
        try:
            return _values(json.loads(value))
        except Exception:
            return []
    return []


def _actor_values(actor, camel_key, snake_key):
    return _values((actor or {}).get(camel_key, (actor or {}).get(snake_key, [])))


def _assigned_projects(actor):
    projects = _actor_values(actor, "assignedProjects", "assigned_projects")
    legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    return sorted(set(projects + ([legacy_project] if legacy_project else [])))


def estimate_visibility_filter(company_actors, full_view_roles, package_limit_roles, column_prefix="e"):
    """Build a fail-closed estimate filter for effective company memberships."""
    prefix = str(column_prefix or "e").strip()
    if not prefix.replace("_", "").isalnum():
        raise ValueError("Invalid estimate table alias")
    full_roles = {str(role or "").strip() for role in full_view_roles or () if str(role or "").strip()}
    package_roles = {str(role or "").strip() for role in package_limit_roles or () if str(role or "").strip()}
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id:
            continue
        actor_clauses = [f"{prefix}.company_id=%s"]
        actor_params = [company_id]
        if role not in full_roles:
            projects = _assigned_projects(actor)
            if not projects:
                continue
            actor_clauses.append(f"{prefix}.project_name = ANY(%s)")
            actor_params.append(projects)
        if role in package_roles:
            packages = _actor_values(actor, "assignedPackages", "assigned_packages")
            if not packages:
                continue
            actor_clauses.append(
                f"COALESCE(NULLIF({prefix}.work_package,''),'Основная') = ANY(%s)"
            )
            actor_params.append(packages)
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
    if not clauses:
        return "FALSE", []
    return "(" + " OR ".join(clauses) + ")", params


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def resolve_estimate_parent(cur, actor, estimate_id, *, for_update=False, allow_template=False):
    """Resolve an estimate and verify its project inside the selected company."""
    company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
    normalized_estimate_id = _positive_int(estimate_id)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания сметы не определена")
    if not normalized_estimate_id:
        raise HTTPException(status_code=400, detail="Некорректный id сметы")
    lock_sql = " FOR UPDATE" if for_update else ""
    cur.execute(
        """SELECT id,company_id,project_id,project_name,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  COALESCE(is_template,FALSE) AS is_template
             FROM estimates
            WHERE id=%s AND company_id=%s""" + lock_sql,
        (normalized_estimate_id, company_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Смета не найдена в выбранной компании")
    estimate = {
        "id": _positive_int(_row_value(row, "id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "projectId": _positive_int(_row_value(row, "project_id", 2)),
        "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
        "workPackage": str(_row_value(row, "work_package", 4) or "Основная").strip() or "Основная",
        "isTemplate": bool(_row_value(row, "is_template", 5)),
    }
    if estimate["isTemplate"] and not estimate["projectId"] and not estimate["projectName"]:
        if allow_template:
            return estimate
        raise HTTPException(status_code=409, detail="Шаблон сметы не привязан к объекту")
    project = resolve_project_parent(
        cur,
        actor,
        project_id=estimate["projectId"],
        project_name=estimate["projectName"],
        for_update=for_update,
    )
    require_child_project_identity(estimate, project, child_label="Смета")
    estimate["projectId"] = project["id"]
    estimate["projectName"] = project["name"]
    return estimate
