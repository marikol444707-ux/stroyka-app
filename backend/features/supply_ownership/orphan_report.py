"""Read-only downstream-reference report for orphaned core-supply rows."""

import hashlib
import json
from collections import defaultdict

import psycopg2.extras


EXPECTED_SOURCE_COUNT = 25
EXPECTED_SOURCE_SHA256 = "99f5b9b8a3e7d45bbea2042e12dfbadf727447e58996975243f36f5cf0f001e8"
REFERENCE_TABLES = (
    "supplier_offer_events",
    "supplier_invoices",
    "supply_deliveries",
    "supply_claims",
    "supply_history",
    "warehouse_invoices",
    "messenger_outbox",
)


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _source_rows(rows):
    result = []
    for key, table in (
        ("orphan_recipients", "supply_request_recipients"),
        ("orphan_offers", "supplier_offers"),
    ):
        for raw in rows.get(key) or []:
            row = dict(raw or {})
            result.append({
                "table": table,
                "recordId": _positive_int(row.get("id")),
                "companyId": _positive_int(row.get("company_id")),
                "requestId": _positive_int(row.get("request_id")),
                "maxOutboxId": _positive_int(row.get("max_outbox_id")),
            })
    return result


def _source_sha256(source_rows):
    plan = sorted(
        [
            [item["table"], item["recordId"], item["companyId"], item["requestId"]]
            for item in source_rows
        ],
        key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")),
    )
    payload = json.dumps(plan, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reference_matches(source, table, row):
    request_id = _positive_int(row.get("request_id"))
    offer_id = _positive_int(row.get("offer_id"))
    record_id = _positive_int(row.get("id"))
    if request_id and request_id == source["requestId"]:
        return True
    if source["table"] == "supplier_offers" and offer_id == source["recordId"]:
        return True
    return (
        table == "messenger_outbox"
        and source.get("maxOutboxId")
        and record_id == source["maxOutboxId"]
    )


def _references_for_source(source, rows):
    references = []
    for table in REFERENCE_TABLES:
        matching = []
        owner_mismatches = []
        for raw in rows.get(table) or []:
            row = dict(raw or {})
            if not _reference_matches(source, table, row):
                continue
            record_id = _positive_int(row.get("id"))
            if record_id:
                matching.append(record_id)
                row_company_id = _positive_int(row.get("company_id"))
                if row_company_id and row_company_id != source["companyId"]:
                    owner_mismatches.append(record_id)
        if matching:
            references.append({
                "table": table,
                "count": len(set(matching)),
                "recordIds": sorted(set(matching)),
                "ownerMismatchRecordIds": sorted(set(owner_mismatches)),
            })
    return references


def build_report_from_rows(
    rows,
    expected_source_count=None,
    expected_source_sha256=None,
):
    sources = _source_rows(rows)
    source_sha256 = _source_sha256(sources)
    count_matches = expected_source_count is None or len(sources) == expected_source_count
    sha_matches = expected_source_sha256 is None or source_sha256 == expected_source_sha256
    source_set_matches = count_matches and sha_matches

    orphan_rows = []
    reference_links = 0
    owner_mismatch_links = 0
    for source in sources:
        references = _references_for_source(source, rows)
        reference_links += sum(ref["count"] for ref in references)
        owner_mismatch_links += sum(len(ref["ownerMismatchRecordIds"]) for ref in references)
        orphan_rows.append({
            "table": source["table"],
            "recordId": source["recordId"],
            "companyId": source["companyId"],
            "requestId": source["requestId"],
            "classification": (
                "has_downstream_references" if references else "residue_candidate"
            ),
            "references": references,
        })

    with_references = sum(
        item["classification"] == "has_downstream_references" for item in orphan_rows
    )
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "expectedSourceCount": expected_source_count,
        "expectedSourceSha256": expected_source_sha256,
        "sourceCount": len(sources),
        "sourceSha256": source_sha256,
        "sourceSetMatchesExpected": source_set_matches,
        "readyForRemediationPlanning": source_set_matches and owner_mismatch_links == 0,
        "reportConsistent": len(orphan_rows) == len(sources),
        "summary": {
            "orphanRows": len(orphan_rows),
            "residueCandidates": len(orphan_rows) - with_references,
            "withDownstreamReferences": with_references,
            "referenceLinks": reference_links,
            "ownerMismatchLinks": owner_mismatch_links,
        },
        "orphanRows": orphan_rows,
    }


def load_orphan_rows(cur):
    rows = {}
    cur.execute("""
        SELECT child.id, child.company_id, child.request_id, child.max_outbox_id
          FROM supply_request_recipients child
          LEFT JOIN supply_requests parent ON parent.id=child.request_id
         WHERE parent.id IS NULL
         ORDER BY child.id
    """)
    rows["orphan_recipients"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("""
        SELECT child.id, child.company_id, child.request_id
          FROM supplier_offers child
          LEFT JOIN supply_requests parent ON parent.id=child.request_id
         WHERE parent.id IS NULL
         ORDER BY child.id
    """)
    rows["orphan_offers"] = [dict(row or {}) for row in (cur.fetchall() or [])]

    sources = _source_rows(rows)
    request_ids = sorted({item["requestId"] for item in sources if item["requestId"]})
    offer_ids = sorted({
        item["recordId"] for item in sources
        if item["table"] == "supplier_offers" and item["recordId"]
    })
    outbox_ids = sorted({item["maxOutboxId"] for item in sources if item["maxOutboxId"]})
    if not sources:
        for table in REFERENCE_TABLES:
            rows[table] = []
        return rows

    queries = {
        "supplier_offer_events": (
            "SELECT id,offer_id FROM supplier_offer_events WHERE offer_id=ANY(%s) ORDER BY id",
            (offer_ids,),
        ),
        "supplier_invoices": (
            "SELECT id,company_id,request_id,offer_id FROM supplier_invoices "
            "WHERE request_id=ANY(%s) OR offer_id=ANY(%s) ORDER BY id",
            (request_ids, offer_ids),
        ),
        "supply_deliveries": (
            "SELECT id,company_id,request_id,offer_id FROM supply_deliveries "
            "WHERE request_id=ANY(%s) OR offer_id=ANY(%s) ORDER BY id",
            (request_ids, offer_ids),
        ),
        "supply_claims": (
            "SELECT id,request_id,offer_id FROM supply_claims "
            "WHERE request_id=ANY(%s) OR offer_id=ANY(%s) ORDER BY id",
            (request_ids, offer_ids),
        ),
        "supply_history": (
            "SELECT id,company_id,request_id FROM supply_history "
            "WHERE request_id=ANY(%s) ORDER BY id",
            (request_ids,),
        ),
        "warehouse_invoices": (
            "SELECT id,company_id,supply_request_id AS request_id FROM warehouse_invoices "
            "WHERE supply_request_id=ANY(%s) ORDER BY id",
            (request_ids,),
        ),
        "messenger_outbox": (
            "SELECT id,company_id,owner_scope,status,"
            "CASE WHEN entity_type='supply_request' THEN entity_id END AS request_id "
            "FROM messenger_outbox WHERE (entity_type='supply_request' AND entity_id=ANY(%s)) "
            "OR id=ANY(%s) ORDER BY id",
            (request_ids, outbox_ids),
        ),
    }
    for table in REFERENCE_TABLES:
        query, params = queries[table]
        cur.execute(query, params)
        rows[table] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows


def run_orphan_report(
    get_db,
    expected_source_count=None,
    expected_source_sha256=None,
):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_report_from_rows(
                load_orphan_rows(cur),
                expected_source_count=expected_source_count,
                expected_source_sha256=expected_source_sha256,
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
    result = run_orphan_report(
        get_db,
        expected_source_count=EXPECTED_SOURCE_COUNT,
        expected_source_sha256=EXPECTED_SOURCE_SHA256,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["sourceSetMatchesExpected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
