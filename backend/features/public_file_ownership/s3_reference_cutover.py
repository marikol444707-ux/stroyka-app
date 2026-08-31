"""Guarded cutover from direct S3 URLs to protected tenant file routes.

Dry-run is the default. The report never exposes storage URLs, object keys, or
business field values; it keeps only hashes and stable database identities.
"""

import hashlib
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlsplit

import psycopg2.extras
from psycopg2 import sql

from .public_exposure_report import (
    REFERENCE_GROUP_LIMIT,
    URLISH_COLUMN_PATTERN,
)


APPLY_CONFIRMATION = "CUTOVER_S3_UPLOAD_REFERENCES"
PREVIEW_LIMIT = 100
ALLOWED_DATA_TYPES = {
    "character",
    "character varying",
    "json",
    "jsonb",
    "text",
}
HTTP_URL_PATTERN = re.compile(r"https?://[^\s\"'<>\\]+", re.IGNORECASE)


class S3ReferenceCutoverError(RuntimeError):
    pass


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _expected_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _sha256(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _http_storage_url(value):
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.path:
        return None
    if parsed.username or parsed.password or parsed.fragment:
        return None
    return raw


def _storage_hosts(ownership_rows):
    return {
        urlsplit(url).netloc.lower()
        for raw in ownership_rows or []
        for url in [_http_storage_url((raw or {}).get("file_url"))]
        if url and str((raw or {}).get("storage_key") or "").strip()
    }


def _visit_text_values(value):
    result = []

    def visit(item):
        if isinstance(item, dict):
            for nested in item.values():
                visit(nested)
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)
            return
        if isinstance(item, str):
            text = item.strip()
            if text[:1] in ("[", "{"):
                try:
                    parsed = json.loads(text)
                except (TypeError, ValueError):
                    parsed = None
                if isinstance(parsed, (dict, list)):
                    visit(parsed)
                    return
            result.append(item)

    visit(value)
    return result


def _extract_storage_urls(value, storage_hosts):
    found = []
    for text in _visit_text_values(value):
        exact = _http_storage_url(text)
        if exact and urlsplit(exact).netloc.lower() in storage_hosts:
            found.append(exact)
            continue
        for match in HTTP_URL_PATTERN.finditer(text):
            url = _http_storage_url(match.group(0))
            if url and urlsplit(url).netloc.lower() in storage_hosts:
                found.append(url)
    return found


def _rewrite_value(value, replacements):
    count = 0
    if replacements:
        pattern = re.compile(
            "|".join(
                re.escape(url)
                for url in sorted(replacements, key=lambda item: (-len(item), item))
            )
        )
    else:
        pattern = None

    def rewrite_text(text):
        nonlocal count
        if not pattern:
            return text

        def replace(match):
            nonlocal count
            replacement = replacements.get(match.group(0))
            if not replacement:
                return match.group(0)
            count += 1
            return replacement

        return pattern.sub(replace, text)

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


def _ownership_index(rows):
    result = defaultdict(list)
    invalid = 0
    for raw in rows or []:
        row = dict(raw or {})
        file_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        project_id = _positive_int(row.get("project_id"))
        storage_key = str(row.get("storage_key") or "").strip()
        file_url = _http_storage_url(row.get("file_url"))
        if not file_id or not company_id or not storage_key or not file_url:
            invalid += 1
            continue
        result[file_url].append({
            "id": file_id,
            "companyId": company_id,
            "projectId": project_id,
        })
    return result, invalid


def _owner_issue(record, registration):
    company_id = _positive_int(record.get("companyId"))
    project_id = _positive_int(record.get("projectId"))
    if not company_id and not project_id:
        return "unresolved", "source_owner_missing"
    if company_id and company_id != registration["companyId"]:
        return "conflicting", "reference_owner_mismatch"
    if (
        project_id
        and (
            not registration["projectId"]
            or project_id != registration["projectId"]
        )
    ):
        return "conflicting", "reference_owner_mismatch"
    return None


def _public_update(item):
    return {
        "source": item["source"],
        "recordId": item["recordId"],
        "referenceCount": item["referenceCount"],
        "oldValueSha256": item["oldValueSha256"],
        "newValueSha256": item["newValueSha256"],
        "fileIds": item["fileIds"],
    }


def _prepare_s3_reference_cutover(records, ownership_rows, sources, scan=None):
    ownership_by_url, invalid_registry_rows = _ownership_index(ownership_rows)
    storage_hosts = _storage_hosts(ownership_rows)
    updates = []
    review = []
    source_references = Counter()
    source_updates = Counter()
    referenced_urls = set()
    unresolved_references = 0
    conflicting_references = 0

    for raw in records or []:
        record = dict(raw or {})
        source = str(record.get("source") or "")
        record_id = _positive_int(record.get("recordId"))
        data_type = str(record.get("dataType") or "text").strip().lower()
        value = str(record.get("value") or "")
        urls = _extract_storage_urls(value, storage_hosts)
        if not urls:
            continue
        source_references[source] += len(urls)
        referenced_urls.update(urls)
        replacements = {}
        file_ids = []
        record_has_issue = False

        for url in urls:
            status = "unresolved"
            reason = None
            registered = ownership_by_url.get(url, [])
            if source not in sources or not record_id:
                reason = "source_record_invalid"
            elif data_type not in ALLOWED_DATA_TYPES:
                reason = "source_data_type_unsupported"
            elif not registered:
                reason = "file_registration_missing"
            elif len(registered) != 1:
                reason = "file_registration_ambiguous"
                status = "conflicting"
            else:
                owner_issue = _owner_issue(record, registered[0])
                if owner_issue:
                    status, reason = owner_issue
                else:
                    file_id = registered[0]["id"]
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
        remaining = _extract_storage_urls(new_value, storage_hosts)
        if replacement_count != len(urls) or remaining:
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
            "fileIds": sorted(set(file_ids)),
        })
        source_updates[source] += 1

    scan = dict(scan or {})
    truncated_sources = sorted(set(scan.get("truncatedSources") or []))
    blockers = sorted({item["reason"] for item in review})
    if invalid_registry_rows:
        blockers.append("invalid_s3_file_registration")
    if truncated_sources:
        blockers.append("reference_scan_truncated")
    blockers = sorted(set(blockers))
    reference_count = sum(source_references.values())
    rewritten_reference_count = sum(item["referenceCount"] for item in updates)
    public_updates = [_public_update(item) for item in updates]
    plan_payload = {
        "updates": public_updates,
        "review": review,
        "invalidRegistryRows": invalid_registry_rows,
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
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForApply": not blockers and reference_count == rewritten_reference_count,
        "summary": {
            "registryRowCount": len(ownership_rows or []),
            "referenceCount": reference_count,
            "uniqueFileCount": len(referenced_urls),
            "cellUpdateCount": len(updates),
            "rewrittenReferenceCount": rewritten_reference_count,
            "unresolvedReferences": unresolved_references,
            "conflictingReferences": conflicting_references,
            "invalidRegistryRows": invalid_registry_rows,
        },
        "scan": {
            "scannedSources": sorted(set(scan.get("scannedSources") or [])),
            "truncatedSources": truncated_sources,
        },
        "bySource": [
            {
                "source": source,
                "referenceCount": source_references[source],
                "cellUpdateCount": source_updates[source],
            }
            for source in sorted(source_references)
        ],
        "blockers": blockers,
        "updatesPreview": public_updates[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "updateListTruncated": len(updates) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }, updates


def build_s3_reference_cutover_plan(
    records,
    ownership_rows,
    sources=None,
    scan=None,
):
    if sources is None:
        sources = {
            str((record or {}).get("source") or ""): ("test", "value")
            for record in records or []
            if str((record or {}).get("source") or "")
        }
    report, _ = _prepare_s3_reference_cutover(
        records,
        ownership_rows,
        sources,
        scan,
    )
    return report


def _row_dict(row):
    return dict(row) if isinstance(row, dict) else {}


def _discover_source_columns(cur):
    cur.execute(
        """
        SELECT c.table_name,c.column_name,c.data_type
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema=c.table_schema AND t.table_name=c.table_name
         WHERE c.table_schema='public'
           AND t.table_type='BASE TABLE'
           AND c.table_name <> 'file_ownership'
         ORDER BY c.table_name,c.ordinal_position
        """
    )
    tables = defaultdict(dict)
    for raw in cur.fetchall() or []:
        row = _row_dict(raw)
        table = str(row.get("table_name") or "")
        column = str(row.get("column_name") or "")
        data_type = str(row.get("data_type") or "").strip().lower()
        if table and column:
            tables[table][column] = data_type
    result = {}
    for table, columns in tables.items():
        if "id" not in columns:
            continue
        for column, data_type in columns.items():
            if data_type in ALLOWED_DATA_TYPES and URLISH_COLUMN_PATTERN.search(column):
                result[table + "." + column] = {
                    "table": table,
                    "column": column,
                    "dataType": data_type,
                    "columns": columns,
                }
    return result


def _optional_column(name, columns, alias):
    if name in columns:
        return sql.SQL("{column} AS {alias}").format(
            column=sql.Identifier(name),
            alias=sql.Identifier(alias),
        )
    return sql.SQL("NULL AS {alias}").format(alias=sql.Identifier(alias))


def load_s3_reference_cutover_rows(cur):
    cur.execute(
        """SELECT id,company_id,project_id,file_url,COALESCE(storage_key,'') AS storage_key
             FROM file_ownership
            WHERE COALESCE(storage_key,'') <> ''
            ORDER BY id"""
    )
    ownership_rows = [_row_dict(row) for row in (cur.fetchall() or [])]
    hosts = sorted(_storage_hosts(ownership_rows))
    discovered = _discover_source_columns(cur)
    sources = {
        source: (item["table"], item["column"])
        for source, item in discovered.items()
    }
    if not hosts:
        return [], ownership_rows, sources, {
            "scannedSources": [],
            "truncatedSources": [],
        }

    records = []
    scanned_sources = []
    truncated_sources = []
    patterns = ["%" + host + "%" for host in hosts]
    for source in sorted(discovered):
        item = discovered[source]
        columns = item["columns"]
        scanned_sources.append(source)
        query = sql.SQL(
            "SELECT id AS record_id,{value}::text AS value,{company_id},"
            "{project_id} FROM {table} WHERE {value}::text LIKE ANY(%s) "
            "ORDER BY id LIMIT %s"
        ).format(
            value=sql.Identifier(item["column"]),
            company_id=_optional_column("company_id", columns, "company_id"),
            project_id=_optional_column("project_id", columns, "project_id"),
            table=sql.Identifier("public", item["table"]),
        )
        cur.execute(query, (patterns, REFERENCE_GROUP_LIMIT + 1))
        rows = list(cur.fetchall() or [])
        if len(rows) > REFERENCE_GROUP_LIMIT:
            truncated_sources.append(source)
            rows = rows[:REFERENCE_GROUP_LIMIT]
        for raw in rows:
            row = _row_dict(raw)
            records.append({
                "source": source,
                "recordId": row.get("record_id"),
                "value": row.get("value"),
                "companyId": row.get("company_id"),
                "projectId": row.get("project_id"),
                "dataType": item["dataType"],
            })
    return records, ownership_rows, sources, {
        "scannedSources": scanned_sources,
        "truncatedSources": truncated_sources,
    }


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_update_count,
    expected_reference_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise S3ReferenceCutoverError("apply_confirmation_invalid")
    if not report["readyForApply"]:
        raise S3ReferenceCutoverError("cutover_plan_not_ready")
    if _expected_int(expected_update_count) != report["summary"]["cellUpdateCount"]:
        raise S3ReferenceCutoverError("update_count_mismatch")
    if _expected_int(expected_reference_count) != report["summary"]["referenceCount"]:
        raise S3ReferenceCutoverError("reference_count_mismatch")
    if str(expected_plan_sha256 or "") != report["planSha256"]:
        raise S3ReferenceCutoverError("plan_sha256_mismatch")


def _apply_updates(cur, updates, sources):
    rewritten_references = 0
    for item in updates:
        source = item["source"]
        if source not in sources:
            raise S3ReferenceCutoverError("source_not_allowlisted")
        if item["dataType"] not in ALLOWED_DATA_TYPES:
            raise S3ReferenceCutoverError("source_data_type_unsupported")
        table, column = sources[source]
        value_expression = {
            "json": sql.SQL("%s::json"),
            "jsonb": sql.SQL("%s::jsonb"),
        }.get(item["dataType"], sql.SQL("%s"))
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
            raise S3ReferenceCutoverError("concurrent_source_change")
        rewritten_references += item["referenceCount"]
    return len(updates), rewritten_references


def run_s3_reference_cutover(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_update_count=None,
    expected_reference_count=None,
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
            rows = load_s3_reference_cutover_rows(cur)
            report, updates = _prepare_s3_reference_cutover(*rows)
            if not apply:
                conn.rollback()
                report["rolledBack"] = True
                return report
            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_update_count=expected_update_count,
                expected_reference_count=expected_reference_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            updated_cells, rewritten_references = _apply_updates(
                cur,
                updates,
                rows[2],
            )
            conn.commit()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "writesAttempted": updated_cells,
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
    print(json.dumps(run_s3_reference_cutover(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
