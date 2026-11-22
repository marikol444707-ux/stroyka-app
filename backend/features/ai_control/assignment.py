"""Choose who should see an AI task inside one already-known company.

A person's name never selects a company. It only distinguishes people who
already belong to the company that owns the project.
"""

GROUPS = {
    "materials": ["снабженец", "кладовщик", "зам_директора", "директор"],
    "estimate": ["сметчик", "главный_инженер", "директор", "зам_директора"],
    "rooms": ["прораб", "главный_инженер", "директор"],
    "work_room": ["прораб", "главный_инженер", "директор"],
    "documents": ["прораб", "главный_инженер", "директор"],
}


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _row(row, key, index, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    if row and len(row) > index:
        return row[index]
    return default


def _projects(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if not value:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                import json
                parsed = json.loads(text)
            except ValueError:
                return []
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item or "").strip()]
        return []
    return []


def _covers_project(assigned_projects, project_name):
    projects = _projects(assigned_projects)
    if not projects:
        return True
    return bool(project_name and project_name in projects)


def company_members(cur, company_id, role, preferred_name=""):
    """People of one company and one role. The name stays inside that company."""
    company_id = _positive(company_id)
    role = str(role or "").strip()
    if not company_id or not role:
        return []
    params = [company_id, role]
    name_sql = ""
    preferred_name = str(preferred_name or "").strip()
    if preferred_name:
        name_sql = " AND LOWER(BTRIM(u.name))=LOWER(BTRIM(%s))"
        params.append(preferred_name)
    cur.execute(
        f"""SELECT u.id, u.name, m.role, m.assigned_projects
              FROM user_company_roles m
              JOIN users u ON u.id=m.user_id
             WHERE m.company_id=%s
               AND m.role=%s
               AND COALESCE(m.active, TRUE)=TRUE
               AND COALESCE(u.active, TRUE)=TRUE
               {name_sql}
             ORDER BY COALESCE(m.is_default, FALSE) DESC, m.id
             LIMIT 50""",
        tuple(params),
    )
    return [dict(row) if isinstance(row, dict) else {
        "id": _row(row, "id", 0),
        "name": _row(row, "name", 1, ""),
        "role": _row(row, "role", 2, role),
        "assigned_projects": _row(row, "assigned_projects", 3),
    } for row in cur.fetchall() or []]


def _first_cover(rows, project_name, fallback_role):
    for row in rows:
        if _covers_project(row.get("assigned_projects"), project_name):
            return (row.get("role") or fallback_role, row.get("name") or "")
    return None


def find_responsible(cur, company_id, project_name, roles, preferred_name="", preferred_role=""):
    company_id = _positive(company_id)
    roles = [str(role) for role in roles or [] if str(role or "").strip()]
    preferred_name = str(preferred_name or "").strip()
    preferred_role = str(preferred_role or "").strip()
    if not company_id:
        return ((roles[0] if roles else "директор"), "")
    if preferred_name and preferred_role:
        match = _first_cover(
            company_members(cur, company_id, preferred_role, preferred_name),
            project_name,
            preferred_role,
        )
        if match:
            return match
    for role in roles:
        match = _first_cover(company_members(cur, company_id, role), project_name, role)
        if match:
            return match
    if "директор" not in roles:
        return find_responsible(cur, company_id, project_name, ["директор", "зам_директора"])
    return ("директор", "")


def assignment(cur, company_id, project_name, group, preferred_name=""):
    roles = GROUPS.get(group) or ["директор"]
    if group == "work_room" and str(preferred_name or "").strip():
        role, name = find_responsible(
            cur, company_id, project_name, roles, preferred_name, "мастер",
        )
    else:
        role, name = find_responsible(cur, company_id, project_name, roles)
    return {"assignedRole": role, "assignedTo": name}


def active_user_for_role(cur, company_id, project_name, role, preferred_name=""):
    role = str(role or "").strip()
    if not role or not _positive(company_id):
        return None
    match = _first_cover(
        company_members(cur, company_id, role, preferred_name),
        project_name,
        role,
    )
    if not match:
        return None
    return {"assignedRole": match[0], "assignedTo": match[1]}


def normalize_assignment(cur, project_name, assigned_role="", assigned_to="", group="", company_id=None):
    assigned_role = str(assigned_role or "").strip()
    assigned_to = str(assigned_to or "").strip()
    if not _positive(company_id):
        # No company is known yet. Do not search people by name.
        if assigned_role:
            return {"assignedRole": assigned_role, "assignedTo": ""}
        return assignment(cur, None, project_name, group or "documents")
    if assigned_role and assigned_to:
        exact = active_user_for_role(cur, company_id, project_name, assigned_role, assigned_to)
        if exact:
            return exact
    if assigned_role:
        by_role = active_user_for_role(cur, company_id, project_name, assigned_role)
        if by_role:
            return by_role
    return assignment(
        cur,
        company_id,
        project_name,
        group or _group_from_role(assigned_role),
        assigned_to,
    )


def _group_from_role(role):
    if role in ("снабженец", "кладовщик"):
        return "materials"
    if role == "сметчик":
        return "estimate"
    if role in ("прораб", "главный_инженер", "мастер", "субподрядчик", "бригадир"):
        return "work_room"
    return "documents"
