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


def _company_from_project_sql():
    """The linked project names the company. The verified flag is only a fallback.

    A project name that belongs to exactly one company selects that company even
    when the payment is unverified or still carries another company's id. A
    shared name, or a namesake project that has no company, matches nothing.
    A verified payment is kept only when no project of that name exists.
    """
    return (
        "((EXISTS (SELECT 1 FROM projects owned_project "
        "WHERE owned_project.company_id=%s "
        "AND BTRIM(owned_project.name)=BTRIM(pp.project_name) "
        "AND NOT EXISTS (SELECT 1 FROM projects other_project "
        "WHERE BTRIM(other_project.name)=BTRIM(owned_project.name) "
        "AND other_project.id<>owned_project.id "
        "AND (other_project.company_id IS DISTINCT FROM owned_project.company_id "
        "OR other_project.company_id IS NULL))) "
        "OR (pp.company_id=%s AND pp.company_scope_verified=TRUE "
        "AND NOT EXISTS (SELECT 1 FROM projects named_project "
        "WHERE BTRIM(named_project.name)=BTRIM(pp.project_name)))))"
    )


def project_payment_visibility_filter(company_actors, finance_roles, *, ledger_exists=False):
    """Build a fail-closed payment read filter for effective company memberships."""
    allowed_finance_roles = {
        str(role or "").strip()
        for role in finance_roles or ()
        if str(role or "").strip()
    }
    clauses = []
    params = []
    owner_sql = _company_from_project_sql()
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id:
            continue
        if role in allowed_finance_roles:
            clauses.append(owner_sql)
            params.extend([company_id, company_id])
            continue
        if role != "заказчик":
            continue
        projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
        legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
        if legacy_project:
            projects = sorted(set(projects + [legacy_project]))
        if not projects:
            continue
        ledger_exclusion = 'ledger.id IS NULL AND ' if ledger_exists else ''
        clauses.append(
            f"({owner_sql} AND {ledger_exclusion}pp.amount > 0 AND pp.project_name = ANY(%s))"
        )
        params.extend([company_id, company_id, projects])
    if not clauses:
        return "FALSE", []
    if len(clauses) == 1:
        return clauses[0], params
    return "(" + " OR ".join(clauses) + ")", params
