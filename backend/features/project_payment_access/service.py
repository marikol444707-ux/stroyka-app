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


def project_payment_visibility_filter(company_actors, finance_roles):
    """Build a fail-closed payment read filter for effective company memberships."""
    allowed_finance_roles = {
        str(role or "").strip()
        for role in finance_roles or ()
        if str(role or "").strip()
    }
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id:
            continue
        if role in allowed_finance_roles:
            clauses.append("(pp.company_id=%s)")
            params.append(company_id)
            continue
        if role != "заказчик":
            continue
        projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
        legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
        if legacy_project:
            projects = sorted(set(projects + [legacy_project]))
        if not projects:
            continue
        clauses.append("(pp.company_id=%s AND pp.amount > 0 AND pp.project_name = ANY(%s))")
        params.extend([company_id, projects])
    if not clauses:
        return "FALSE", []
    if len(clauses) == 1:
        return clauses[0], params
    return "(" + " OR ".join(clauses) + ")", params
