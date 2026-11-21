"""Give legacy field records to the company that already owns them.

A row that already stores a company is left as it is. A row with no company
is filled in only in two safe cases: the database has one operating company,
or the project name points at exactly one project of one company. A person's
name is never used. A newer company does not receive these old rows.
"""
TABLES = (
    "contracts",
    "piecework",
    "project_checklists",
    "checklist_items",
    "material_inspection_journal",
    "cable_journal",
    "material_aliases",
)

_NEW_OWNER_TABLES = ("contracts", "piecework", "checklist_items", "material_aliases")
_CHECKLIST_TABLE = "project_checklists"
_JOURNAL_TABLES = ("material_inspection_journal", "cable_journal")

ADD_COLUMNS_SQL = "\n".join(
    [
        *(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner_scope TEXT;\n"
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER;\n"
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INTEGER;"
            for table in _NEW_OWNER_TABLES
        ),
        "ALTER TABLE project_checklists ADD COLUMN IF NOT EXISTS owner_scope TEXT;",
        "ALTER TABLE project_checklists ADD COLUMN IF NOT EXISTS company_id INTEGER;",
        *(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner_scope TEXT;"
            for table in _JOURNAL_TABLES
        ),
    ]
)

DROP_JOURNAL_COMPLETE_SQL = "\n".join(
    f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_quality_owner_complete;"
    for table in _JOURNAL_TABLES
)

def _owner_check(table):
    # Checklists already stored a project link. An unowned row may keep that
    # link and still stay hidden, because it has no company.
    if table == "project_checklists":
        return """
            (owner_scope IS NULL AND company_id IS NULL) OR
            (owner_scope = 'company' AND company_id IS NOT NULL AND project_id IS NULL) OR
            (owner_scope = 'project' AND company_id IS NOT NULL AND project_id IS NOT NULL)
        """
    return """
            (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
            (owner_scope = 'company' AND company_id IS NOT NULL AND project_id IS NULL) OR
            (owner_scope = 'project' AND company_id IS NOT NULL AND project_id IS NOT NULL)
        """


_CONSTRAINTS = []
for _table in TABLES:
    _CONSTRAINTS.append(f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_{_table}_owner') THEN
        ALTER TABLE {_table} ADD CONSTRAINT ck_{_table}_owner CHECK ({_owner_check(_table)});
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
    if not scope and company_id and project_id:
        return {
            "state": "already_owned", "owner_scope": "project",
            "company_id": company_id, "project_id": project_id, "fill_scope": True,
        }
    if not scope and company_id and not project_id:
        return {
            "state": "already_owned", "owner_scope": "company",
            "company_id": company_id, "project_id": None, "fill_scope": True,
        }
    # A project link without a company is not an owner. Checklists already
    # stored that link before this migration.
    if not scope and not company_id:
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
    by_id = {}
    for project in projects or []:
        name = _project_key((project or {}).get("name"))
        company_id = _positive((project or {}).get("company_id"))
        project_id = _positive((project or {}).get("id"))
        if not company_id or not project_id:
            continue
        by_id[project_id] = {"company_id": company_id, "project_id": project_id, "name": name}
        if name is None:
            continue
        grouped.setdefault(name, []).append({"company_id": company_id, "project_id": project_id})
    return grouped, by_id


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


def _owner_from_stored_project(row, name_key, groups, by_id, legacy_company):
    stored = _stored_owner(row)
    if stored:
        return stored
    project_id = _positive((row or {}).get("project_id"))
    project = by_id.get(project_id) if project_id else None
    if not project:
        return _owner_from_project_name((row or {}).get(name_key), groups, legacy_company)
    label = _project_key((row or {}).get(name_key))
    if label is None or label == project.get("name"):
        return _project_owner(project["company_id"], project_id)
    named = _owner_from_project_name(label, groups, None)
    if named.get("state") == "assign" and named["company_id"] == project["company_id"]:
        return _project_owner(project["company_id"], project_id)
    return {"state": "conflict"}


def _owned(decision):
    return bool(decision) and decision.get("state") in ("already_owned", "assign", "inherited")


def _journal_fields(journal, groups):
    """Copy the work journal's stored company when the piecework label cannot."""
    company_id = _positive((journal or {}).get("company_id"))
    if not company_id:
        return None
    label = _project_key((journal or {}).get("project"))
    matches = [item for item in (groups.get(label) or []) if item["company_id"] == company_id] if label else []
    if len(matches) == 1:
        decision = _project_owner(company_id, matches[0]["project_id"])
    else:
        decision = _company_owner(company_id)
    decision["state"] = "inherited"
    return decision


def _piecework_owner(row, groups, legacy_company, journals):
    stored = _stored_owner(row)
    if stored:
        return stored
    named = _owner_from_project_name(row.get("project"), groups, legacy_company)
    journal = journals.get(_positive((row or {}).get("work_journal_id")))
    if not journal:
        return named
    parent = _journal_fields(journal, groups)
    if not parent:
        return named
    if named.get("state") == "assign" and named["company_id"] == parent["company_id"]:
        named["state"] = "inherited"
        return named
    if named.get("state") == "assign" and named["company_id"] != parent["company_id"]:
        return {"state": "conflict"}
    return parent


def plan_backfill(companies, projects, tables):
    """Assign legacy rows to the original company or to one exact project."""
    planned = {}
    counts = {}
    assignments = []
    scope_fills = []

    def remember(table, row_id, decision):
        planned.setdefault(table, {})[_positive(row_id)] = decision
        _bump(counts, table, decision["state"])
        row_number = _positive(row_id)
        if not row_number:
            return
        if decision.get("fill_scope") and decision["state"] == "already_owned":
            scope_fills.append({
                "table": table,
                "id": row_number,
                "owner_scope": decision["owner_scope"],
                "company_id": decision["company_id"],
                "project_id": decision["project_id"],
            })
        elif decision["state"] in ("assign", "inherited"):
            assignments.append({
                "table": table,
                "id": row_number,
                "owner_scope": decision["owner_scope"],
                "company_id": decision["company_id"],
                "project_id": decision["project_id"],
            })

    legacy_company = legacy_company_id(companies, projects)
    groups, by_id = _project_groups(projects)

    for row in tables.get("contracts") or []:
        row = dict(row or {})
        remember("contracts", row.get("id"), _stored_owner(row) or _owner_from_project_name(row.get("project"), groups, legacy_company))

    journals = {
        _positive((row or {}).get("id")): dict(row or {})
        for row in tables.get("work_journal") or []
        if _positive((row or {}).get("id"))
    }
    for row in tables.get("piecework") or []:
        row = dict(row or {})
        remember("piecework", row.get("id"), _piecework_owner(row, groups, legacy_company, journals))

    for row in tables.get("project_checklists") or []:
        row = dict(row or {})
        remember(
            "project_checklists", row.get("id"),
            _owner_from_stored_project(row, "project_name", groups, by_id, legacy_company),
        )

    for row in tables.get("checklist_items") or []:
        row = dict(row or {})
        decision = _stored_owner(row)
        if decision is None:
            parent = planned.get("project_checklists", {}).get(_positive(row.get("checklist_id")))
            if _owned(parent):
                decision = _owned_fields(parent)
            elif legacy_company:
                decision = _company_owner(legacy_company)
            elif parent is not None:
                decision = {"state": "parent_unowned"}
            else:
                decision = {"state": "unknown"}
        remember("checklist_items", row.get("id"), decision)

    for table in _JOURNAL_TABLES:
        for row in tables.get(table) or []:
            row = dict(row or {})
            remember(table, row.get("id"), _owner_from_stored_project(row, "project_name", groups, by_id, legacy_company))

    for row in tables.get("material_aliases") or []:
        row = dict(row or {})
        remember(
            "material_aliases", row.get("id"),
            _stored_owner(row) or _owner_from_project_name(row.get("project_name"), groups, legacy_company),
        )

    for table in TABLES:
        counts.setdefault(table, _empty_counts())
    return {
        "assignments": assignments,
        "scopeFills": scope_fills,
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
    tables = {}
    cur.execute(f"SELECT id, project, {owner_sql} FROM contracts")
    tables["contracts"] = [
        _row_dict(row, ("id", "project", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute(f"SELECT id, project, work_journal_id, {owner_sql} FROM piecework")
    tables["piecework"] = [
        _row_dict(row, ("id", "project", "work_journal_id", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    cur.execute("SELECT id, company_id, project FROM work_journal")
    tables["work_journal"] = [
        _row_dict(row, ("id", "company_id", "project"))
        for row in cur.fetchall()
    ]
    if owner_columns:
        cur.execute(
            "SELECT id, project_name, project_id, owner_scope, company_id FROM project_checklists"
        )
        tables["project_checklists"] = [
            _row_dict(row, ("id", "project_name", "project_id", "owner_scope", "company_id"))
            for row in cur.fetchall()
        ]
    else:
        cur.execute("SELECT id, project_name, project_id, NULL::text, NULL::integer FROM project_checklists")
        tables["project_checklists"] = [
            _row_dict(row, ("id", "project_name", "project_id", "owner_scope", "company_id"))
            for row in cur.fetchall()
        ]
    cur.execute(f"SELECT id, checklist_id, {owner_sql} FROM checklist_items")
    tables["checklist_items"] = [
        _row_dict(row, ("id", "checklist_id", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    for table in _JOURNAL_TABLES:
        if owner_columns:
            cur.execute(f"SELECT id, project_name, owner_scope, company_id, project_id FROM {table}")
        else:
            cur.execute(
                f"SELECT id, project_name, NULL::text, company_id, project_id FROM {table}"
            )
        tables[table] = [
            _row_dict(row, ("id", "project_name", "owner_scope", "company_id", "project_id"))
            for row in cur.fetchall()
        ]
    cur.execute(f"SELECT id, project_name, {owner_sql} FROM material_aliases")
    tables["material_aliases"] = [
        _row_dict(row, ("id", "project_name", "owner_scope", "company_id", "project_id"))
        for row in cur.fetchall()
    ]
    return companies, projects, tables


def apply_backfill(cur, *, write):
    """Read a snapshot and fill missing owners only when `write` is true.

    The caller owns the transaction. Updates touch only rows that still have
    no owner scope and no company. A journal that already stores a company
    only receives the missing scope label.
    """
    companies, projects, tables = load_snapshot(cur, owner_columns=True)
    plan = plan_backfill(companies, projects, tables)
    applied = 0
    if write:
        for item in plan["scopeFills"]:
            if item["table"] not in TABLES or not item["id"]:
                continue
            cur.execute(
                f"UPDATE {item['table']} SET owner_scope=%s "
                "WHERE id=%s AND owner_scope IS NULL AND company_id=%s "
                "AND project_id IS NOT DISTINCT FROM %s",
                (item["owner_scope"], item["id"], item["company_id"], item["project_id"]),
            )
            applied += 1
        for item in plan["assignments"]:
            if item["table"] not in TABLES or not item["id"]:
                continue
            if item["table"] == "project_checklists":
                cur.execute(
                    "UPDATE project_checklists SET owner_scope=%s, company_id=%s, project_id=%s "
                    "WHERE id=%s AND owner_scope IS NULL AND company_id IS NULL "
                    "AND (project_id IS NULL OR project_id=%s)",
                    (item["owner_scope"], item["company_id"], item["project_id"], item["id"], item["project_id"]),
                )
            else:
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
    raise RuntimeError("Cannot reach the database cursor for field record ownership backfill")
