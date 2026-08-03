"""Read-only audit for legacy tenant ownership fallback candidates."""

import json
from collections import Counter

import psycopg2.extras


TARGETS = (
    {
        "resource": "projects",
        "query": """SELECT p.id AS record_id,
                           p.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           NULL::INT AS parent_company_id
                      FROM projects p
                      LEFT JOIN companies company ON company.id=p.company_id
                     ORDER BY p.id""",
    },
    {
        "resource": "staff",
        "query": """SELECT s.id AS record_id,
                           s.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           NULL::INT AS parent_company_id
                      FROM staff s
                      LEFT JOIN companies company ON company.id=s.company_id
                     ORDER BY s.id""",
    },
    {
        "resource": "estimates",
        "query": """SELECT e.id AS record_id,
                           e.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           project.company_id AS parent_company_id
                      FROM estimates e
                      LEFT JOIN companies company ON company.id=e.company_id
                      LEFT JOIN projects project ON project.id=e.project_id
                     ORDER BY e.id""",
    },
    {
        "resource": "brigade_contracts",
        "query": """SELECT contract.id AS record_id,
                           contract.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           project.company_id AS parent_company_id
                      FROM brigade_contracts contract
                      LEFT JOIN companies company ON company.id=contract.company_id
                      LEFT JOIN projects project ON project.id=contract.project_id
                     ORDER BY contract.id""",
    },
    {
        "resource": "interim_acts",
        "query": """SELECT act.id AS record_id,
                           act.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           NULL::INT AS parent_company_id
                      FROM interim_acts act
                      LEFT JOIN companies company ON company.id=act.company_id
                     ORDER BY act.id""",
    },
    {
        "resource": "hidden_works_acts",
        "query": """SELECT act.id AS record_id,
                           act.company_id,
                           (company.id IS NOT NULL) AS company_found,
                           estimate.company_id AS parent_company_id
                      FROM hidden_works_acts act
                      LEFT JOIN companies company ON company.id=act.company_id
                      LEFT JOIN estimates estimate ON estimate.id=act.estimate_id
                     ORDER BY act.id""",
    },
)


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def classify_record(row):
    """Classify one row without examining business payload fields."""
    item = dict(row or {})
    record_id = _positive_int(item.get("record_id"))
    company_id = _positive_int(item.get("company_id"))
    parent_company_id = _positive_int(item.get("parent_company_id"))
    company_found = bool(item.get("company_found"))

    if not record_id:
        return {"recordId": None, "status": "unresolved", "reason": "record_id_missing"}
    if company_id and not company_found:
        status, reason, owner_id = "unresolved", "company_not_found", None
    elif company_id and parent_company_id and company_id != parent_company_id:
        status, reason, owner_id = "unresolved", "parent_company_mismatch", None
    elif company_id:
        status, reason, owner_id = "verified", "stored_company", company_id
    elif parent_company_id:
        status, reason, owner_id = "fallback", "verified_parent", parent_company_id
    else:
        status, reason, owner_id = "unresolved", "owner_missing", None

    return {
        "recordId": record_id,
        "status": status,
        "reason": reason,
        "companyId": owner_id,
        "storedCompanyId": company_id,
        "parentCompanyId": parent_company_id,
    }


def build_report(rows_by_resource):
    by_table = {}
    needs_review = []
    fallback_preview = []
    totals = Counter()

    for target in TARGETS:
        resource = target["resource"]
        records = [classify_record(row) for row in rows_by_resource.get(resource, [])]
        counts = Counter(record["status"] for record in records)
        totals.update(counts)
        for record in records:
            enriched = {"table": resource, **record}
            if record["status"] == "unresolved":
                needs_review.append(enriched)
            elif record["status"] == "fallback":
                fallback_preview.append(enriched)
        by_table[resource] = {
            "totalRows": len(records),
            "verified": counts["verified"],
            "fallback": counts["fallback"],
            "unresolved": counts["unresolved"],
        }

    total_rows = sum(item["totalRows"] for item in by_table.values())
    report_consistent = total_rows == totals["verified"] + totals["fallback"] + totals["unresolved"]
    return {
        "ok": True,
        "dryRun": True,
        "tables": [target["resource"] for target in TARGETS],
        "writesAttempted": 0,
        "reportConsistent": report_consistent,
        "readyForStrictRuntime": report_consistent and not totals["fallback"] and not totals["unresolved"],
        "summary": {
            "totalRows": total_rows,
            "verified": totals["verified"],
            "fallback": totals["fallback"],
            "unresolved": totals["unresolved"],
        },
        "byTable": by_table,
        "fallbackPreview": fallback_preview,
        "needsReview": needs_review,
        "previewTruncated": False,
        "reviewListTruncated": False,
    }


def run_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows_by_resource = {}
            for target in TARGETS:
                cur.execute(target["query"])
                rows_by_resource[target["resource"]] = cur.fetchall() or []
            result = build_report(rows_by_resource)
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db

    print(json.dumps(run_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
