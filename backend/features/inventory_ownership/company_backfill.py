"""Assign tool and inventory owners from a unique project or a unique creator.

A project name is used only when exactly one projects row has that name and
that row already has a company. A creator name is used only when every active
membership of that exact name belongs to one company. A known creator in a
different company blocks the project match. Shared names, unknown names and
rows that already have an owner are left untouched.
"""
from collections import defaultdict


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

_OWNED = ("already_owned", "assign", "inherited")
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


def _creator_name(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def unique_project_owners(projects):
    grouped = defaultdict(list)
    for project in projects or []:
        name = _project_key((project or {}).get("name"))
        if name is None:
            continue
        grouped[name].append(project)
    owners = {}
    ambiguous = set()
    for name, rows in grouped.items():
        if len(rows) > 1:
            ambiguous.add(name)
            continue
        company_id = _positive(rows[0].get("company_id"))
        project_id = _positive(rows[0].get("id"))
        if company_id and project_id:
            owners[name] = {"company_id": company_id, "project_id": project_id}
    return owners, ambiguous


def creator_companies(memberships):
    """Map a person name to one company. Two companies for one name map to nothing."""
    grouped = defaultdict(set)
    for row in memberships or []:
        name = _creator_name((row or {}).get("name"))
        company_id = _positive((row or {}).get("company_id"))
        if name and company_id:
            grouped[name].add(company_id)
    return {name: next(iter(companies)) for name, companies in grouped.items() if len(companies) == 1}


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


def _from_project(name, owners, ambiguous):
    key = _project_key(name)
    if key is None:
        return {"state": "blank"}
    if key in owners:
        owner = owners[key]
        return {
            "state": "assign", "owner_scope": "project",
            "company_id": owner["company_id"], "project_id": owner["project_id"],
        }
    if key in ambiguous:
        return {"state": "ambiguous"}
    return {"state": "unknown"}


def _creator_company(created_by, creators):
    name = _creator_name(created_by)
    if name is None:
        return None
    return creators.get(name, "unknown")


def _confirm_project(decision, created_by, creators):
    if decision.get("state") != "assign":
        return decision
    creator = _creator_company(created_by, creators)
    if isinstance(creator, int) and creator != decision["company_id"]:
        return {"state": "conflict"}
    return decision


def _from_creator(created_by, creators):
    creator = _creator_company(created_by, creators)
    if isinstance(creator, int):
        return {
            "state": "assign", "owner_scope": "company",
            "company_id": creator, "project_id": None,
        }
    return {"state": "unknown"}


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
        "blank": "unknown",
        "conflict": "conflict",
        "partial": "partial",
        "parent_unowned": "parentUnowned",
    }[state]
    bucket[key] += 1


def plan_backfill(projects, creators, tables):
    """Classify rows and list unowned rows that can receive an owner.

    `creators` is the membership list `{name, company_id}`. `tables` maps each
    table to rows. A child sees the owner its parent receives in this same plan.
    """
    owners, ambiguous = unique_project_owners(projects)
    creator_map = creator_companies(creators)
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

    tool_rows = {}
    for row in tables.get("tools") or []:
        row = dict(row or {})
        tool_rows[_positive(row.get("id"))] = row
        decision = _stored_owner(row)
        if decision is None:
            decision = _from_project(row.get("project"), owners, ambiguous)
            if decision["state"] == "blank":
                decision = {"state": "unknown"}
        remember("tools", row.get("id"), decision)

    for row in tables.get("tool_history") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            tool_id = _positive(row.get("tool_id"))
            parent = planned.get("tools", {}).get(tool_id)
            tool = tool_rows.get(tool_id)
            history_project = _project_key(row.get("project"))
            tool_project = _project_key((tool or {}).get("project"))
            if parent and parent.get("state") in _OWNED and (
                history_project is None or history_project == tool_project
            ):
                decision = _owned_fields(parent)
            elif parent and parent.get("state") in _OWNED:
                decision = {"state": "conflict"}
            elif tool is not None:
                decision = {"state": "parent_unowned"}
            else:
                decision = _confirm_project(
                    _from_project(row.get("project"), owners, ambiguous),
                    row.get("created_by"), creator_map,
                )
                if decision["state"] == "blank":
                    decision = _from_creator(row.get("created_by"), creator_map)
        remember("tool_history", row.get("id"), decision)

    for row in tables.get("inventory") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            decision = _confirm_project(
                _from_project(row.get("project"), owners, ambiguous),
                row.get("created_by"), creator_map,
            )
            if decision["state"] == "blank":
                decision = _from_creator(row.get("created_by"), creator_map)
        remember("inventory", row.get("id"), decision)

    for row in tables.get("inventory_items") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            parent = planned.get("inventory", {}).get(_positive(row.get("inventory_id")))
            if parent and parent.get("state") in _OWNED:
                decision = _owned_fields(parent)
            elif parent:
                decision = {"state": "parent_unowned"}
            else:
                decision = {"state": "unknown"}
        remember("inventory_items", row.get("id"), decision)

    for table in TABLES:
        counts.setdefault(table, _empty_counts())
    return {
        "assignments": assignments,
        "counts": counts,
        "ambiguousNames": sorted(ambiguous),
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
    cur.execute("SELECT id, company_id, name FROM projects")
    projects = [_row_dict(row, ("id", "company_id", "name")) for row in cur.fetchall()]
    cur.execute(
        """SELECT u.name, r.company_id
           FROM users u
           JOIN user_company_roles r ON r.user_id = u.id
           WHERE COALESCE(u.active, TRUE) IS TRUE
             AND COALESCE(r.active, TRUE) IS TRUE
             AND u.name IS NOT NULL"""
    )
    creators = [_row_dict(row, ("name", "company_id")) for row in cur.fetchall()]
    cur.execute(f"SELECT id, project, {owner_sql} FROM tools")
    tools = [
        _row_dict(row, ("id", "project", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, tool_id, project, created_by, {owner_sql} FROM tool_history")
    history = [
        _row_dict(row, ("id", "tool_id", "project", "created_by", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, project, created_by, {owner_sql} FROM inventory")
    inventory = [
        _row_dict(row, ("id", "project", "created_by", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, inventory_id, {owner_sql} FROM inventory_items")
    items = [
        _row_dict(row, ("id", "inventory_id", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    return projects, creators, {
        "tools": tools,
        "tool_history": history,
        "inventory": inventory,
        "inventory_items": items,
    }


def apply_backfill(cur, *, write):
    """Read a snapshot, plan owners, and update only when `write` is true.

    The caller owns the transaction. Updates touch only rows that still have
    no owner scope, company or project.
    """
    projects, creators, tables = load_snapshot(cur, owner_columns=True)
    plan = plan_backfill(projects, creators, tables)
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
