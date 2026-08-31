"""Read-only plan for moving legacy accounting objects into tenant S3 paths.

This module deliberately has no apply mode.  It proves the source object,
tenant owner, project-name segment, and deterministic destination without
copying an object or changing a database reference.
"""

import hashlib
import json
import os
import posixpath
import re
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import quote

import psycopg2.extras

from .s3_registration_plan import (
    VERIFIED_SOURCES,
    _configured_storage_prefixes,
    _known_storage_layout,
    _owner_for_record,
    _positive_int,
    _reference_urls,
    _safe_storage_key,
    _sha256,
    _storage_key_from_url,
    _verify_s3_storage_key,
    load_s3_registration_rows,
)


PREVIEW_LIMIT = 100
ALLOWED_EXTENSIONS = frozenset((".heic", ".jpeg", ".jpg", ".pdf", ".png", ".webp"))
SOURCE_CONTEXTS = {
    "expenses.photo_url": frozenset(("expenses", "manual-expenses", "own-expenses")),
    "own_expenses.photo_url": frozenset(("own-expenses",)),
}


def _project_index(projects):
    result = {}
    for raw in projects or []:
        row = dict(raw or {})
        project_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        name = str(row.get("name") or "").strip()
        if project_id and company_id and name:
            result[project_id] = {
                "companyId": company_id,
                "name": name,
            }
    return result


def _name_fingerprint(value):
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "-".join(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _normalized_prefixes(storage_prefixes):
    result = []
    for raw in storage_prefixes or ():
        value = _safe_storage_key(raw)
        if value:
            result.append((value, value.split("/")))
    return sorted(result, key=lambda item: (-len(item[1]), item[0]))


def _legacy_key_parts(storage_key, storage_prefixes):
    parts = str(storage_key or "").split("/")
    for prefix, prefix_parts in _normalized_prefixes(storage_prefixes):
        index = len(prefix_parts)
        if parts[:index] != prefix_parts or len(parts) < index + 3:
            continue
        namespace = parts[index]
        context = parts[index + 1]
        if namespace.startswith("company-"):
            return None, "source_namespace_not_legacy"
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", context):
            return None, "legacy_context_invalid"
        return {
            "prefix": prefix,
            "projectSegment": namespace,
            "context": context,
        }, None
    return None, "source_storage_key_invalid"


def _safe_extension(storage_key):
    extension = posixpath.splitext(posixpath.basename(storage_key))[1].lower()
    return extension if extension in ALLOWED_EXTENSIONS else None


def _storage_base_for_url(file_url, storage_key, bases):
    encoded_key = quote(storage_key, safe="/")
    for base in bases:
        if file_url == base + encoded_key:
            return base
    return None


def _public_migration(item):
    return {
        "sourceUrlSha256": item["sourceUrlSha256"],
        "sourceKeySha256": item["sourceKeySha256"],
        "destinationUrlSha256": item["destinationUrlSha256"],
        "destinationKeySha256": item["destinationKeySha256"],
        "companyId": item["companyId"],
        "projectId": item["projectId"],
        "context": item["context"],
        "sources": item["sources"],
        "recordIds": item["recordIds"],
    }


def _prepare_s3_namespace_migration_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    verified_source_keys,
    storage_prefixes,
):
    bases, registered_urls, registered_keys, invalid_registry_rows = _known_storage_layout(
        ownership_rows
    )
    projects_by_id = _project_index(projects)
    owner_projects = {
        project_id: item["companyId"] for project_id, item in projects_by_id.items()
    }
    normalized_company_ids = {
        company_id
        for raw in (company_ids or set())
        for company_id in [_positive_int(raw)]
        if company_id
    }
    verified_source_keys = set(verified_source_keys or set())
    references = defaultdict(list)

    for raw in records or []:
        record = dict(raw or {})
        owner, status, reason = _owner_for_record(
            record,
            owner_projects,
            normalized_company_ids,
        )
        for file_url in _reference_urls(record.get("value")):
            references[file_url].append({
                "source": str(record.get("source") or ""),
                "recordId": _positive_int(record.get("recordId")),
                "owner": owner,
                "status": status,
                "reason": reason,
            })

    ready = []
    review = []
    already_registered = set(references) & registered_urls
    destination_keys = set()
    for file_url in sorted(set(references) - already_registered, key=_sha256):
        evidence = references[file_url]
        sources = sorted({item["source"] for item in evidence})
        record_ids = sorted({item["recordId"] for item in evidence if item["recordId"]})
        invalid = [item for item in evidence if item["status"] != "ready"]
        owners = {item["owner"] for item in evidence if item["owner"]}
        storage_key = _storage_key_from_url(file_url, bases)
        reason = None
        status = "unresolved"

        if invalid:
            selected = sorted(
                invalid,
                key=lambda item: 0 if item["status"] == "conflicting" else 1,
            )[0]
            status, reason = selected["status"], selected["reason"]
        elif len(owners) != 1:
            status, reason = "conflicting", "owner_conflict"
        elif not storage_key:
            reason = "storage_url_not_recognized"
        else:
            company_id, project_id = next(iter(owners))
            project = projects_by_id.get(project_id)
            layout, layout_error = _legacy_key_parts(storage_key, storage_prefixes)
            if not project or project["companyId"] != company_id:
                status, reason = "conflicting", "project_company_mismatch"
            elif layout_error:
                status = "conflicting" if layout_error == "source_namespace_not_legacy" else "unresolved"
                reason = layout_error
            elif _name_fingerprint(layout["projectSegment"]) != _name_fingerprint(project["name"]):
                status, reason = "conflicting", "legacy_project_name_mismatch"
            elif not any(
                layout["context"] in SOURCE_CONTEXTS.get(source, frozenset())
                for source in sources
            ):
                status, reason = "conflicting", "legacy_context_source_mismatch"
            elif storage_key not in verified_source_keys:
                reason = "source_object_not_verified"
            else:
                extension = _safe_extension(storage_key)
                storage_base = _storage_base_for_url(file_url, storage_key, bases)
                if not storage_base:
                    reason = "storage_url_not_recognized"
                elif not extension:
                    reason = "source_file_extension_not_allowed"
                else:
                    namespace = (
                        f"company-{company_id}-project-{project_id}-{layout['context']}"
                    )
                    destination_key = (
                        f"{layout['prefix']}/{namespace}/{layout['context']}/"
                        f"legacy-migrated/{_sha256(file_url)}{extension}"
                    )
                    destination_url = storage_base + quote(destination_key, safe="/")
                    if destination_key in registered_keys:
                        status, reason = "conflicting", "destination_key_already_registered"
                    elif destination_key in destination_keys:
                        status, reason = "conflicting", "destination_key_collision"

        if reason:
            review.append({
                "sourceUrlSha256": _sha256(file_url),
                "sourceKeySha256": _sha256(storage_key) if storage_key else None,
                "status": status,
                "reason": reason,
                "sources": sources,
                "recordIds": record_ids,
            })
            continue

        destination_keys.add(destination_key)
        ready.append({
            "sourceUrl": file_url,
            "sourceKey": storage_key,
            "destinationUrl": destination_url,
            "destinationKey": destination_key,
            "sourceUrlSha256": _sha256(file_url),
            "sourceKeySha256": _sha256(storage_key),
            "destinationUrlSha256": _sha256(destination_url),
            "destinationKeySha256": _sha256(destination_key),
            "companyId": company_id,
            "projectId": project_id,
            "context": layout["context"],
            "sources": sources,
            "recordIds": record_ids,
            "cells": sorted({
                (item["source"], item["recordId"])
                for item in evidence
                if item["recordId"]
            }),
        })

    public_ready = [_public_migration(item) for item in ready]
    blockers = sorted({item["reason"] for item in review})
    if invalid_registry_rows:
        blockers.append("invalid_s3_file_registration")
    blockers = sorted(set(blockers))
    review_counts = Counter(item["status"] for item in review)
    affected_cells = {
        cell for item in ready for cell in item["cells"]
    }
    payload = {
        "ready": public_ready,
        "review": review,
        "alreadyRegistered": sorted(_sha256(url) for url in already_registered),
        "invalidRegistryRows": invalid_registry_rows,
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    report = {
        "ok": True,
        "dryRun": True,
        "applySupported": False,
        "writesAttempted": 0,
        "readyForApply": not blockers,
        "summary": {
            "referenceCount": sum(len(items) for items in references.values()),
            "uniqueFileCount": len(references),
            "alreadyRegisteredUniqueFiles": len(already_registered),
            "readyObjectCopies": len(ready),
            "affectedCells": len(affected_cells),
            "needsReview": len(review),
            "unresolved": review_counts["unresolved"],
            "conflicting": review_counts["conflicting"],
            "invalidRegistryRows": invalid_registry_rows,
        },
        "blockers": blockers,
        "migrationsPreview": public_ready[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "migrationListTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }
    return report, ready


def build_s3_namespace_migration_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    verified_source_keys,
    storage_prefixes=("uploads",),
):
    report, _ready = _prepare_s3_namespace_migration_plan(
        records,
        ownership_rows,
        projects,
        company_ids,
        verified_source_keys,
        storage_prefixes,
    )
    return report


def _candidate_source_keys(
    records,
    ownership_rows,
    projects,
    company_ids,
    storage_prefixes,
):
    bases, registered_urls, _registered_keys, _invalid = _known_storage_layout(
        ownership_rows
    )
    recognized_keys = set()
    for raw in records or []:
        record = dict(raw or {})
        if str(record.get("source") or "") not in VERIFIED_SOURCES:
            continue
        for file_url in _reference_urls(record.get("value")):
            if file_url in registered_urls:
                continue
            storage_key = _storage_key_from_url(file_url, bases)
            if storage_key:
                recognized_keys.add(storage_key)

    # Treat recognized objects as present only to reuse the full ownership,
    # project, legacy-layout, context, extension, and collision policy.  The
    # returned keys are then the only objects the runner is allowed to open.
    _report, eligible = _prepare_s3_namespace_migration_plan(
        records,
        ownership_rows,
        projects,
        company_ids,
        verified_source_keys=recognized_keys,
        storage_prefixes=storage_prefixes,
    )
    return {item["sourceKey"] for item in eligible}


def run_s3_namespace_migration_plan(get_db, *, verify_storage_key=None):
    verifier = verify_storage_key or _verify_s3_storage_key
    storage_prefixes = _configured_storage_prefixes()
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows = load_s3_registration_rows(cur)
            verified_source_keys = {
                key
                for key in sorted(
                    _candidate_source_keys(*rows, storage_prefixes),
                    key=_sha256,
                )
                if verifier(key) is True
            }
            report, _ready = _prepare_s3_namespace_migration_plan(
                *rows,
                verified_source_keys=verified_source_keys,
                storage_prefixes=storage_prefixes,
            )
            conn.rollback()
            report["rolledBack"] = True
            return report
        finally:
            cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    from backend.db import get_db

    print(json.dumps(
        run_s3_namespace_migration_plan(get_db),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
