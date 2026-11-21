"""Safe project-name backfill for room and measurement tables.

A stored name is assigned only when exactly one projects row has that name and
that row already has a company. Blank names, unknown names and names shared by
two companies stay unowned. A child whose own name points at a different
planned owner than its parent also stays unowned.
"""
from collections import defaultdict


NAMED_TABLES = (
    {"table": "rooms", "name": "project", "parent_table": None, "parent_fk": None},
    {"table": "project_measurements", "name": "project_name", "parent_table": None, "parent_fk": None},
    {"table": "room_works", "name": "project", "parent_table": "rooms", "parent_fk": "room_id"},
    {
        "table": "measurement_room_drafts",
        "name": "project_name",
        "parent_table": "project_measurements",
        "parent_fk": "measurement_id",
    },
)
CHILD_TABLES = (
    {"table": "room_windows", "parent_table": "rooms", "parent_fk": "room_id"},
    {"table": "room_doors", "parent_table": "rooms", "parent_fk": "room_id"},
)
TABLE_NAMES = tuple(item["table"] for item in NAMED_TABLES + CHILD_TABLES)

ADD_COLUMNS_SQL = "\n".join(
    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER;\n"
    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INTEGER;"
    for table in TABLE_NAMES
)

_CONSTRAINTS = []
for _table in TABLE_NAMES:
    _CONSTRAINTS.append(f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{_table}_owner_pair') THEN
        ALTER TABLE {_table} ADD CONSTRAINT {_table}_owner_pair CHECK (
            (company_id IS NULL AND project_id IS NULL) OR
            (company_id IS NOT NULL AND project_id IS NOT NULL)
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{_table}_project_owner_fk') THEN
        ALTER TABLE {_table} ADD CONSTRAINT {_table}_project_owner_fk
            FOREIGN KEY (project_id, company_id) REFERENCES projects(id, company_id);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS {_table}_owner_idx ON {_table}(company_id, project_id, id);
""")
CONSTRAINTS_SQL = "CREATE UNIQUE INDEX IF NOT EXISTS quality_projects_id_company_idx ON projects(id, company_id);\n" + "\n".join(_CONSTRAINTS)


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _raw_name(value):
    if value is None:
        return None
    text = str(value)
    if not text.strip():
        return None
    return text


def unique_name_owners(projects):
    """Return (owners_by_exact_name, ambiguous_names). Blank names are ignored."""
    grouped = defaultdict(list)
    for project in projects or []:
        name = _raw_name(project.get("name"))
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


def _stored_owner(row):
    company_id = _positive(row.get("company_id"))
    project_id = _positive(row.get("project_id"))
    if company_id and project_id:
        return {"company_id": company_id, "project_id": project_id, "state": "already_owned"}
    if company_id or project_id:
        return {"state": "partial"}
    return None


def _planned_named_owner(row, owners, ambiguous):
    stored = _stored_owner(row)
    if stored:
        return stored
    name = _raw_name(row.get("name"))
    if name in owners:
        return {**owners[name], "state": "assign"}
    if name in ambiguous:
        return {"state": "ambiguous"}
    return {"state": "unknown"}


def plan_backfill(projects, tables):
    """Classify every row and list the unowned rows that can receive an owner.

    `tables` maps a table name to rows with id, name (named tables), parent_id
    (children), company_id and project_id. The plan is computed from this
    snapshot, so a child sees the owner its parent will receive in the same run.
    """
    owners, ambiguous = unique_name_owners(projects)
    planned = {}
    counts = {}
    assignments = []

    def bump(table, state):
        bucket = counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0, "parentConflict": 0, "partial": 0,
            "parentUnowned": 0,
        })
        bucket["total"] += 1
        key = {
            "already_owned": "alreadyOwned",
            "assign": "assign",
            "inherited": "inherited",
            "ambiguous": "ambiguous",
            "unknown": "unknown",
            "parent_conflict": "parentConflict",
            "partial": "partial",
            "parent_unowned": "parentUnowned",
        }[state]
        bucket[key] += 1

    for spec in NAMED_TABLES:
        table = spec["table"]
        for row in tables.get(table) or []:
            decision = _planned_named_owner(row, owners, ambiguous)
            if spec["parent_table"] and decision.get("state") == "assign":
                parent = planned.get(spec["parent_table"], {}).get(_positive(row.get("parent_id")))
                if parent and parent.get("state") in ("already_owned", "assign", "inherited"):
                    if (parent.get("company_id"), parent.get("project_id")) != (
                        decision.get("company_id"), decision.get("project_id")
                    ):
                        decision = {"state": "parent_conflict"}
            planned.setdefault(table, {})[_positive(row.get("id"))] = decision
            bump(table, decision["state"])
            if decision["state"] == "assign":
                assignments.append({
                    "table": table,
                    "id": _positive(row.get("id")),
                    "company_id": decision["company_id"],
                    "project_id": decision["project_id"],
                })

    for spec in CHILD_TABLES:
        table = spec["table"]
        parent_plan = planned.get(spec["parent_table"], {})
        for row in tables.get(table) or []:
            stored = _stored_owner(row)
            if stored:
                decision = stored
            else:
                parent = parent_plan.get(_positive(row.get("parent_id")))
                if parent and parent.get("state") in ("already_owned", "assign", "inherited"):
                    decision = {
                        "company_id": parent["company_id"],
                        "project_id": parent["project_id"],
                        "state": "inherited",
                    }
                elif parent:
                    decision = {"state": "parent_unowned"}
                else:
                    decision = {"state": "unknown"}
            planned.setdefault(table, {})[_positive(row.get("id"))] = decision
            bump(table, decision["state"])
            if decision["state"] == "inherited":
                assignments.append({
                    "table": table,
                    "id": _positive(row.get("id")),
                    "company_id": decision["company_id"],
                    "project_id": decision["project_id"],
                })

    for table in TABLE_NAMES:
        counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0, "parentConflict": 0, "partial": 0,
            "parentUnowned": 0,
        })
    return {
        "assignments": assignments,
        "counts": counts,
        "ambiguousNames": sorted(ambiguous),
    }


def _row_dict(row, columns):
    if isinstance(row, dict):
        return {column: row.get(column) for column in columns}
    return dict(zip(columns, row))


def load_snapshot(cur, *, owner_columns=True):
    cur.execute("SELECT id, company_id, name FROM projects")
    projects = [
        _row_dict(row, ("id", "company_id", "name"))
        for row in cur.fetchall()
    ]
    tables = {}
    owner_sql = "company_id, project_id" if owner_columns else "NULL::integer, NULL::integer"
    for spec in NAMED_TABLES:
        parent_sql = spec["parent_fk"] if spec["parent_fk"] else "NULL::integer"
        cur.execute(
            f"SELECT id, {spec['name']}, {parent_sql}, {owner_sql} FROM {spec['table']}"
        )
        tables[spec["table"]] = [
            _row_dict(row, ("id", "name", "parent_id", "company_id", "project_id"))
            for row in cur.fetchall()
        ]
    for spec in CHILD_TABLES:
        cur.execute(
            f"SELECT id, {spec['parent_fk']}, {owner_sql} FROM {spec['table']}"
        )
        tables[spec["table"]] = [
            _row_dict(row, ("id", "parent_id", "company_id", "project_id"))
            for row in cur.fetchall()
        ]
    return projects, tables


def apply_backfill(cur, *, write):
    """Read a snapshot, plan owners, and update only when `write` is true.

    The caller owns the transaction. This function never commits or rolls back.
    Updates touch only rows that are still missing both owner columns.
    """
    projects, tables = load_snapshot(cur, owner_columns=True)
    plan = plan_backfill(projects, tables)
    applied = 0
    if write:
        for item in plan["assignments"]:
            if item["table"] not in TABLE_NAMES or not item["id"]:
                continue
            cur.execute(
                f"UPDATE {item['table']} SET company_id=%s, project_id=%s "
                "WHERE id=%s AND company_id IS NULL AND project_id IS NULL",
                (item["company_id"], item["project_id"], item["id"]),
            )
            applied += 1
    plan["applied"] = applied
    plan["write"] = bool(write)
    return plan


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
    raise RuntimeError("Cannot reach the database cursor for room ownership backfill")


def owner_columns_present(cur):
    cur.execute(
        """SELECT table_name FROM information_schema.columns
           WHERE table_schema='public' AND column_name='company_id'
             AND table_name = ANY(%s)""",
        (list(TABLE_NAMES),),
    )
    found = {row[0] if not isinstance(row, dict) else row.get("table_name") for row in cur.fetchall()}
    return set(TABLE_NAMES).issubset(found)
