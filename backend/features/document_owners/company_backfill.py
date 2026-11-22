"""Fill a blank document only when one project can own it.

A document that already stores a company is left as it is. A blank project
document or letter is filled only when its name matches exactly one project,
or when the install has a single operating company with exactly one project
and the document names none. A person's name is never read. A shared name,
or a namesake project that still has no company, leaves the row blank.

A document version takes the company already stored on its hidden-work act.
It is not guessed from a project name.
"""

from backend.features.explicit_company.company_backfill import (
    _positive,
    _project_groups,
    _text,
    dbapi_cursor,
    legacy_company_id,
)

DOCUMENT_TABLES = (
    ("project_documents", "project_name"),
    ("project_letters", "project_name"),
)
VERSION_TABLE = "document_versions"


def _sole_legacy_project(projects, legacy_company, unresolved):
    if not legacy_company:
        return None
    matches = []
    for project in projects or []:
        project = dict(project or {})
        name = _text(project.get("name"))
        company_id = _positive(project.get("company_id"))
        project_id = _positive(project.get("id"))
        if not name or not project_id or company_id != legacy_company or name in unresolved:
            continue
        matches.append({"company_id": company_id, "project_id": project_id})
    if len(matches) != 1:
        return None
    return matches[0]


def _named_project(name, groups, unresolved):
    key = _text(name)
    if not key or key in unresolved:
        return None
    matches = groups.get(key) or []
    if len(matches) != 1:
        return None
    return matches[0]


def plan_document_owners(companies, projects, documents, versions):
    groups, unresolved = _project_groups(projects)
    legacy_company = legacy_company_id(companies, projects)
    sole_project = _sole_legacy_project(projects, legacy_company, unresolved)
    assignments = []
    counts = {}

    def remember(table, row_id, decision):
        state = decision["state"]
        bucket = counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0,
        })
        bucket["total"] += 1
        bucket[{
            "already_owned": "alreadyOwned",
            "assign": "assign",
            "inherited": "inherited",
            "ambiguous": "ambiguous",
            "unknown": "unknown",
        }[state]] += 1
        if state in ("assign", "inherited") and _positive(row_id):
            item = {
                "table": table,
                "id": _positive(row_id),
                "company_id": decision["company_id"],
                "state": state,
            }
            if decision.get("project_id"):
                item["project_id"] = decision["project_id"]
            assignments.append(item)

    for table, column in DOCUMENT_TABLES:
        for row in (documents or {}).get(table) or []:
            row = dict(row or {})
            company_id = _positive(row.get("company_id"))
            project_id = _positive(row.get("project_id"))
            if company_id or project_id:
                remember(table, row.get("id"), {
                    "state": "already_owned",
                    "company_id": company_id,
                })
                continue
            key = _text(row.get(column))
            if key and key in unresolved:
                decision = {"state": "ambiguous"}
            elif key and key in groups and len(groups[key]) != 1:
                decision = {"state": "ambiguous"}
            else:
                chosen = _named_project(key, groups, unresolved) if key else sole_project
                if chosen:
                    decision = {
                        "state": "assign",
                        "company_id": chosen["company_id"],
                        "project_id": chosen["project_id"],
                    }
                elif key and key in groups:
                    decision = {"state": "ambiguous"}
                else:
                    decision = {"state": "unknown"}
            remember(table, row.get("id"), decision)

    for row in versions or []:
        row = dict(row or {})
        company_id = _positive(row.get("company_id"))
        parent_company = _positive(row.get("parent_company_id"))
        if company_id:
            decision = {"state": "already_owned", "company_id": company_id}
        elif parent_company:
            decision = {"state": "inherited", "company_id": parent_company}
        else:
            decision = {"state": "unknown"}
        remember(VERSION_TABLE, row.get("id"), decision)

    for table, _column in DOCUMENT_TABLES:
        counts.setdefault(table, {
            "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
            "ambiguous": 0, "unknown": 0,
        })
    counts.setdefault(VERSION_TABLE, {
        "total": 0, "alreadyOwned": 0, "assign": 0, "inherited": 0,
        "ambiguous": 0, "unknown": 0,
    })
    return {
        "assignments": assignments,
        "counts": counts,
        "legacyCompanyId": legacy_company,
    }


def _row_dict(row, columns):
    if isinstance(row, dict):
        return {column: row.get(column) for column in columns}
    return dict(zip(columns, row))


def _present(cur, names):
    cur.execute(
        """SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_name = ANY(%s)""",
        (list(names),),
    )
    found = set()
    for row in cur.fetchall() or []:
        found.add(row[0] if not isinstance(row, dict) else row.get("table_name"))
    return found


ADD_COLUMNS_SQL = """
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS company_id INTEGER;
"""


def load_snapshot(cur):
    names = [table for table, _column in DOCUMENT_TABLES] + [VERSION_TABLE, "hidden_works_acts"]
    present = _present(cur, names)
    cur.execute("SELECT id FROM companies ORDER BY id")
    companies = [_row_dict(row, ("id",)) for row in cur.fetchall() or []]
    cur.execute("SELECT id, company_id, name FROM projects ORDER BY id")
    projects = [
        _row_dict(row, ("id", "company_id", "name")) for row in cur.fetchall() or []
    ]
    documents = {}
    for table, column in DOCUMENT_TABLES:
        if table not in present:
            documents[table] = []
            continue
        cur.execute(
            f"SELECT id, company_id, project_id, {column} FROM {table} ORDER BY id"
        )
        documents[table] = [
            _row_dict(row, ("id", "company_id", "project_id", column))
            for row in cur.fetchall() or []
        ]
    versions = []
    if VERSION_TABLE in present:
        parent = (
            "LEFT JOIN hidden_works_acts h ON v.document_type='hidden_works_act' AND h.id=v.document_id"
            if "hidden_works_acts" in present else ""
        )
        parent_company = "h.company_id" if parent else "NULL"
        cur.execute(
            f"""SELECT v.id, v.company_id, v.document_type, v.document_id, {parent_company}
                  FROM document_versions v {parent} ORDER BY v.id"""
        )
        versions = [
            _row_dict(row, ("id", "company_id", "document_type", "document_id", "parent_company_id"))
            for row in cur.fetchall() or []
        ]
    return companies, projects, documents, versions, present


def apply_document_owners(cur, *, write):
    companies, projects, documents, versions, present = load_snapshot(cur)
    plan = plan_document_owners(companies, projects, documents, versions)
    applied = 0
    if write:
        for item in plan["assignments"]:
            if item["table"] not in present:
                continue
            if item["table"] == VERSION_TABLE:
                cur.execute(
                    "UPDATE document_versions SET company_id=%s WHERE id=%s AND company_id IS NULL",
                    (item["company_id"], item["id"]),
                )
            else:
                cur.execute(
                    f"UPDATE {item['table']} SET company_id=%s, project_id=%s "
                    "WHERE id=%s AND company_id IS NULL AND project_id IS NULL",
                    (item["company_id"], item["project_id"], item["id"]),
                )
            applied += 1
    plan["applied"] = applied
    plan["write"] = bool(write)
    plan["presentTables"] = sorted(present)
    return plan


__all__ = [
    "ADD_COLUMNS_SQL",
    "apply_document_owners",
    "dbapi_cursor",
    "plan_document_owners",
]
