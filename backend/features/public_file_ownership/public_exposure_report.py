"""Read-only readiness report for retiring the public ``/uploads`` route.

The report deliberately never returns file names or URLs.  Potentially sensitive
paths are represented by SHA-256 only, so the diagnostic itself can be retained
as operational evidence without becoming another document disclosure channel.
"""

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from urllib.parse import quote, unquote, urlsplit

import psycopg2.extras
from psycopg2 import sql

from .ownership_report import build_report_from_rows, load_ownership_rows


PREVIEW_LIMIT = 100
REFERENCE_GROUP_LIMIT = 5000
LOCAL_UPLOAD_PATTERN = re.compile(r"/uploads/[^\s\"'<>\\?#]+")
URLISH_COLUMN_PATTERN = re.compile(
    r"(?:url|file|photo|scan|image|attachment|document|media)",
    re.IGNORECASE,
)


def public_uploads_mount_enabled(environ=None):
    source = os.environ if environ is None else environ
    value = str(source.get("PUBLIC_UPLOADS_MOUNT_ENABLED", "true") or "").strip().lower()
    return value in ("1", "true", "yes", "on")


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _normalize_local_upload_url(value):
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/uploads/"):
        return None
    decoded_path = unquote(parsed.path)
    relative = decoded_path[len("/uploads/"):]
    parts = relative.split("/")
    if (
        not relative
        or any(part in ("", ".", "..") for part in parts)
        or any("\\" in part or "\x00" in part for part in parts)
    ):
        return None
    return quote(
        "/uploads/" + "/".join(parts),
        safe="/:@-._~!$&'()*+,;=",
    )


def extract_local_upload_urls(value):
    """Extract canonical local upload URLs from scalar or nested JSON values."""
    found = []

    def visit(item):
        if isinstance(item, dict):
            for nested in item.values():
                visit(nested)
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)
            return
        if not isinstance(item, str):
            return

        text = item.strip()
        if text[:1] in ("[", "{"):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, (dict, list)):
                visit(parsed)
                return

        exact_url = _normalize_local_upload_url(text)
        if exact_url:
            found.append(exact_url)
            return

        for match in LOCAL_UPLOAD_PATTERN.finditer(text):
            normalized = _normalize_local_upload_url(match.group(0))
            if normalized:
                found.append(normalized)

    visit(value)
    return found


def _url_sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_name(item):
    return str(item.get("table") or "unknown") + "." + str(item.get("column") or "unknown")


def _is_public_s3_acl(storage_backend, s3_acl):
    if str(storage_backend or "").strip().lower() != "s3":
        return False
    acl = str(s3_acl or "").strip().lower()
    return acl not in ("", "private", "bucket-owner-full-control")


def build_public_exposure_report(
    ownership_rows,
    reference_values,
    *,
    public_mount_enabled,
    storage_backend,
    s3_acl,
    ownership_scope_ready=True,
    ownership_scope_summary=None,
    scanned_sources=None,
    scan_truncated_sources=None,
):
    """Build a privacy-safe cutover report from already collected rows."""
    registry_counts = Counter()
    invalid_registry_rows = 0
    s3_registry_rows = 0

    for raw_row in ownership_rows or []:
        row = dict(raw_row or {})
        if not _positive_int(row.get("id")):
            invalid_registry_rows += 1
            continue
        if str(row.get("storage_key") or "").strip():
            s3_registry_rows += 1
            continue
        normalized = _normalize_local_upload_url(row.get("file_url"))
        if not normalized:
            invalid_registry_rows += 1
            continue
        registry_counts[normalized] += 1

    duplicate_urls = {url for url, count in registry_counts.items() if count > 1}
    registered_urls = set(registry_counts)

    reference_counts = Counter()
    reference_sources = defaultdict(set)
    source_totals = Counter()
    source_urls = defaultdict(set)
    source_registered = defaultdict(set)
    source_unregistered = defaultdict(set)

    for raw_item in reference_values or []:
        item = dict(raw_item or {})
        source = _source_name(item)
        occurrences = _positive_int(item.get("occurrences")) or 1
        for url in extract_local_upload_urls(item.get("value")):
            reference_counts[url] += occurrences
            reference_sources[url].add(source)
            source_totals[source] += occurrences
            source_urls[source].add(url)
            if url in registered_urls:
                source_registered[source].add(url)
            else:
                source_unregistered[source].add(url)

    referenced_urls = set(reference_counts)
    unregistered_urls = referenced_urls - registered_urls
    registered_reference_urls = referenced_urls & registered_urls

    truncated_sources = sorted(set(scan_truncated_sources or []))
    data_blockers = []
    if truncated_sources:
        data_blockers.append("reference_scan_truncated")
    if not ownership_scope_ready:
        data_blockers.append("unverified_file_ownership_scope")
    if invalid_registry_rows:
        data_blockers.append("invalid_local_upload_registry")
    if duplicate_urls:
        data_blockers.append("duplicate_local_upload_registry")
    if unregistered_urls:
        data_blockers.append("unregistered_local_upload_references")

    runtime_blockers = []
    if public_mount_enabled:
        runtime_blockers.append("public_uploads_mount_enabled")
    if _is_public_s3_acl(storage_backend, s3_acl):
        runtime_blockers.append("s3_objects_may_be_public")

    by_source = []
    for source in sorted(source_urls):
        table, column = source.split(".", 1)
        by_source.append({
            "table": table,
            "column": column,
            "referenceCount": source_totals[source],
            "uniqueUrlCount": len(source_urls[source]),
            "registeredUniqueUrls": len(source_registered[source]),
            "unregisteredUniqueUrls": len(source_unregistered[source]),
        })

    unregistered_preview = [
        {
            "urlSha256": _url_sha256(url),
            "referenceCount": reference_counts[url],
            "sources": sorted(reference_sources[url]),
        }
        for url in sorted(unregistered_urls, key=_url_sha256)[:PREVIEW_LIMIT]
    ]

    plan_payload = {
        "registry": sorted(
            (_url_sha256(url), count)
            for url, count in registry_counts.items()
        ),
        "references": sorted(
            (
                _url_sha256(url),
                reference_counts[url],
                sorted(reference_sources[url]),
            )
            for url in referenced_urls
        ),
        "runtime": {
            "publicMountEnabled": bool(public_mount_enabled),
            "storageBackend": str(storage_backend or "").strip().lower(),
            "publicS3Acl": _is_public_s3_acl(storage_backend, s3_acl),
        },
        "ownershipScope": dict(ownership_scope_summary or {}),
        "scan": {
            "scannedSources": sorted(set(scanned_sources or [])),
            "truncatedSources": truncated_sources,
        },
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(
            plan_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    data_ready = not data_blockers
    blockers = data_blockers + runtime_blockers
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "dataReadyForProtectedDelivery": data_ready,
        "publicExposureClosed": data_ready and not runtime_blockers,
        "summary": {
            "registryRows": len(ownership_rows or []),
            "registeredLocalUniqueUrls": len(registered_urls),
            "registeredS3Rows": s3_registry_rows,
            "duplicateRegisteredLocalUrls": len(duplicate_urls),
            "invalidLocalRegistryRows": invalid_registry_rows,
            "localReferenceCount": sum(reference_counts.values()),
            "localReferenceUniqueUrls": len(referenced_urls),
            "registeredReferenceUniqueUrls": len(registered_reference_urls),
            "unregisteredUniqueUrls": len(unregistered_urls),
        },
        "runtime": {
            "publicUploadsMountEnabled": bool(public_mount_enabled),
            "storageBackend": str(storage_backend or "local").strip().lower(),
            "s3AclPublic": _is_public_s3_acl(storage_backend, s3_acl),
        },
        "ownershipScope": dict(ownership_scope_summary or {}),
        "scan": {
            "scannedSources": sorted(set(scanned_sources or [])),
            "truncatedSources": truncated_sources,
        },
        "bySource": by_source,
        "blockers": blockers,
        "unregisteredPreview": unregistered_preview,
        "reviewListTruncated": len(unregistered_urls) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }


def _row_dict(row):
    if isinstance(row, dict):
        return dict(row)
    return {}


def _discover_reference_columns(cur):
    cur.execute(
        """
        SELECT c.table_schema,c.table_name,c.column_name,c.data_type
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema=c.table_schema AND t.table_name=c.table_name
         WHERE c.table_schema='public'
           AND t.table_type='BASE TABLE'
           AND c.table_name <> 'file_ownership'
           AND c.data_type IN ('text','character varying','character','json','jsonb')
           AND LOWER(c.column_name) ~ '(url|file|photo|scan|image|attachment|document|media)'
         ORDER BY c.table_name,c.ordinal_position
        """
    )
    result = []
    for raw_row in cur.fetchall() or []:
        row = _row_dict(raw_row)
        table = str(row.get("table_name") or "")
        column = str(row.get("column_name") or "")
        if table and column and URLISH_COLUMN_PATTERN.search(column):
            result.append((table, column))
    return result


def load_public_exposure_rows(cur):
    """Load only ownership identities and values that actually contain /uploads/."""
    cur.execute(
        """SELECT id,company_id,project_id,file_url,COALESCE(storage_key,'') AS storage_key
             FROM file_ownership
            ORDER BY id"""
    )
    ownership_rows = [_row_dict(row) for row in (cur.fetchall() or [])]

    reference_values = []
    scanned_sources = []
    truncated_sources = []
    for table, column in _discover_reference_columns(cur):
        source = table + "." + column
        scanned_sources.append(source)
        query = sql.SQL(
            "SELECT {column}::text AS value,COUNT(*) AS occurrences "
            "FROM {table} WHERE {column}::text LIKE %s "
            "GROUP BY {column}::text ORDER BY {column}::text LIMIT %s"
        ).format(
            table=sql.Identifier("public", table),
            column=sql.Identifier(column),
        )
        cur.execute(query, ("%/uploads/%", REFERENCE_GROUP_LIMIT + 1))
        source_rows = list(cur.fetchall() or [])
        if len(source_rows) > REFERENCE_GROUP_LIMIT:
            truncated_sources.append(source)
            source_rows = source_rows[:REFERENCE_GROUP_LIMIT]
        for raw_row in source_rows:
            row = _row_dict(raw_row)
            reference_values.append({
                "table": table,
                "column": column,
                "value": row.get("value"),
                "occurrences": row.get("occurrences") or 1,
            })
    ownership_scope_rows = load_ownership_rows(cur)
    return ownership_rows, reference_values, ownership_scope_rows, {
        "scannedSources": scanned_sources,
        "truncatedSources": truncated_sources,
    }


def run_public_exposure_report(
    get_db,
    *,
    public_mount_enabled=True,
    storage_backend="local",
    s3_acl="public-read",
):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            (
                ownership_rows,
                reference_values,
                ownership_scope_rows,
                scan,
            ) = load_public_exposure_rows(cur)
            ownership_scope = build_report_from_rows(ownership_scope_rows)
            result = build_public_exposure_report(
                ownership_rows,
                reference_values,
                public_mount_enabled=public_mount_enabled,
                storage_backend=storage_backend,
                s3_acl=s3_acl,
                ownership_scope_ready=ownership_scope["readyForStrictRuntime"],
                ownership_scope_summary=ownership_scope["summary"],
                scanned_sources=scan.get("scannedSources"),
                scan_truncated_sources=scan.get("truncatedSources"),
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

    report = run_public_exposure_report(
        get_db,
        public_mount_enabled=public_uploads_mount_enabled(),
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        s3_acl=os.getenv("S3_ACL", "public-read"),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
