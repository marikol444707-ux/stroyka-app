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


def resolved_payment_company_sql(alias="pp"):
    """The one project company for this name, otherwise the company stored on the row."""
    prefix = str(alias or "pp").strip()
    if not prefix.replace("_", "").isalnum():
        raise ValueError("Invalid payment table alias")
    return (
        f"COALESCE((SELECT MIN(owned_project.company_id) FROM projects owned_project "
        f"WHERE owned_project.company_id IS NOT NULL "
        f"AND BTRIM(owned_project.name)=BTRIM({prefix}.project_name) "
        f"AND NOT EXISTS (SELECT 1 FROM projects other_project "
        f"WHERE BTRIM(other_project.name)=BTRIM(owned_project.name) "
        f"AND other_project.id<>owned_project.id "
        f"AND (other_project.company_id IS DISTINCT FROM owned_project.company_id "
        f"OR other_project.company_id IS NULL))), {prefix}.company_id)"
    )


UNIQUE_PROJECT_COMPANY_SQL = """
SELECT MIN(owned_project.company_id) AS company_id
  FROM projects owned_project
 WHERE owned_project.company_id IS NOT NULL
   AND BTRIM(owned_project.name)=BTRIM(%s)
   AND NOT EXISTS (
        SELECT 1 FROM projects other_project
         WHERE BTRIM(other_project.name)=BTRIM(owned_project.name)
           AND other_project.id<>owned_project.id
           AND (other_project.company_id IS DISTINCT FROM owned_project.company_id
                OR other_project.company_id IS NULL)
   )
"""


def _company_from_project_sql():
    """Show a payment to the company that can also reverse it.

    A unique project selects its company only when the payment has no stored
    company or already stores that same company. A stored company that belongs
    to a different project stays hidden. A verified payment with no project of
    that name keeps the company stored on the row.
    """
    return (
        "(((EXISTS (SELECT 1 FROM projects owned_project "
        "WHERE owned_project.company_id=%s "
        "AND BTRIM(owned_project.name)=BTRIM(pp.project_name) "
        "AND NOT EXISTS (SELECT 1 FROM projects other_project "
        "WHERE BTRIM(other_project.name)=BTRIM(owned_project.name) "
        "AND other_project.id<>owned_project.id "
        "AND (other_project.company_id IS DISTINCT FROM owned_project.company_id "
        "OR other_project.company_id IS NULL))) "
        "AND (pp.company_id IS NULL OR pp.company_id=%s)) "
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
            params.extend([company_id, company_id, company_id])
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
        params.extend([company_id, company_id, company_id, projects])
    if not clauses:
        return "FALSE", []
    if len(clauses) == 1:
        return clauses[0], params
    return "(" + " OR ".join(clauses) + ")", params
