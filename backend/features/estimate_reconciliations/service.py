import json


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


def reconciliation_visibility_filter(
    company_actors,
    document_roles,
    full_view_roles,
    package_limit_roles,
    package_unrestricted_roles=(),
    customer_roles=(),
):
    allowed_roles = {str(role or "").strip() for role in document_roles or ()}
    full_roles = {str(role or "").strip() for role in full_view_roles or ()}
    package_roles = {str(role or "").strip() for role in package_limit_roles or ()}
    unrestricted_package_roles = {
        str(role or "").strip() for role in package_unrestricted_roles or ()
    }
    normalized_customer_roles = {str(role or "").strip() for role in customer_roles or ()}
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id or role not in allowed_roles:
            continue
        actor_clauses = ["p.company_id=%s"]
        actor_params = [company_id]
        if role not in full_roles:
            projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
            legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
            if legacy_project:
                projects = sorted(set(projects + [legacy_project]))
            if not projects:
                continue
            actor_clauses.append("p.name = ANY(%s)")
            actor_params.append(projects)
        if role in package_roles and role not in unrestricted_package_roles:
            packages = _values((actor or {}).get("assignedPackages", (actor or {}).get("assigned_packages", [])))
            if not packages:
                continue
            actor_clauses.append("COALESCE(NULLIF(r.work_package,''),'Основная') = ANY(%s)")
            actor_params.append(packages)
        if role in normalized_customer_roles:
            actor_clauses.append("r.status='Утверждена'")
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
    if not clauses:
        return "FALSE", []
    return "(" + " OR ".join(clauses) + ")", params
