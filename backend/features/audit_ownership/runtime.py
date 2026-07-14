"""Runtime ownership resolution and writes for the company activity log."""

from collections import defaultdict

try:
    from backend.features.audit_ownership.ownership_report import (
        ENTITY_SPECS,
        PLATFORM_ACTIONS,
        _entity_index,
        _membership_index,
        _positive_int,
        _project_indexes,
        classify_audit_row,
    )
except ModuleNotFoundError:
    from features.audit_ownership.ownership_report import (
        ENTITY_SPECS,
        PLATFORM_ACTIONS,
        _entity_index,
        _membership_index,
        _positive_int,
        _project_indexes,
        classify_audit_row,
    )


ENTITY_SPEC_BY_TYPE = {spec[0]: spec for spec in ENTITY_SPECS}


def legacy_owner(reason):
    return {
        "scope": "legacy",
        "companyId": None,
        "projectId": None,
        "reason": str(reason or "owner_evidence_missing"),
    }


def _owner(scope, company_id=None, project_id=None, reason="explicit_owner"):
    return {
        "scope": scope,
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "reason": reason,
    }


def _dict_rows(cur):
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _available_columns(cur, table):
    cur.execute(
        """SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s ORDER BY column_name""",
        (table,),
    )
    return {str(row.get("column_name") or "") for row in _dict_rows(cur)}


def _column_expr(column, available, alias):
    return f"{column} AS {alias}" if column and column in available else f"NULL AS {alias}"


def _load_entity_rows(cur, entity_type, entity_id):
    spec = ENTITY_SPEC_BY_TYPE.get(str(entity_type or "").strip())
    entity_id = _positive_int(entity_id)
    if not spec or not entity_id:
        return []
    _, table, id_col, company_col, project_id_col, project_name_col = spec
    available = _available_columns(cur, table)
    if id_col not in available:
        return []
    select = ",".join((
        f"'{spec[0]}' AS entity_type",
        f"{id_col} AS entity_id",
        _column_expr(company_col, available, "company_id"),
        _column_expr(project_id_col, available, "project_id"),
        _column_expr(project_name_col, available, "project_name"),
    ))
    cur.execute(f"SELECT {select} FROM {table} WHERE {id_col}=%s ORDER BY {id_col}", (entity_id,))
    return _dict_rows(cur)


def _load_memberships(cur, user_ids):
    ids = sorted({_positive_int(value) for value in user_ids if _positive_int(value)})
    if not ids:
        return []
    cur.execute(
        """SELECT user_id,company_id,active FROM user_company_roles
            WHERE user_id=ANY(%s) AND COALESCE(active,TRUE)=TRUE
            ORDER BY user_id,company_id""",
        (ids,),
    )
    return _dict_rows(cur)


def _load_projects(cur, project_ids, project_names):
    ids = sorted({_positive_int(value) for value in project_ids if _positive_int(value)})
    names = sorted({str(value or "").strip() for value in project_names if str(value or "").strip()})
    if not ids and not names:
        return []
    clauses = []
    params = []
    if ids:
        clauses.append("id=ANY(%s)")
        params.append(ids)
    if names:
        clauses.append("name=ANY(%s)")
        params.append(names)
    cur.execute(
        "SELECT id,name,company_id FROM projects WHERE " + " OR ".join(clauses) + " ORDER BY id",
        tuple(params),
    )
    return _dict_rows(cur)


def resolve_audit_owner(
    cur,
    *,
    action="",
    entity_type="",
    entity_id=None,
    project_name="",
    user_id=None,
    owner_scope=None,
    company_id=None,
    project_id=None,
):
    action = str(action or "").strip().lower()
    entity_type = str(entity_type or "").strip()
    explicit_scope = str(owner_scope or "").strip().lower()
    explicit_company_id = _positive_int(company_id)
    explicit_project_id = _positive_int(project_id)

    if explicit_scope:
        if explicit_scope == "platform":
            if action in PLATFORM_ACTIONS and entity_type in {"", "user"}:
                return _owner("platform", reason="explicit_platform_owner")
            return legacy_owner("explicit_platform_owner_invalid")
        if explicit_scope == "legacy":
            return legacy_owner("explicit_legacy_owner")
        if explicit_scope != "company" or not explicit_company_id:
            return legacy_owner("explicit_company_owner_invalid")
        if explicit_project_id:
            projects = _load_projects(cur, [explicit_project_id], [])
            if len(projects) != 1:
                return legacy_owner("explicit_project_not_found")
            if _positive_int(projects[0].get("company_id")) != explicit_company_id:
                return legacy_owner("explicit_project_company_mismatch")
        return _owner(
            "company",
            explicit_company_id,
            explicit_project_id,
            "explicit_company_owner",
        )

    if action in PLATFORM_ACTIONS and entity_type in {"", "user"}:
        return _owner("platform", reason="platform_identity_event")

    target_user_id = entity_id if entity_type == "user" else None
    memberships = _load_memberships(cur, [user_id, target_user_id])
    entity_rows = _load_entity_rows(cur, entity_type, entity_id)

    project_ids = [project_id]
    project_names = [project_name]
    if entity_type == "project":
        project_ids.append(entity_id)
    for row in entity_rows:
        project_ids.append(row.get("project_id"))
        project_names.append(row.get("project_name"))
    projects = _load_projects(cur, project_ids, project_names)

    projects_by_id, projects_by_name = _project_indexes(projects)
    user_companies = _membership_index(memberships)
    entities = _entity_index(entity_rows, projects_by_id, projects_by_name, user_companies)
    evidence = classify_audit_row(
        {
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_name": str(project_name or "").strip(),
        },
        projects_by_name,
        entities,
        user_companies,
    )
    if evidence.get("status") != "verified":
        return legacy_owner(evidence.get("reason"))
    return _owner(
        evidence.get("scope"),
        evidence.get("companyId"),
        evidence.get("projectId"),
        evidence.get("reason"),
    )


def insert_audit_event(
    cur,
    *,
    user_id=None,
    user_name="",
    user_role="",
    action="",
    entity_type="",
    entity_id=None,
    description="",
    project_name="",
    owner_scope=None,
    company_id=None,
    project_id=None,
):
    owner = resolve_audit_owner(
        cur,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        project_name=project_name,
        user_id=user_id,
        owner_scope=owner_scope,
        company_id=company_id,
        project_id=project_id,
    )
    cur.execute(
        """INSERT INTO audit_log
           (user_id,user_name,user_role,action,entity_type,entity_id,description,project_name,
            owner_scope,company_id,project_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (
            _positive_int(user_id),
            str(user_name or "")[:255],
            str(user_role or "")[:100],
            str(action or "")[:100],
            str(entity_type or "")[:100],
            _positive_int(entity_id),
            str(description or ""),
            str(project_name or "")[:255],
            owner["scope"],
            owner["companyId"],
            owner["projectId"],
        ),
    )
    row = cur.fetchone()
    record_id = row.get("id") if isinstance(row, dict) else row[0]
    return {"id": record_id, "owner": owner}
