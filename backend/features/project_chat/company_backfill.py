"""Give a chat row a company only when its project name picks one project.

A row that already stores a company keeps it. A shared name, or a namesake
project that still has no company, stays blank and hidden. A person's name
is never read.
"""

from backend.features.explicit_company.company_backfill import (
    _positive,
    _project_groups,
    _text,
)


def plan_chat_owners(projects, messages):
    groups, unresolved = _project_groups(projects)
    assignments = []
    unknown = 0
    kept = 0
    for row in messages or []:
        row = dict(row or {})
        if _positive(row.get("company_id")):
            kept += 1
            continue
        name = _text(row.get("project_name"))
        matches = [] if not name or name in unresolved else groups.get(name) or []
        if len(matches) != 1 or not _positive(row.get("id")):
            unknown += 1
            continue
        assignments.append({
            "id": _positive(row.get("id")),
            "company_id": matches[0]["company_id"],
        })
    return {"assignments": assignments, "alreadyOwned": kept, "unknown": unknown}
