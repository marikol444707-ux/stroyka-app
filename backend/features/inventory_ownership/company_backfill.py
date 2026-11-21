"""Give legacy tool and inventory rows to the company that already owns them.

A row that already stores a company is left as it is. A row with no company
is filled in only in two safe cases: the database has one operating company,
or the project name points at exactly one project of one company. A person's
name is never used. A newer company does not receive these old rows.
"""
TABLES = ("tools", "tool_history", "inventory", "inventory_items")

ADD_COLUMNS_SQL = "\n".join(
    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner_scope TEXT;\n"
    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER;\n"
    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INTEGER;"
    for table in TABLES
)

_CONSTRAINTS = []
for _table in TABLES:
    _CONSTRAINTS.append(f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_{_table}_owner') THEN
        ALTER TABLE {_table} ADD CONSTRAINT ck_{_table}_owner CHECK (
            (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
            (owner_scope = 'company' AND company_id IS NOT NULL AND project_id IS NULL) OR
            (owner_scope = 'project' AND company_id IS NOT NULL AND project_id IS NOT NULL)
        );
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_{_table}_owner ON {_table}(owner_scope, company_id, project_id);
""")
CONSTRAINTS_SQL = "\n".join(_CONSTRAINTS)

_COUNT_KEYS = (
    "total", "alreadyOwned", "assign", "inherited", "ambiguous", "unknown",
    "conflict", "partial", "parentUnowned",
)


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _project_key(value):
    if value is None:
        return None
    text = str(value)
    if not text.strip():
        return None
    return text


def _stored_owner(row):
    scope = str((row or {}).get("owner_scope") or "").strip()
    company_id = _positive((row or {}).get("company_id"))
    project_id = _positive((row or {}).get("project_id"))
    if not scope and not company_id and not project_id:
        return None
    if scope == "company" and company_id and not project_id:
        return {
            "state": "already_owned", "owner_scope": "company",
            "company_id": company_id, "project_id": None,
        }
    if scope == "project" and company_id and project_id:
        return {
            "state": "already_owned", "owner_scope": "project",
            "company_id": company_id, "project_id": project_id,
        }
    return {"state": "partial"}


def _owned_fields(decision):
    return {
        "state": "inherited",
        "owner_scope": decision["owner_scope"],
        "company_id": decision["company_id"],
        "project_id": decision["project_id"],
    }


def _empty_counts():
    return {key: 0 for key in _COUNT_KEYS}


def _bump(counts, table, state):
    bucket = counts.setdefault(table, _empty_counts())
    bucket["total"] += 1
    key = {
        "already_owned": "alreadyOwned",
        "assign": "assign",
        "inherited": "inherited",
        "ambiguous": "ambiguous",
        "unknown": "unknown",
        "conflict": "conflict",
        "partial": "partial",
        "parent_unowned": "parentUnowned",
    }[state]
    bucket[key] += 1


def legacy_company_id(companies, projects):
    """The one company that can receive old rows which name no other company.

    This is the only company in the database, or the only company that already
    has a project. It is not a hardcoded company number. When two companies
    both have projects, there is no single legacy company.
    """
    company_ids = []
    for row in companies or []:
        company_id = _positive((row or {}).get("id"))
        if company_id and company_id not in company_ids:
            company_ids.append(company_id)
    if len(company_ids) == 1:
        return company_ids[0]
    project_companies = []
    for row in projects or []:
        company_id = _positive((row or {}).get("company_id"))
        if company_id and company_id not in project_companies:
            project_companies.append(company_id)
    if len(project_companies) == 1:
        return project_companies[0]
    return None


def _project_groups(projects):
    grouped = {}
    for project in projects or []:
        name = _project_key((project or {}).get("name"))
        company_id = _positive((project or {}).get("company_id"))
        project_id = _positive((project or {}).get("id"))
        if name is None or not company_id or not project_id:
            continue
        grouped.setdefault(name, []).append({"company_id": company_id, "project_id": project_id})
    return grouped


def _company_owner(company_id):
    return {
        "state": "assign", "owner_scope": "company",
        "company_id": company_id, "project_id": None,
    }


def _project_owner(company_id, project_id):
    return {
        "state": "assign", "owner_scope": "project",
        "company_id": company_id, "project_id": project_id,
    }


def _owner_from_project_name(name, groups, legacy_company):
    """Resolve a project label without giving one company's row to another."""
    key = _project_key(name)
    if key is None:
        if legacy_company:
            return _company_owner(legacy_company)
        return {"state": "unknown"}
    matches = groups.get(key) or []
    companies = {item["company_id"] for item in matches}
    if len(matches) == 1:
        return _project_owner(matches[0]["company_id"], matches[0]["project_id"])
    if len(companies) == 1:
        return _company_owner(next(iter(companies)))
    if not matches and legacy_company:
        return _company_owner(legacy_company)
    if len(companies) > 1:
        return {"state": "ambiguous"}
    return {"state": "unknown"}


def _owned(decision):
    return bool(decision) and decision.get("state") in ("already_owned", "assign", "inherited")


def plan_backfill(companies, projects, tables):
    """Assign legacy rows to the original company or to one exact project."""
    planned = {}
    counts = {}
    assignments = []

    def remember(table, row_id, decision):
        planned.setdefault(table, {})[_positive(row_id)] = decision
        _bump(counts, table, decision["state"])
        if decision["state"] in ("assign", "inherited") and _positive(row_id):
            assignments.append({
                "table": table,
                "id": _positive(row_id),
                "owner_scope": decision["owner_scope"],
                "company_id": decision["company_id"],
                "project_id": decision["project_id"],
            })

    legacy_company = legacy_company_id(companies, projects)
    groups = _project_groups(projects)
    tool_rows = {}
    for row in tables.get("tools") or []:
        row = dict(row or {})
        tool_rows[_positive(row.get("id"))] = row
        decision = _stored_owner(row) or _owner_from_project_name(row.get("project"), groups, legacy_company)
        remember("tools", row.get("id"), decision)

    for row in tables.get("tool_history") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            tool = tool_rows.get(_positive(row.get("tool_id")))
            parent = planned.get("tools", {}).get(_positive(row.get("tool_id")))
            history_project = _project_key(row.get("project"))
            tool_project = _project_key((tool or {}).get("project"))
            own = _owner_from_project_name(row.get("project"), groups, None)
            if _owned(parent) and (history_project is None or history_project == tool_project):
                decision = _owned_fields(parent)
            elif _owned(parent) and own.get("state") == "assign" and own["company_id"] == parent["company_id"]:
                decision = own
            elif _owned(parent):
                decision = {"state": "conflict"}
            elif own.get("state") == "assign":
                decision = own
            elif legacy_company and own.get("state") in ("unknown", "ambiguous"):
                decision = _company_owner(legacy_company)
            elif tool is not None or parent is not None:
                decision = {"state": "parent_unowned"}
            else:
                decision = own
        remember("tool_history", row.get("id"), decision)

    for row in tables.get("inventory") or []:
        row = dict(row or {})
        decision = _stored_owner(row) or _owner_from_project_name(row.get("project"), groups, legacy_company)
        remember("inventory", row.get("id"), decision)

    for row in tables.get("inventory_items") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            parent = planned.get("inventory", {}).get(_positive(row.get("inventory_id")))
            if _owned(parent):
                decision = _owned_fields(parent)
            elif legacy_company:
                decision = _company_owner(legacy_company)
            elif parent is not None:
                decision = {"state": "parent_unowned"}
            else:
                decision = {"state": "unknown"}
        remember("inventory_items", row.get("id"), decision)

    for table in TABLES:
        counts.setdefault(table, _empty_counts())
    return {
        "assignments": assignments,
        "counts": counts,
        "ambiguousNames": sorted(
            name for name, matches in groups.items()
            if len({item["company_id"] for item in matches}) > 1
        ),
        "legacyCompanyId": legacy_company,
    }


def _row_dict(row, columns):
    if isinstance(row, dict):
        return {column: row.get(column) for column in columns}
    return dict(zip(columns, row))


def _owner_sql(present):
    if present:
        return "owner_scope, company_id, project_id"
    return "NULL::text, NULL::integer, NULL::integer"


def load_snapshot(cur, *, owner_columns=True):
    owner_sql = _owner_sql(owner_columns)
    cur.execute("SELECT id FROM companies")
    companies = [_row_dict(row, ("id",)) for row in cur.fetchall()]
    cur.execute("SELECT id, company_id, name FROM projects")
    projects = [_row_dict(row, ("id", "company_id", "name")) for row in cur.fetchall()]
    cur.execute(f"SELECT id, project, {owner_sql} FROM tools")
    tools = [
        _row_dict(row, ("id", "project", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, tool_id, project, {owner_sql} FROM tool_history")
    history = [
        _row_dict(row, ("id", "tool_id", "project", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, project, {owner_sql} FROM inventory")
    inventory = [
        _row_dict(row, ("id", "project", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, inventory_id, {owner_sql} FROM inventory_items")
    items = [
        _row_dict(row, ("id", "inventory_id", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    return companies, projects, {
        "tools": tools,
        "tool_history": history,
        "inventory": inventory,
        "inventory_items": items,
    }


def apply_backfill(cur, *, write):
    """Read a snapshot and fill missing owners only when `write` is true.

    The caller owns the transaction. Updates touch only rows that still have
    no owner scope, company or project.
    """
    companies, projects, tables = load_snapshot(cur, owner_columns=True)
    plan = plan_backfill(companies, projects, tables)
    applied = 0
    if write:
        for item in plan["assignments"]:
            if item["table"] not in TABLES or not item["id"]:
                continue
            cur.execute(
                f"UPDATE {item['table']} SET owner_scope=%s, company_id=%s, project_id=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL",
                (item["owner_scope"], item["company_id"], item["project_id"], item["id"]),
            )
            applied += 1
    plan["applied"] = applied
    plan["write"] = bool(write)
    return plan


def owner_columns_present(cur):
    cur.execute(
        """SELECT table_name FROM information_schema.columns
           WHERE table_schema='public' AND column_name='company_id'
             AND table_name = ANY(%s)""",
        (list(TABLES),),
    )
    found = {row[0] if not isinstance(row, dict) else row.get("table_name") for row in cur.fetchall()}
    return set(TABLES).issubset(found)


def dbapi_cursor(bind):
    """Return a DB-API cursor from an Alembic/SQLAlchemy connection."""
    candidates = [bind]
    for attr in ("connection", "dbapi_connection", "driver_connection"):
        value = getattr(bind, attr, None)
        if value is not None:
            candidates.append(value)
            nested = getattr(value, "dbapi_connection", None) or getattr(value, "driver_connection", None)
            if nested is not None:
                candidates.append(nested)
    for candidate in candidates:
        if hasattr(candidate, "cursor"):
            return candidate.cursor()
    raise RuntimeError("Cannot reach the database cursor for tool inventory ownership backfill")
