"""Give a blank company only when one company can own the old row.

A row that already stores a company is left as it is. A blank row is filled
when the database has one operating company, or when its project name points
at exactly one project. A person's name is never read. When two companies
already have projects and the name does not pick one of them, the row stays
blank and hidden.
"""

NAMED_TABLES = (
    ("supply_requests", "project"),
    ("supplier_invoices", "project_name"),
    ("estimates", "project_name"),
    ("materials", "project"),
    ("work_journal", "project"),
    ("interim_acts", "project"),
    ("hidden_works_acts", "project_name"),
    ("supply_deliveries", "project"),
    ("supply_history", "project"),
    ("warehouse_invoices", "project"),
    ("warehouse_history", "project"),
    ("brigade_contracts", "project_name"),
)
PLAIN_TABLES = (
    "projects",
    "users",
    "staff",
    "warehouse_main",
    "company_requisites",
)
PARENT_TABLE = "supplier_offers"
MOVEMENT_TABLE = "warehouse_movements"
TABLES = tuple(table for table, _column in NAMED_TABLES) + PLAIN_TABLES + (
    PARENT_TABLE,
    MOVEMENT_TABLE,
)

_MAIN_WAREHOUSE = "Основной склад"
_UNBOUND_USER_ROLES = frozenset({"поставщик"})


def _positive(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def legacy_company_id(companies, projects):
    """The one company that can receive old rows which name no other company."""
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
    unresolved = set()
    for project in projects or []:
        name = _text((project or {}).get("name"))
        if not name:
            continue
        company_id = _positive((project or {}).get("company_id"))
        project_id = _positive((project or {}).get("id"))
        if not company_id or not project_id:
            unresolved.add(name)
            continue
        grouped.setdefault(name, []).append({
            "company_id": company_id,
            "project_id": project_id,
        })
    return grouped, unresolved


def unique_project_company_id(rows):
    """Return a company only when every named project belongs to that one company."""
    company_ids = []
    saw_unowned = False
    for row in rows or []:
        if isinstance(row, dict):
            company_id = _positive(row.get("company_id"))
        elif row:
            company_id = _positive(row[0])
        else:
            company_id = None
        if not company_id:
            saw_unowned = True
            continue
        if company_id not in company_ids:
            company_ids.append(company_id)
    if saw_unowned or len(company_ids) != 1:
        return None
    return company_ids[0]


def _kept(company_id):
    return {"state": "already_owned", "company_id": company_id}


def _assigned(company_id):
    return {"state": "assign", "company_id": company_id}


def _from_project_name(name, groups, legacy_company, unresolved):
    key = _text(name)
    if key is None or key == _MAIN_WAREHOUSE:
        if legacy_company:
            return _assigned(legacy_company)
        return {"state": "unknown"}
    if key in unresolved:
        return {"state": "ambiguous"}
    matches = groups.get(key) or []
    companies = {item["company_id"] for item in matches}
    if len(companies) == 1:
        return _assigned(next(iter(companies)))
    if not matches and legacy_company:
        return _assigned(legacy_company)
    if len(companies) > 1:
        return {"state": "ambiguous"}
    return {"state": "unknown"}


def _from_locations(from_location, to_location, groups, legacy_company, unresolved):
    decisions = []
    for location in (from_location, to_location):
        key = _text(location)
        if key is None or key == _MAIN_WAREHOUSE:
            continue
        decisions.append(_from_project_name(key, groups, None, unresolved))
    if any(item.get("state") == "ambiguous" for item in decisions):
        return {"state": "ambiguous"}
    companies = {item["company_id"] for item in decisions if item.get("state") == "assign"}
    if len(companies) == 1:
        return _assigned(next(iter(companies)))
    if len(companies) > 1:
        return {"state": "ambiguous"}
    if legacy_company:
        return _assigned(legacy_company)
    return {"state": "unknown"}


def plan_backfill(companies, projects, tables):
    groups, unresolved = _project_groups(projects)
    legacy_company = legacy_company_id(companies, projects)
    requests = {
        _positive((row or {}).get("id")): _positive((row or {}).get("company_id"))
        for row in (tables or {}).get("supply_requests") or []
    }
    assignments = []
    counts = {}

    def remember(table, row_id, decision):
        state = decision.get("state")
        bucket = counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0,
        })
        bucket["total"] += 1
        key = {
            "already_owned": "alreadyOwned",
            "assign": "assign",
            "inherited": "inherited",
            "ambiguous": "ambiguous",
            "unknown": "unknown",
        }[state]
        bucket[key] += 1
        if state in ("assign", "inherited") and _positive(row_id):
            assignments.append({
                "table": table,
                "id": _positive(row_id),
                "company_id": decision["company_id"],
                "state": state,
            })

    for table, column in NAMED_TABLES:
        for row in (tables or {}).get(table) or []:
            row = dict(row or {})
            company_id = _positive(row.get("company_id"))
            decision = _kept(company_id) if company_id else _from_project_name(
                row.get(column), groups, legacy_company, unresolved,
            )
            remember(table, row.get("id"), decision)

    for table in PLAIN_TABLES:
        for row in (tables or {}).get(table) or []:
            row = dict(row or {})
            company_id = _positive(row.get("company_id"))
            role = str(row.get("role") or "").strip()
            if company_id:
                decision = _kept(company_id)
            elif table == "users" and role in _UNBOUND_USER_ROLES:
                decision = {"state": "unknown"}
            elif legacy_company:
                decision = _assigned(legacy_company)
            else:
                decision = {"state": "unknown"}
            remember(table, row.get("id"), decision)

    for row in (tables or {}).get(PARENT_TABLE) or []:
        row = dict(row or {})
        company_id = _positive(row.get("company_id"))
        if company_id:
            decision = _kept(company_id)
        else:
            parent_company = requests.get(_positive(row.get("request_id")))
            if parent_company:
                decision = {"state": "inherited", "company_id": parent_company}
            elif legacy_company:
                decision = _assigned(legacy_company)
            else:
                decision = {"state": "unknown"}
        remember(PARENT_TABLE, row.get("id"), decision)

    for row in (tables or {}).get(MOVEMENT_TABLE) or []:
        row = dict(row or {})
        company_id = _positive(row.get("company_id"))
        decision = _kept(company_id) if company_id else _from_locations(
            row.get("from_location"), row.get("to_location"), groups, legacy_company, unresolved,
        )
        remember(MOVEMENT_TABLE, row.get("id"), decision)

    for table in TABLES:
        counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0,
        })
    return {
        "assignments": assignments,
        "counts": counts,
        "legacyCompanyId": legacy_company,
        "ambiguousNames": sorted(
            name for name, matches in groups.items()
            if len({item["company_id"] for item in matches}) > 1
        ),
    }


def _row_dict(row, columns):
    if isinstance(row, dict):
        return {column: row.get(column) for column in columns}
    return dict(zip(columns, row))


def _present_tables(cur, names):
    cur.execute(
        """SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_name = ANY(%s)""",
        (list(names),),
    )
    found = set()
    for row in cur.fetchall() or []:
        found.add(row[0] if not isinstance(row, dict) else row.get("table_name"))
    cur.execute(
        """SELECT table_name FROM information_schema.columns
            WHERE table_schema='public' AND column_name='company_id'
              AND table_name = ANY(%s)""",
        (list(names),),
    )
    owned = set()
    for row in cur.fetchall() or []:
        owned.add(row[0] if not isinstance(row, dict) else row.get("table_name"))
    return found & owned


def load_snapshot(cur):
    present = _present_tables(cur, TABLES)
    cur.execute("SELECT id FROM companies ORDER BY id")
    companies = [_row_dict(row, ("id",)) for row in cur.fetchall() or []]
    cur.execute("SELECT id, company_id, name FROM projects ORDER BY id")
    projects = [
        _row_dict(row, ("id", "company_id", "name")) for row in cur.fetchall() or []
    ]
    tables = {}
    for table, column in NAMED_TABLES:
        if table not in present:
            tables[table] = []
            continue
        cur.execute(f"SELECT id, company_id, {column} FROM {table} ORDER BY id")
        tables[table] = [
            _row_dict(row, ("id", "company_id", column)) for row in cur.fetchall() or []
        ]
    for table in PLAIN_TABLES:
        if table not in present:
            tables[table] = []
            continue
        if table == "users":
            cur.execute("SELECT id, company_id, role FROM users ORDER BY id")
            tables[table] = [
                _row_dict(row, ("id", "company_id", "role")) for row in cur.fetchall() or []
            ]
            continue
        cur.execute(f"SELECT id, company_id FROM {table} ORDER BY id")
        tables[table] = [_row_dict(row, ("id", "company_id")) for row in cur.fetchall() or []]
    if PARENT_TABLE in present:
        cur.execute("SELECT id, company_id, request_id FROM supplier_offers ORDER BY id")
        tables[PARENT_TABLE] = [
            _row_dict(row, ("id", "company_id", "request_id")) for row in cur.fetchall() or []
        ]
    else:
        tables[PARENT_TABLE] = []
    if MOVEMENT_TABLE in present:
        cur.execute(
            "SELECT id, company_id, from_location, to_location FROM warehouse_movements ORDER BY id"
        )
        tables[MOVEMENT_TABLE] = [
            _row_dict(row, ("id", "company_id", "from_location", "to_location"))
            for row in cur.fetchall() or []
        ]
    else:
        tables[MOVEMENT_TABLE] = []
    return companies, projects, tables, present


def apply_backfill(cur, *, write):
    companies, projects, tables, present = load_snapshot(cur)
    plan = plan_backfill(companies, projects, tables)
    applied = 0
    if write:
        for item in plan["assignments"]:
            if item["table"] not in present:
                continue
            cur.execute(
                f"UPDATE {item['table']} SET company_id=%s WHERE id=%s AND company_id IS NULL",
                (item["company_id"], item["id"]),
            )
            applied += 1
    plan["applied"] = applied
    plan["write"] = bool(write)
    plan["presentTables"] = sorted(present)
    return plan


def drop_default_sql():
    names = ", ".join("'" + table + "'" for table in TABLES)
    return f"""
DO $$
DECLARE target text;
BEGIN
  FOREACH target IN ARRAY ARRAY[{names}]
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
       WHERE table_schema='public' AND table_name=target AND column_name='company_id'
    ) THEN
      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN company_id DROP DEFAULT', target);
    END IF;
  END LOOP;
END $$;
"""


DROP_DEFAULTS_SQL = drop_default_sql()


def dbapi_cursor(bind):
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
    raise RuntimeError("Alembic connection has no DB-API cursor")
