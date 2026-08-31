"""Privacy-safe dry-run for legacy references whose files are absent.

The plan never changes source records or the ownership registry.  It only
classifies exact, owner-verified references and reports hashes instead of file
paths so the evidence can be retained without disclosing document names.
"""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras

from .legacy_reference_cutover import (
    SOURCE_BY_NAME,
    _storage_context,
    load_legacy_reference_cutover_rows,
)
from .legacy_registration_plan import (
    _classify_record,
    _positive_int,
    _project_indexes,
)
from .public_exposure_report import (
    _normalize_local_upload_url,
    extract_local_upload_urls,
)


PREVIEW_LIMIT = 100
LOCAL_MISSING_REASON = "local_file_unavailable"


def _sha256(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _registration_index(rows, referenced_urls):
    indexed = defaultdict(list)
    invalid = 0
    for raw in rows or []:
        row = dict(raw or {})
        url = _normalize_local_upload_url(row.get("file_url"))
        if url not in referenced_urls:
            continue
        file_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        if not file_id or not company_id or not _storage_context(row, url):
            invalid += 1
            continue
        indexed[url].append({
            "id": file_id,
            "companyId": company_id,
            "projectId": _positive_int(row.get("project_id")),
            "storageReady": row.get("storageReady") is True,
            "storageReason": str(row.get("storageReason") or ""),
        })
    return indexed, invalid


def build_legacy_missing_file_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    scan=None,
):
    records = [dict(row or {}) for row in (records or [])]
    referenced_urls = {
        url
        for record in records
        for url in extract_local_upload_urls(record.get("value"))
    }
    registrations, invalid_registry_rows = _registration_index(
        ownership_rows,
        referenced_urls,
    )
    projects_by_id, projects_by_name = _project_indexes(projects)
    company_ids = set(company_ids or set())
    source_counts = defaultdict(Counter)
    updates = []
    review = []
    missing_file_ids = set()
    missing_references = 0
    available_references = 0
    unresolved_references = 0
    conflicting_references = 0

    for record in records:
        source = str(record.get("source") or "")
        record_id = _positive_int(record.get("recordId"))
        value = str(record.get("value") or "")
        urls = extract_local_upload_urls(value)
        if not urls:
            continue
        source_counts[source]["references"] += len(urls)
        owner, owner_status, owner_reason = _classify_record(
            record,
            projects_by_id,
            projects_by_name,
            company_ids,
        )
        cell_missing_ids = []
        cell_has_issue = False

        for url in urls:
            reason = None
            status = "unresolved"
            matches = registrations.get(url, [])
            if source not in SOURCE_BY_NAME or not record_id:
                reason = "source_record_invalid"
            elif owner_status != "ready":
                reason = owner_reason
                status = owner_status
            elif not matches:
                reason = "file_registration_missing"
            elif len(matches) != 1:
                reason = "file_registration_ambiguous"
                status = "conflicting"
            else:
                registration = matches[0]
                if (
                    registration["companyId"] != owner["companyId"]
                    or registration["projectId"] != owner["projectId"]
                ):
                    reason = "reference_owner_mismatch"
                    status = "conflicting"
                elif registration["storageReady"]:
                    available_references += 1
                    source_counts[source]["available"] += 1
                elif registration["storageReason"] == LOCAL_MISSING_REASON:
                    file_id = registration["id"]
                    cell_missing_ids.append(file_id)
                    missing_file_ids.add(file_id)
                    missing_references += 1
                    source_counts[source]["missing"] += 1
                else:
                    reason = "file_storage_not_verified"

            if reason:
                cell_has_issue = True
                if status == "conflicting":
                    conflicting_references += 1
                else:
                    unresolved_references += 1
                review.append({
                    "source": source,
                    "recordId": record_id,
                    "urlSha256": _sha256(url),
                    "status": status,
                    "reason": reason,
                })

        if cell_missing_ids and not cell_has_issue:
            updates.append({
                "source": source,
                "recordId": record_id,
                "missingReferenceCount": len(cell_missing_ids),
                "fileIds": sorted(cell_missing_ids),
                "oldValueSha256": _sha256(value),
            })
            source_counts[source]["cells"] += 1

    scan = dict(scan or {})
    truncated_sources = sorted(set(scan.get("truncatedSources") or []))
    blockers = {item["reason"] for item in review}
    if invalid_registry_rows:
        blockers.add("invalid_file_registration")
    if truncated_sources:
        blockers.add("reference_scan_truncated")
    blockers = sorted(blockers)
    state = "review_required" if blockers else (
        "ready" if missing_references else "clear"
    )
    plan_payload = {
        "updates": updates,
        "review": review,
        "missingFileIds": sorted(missing_file_ids),
        "invalidRegistryRows": invalid_registry_rows,
        "truncatedSources": truncated_sources,
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(
            plan_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    by_source = [
        {
            "source": source,
            "referenceCount": counts["references"],
            "missingReferenceCount": counts["missing"],
            "availableReferenceCount": counts["available"],
            "plannedCellUpdateCount": counts["cells"],
        }
        for source, counts in sorted(source_counts.items())
    ]
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": state,
        "readyForCleanup": state == "ready",
        "summary": {
            "referenceCount": sum(
                counts["references"] for counts in source_counts.values()
            ),
            "missingReferenceCount": missing_references,
            "availableReferenceCount": available_references,
            "missingUniqueFileCount": len(missing_file_ids),
            "plannedCellUpdateCount": len(updates),
            "businessRecordsToDelete": 0,
            "registryRowsToDelete": 0,
            "unresolvedReferenceCount": unresolved_references,
            "conflictingReferenceCount": conflicting_references,
            "invalidRegistryRows": invalid_registry_rows,
        },
        "scan": {
            "scannedSources": sorted(
                set(scan.get("scannedSources") or [])
            ),
            "truncatedSources": truncated_sources,
        },
        "bySource": by_source,
        "blockers": blockers,
        "updatesPreview": updates[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "updateListTruncated": len(updates) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }


def run_legacy_missing_file_plan(get_db):
    connection = get_db()
    try:
        connection.set_session(readonly=True, autocommit=False)
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        try:
            rows = load_legacy_reference_cutover_rows(cursor)
            report = build_legacy_missing_file_plan(*rows)
            connection.rollback()
            report["rolledBack"] = True
            return report
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(
        run_legacy_missing_file_plan(get_db),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
