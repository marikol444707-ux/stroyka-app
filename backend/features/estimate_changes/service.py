import json
import re

from ..project_access.service import project_visibility_filter


def _values(value):
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item or "").strip()})
    if isinstance(value, str):
        try:
            return _values(json.loads(value))
        except (TypeError, ValueError):
            return []
    return []


def _actor_values(actor, camel_key, snake_key):
    return _values((actor or {}).get(camel_key, (actor or {}).get(snake_key, [])))


def _validated_alias(value, label):
    alias = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("Invalid " + label + " table alias")
    return alias


def estimate_change_visibility_filter(
    company_actors,
    document_roles,
    full_view_roles,
    package_limit_roles,
    package_unrestricted_roles,
    customer_roles,
    customer_statuses,
    *,
    project_prefix="p",
    change_prefix="uw",
):
    """Build a fail-closed list filter for effective company memberships."""
    project_alias = _validated_alias(project_prefix, "project")
    change_alias = _validated_alias(change_prefix, "estimate change")
    allowed_roles = {str(role or "").strip() for role in document_roles or () if str(role or "").strip()}
    package_roles = {
        str(role or "").strip() for role in package_limit_roles or () if str(role or "").strip()
    }
    unrestricted_packages = {
        str(role or "").strip() for role in package_unrestricted_roles or () if str(role or "").strip()
    }
    customers = {str(role or "").strip() for role in customer_roles or () if str(role or "").strip()}
    visible_customer_statuses = [
        str(status or "").strip() for status in customer_statuses or () if str(status or "").strip()
    ]

    clauses = []
    params = []
    for actor in company_actors or []:
        role = str((actor or {}).get("role") or "").strip()
        if role not in allowed_roles:
            continue
        project_sql, project_params = project_visibility_filter(
            [actor],
            full_view_roles,
            column_prefix=project_alias,
        )
        if project_sql == "FALSE":
            continue
        actor_clauses = [project_sql]
        actor_params = list(project_params)

        if role in package_roles and role not in unrestricted_packages:
            packages = _actor_values(actor, "assignedPackages", "assigned_packages")
            if not packages:
                continue
            actor_clauses.append(
                f"COALESCE(NULLIF({change_alias}.section_name,''),'Основная') = ANY(%s)"
            )
            actor_params.append(packages)

        if role in customers:
            if not visible_customer_statuses:
                continue
            actor_clauses.append(f"{change_alias}.status = ANY(%s)")
            actor_params.append(visible_customer_statuses)
        else:
            actor_clauses.append(f"COALESCE({change_alias}.status,'') <> 'Аннулировано'")

        clauses.append("(" + " AND ".join(actor_clauses) + ")")
        params.extend(actor_params)

    if not clauses:
        return "FALSE", []
    return "(" + " OR ".join(clauses) + ")", params
