"""Privacy-safe dry-run for legacy references whose files are absent.

The plan never changes source records or the ownership registry.  It only
classifies exact, owner-verified references and reports hashes instead of file
paths so the evidence can be retained without disclosing document names.
"""

import hashlib
import json
from collections import Counter, defaultdict
from urllib.parse import urlsplit

import psycopg2.extras
from psycopg2 import sql

from .legacy_reference_cutover import (
    ALLOWED_DATA_TYPES,
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
LEGACY_REGISTRATION_CONTEXT = "legacy_backfill"
APPLY_CONFIRMATION = "CLEAN_MISSING_LEGACY_FILE_REFERENCES"


class LegacyMissingFilePlanError(RuntimeError):
    pass


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
        storage_context = _storage_context(row, url)
        is_registered_legacy_url = (
            str(row.get("context") or "") == LEGACY_REGISTRATION_CONTEXT
        )
        if (
            not file_id
            or not company_id
            or not (storage_context or is_registered_legacy_url)
        ):
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


def _public_update(item):
    return {
        "source": item["source"],
        "recordId": item["recordId"],
        "missingReferenceCount": item["missingReferenceCount"],
        "fileIds": item["fileIds"],
        "oldValueSha256": item["oldValueSha256"],
        "newValueSha256": item["newValueSha256"],
    }


def _normalize_collection_item_url(value):
    normalized = _normalize_local_upload_url(value)
    if normalized:
        return normalized
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return _normalize_local_upload_url(parsed.path)


def _clean_reference_value(source, value, missing_urls, data_type="text"):
    expected_removals = len(missing_urls)
    missing_urls = set(missing_urls)
    if source.endswith(".photo_url"):
        scalar_value = value
        cleared_value = ""
        if data_type in ("json", "jsonb"):
            try:
                scalar_value = json.loads(value)
            except (TypeError, ValueError):
                return None, 0, "scalar_reference_shape_invalid"
            if not isinstance(scalar_value, str):
                return None, 0, "scalar_reference_shape_invalid"
            cleared_value = json.dumps("", ensure_ascii=False)
        normalized = _normalize_local_upload_url(scalar_value)
        if len(missing_urls) != 1 or normalized not in missing_urls:
            return None, 0, "scalar_reference_shape_invalid"
        return cleared_value, 1, None

    if not source.endswith(".photo_urls"):
        return None, 0, "source_reference_shape_unsupported"
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None, 0, "reference_collection_invalid"
    if not isinstance(parsed, list):
        return None, 0, "reference_collection_invalid"

    cleaned = []
    removed = 0
    for item in parsed:
        normalized = (
            _normalize_collection_item_url(item)
            if isinstance(item, str)
            else None
        )
        if normalized in missing_urls:
            removed += 1
            continue
        cleaned.append(item)
    if removed != expected_removals:
        return None, removed, "reference_collection_rewrite_incomplete"
    return json.dumps(
        cleaned,
        ensure_ascii=False,
        separators=(",", ":"),
    ), removed, None


def _prepare_legacy_missing_file_plan(
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
        data_type = str(record.get("dataType") or "text").strip().lower()
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
        cell_missing_urls = []
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
                    cell_missing_urls.append(url)
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
            new_value, removed, rewrite_error = _clean_reference_value(
                source,
                value,
                cell_missing_urls,
                data_type,
            )
            if rewrite_error or removed != len(cell_missing_urls):
                unresolved_references += len(cell_missing_urls)
                review.append({
                    "source": source,
                    "recordId": record_id,
                    "status": "unresolved",
                    "reason": rewrite_error or "reference_rewrite_incomplete",
                })
                continue
            updates.append({
                "source": source,
                "recordId": record_id,
                "dataType": data_type,
                "oldValue": value,
                "newValue": new_value,
                "missingReferenceCount": len(cell_missing_ids),
                "fileIds": sorted(cell_missing_ids),
                "oldValueSha256": _sha256(value),
                "newValueSha256": _sha256(new_value),
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
    public_updates = [_public_update(item) for item in updates]
    plan_payload = {
        "updates": public_updates,
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
    report = {
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
        "updatesPreview": public_updates[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "updateListTruncated": len(updates) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }
    return report, updates


def build_legacy_missing_file_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    scan=None,
):
    report, _ = _prepare_legacy_missing_file_plan(
        records,
        ownership_rows,
        projects,
        company_ids,
        scan,
    )
    return report


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_update_count,
    expected_reference_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise LegacyMissingFilePlanError("apply_confirmation_invalid")
    if not report["readyForCleanup"]:
        raise LegacyMissingFilePlanError("cleanup_plan_not_ready")
    if (
        _positive_int(expected_update_count)
        != report["summary"]["plannedCellUpdateCount"]
    ):
        raise LegacyMissingFilePlanError("update_count_mismatch")
    if (
        _positive_int(expected_reference_count)
        != report["summary"]["missingReferenceCount"]
    ):
        raise LegacyMissingFilePlanError("reference_count_mismatch")
    if str(expected_plan_sha256 or "") != report["planSha256"]:
        raise LegacyMissingFilePlanError("plan_sha256_mismatch")


def _apply_cleanup_updates(cursor, updates):
    removed_references = 0
    for item in updates:
        source = item["source"]
        data_type = item["dataType"]
        if source not in SOURCE_BY_NAME:
            raise LegacyMissingFilePlanError("source_not_allowlisted")
        if data_type not in ALLOWED_DATA_TYPES:
            raise LegacyMissingFilePlanError("source_data_type_unsupported")
        table, column = SOURCE_BY_NAME[source]
        value_expression = {
            "json": sql.SQL("%s::json"),
            "jsonb": sql.SQL("%s::jsonb"),
        }.get(data_type, sql.SQL("%s"))
        query = sql.SQL(
            "UPDATE {table} SET {column}={value} "
            "WHERE id=%s AND {column}::text=%s RETURNING id"
        ).format(
            table=sql.Identifier("public", table),
            column=sql.Identifier(column),
            value=value_expression,
        )
        cursor.execute(
            query,
            (item["newValue"], item["recordId"], item["oldValue"]),
        )
        if not cursor.fetchone():
            raise LegacyMissingFilePlanError("concurrent_source_change")
        removed_references += item["missingReferenceCount"]
    return len(updates), removed_references


def run_legacy_missing_file_plan(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_update_count=None,
    expected_reference_count=None,
    expected_plan_sha256="",
):
    connection = get_db()
    try:
        if apply:
            connection.set_session(autocommit=False)
        else:
            connection.set_session(readonly=True, autocommit=False)
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        try:
            rows = load_legacy_reference_cutover_rows(cursor)
            report, updates = _prepare_legacy_missing_file_plan(*rows)
            if not apply:
                connection.rollback()
                report["rolledBack"] = True
                return report
            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_update_count=expected_update_count,
                expected_reference_count=expected_reference_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            updated_cells, removed_references = _apply_cleanup_updates(
                cursor,
                updates,
            )
            connection.commit()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "writesAttempted": updated_cells,
                "updatedCellCount": updated_cells,
                "removedReferenceCount": removed_references,
                "businessRecordsDeleted": 0,
                "registryRowsDeleted": 0,
                "appliedPlanSha256": report["planSha256"],
            }
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
