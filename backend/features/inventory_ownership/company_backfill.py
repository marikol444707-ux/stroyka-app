"""Copy a stored owner from a tool or inventory row onto its children.

A project name or a creator name is not an ownership link. Rows that do not
already store a company stay unowned. History is updated only from the tool
it points at, and only when that tool already has an owner and the history
does not name a different project. Inventory lines are updated only from the
inventory card they point at, and only when that card already has an owner.
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
        "inherited": "inherited",
        "unknown": "unknown",
        "conflict": "conflict",
        "partial": "partial",
        "parent_unowned": "parentUnowned",
    }[state]
    bucket[key] += 1


def plan_backfill(tables):
    """List child rows that can copy an owner their parent already stores."""
    planned = {}
    counts = {}
    assignments = []

    def remember(table, row_id, decision):
        planned.setdefault(table, {})[_positive(row_id)] = decision
        _bump(counts, table, decision["state"])
        if decision["state"] == "inherited" and _positive(row_id):
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
        remember("tools", row.get("id"), _stored_owner(row) or {"state": "unknown"})

    for row in tables.get("tool_history") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            tool = tool_rows.get(_positive(row.get("tool_id")))
            parent = planned.get("tools", {}).get(_positive(row.get("tool_id")))
            history_project = _project_key(row.get("project"))
            tool_project = _project_key((tool or {}).get("project"))
            if parent and parent.get("state") == "already_owned" and (
                history_project is None or history_project == tool_project
            ):
                decision = _owned_fields(parent)
            elif parent and parent.get("state") == "already_owned":
                decision = {"state": "conflict"}
            elif tool is not None or parent is not None:
                decision = {"state": "parent_unowned"}
            else:
                decision = {"state": "unknown"}
        remember("tool_history", row.get("id"), decision)

    for row in tables.get("inventory") or []:
        row = dict(row or {})
        remember("inventory", row.get("id"), _stored_owner(row) or {"state": "unknown"})

    for row in tables.get("inventory_items") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            parent = planned.get("inventory", {}).get(_positive(row.get("inventory_id")))
            if parent and parent.get("state") == "already_owned":
                decision = _owned_fields(parent)
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
        "ambiguousNames": [],
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
    return {
        "tools": tools,
        "tool_history": history,
        "inventory": inventory,
        "inventory_items": items,
    }


def apply_backfill(cur, *, write):
    """Read a snapshot and copy stored parent owners only when `write` is true.

    The caller owns the transaction. Updates touch only rows that still have
    no owner scope, company or project.
    """
    plan = plan_backfill(load_snapshot(cur, owner_columns=True))
    applied = 0
    if write:
        for item in plan["assignments"]:
            if item["table"] not in ("tool_history", "inventory_items") or not item["id"]:
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
