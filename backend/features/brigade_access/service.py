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


def _actor_projects(actor):
    projects = _values((actor or {}).get("assignedProjects", (actor or {}).get("assigned_projects", [])))
    legacy_project = str((actor or {}).get("projectName") or (actor or {}).get("project_name") or "").strip()
    return sorted(set(projects + ([legacy_project] if legacy_project else [])))


def brigade_contract_visibility_filter(
    company_actors,
    *,
    allowed_roles,
    full_view_roles,
    worker_roles=(),
    package_limit_roles=(),
    package_optional_roles=(),
    item_alias="",
):
    """Build a fail-closed contract scope for effective company memberships."""
    allowed = {str(role or "").strip() for role in allowed_roles or () if str(role or "").strip()}
    full_view = {str(role or "").strip() for role in full_view_roles or () if str(role or "").strip()}
    workers = {str(role or "").strip() for role in worker_roles or () if str(role or "").strip()}
    package_limited = {
        str(role or "").strip() for role in package_limit_roles or () if str(role or "").strip()
    }
    package_optional = {
        str(role or "").strip() for role in package_optional_roles or () if str(role or "").strip()
    }
    item_prefix = str(item_alias or "").strip()
    if item_prefix and not item_prefix.replace("_", "").isalnum():
        raise ValueError("Invalid brigade item table alias")
    clauses = []
    params = []
    for actor in company_actors or []:
        company_id = _positive_int((actor or {}).get("companyId") or (actor or {}).get("company_id"))
        role = str((actor or {}).get("role") or "").strip()
        if not company_id or role not in allowed:
            continue
        actor_clauses = ["bc.company_id=%s"]
        actor_params = [company_id]
        if role not in full_view:
            projects = _actor_projects(actor)
            if not projects:
                continue
            actor_clauses.append("bc.project_name = ANY(%s)")
            actor_params.append(projects)
        if role in workers:
            actor_id = _positive_int((actor or {}).get("id")) or 0
            actor_name = str((actor or {}).get("name") or "").strip()
            if not actor_id and not actor_name:
                continue
            actor_clauses.append(
                "(COALESCE(bc.contractor_id,0)=%s OR "
                "(COALESCE(bc.contractor_id,0)=0 AND LOWER(COALESCE(bc.brigade_name,''))=LOWER(%s)))"
            )
            actor_params.extend([actor_id, actor_name])
        if role in package_limited:
            packages = _values((actor or {}).get("assignedPackages", (actor or {}).get("assigned_packages", [])))
            if not packages and role not in package_optional:
                continue
            if packages:
                if item_prefix:
                    actor_clauses.append(
                        f"COALESCE(NULLIF({item_prefix}.work_package,''), "
                        "NULLIF(bc.work_package,''), 'Основная') = ANY(%s)"
                    )
                else:
                    actor_clauses.append("""EXISTS (
                        SELECT 1 FROM brigade_contract_items bci_scope
                        WHERE bci_scope.contract_id=bc.id
                          AND COALESCE(NULLIF(bci_scope.work_package,''), NULLIF(bc.work_package,''), 'Основная') = ANY(%s)
                    )""")
                actor_params.append(packages)
        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)
    if not clauses:
        return "FALSE", []
    if len(clauses) == 1:
        return clauses[0], params
    return "(" + " OR ".join(clauses) + ")", params
