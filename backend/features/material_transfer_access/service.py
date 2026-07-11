import json

from fastapi import HTTPException

from ..project_access.service import (
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


def material_transfer_visibility_filter(
    company_actors,
    full_view_roles,
    worker_roles,
    package_limit_roles,
    package_optional_roles=(),
    column_prefix="mt",
):
    """Build fail-closed material transfer visibility per effective company role."""
    prefix = str(column_prefix or "mt").strip()
    if not prefix.replace("_", "").isalnum():
        raise ValueError("Invalid material transfer table alias")
    full_roles = {str(role or "").strip() for role in full_view_roles or () if str(role or "").strip()}
    workers = {str(role or "").strip() for role in worker_roles or () if str(role or "").strip()}
    package_roles = {str(role or "").strip() for role in package_limit_roles or () if str(role or "").strip()}
    optional_package_roles = {
        str(role or "").strip() for role in package_optional_roles or () if str(role or "").strip()
    }
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id or (role not in full_roles and role not in workers):
            continue
        actor_clauses = [f"{prefix}.company_id=%s"]
        actor_params = [company_id]
        projects = _assigned_projects(actor)
        if role not in full_roles:
            if not projects:
                continue
            actor_clauses.append(f"{prefix}.project_name = ANY(%s)")
            actor_params.append(projects)
        if role in workers:
            actor_clauses.append(
                f"({prefix}.to_user_id=%s OR "
                f"({prefix}.to_user_id IS NULL AND LOWER(TRIM({prefix}.to_person))=LOWER(TRIM(%s))))"
            )
            actor_params.extend([(actor or {}).get("id"), (actor or {}).get("name") or ""])
        if role in package_roles:
            packages = _actor_values(actor, "assignedPackages", "assigned_packages")
            if not packages and role not in optional_package_roles:
                continue
            if packages:
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


def resolve_material_transfer_parent(cur, actor, transfer_id, *, for_update=False):
    """Resolve one transfer and verify its project under the selected company."""
    company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
    normalized_id = _positive_int(transfer_id)
    if not company_id:
        raise HTTPException(status_code=409, detail="Компания передачи материала не определена")
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Некорректный id передачи материала")
    lock_sql = " FOR UPDATE" if for_update else ""
    cur.execute(
        """SELECT id,company_id,project_id,project_name,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  to_user_id,to_person,COALESCE(status,'Активна') AS status,signed
             FROM material_transfers
            WHERE id=%s AND company_id=%s""" + lock_sql,
        (normalized_id, company_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Передача материала не найдена в выбранной компании")
    transfer = {
        "id": _positive_int(_row_value(row, "id", 0)),
        "companyId": _positive_int(_row_value(row, "company_id", 1)),
        "projectId": _positive_int(_row_value(row, "project_id", 2)),
        "projectName": str(_row_value(row, "project_name", 3) or "").strip(),
        "workPackage": str(_row_value(row, "work_package", 4) or "Основная").strip() or "Основная",
        "toUserId": _positive_int(_row_value(row, "to_user_id", 5)),
        "toPerson": str(_row_value(row, "to_person", 6) or "").strip(),
        "status": str(_row_value(row, "status", 7) or "Активна").strip() or "Активна",
        "signed": bool(_row_value(row, "signed", 8)),
    }
    project = resolve_project_parent(
        cur,
        actor,
        project_id=transfer["projectId"],
        project_name=transfer["projectName"],
        for_update=for_update,
    )
    require_child_project_identity(transfer, project, child_label="Передача материала")
    transfer["projectId"] = project["id"]
    transfer["projectName"] = project["name"]
    return transfer
