"""Read-only plan for registering legacy ``/uploads`` references.

The plan never returns file paths.  It proves one tenant owner for every
unregistered URL and stops on missing, ambiguous, or conflicting evidence.
"""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras
from psycopg2 import sql

from .public_exposure_report import extract_local_upload_urls, _normalize_local_upload_url


PREVIEW_LIMIT = 100
VERIFIED_OWNER_SOURCES = {"expenses.photo_url", "own_expenses.photo_url"}

# Static metadata only.  No database or user value can become an identifier.
SOURCE_SPECS = (
    ("expenses", "photo_url", "project"),
    ("interim_acts", "photo_urls", "project"),
    ("own_expenses", "photo_url", "project_name"),
    ("room_works", "photo_url", "project"),
    ("supplier_invoices", "photo_url", "project_name"),
    ("warehouse_invoices", "photo_url", "project"),
    ("warehouse_invoices", "photo_urls", "project"),
    ("work_journal", "photo_url", "project"),
)


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _url_sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _owner(company_id, project_id=None):
    return {
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
    }


def _project_indexes(projects):
    by_id = {}
    by_name = defaultdict(list)
    for raw in projects or []:
        row = dict(raw or {})
        project_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        name = str(row.get("name") or "").strip()
        if not project_id or not company_id:
            continue
        item = {"id": project_id, "companyId": company_id, "name": name}
        by_id[project_id] = item
        if name:
            by_name[name].append(item)
    return by_id, by_name


def _classify_record(record, projects_by_id, projects_by_name, company_ids):
    item = dict(record or {})
    source = str(item.get("source") or "")
    if source in VERIFIED_OWNER_SOURCES and item.get("ownershipVerified") is not True:
        return None, "unresolved", "source_owner_not_verified"

    company_id = _positive_int(item.get("companyId"))
    project_id = _positive_int(item.get("projectId"))
    project_name = str(item.get("projectName") or "").strip()

    if project_id:
        project = projects_by_id.get(project_id)
        if not project:
            return None, "unresolved", "project_not_found"
        if company_id and company_id != project["companyId"]:
            return None, "conflicting", "project_company_mismatch"
        if project_name and project_name != project["name"]:
            return None, "conflicting", "project_name_mismatch"
        if project["companyId"] not in company_ids:
            return None, "unresolved", "company_not_found"
        return _owner(project["companyId"], project_id), "ready", "verified_project_id"

    if project_name:
        candidates = list(projects_by_name.get(project_name, []))
        if company_id:
            candidates = [row for row in candidates if row["companyId"] == company_id]
        if not candidates:
            return None, "unresolved", "project_not_found"
        if len(candidates) > 1:
            return None, "ambiguous", "project_name_ambiguous"
        project = candidates[0]
        if project["companyId"] not in company_ids:
            return None, "unresolved", "company_not_found"
        return _owner(project["companyId"], project["id"]), "ready", "verified_project_name"

    if company_id:
        if company_id not in company_ids:
            return None, "unresolved", "company_not_found"
        if len(company_ids) != 1:
            return None, "ambiguous", "company_scope_not_provable"
        return _owner(company_id), "ready", "verified_company_id"
    return None, "unresolved", "company_owner_missing"


def _review_priority(status):
    return {"conflicting": 0, "ambiguous": 1, "unresolved": 2}.get(status, 3)


def build_legacy_registration_plan(records, projects, registered_urls, company_ids):
    """Build a privacy-safe, deterministic registration plan."""
    projects_by_id, projects_by_name = _project_indexes(projects)
    company_ids = set(company_ids or set())
    registered = {
        normalized
        for value in (registered_urls or [])
        for normalized in [_normalize_local_upload_url(value)]
        if normalized
    }

    references = defaultdict(list)
    source_reference_counts = Counter()
    source_urls = defaultdict(set)
    for raw in records or []:
        record = dict(raw or {})
        source = str(record.get("source") or "unknown")
        owner, status, reason = _classify_record(
            record, projects_by_id, projects_by_name, company_ids
        )
        for url in extract_local_upload_urls(record.get("value")):
            references[url].append({
                "source": source,
                "recordId": _positive_int(record.get("recordId")),
                "owner": owner,
                "status": status,
                "reason": reason,
            })
            source_reference_counts[source] += 1
            source_urls[source].add(url)

    ready = []
    review = []
    already_registered = set(references) & registered
    for url in sorted(set(references) - registered, key=_url_sha256):
        evidence = references[url]
        invalid = [row for row in evidence if row["status"] != "ready"]
        owners = {
            (row["owner"]["companyId"], row["owner"]["projectId"])
            for row in evidence
            if row.get("owner")
        }
        sources = sorted({row["source"] for row in evidence})
        record_ids = sorted({row["recordId"] for row in evidence if row["recordId"]})
        url_hash = _url_sha256(url)

        if invalid:
            selected = sorted(invalid, key=lambda row: _review_priority(row["status"]))[0]
            review.append({
                "urlSha256": url_hash,
                "status": selected["status"],
                "reason": selected["reason"],
                "sources": sources,
                "recordIds": record_ids,
            })
            continue
        if len(owners) != 1:
            review.append({
                "urlSha256": url_hash,
                "status": "conflicting",
                "reason": "owner_conflict",
                "sources": sources,
                "recordIds": record_ids,
            })
            continue

        company_id, project_id = next(iter(owners))
        ready.append({
            "urlSha256": url_hash,
            "companyId": company_id,
            "projectId": project_id,
            "sources": sources,
            "recordIds": record_ids,
        })

    review_counts = Counter(item["status"] for item in review)
    by_source = []
    for source in sorted(source_urls):
        table, column = source.split(".", 1)
        by_source.append({
            "table": table,
            "column": column,
            "referenceCount": source_reference_counts[source],
            "uniqueUrlCount": len(source_urls[source]),
        })

    plan_payload = {
        "ready": ready,
        "review": review,
        "registered": sorted(_url_sha256(url) for url in already_registered),
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(
            plan_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    blockers = sorted({item["reason"] for item in review})
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForApply": not review,
        "summary": {
            "referenceCount": sum(len(items) for items in references.values()),
            "referencedUniqueUrls": len(references),
            "alreadyRegisteredUniqueUrls": len(already_registered),
            "unregisteredUniqueUrls": len(set(references) - registered),
            "readyRegistrations": len(ready),
            "needsReview": len(review),
            "ambiguous": review_counts["ambiguous"],
            "unresolved": review_counts["unresolved"],
            "conflicting": review_counts["conflicting"],
        },
        "bySource": by_source,
        "blockers": blockers,
        "registrationsPreview": ready[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "registrationListTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }


def _available_columns(cur):
    tables = sorted({spec[0] for spec in SOURCE_SPECS})
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name=ANY(%s)
            ORDER BY table_name,column_name""",
        (tables,),
    )
    result = defaultdict(set)
    for raw in cur.fetchall() or []:
        row = dict(raw or {})
        result[str(row.get("table_name") or "")].add(
            str(row.get("column_name") or "")
        )
    return result


def _column_expression(column, available, alias):
    if column and column in available:
        return sql.SQL("{column} AS {alias}").format(
            column=sql.Identifier(column), alias=sql.Identifier(alias)
        )
    return sql.SQL("NULL AS {alias}").format(alias=sql.Identifier(alias))


def load_legacy_registration_rows(cur):
    """Load the eight known legacy sources and their owner evidence."""
    available_by_table = _available_columns(cur)
    cur.execute("SELECT id,company_id,name FROM projects ORDER BY id")
    projects = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id FROM companies ORDER BY id")
    company_ids = {
        company_id
        for raw in (cur.fetchall() or [])
        for company_id in [_positive_int((raw or {}).get("id"))]
        if company_id
    }
    cur.execute(
        "SELECT file_url FROM file_ownership WHERE file_url LIKE %s ORDER BY file_url",
        ("/uploads/%",),
    )
    registered_urls = [str((row or {}).get("file_url") or "") for row in cur.fetchall() or []]

    records = []
    for table, column, project_name_column in SOURCE_SPECS:
        available = available_by_table.get(table, set())
        if "id" not in available or column not in available:
            continue
        query = sql.SQL(
            "SELECT {record_id},{value},{company_id},{project_id},"
            "{project_name},{ownership_verified} FROM {table} "
            "WHERE {filter_column}::text LIKE %s ORDER BY {order_column}"
        ).format(
            record_id=_column_expression("id", available, "record_id"),
            value=_column_expression(column, available, "value"),
            company_id=_column_expression("company_id", available, "company_id"),
            project_id=_column_expression("project_id", available, "project_id"),
            project_name=_column_expression(
                project_name_column, available, "project_name"
            ),
            ownership_verified=_column_expression(
                "company_scope_verified", available, "ownership_verified"
            ),
            table=sql.Identifier("public", table),
            filter_column=sql.Identifier(column),
            order_column=sql.Identifier("id"),
        )
        cur.execute(query, ("%/uploads/%",))
        source = table + "." + column
        for raw in cur.fetchall() or []:
            row = dict(raw or {})
            records.append({
                "source": source,
                "recordId": row.get("record_id"),
                "value": row.get("value"),
                "companyId": row.get("company_id"),
                "projectId": row.get("project_id"),
                "projectName": row.get("project_name"),
                "ownershipVerified": row.get("ownership_verified"),
            })
    return records, projects, registered_urls, company_ids


def run_legacy_registration_plan(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            records, projects, registered_urls, company_ids = load_legacy_registration_rows(cur)
            result = build_legacy_registration_plan(
                records, projects, registered_urls, company_ids
            )
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
    print(json.dumps(run_legacy_registration_plan(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
