"""Guarded cutover from public ``/uploads`` references to tenant file routes.

Dry-run is the default. Reports contain hashes instead of file paths or field
values so operational evidence cannot become another disclosure channel.
"""

import hashlib
import json
from collections import Counter, defaultdict
from urllib.parse import unquote, urlsplit

import psycopg2.extras
from psycopg2 import sql

from ..document_access.service import open_document_local_file
from .legacy_registration_plan import (
    SOURCE_SPECS,
    _classify_record,
    _column_expression,
    _positive_int,
    _project_indexes,
)
from .public_exposure_report import (
    LOCAL_UPLOAD_PATTERN,
    _normalize_local_upload_url,
    extract_local_upload_urls,
)


APPLY_CONFIRMATION = "CUTOVER_LEGACY_UPLOAD_REFERENCES"
PREVIEW_LIMIT = 100
ALLOWED_DATA_TYPES = {
    "character",
    "character varying",
    "json",
    "jsonb",
    "text",
}
SOURCE_BY_NAME = {
    table + "." + column: (table, column)
    for table, column, _ in SOURCE_SPECS
}


class LegacyReferenceCutoverError(RuntimeError):
    pass


def _sha256(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _storage_context(row, normalized_url):
    company_id = _positive_int(row.get("company_id"))
    project_id = _positive_int(row.get("project_id"))
    relative_path = unquote(urlsplit(normalized_url).path[len("/uploads/"):])
    namespace = relative_path.split("/", 1)[0]
    if project_id:
        prefix = f"company-{company_id}-project-{project_id}-"
    else:
        prefix = f"company-{company_id}-common-"
    if not namespace.startswith(prefix):
        return None
    context = namespace[len(prefix):]
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not context or any(character not in allowed for character in context):
        return None
    return context


def _ownership_index(rows, referenced_urls):
    result = defaultdict(list)
    invalid = 0
    invalid_storage = 0
    unavailable_storage = 0
    context_updates = []
    for raw in rows or []:
        row = dict(raw or {})
        file_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        url = _normalize_local_upload_url(row.get("file_url"))
        if url not in referenced_urls:
            continue
        if not file_id or not company_id or not url:
            invalid += 1
            continue
        if row.get("storageReady") is False:
            unavailable_storage += 1
            continue
        storage_context = _storage_context(row, url)
        if not storage_context:
            invalid_storage += 1
            continue
        current_context = str(row.get("context") or "")
        if current_context != storage_context:
            context_updates.append({
                "fileId": file_id,
                "fileUrl": url,
                "oldContext": current_context,
                "newContext": storage_context,
                "oldContextSha256": _sha256(current_context),
                "newContextSha256": _sha256(storage_context),
            })
        result[url].append({
            "id": file_id,
            "companyId": company_id,
            "projectId": _positive_int(row.get("project_id")),
        })
    return result, invalid, invalid_storage, unavailable_storage, context_updates


def _rewrite_value(value, replacements):
    count = 0

    def replace_match(match):
        nonlocal count
        normalized = _normalize_local_upload_url(match.group(0))
        replacement = replacements.get(normalized)
        if not replacement:
            return match.group(0)
        count += 1
        return replacement

    def rewrite_text(text):
        nonlocal count
        normalized = _normalize_local_upload_url(text)
        replacement = replacements.get(normalized)
        if replacement:
            count += 1
            return replacement
        return LOCAL_UPLOAD_PATTERN.sub(replace_match, text)

    def rewrite_json(item):
        if isinstance(item, dict):
            return {key: rewrite_json(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [rewrite_json(nested) for nested in item]
        if isinstance(item, str):
            return rewrite_text(item)
        return item

    text = str(value or "")
    if text.strip()[:1] in ("[", "{"):
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            rewritten = rewrite_json(parsed)
            return json.dumps(
                rewritten,
                ensure_ascii=False,
                separators=(",", ":"),
            ), count
    return rewrite_text(text), count


def _public_update(item):
    return {
        "source": item["source"],
        "recordId": item["recordId"],
        "referenceCount": item["referenceCount"],
        "oldValueSha256": item["oldValueSha256"],
        "newValueSha256": item["newValueSha256"],
        "fileIds": item["fileIds"],
    }


def _public_context_update(item):
    return {
        "fileId": item["fileId"],
        "oldContextSha256": item["oldContextSha256"],
        "newContextSha256": item["newContextSha256"],
    }


def _prepare_legacy_reference_cutover(
    records,
    ownership_rows,
    projects,
    company_ids,
    scan=None,
):
    referenced_urls = {
        url
        for raw in (records or [])
        for url in extract_local_upload_urls(str((raw or {}).get("value") or ""))
    }
    (
        ownership_by_url,
        invalid_registry_rows,
        invalid_storage_rows,
        unavailable_storage_rows,
        context_updates,
    ) = _ownership_index(ownership_rows, referenced_urls)
    projects_by_id, projects_by_name = _project_indexes(projects)
    company_ids = set(company_ids or set())
    updates = []
    review = []
    source_references = Counter()
    source_updates = Counter()
    unresolved_references = 0
    conflicting_references = 0

    for raw in records or []:
        record = dict(raw or {})
        source = str(record.get("source") or "")
        record_id = _positive_int(record.get("recordId"))
        data_type = str(record.get("dataType") or "text").strip().lower()
        value = str(record.get("value") or "")
        urls = extract_local_upload_urls(value)
        if not urls:
            continue
        source_references[source] += len(urls)
        owner, owner_status, owner_reason = _classify_record(
            record,
            projects_by_id,
            projects_by_name,
            company_ids,
        )
        replacements = {}
        file_ids = []
        record_has_issue = False

        for url in urls:
            reason = None
            status = "unresolved"
            registered = ownership_by_url.get(url, [])
            if source not in SOURCE_BY_NAME or not record_id:
                reason = "source_record_invalid"
            elif data_type not in ALLOWED_DATA_TYPES:
                reason = "source_data_type_unsupported"
            elif owner_status != "ready":
                reason = owner_reason
                status = owner_status
            elif not registered:
                reason = "file_registration_missing"
            elif len(registered) != 1:
                reason = "file_registration_ambiguous"
                status = "conflicting"
            else:
                registration = registered[0]
                if (
                    registration["companyId"] != owner["companyId"]
                    or registration["projectId"] != owner["projectId"]
                ):
                    reason = "reference_owner_mismatch"
                    status = "conflicting"
                else:
                    file_id = registration["id"]
                    replacements[url] = f"/tenant-files/{file_id}/content"
                    file_ids.append(file_id)

            if reason:
                record_has_issue = True
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

        if record_has_issue:
            continue
        new_value, replacement_count = _rewrite_value(value, replacements)
        if replacement_count != len(urls) or extract_local_upload_urls(new_value):
            unresolved_references += len(urls)
            review.append({
                "source": source,
                "recordId": record_id,
                "status": "unresolved",
                "reason": "reference_rewrite_incomplete",
            })
            continue
        updates.append({
            "source": source,
            "recordId": record_id,
            "dataType": data_type,
            "oldValue": value,
            "newValue": new_value,
            "oldValueSha256": _sha256(value),
            "newValueSha256": _sha256(new_value),
            "referenceCount": replacement_count,
            "fileIds": sorted(file_ids),
        })
        source_updates[source] += 1

    public_updates = [_public_update(item) for item in updates]
    blockers = sorted({item["reason"] for item in review})
    if invalid_registry_rows:
        blockers.append("invalid_file_registration")
    if invalid_storage_rows:
        blockers.append("invalid_file_storage_namespace")
    if unavailable_storage_rows:
        blockers.append("file_storage_unavailable")
    blockers = sorted(set(blockers))
    rewritten_reference_count = sum(item["referenceCount"] for item in updates)
    reference_count = sum(source_references.values())
    scan = dict(scan or {})
    truncated_sources = sorted(set(scan.get("truncatedSources") or []))
    if truncated_sources:
        blockers = sorted(set(blockers + ["reference_scan_truncated"]))

    public_context_updates = [
        _public_context_update(item) for item in context_updates
    ]
    plan_payload = {
        "updates": public_updates,
        "contextUpdates": public_context_updates,
        "review": review,
        "invalidRegistryRows": invalid_registry_rows,
        "invalidStorageRows": invalid_storage_rows,
        "unavailableStorageRows": unavailable_storage_rows,
        "scannedSources": sorted(set(scan.get("scannedSources") or [])),
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
            "referenceCount": source_references[source],
            "cellUpdateCount": source_updates[source],
        }
        for source in sorted(source_references)
    ]
    report = {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForApply": not blockers and reference_count == rewritten_reference_count,
        "summary": {
            "referenceCount": reference_count,
            "uniqueFileCount": len(referenced_urls),
            "cellUpdateCount": len(updates),
            "rewrittenReferenceCount": rewritten_reference_count,
            "unresolvedReferences": unresolved_references,
            "conflictingReferences": conflicting_references,
            "invalidRegistryRows": invalid_registry_rows,
            "invalidStorageRows": invalid_storage_rows,
            "unavailableStorageRows": unavailable_storage_rows,
            "registryContextUpdateCount": len(context_updates),
        },
        "scan": {
            "scannedSources": sorted(set(scan.get("scannedSources") or [])),
            "truncatedSources": truncated_sources,
        },
        "bySource": by_source,
        "blockers": blockers,
        "updatesPreview": public_updates[:PREVIEW_LIMIT],
        "registryContextUpdatesPreview": public_context_updates[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "updateListTruncated": len(updates) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }
    return report, updates, context_updates


def build_legacy_reference_cutover_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    scan=None,
):
    report, _, _ = _prepare_legacy_reference_cutover(
        records,
        ownership_rows,
        projects,
        company_ids,
        scan,
    )
    return report


def _available_source_columns(cur):
    tables = sorted({spec[0] for spec in SOURCE_SPECS})
    cur.execute(
        """SELECT table_name,column_name,data_type
             FROM information_schema.columns
            WHERE table_schema='public' AND table_name=ANY(%s)
            ORDER BY table_name,column_name""",
        (tables,),
    )
    result = defaultdict(dict)
    for raw in cur.fetchall() or []:
        row = dict(raw or {})
        result[str(row.get("table_name") or "")][
            str(row.get("column_name") or "")
        ] = str(row.get("data_type") or "").strip().lower()
    return result


def _mark_storage_readiness(rows, upload_dir):
    result = []
    for raw in rows:
        row = dict(raw or {})
        if str(row.get("storage_key") or "").strip():
            row["storageReady"] = False
            row["storageReason"] = "s3_storage_not_verified"
            result.append(row)
            continue
        try:
            stream, _ = open_document_local_file(
                upload_dir,
                row.get("file_url"),
                2 ** 63 - 1,
            )
            stream.close()
            row["storageReady"] = True
        except Exception:
            row["storageReady"] = False
            row["storageReason"] = "local_file_unavailable"
        result.append(row)
    return result


def load_legacy_reference_cutover_rows(cur, *, upload_dir="uploads"):
    available_by_table = _available_source_columns(cur)
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
        """SELECT id,company_id,project_id,file_url,context,
                  COALESCE(storage_key,'') AS storage_key
             FROM file_ownership
            WHERE file_url LIKE %s
            ORDER BY id""",
        ("/uploads/%",),
    )
    ownership_rows = _mark_storage_readiness(
        [dict(row or {}) for row in (cur.fetchall() or [])],
        upload_dir,
    )

    records = []
    scanned_sources = []
    for table, column, project_name_column in SOURCE_SPECS:
        available = available_by_table.get(table, {})
        data_type = available.get(column)
        if "id" not in available or not data_type:
            continue
        source = table + "." + column
        scanned_sources.append(source)
        query = sql.SQL(
            "SELECT {record_id},{column}::text AS value,{company_id},"
            "{project_id},{project_name},{ownership_verified} FROM {table} "
            "WHERE {column}::text LIKE %s ORDER BY {record_id_column}"
        ).format(
            record_id=_column_expression("id", available, "record_id"),
            column=sql.Identifier(column),
            company_id=_column_expression("company_id", available, "company_id"),
            project_id=_column_expression("project_id", available, "project_id"),
            project_name=_column_expression(
                project_name_column,
                available,
                "project_name",
            ),
            ownership_verified=_column_expression(
                "company_scope_verified",
                available,
                "ownership_verified",
            ),
            table=sql.Identifier("public", table),
            record_id_column=sql.Identifier("id"),
        )
        cur.execute(query, ("%/uploads/%",))
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
                "dataType": data_type,
            })
    return records, ownership_rows, projects, company_ids, {
        "scannedSources": scanned_sources,
        "truncatedSources": [],
    }


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_update_count,
    expected_reference_count,
    expected_context_update_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise LegacyReferenceCutoverError("apply_confirmation_invalid")
    if not report["readyForApply"]:
        raise LegacyReferenceCutoverError("cutover_plan_not_ready")
    if _positive_int(expected_update_count) != report["summary"]["cellUpdateCount"]:
        raise LegacyReferenceCutoverError("update_count_mismatch")
    if (
        _positive_int(expected_reference_count)
        != report["summary"]["referenceCount"]
    ):
        raise LegacyReferenceCutoverError("reference_count_mismatch")
    try:
        context_update_count = int(expected_context_update_count)
    except (TypeError, ValueError):
        context_update_count = -1
    if context_update_count != report["summary"]["registryContextUpdateCount"]:
        raise LegacyReferenceCutoverError("context_update_count_mismatch")
    if str(expected_plan_sha256 or "") != report["planSha256"]:
        raise LegacyReferenceCutoverError("plan_sha256_mismatch")


def _apply_updates(cur, updates):
    rewritten_references = 0
    for item in updates:
        source = item["source"]
        if source not in SOURCE_BY_NAME:
            raise LegacyReferenceCutoverError("source_not_allowlisted")
        data_type = item["dataType"]
        if data_type not in ALLOWED_DATA_TYPES:
            raise LegacyReferenceCutoverError("source_data_type_unsupported")
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
        cur.execute(
            query,
            (item["newValue"], item["recordId"], item["oldValue"]),
        )
        if not cur.fetchone():
            raise LegacyReferenceCutoverError("concurrent_source_change")
        rewritten_references += item["referenceCount"]
    return len(updates), rewritten_references


def _apply_context_updates(cur, updates):
    for item in updates:
        cur.execute(
            """UPDATE file_ownership
                  SET context=%s
                WHERE id=%s AND file_url=%s AND COALESCE(context,'')=%s
                RETURNING id""",
            (
                item["newContext"],
                item["fileId"],
                item["fileUrl"],
                item["oldContext"],
            ),
        )
        if not cur.fetchone():
            raise LegacyReferenceCutoverError("concurrent_registry_change")
    return len(updates)


def run_legacy_reference_cutover(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_update_count=None,
    expected_reference_count=None,
    expected_context_update_count=None,
    expected_plan_sha256="",
):
    conn = get_db()
    try:
        if apply:
            conn.set_session(autocommit=False)
        else:
            conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows = load_legacy_reference_cutover_rows(cur)
            report, updates, context_updates = _prepare_legacy_reference_cutover(*rows)
            if not apply:
                conn.rollback()
                report["rolledBack"] = True
                return report
            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_update_count=expected_update_count,
                expected_reference_count=expected_reference_count,
                expected_context_update_count=expected_context_update_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            updated_contexts = _apply_context_updates(cur, context_updates)
            updated_cells, rewritten_references = _apply_updates(cur, updates)
            conn.commit()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "writesAttempted": updated_contexts + updated_cells,
                "updatedRegistryContextCount": updated_contexts,
                "updatedCellCount": updated_cells,
                "rewrittenReferenceCount": rewritten_references,
                "appliedPlanSha256": report["planSha256"],
            }
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
    print(json.dumps(run_legacy_reference_cutover(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
