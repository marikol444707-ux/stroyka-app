"""Guarded migration from public S3 object ACLs to private delivery.

The report contains only file identifiers and SHA-256 fingerprints. Apply is
explicit, count-and-hash guarded, and verifies the signed object ACL plus
authenticated content access after every update. It never deletes objects or
database rows. Bucket-level anonymous access is audited separately.
"""

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import psycopg2.extras
from fastapi import HTTPException

from backend.features.document_access.storage import (
    NoRedirectHandler,
    get_s3_object_acl_summary,
    open_s3_object,
    set_s3_object_acl,
)


APPLY_CONFIRMATION = "PRIVATIZE_VERIFIED_S3_OBJECTS"
PREVIEW_LIMIT = 100
ACCESS_STATES = frozenset(("public", "private", "missing", "unavailable"))


class S3PrivateAclError(RuntimeError):
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


def _safe_storage_key(value):
    raw = str(value or "").strip()
    if not raw or raw != raw.strip("/") or "\\" in raw or "\x00" in raw:
        return None
    if any(part in ("", ".", "..") for part in raw.split("/")):
        return None
    return raw


def _safe_https_url(value):
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    return raw


def _normalized_registry_rows(rows):
    normalized = []
    invalid_reasons = Counter()
    for raw_row in rows or []:
        row = dict(raw_row or {})
        file_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        verified_company_id = _positive_int(row.get("verified_company_id"))
        project_id = _positive_int(row.get("project_id"))
        project_company_id = _positive_int(row.get("project_company_id"))
        storage_key = _safe_storage_key(row.get("storage_key"))
        file_url = _safe_https_url(row.get("file_url"))
        reason = None
        if (
            not file_id
            or not company_id
            or verified_company_id != company_id
            or not storage_key
            or not file_url
        ):
            reason = "registry_identity_invalid"
        elif project_id and project_company_id != company_id:
            reason = "project_company_mismatch"
        elif not file_url.endswith("/" + urllib.parse.quote(storage_key, safe="/")):
            reason = "registry_url_key_mismatch"
        if reason:
            invalid_reasons[reason] += 1
            continue
        normalized.append({
            "fileId": file_id,
            "companyId": company_id,
            "projectId": project_id,
            "storageKey": storage_key,
        })
    return normalized, invalid_reasons


def _candidate_storage_keys(rows):
    normalized, _invalid = _normalized_registry_rows(rows)
    return sorted({item["storageKey"] for item in normalized}, key=_sha256)


def _prepare_s3_private_acl_plan(rows, *, acl_by_key, limit=None):
    normalized, invalid_reasons = _normalized_registry_rows(rows)
    key_counts = Counter(item["storageKey"] for item in normalized)
    duplicate_keys = {key for key, count in key_counts.items() if count > 1}
    access_counts = Counter()
    public_items = []
    unavailable_reasons = Counter()

    for item in normalized:
        key = item["storageKey"]
        if key in duplicate_keys:
            continue
        access = str((acl_by_key or {}).get(key) or "unavailable").strip().lower()
        if access not in ACCESS_STATES:
            access = "unavailable"
        access_counts[access] += 1
        if access == "public":
            public_items.append(item)
        elif access == "missing":
            unavailable_reasons["s3_object_missing"] += 1
        elif access == "unavailable":
            unavailable_reasons["s3_acl_check_unavailable"] += 1

    blockers = []
    if invalid_reasons:
        blockers.append("invalid_s3_registry_owner")
    if duplicate_keys:
        blockers.append("duplicate_s3_storage_key")
    blockers.extend(sorted(unavailable_reasons))

    normalized_limit = None
    if limit is not None:
        normalized_limit = _positive_int(limit)
        if normalized_limit is None:
            blockers.append("selection_limit_invalid")
    public_items.sort(key=lambda item: (_sha256(item["storageKey"]), item["fileId"]))
    selected = public_items if normalized_limit is None else public_items[:normalized_limit]

    plan_payload = {
        "registry": sorted(
            (
                item["fileId"],
                item["companyId"],
                item["projectId"],
                _sha256(item["storageKey"]),
                str((acl_by_key or {}).get(item["storageKey"]) or "unavailable"),
            )
            for item in normalized
        ),
        "invalidReasons": sorted(invalid_reasons.items()),
        "duplicateStorageKeys": sorted(_sha256(key) for key in duplicate_keys),
        "selectionLimit": normalized_limit,
        "selected": [_sha256(item["storageKey"]) for item in selected],
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(
            plan_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    ready = not blockers
    selected_preview = [
        {
            "fileId": item["fileId"],
            "storageKeySha256": _sha256(item["storageKey"]),
            "companyId": item["companyId"],
            "projectId": item["projectId"],
        }
        for item in selected[:PREVIEW_LIMIT]
    ]
    report = {
        "ok": True,
        "dryRun": True,
        "readyForApply": ready,
        "complete": ready and not public_items,
        "selectionMode": "full" if normalized_limit is None else "canary",
        "summary": {
            "registryS3Rows": len(rows or []),
            "validUniqueObjects": sum(
                1 for count in key_counts.values() if count == 1
            ),
            "publicAclObjects": access_counts["public"],
            "privateAclObjects": access_counts["private"],
            "missingAclObjects": access_counts["missing"],
            "unavailableAclObjects": access_counts["unavailable"],
            "selectedObjects": len(selected),
            "invalidRegistryRows": sum(invalid_reasons.values()),
            "duplicateStorageKeys": len(duplicate_keys),
        },
        "blockers": blockers,
        "invalidReasons": dict(sorted(invalid_reasons.items())),
        "selectedPreview": selected_preview,
        "reviewListTruncated": len(selected) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
        "writesAttempted": 0,
    }
    return report, selected if ready else []


def _storage_config():
    try:
        max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    except (TypeError, ValueError):
        max_bytes = 0
    return {
        "endpoint_url": os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT") or "",
        "bucket": os.getenv("S3_BUCKET", ""),
        "region": os.getenv("S3_REGION", "ru-central1"),
        "access_key": os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "",
        "secret_key": os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "",
        "max_bytes": max_bytes,
    }


def _anonymous_object_url(key, storage_config):
    endpoint_url = str(storage_config.get("endpoint_url") or "").rstrip("/")
    endpoint = urllib.parse.urlsplit(endpoint_url)
    bucket = str(storage_config.get("bucket") or "").strip()
    storage_key = _safe_storage_key(key)
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or not bucket
        or not storage_key
    ):
        raise S3PrivateAclError("s3_configuration_invalid")
    return (
        endpoint_url
        + "/"
        + urllib.parse.quote(bucket, safe="")
        + "/"
        + urllib.parse.quote(storage_key, safe="/")
    )


def probe_s3_object_access(key, *, storage_config=None, opener=None, timeout=15):
    config = dict(storage_config or _storage_config())
    url = _anonymous_object_url(key, config)
    request = urllib.request.Request(
        url,
        headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
        method="GET",
    )
    request_opener = opener or urllib.request.build_opener(NoRedirectHandler())
    try:
        response = request_opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        status = int(error.code or 0)
        try:
            error.close()
        except Exception:
            pass
        if status in (401, 403):
            return "private"
        if status == 404:
            return "missing"
        return "unavailable"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "unavailable"
    try:
        status = int(getattr(response, "status", response.getcode()) or 0)
        return "public" if status in (200, 206) else "unavailable"
    finally:
        response.close()


def _set_private_acl(key, storage_config):
    config = {name: value for name, value in storage_config.items() if name != "max_bytes"}
    try:
        return set_s3_object_acl(key=key, acl="private", **config)
    except HTTPException:
        raise S3PrivateAclError("s3_acl_update_failed") from None


def _inspect_object_acl(key, storage_config):
    config = {name: value for name, value in storage_config.items() if name != "max_bytes"}
    try:
        summary = get_s3_object_acl_summary(key=key, **config)
    except HTTPException as error:
        return "missing" if error.status_code == 404 else "unavailable"
    return "private" if summary.get("isPrivate") is True else "public"


def _verify_authenticated_access(key, storage_config):
    try:
        response, _size = open_s3_object(key=key, **storage_config)
    except HTTPException:
        return False
    response.close()
    return True


def load_s3_private_acl_rows(cur):
    cur.execute(
        """SELECT f.id,f.company_id,c.id AS verified_company_id,
                  f.project_id,f.file_url,f.storage_key,
                  p.company_id AS project_company_id
             FROM public.file_ownership f
             LEFT JOIN public.companies c ON c.id=f.company_id
             LEFT JOIN public.projects p ON p.id=f.project_id
            WHERE COALESCE(f.storage_key,'') <> ''
            ORDER BY f.id"""
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_selected_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise S3PrivateAclError("apply_confirmation_invalid")
    if not report.get("readyForApply"):
        raise S3PrivateAclError("private_acl_plan_not_ready")
    if _expected_int(expected_selected_count) != report["summary"]["selectedObjects"]:
        raise S3PrivateAclError("selected_count_mismatch")
    if str(expected_plan_sha256 or "") != report.get("planSha256"):
        raise S3PrivateAclError("plan_sha256_mismatch")


def run_s3_private_acl_migration(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_selected_count=None,
    expected_plan_sha256="",
    limit=None,
    load_rows=load_s3_private_acl_rows,
    inspect_acl=None,
    set_private_acl=None,
    verify_authenticated=None,
):
    config = _storage_config()
    inspector = inspect_acl or (lambda key: _inspect_object_acl(key, config))
    setter = set_private_acl or (lambda key: _set_private_acl(key, config))
    verifier = verify_authenticated or (
        lambda key: _verify_authenticated_access(key, config)
    )
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows = load_rows(cur)
            acl_by_key = {
                key: inspector(key)
                for key in _candidate_storage_keys(rows)
            }
            report, selected = _prepare_s3_private_acl_plan(
                rows,
                acl_by_key=acl_by_key,
                limit=limit,
            )
            if not apply:
                conn.rollback()
                report["rolledBack"] = True
                return report

            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_selected_count=expected_selected_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            writes = 0
            for item in selected:
                key = item["storageKey"]
                if setter(key) is not True:
                    raise S3PrivateAclError("s3_acl_update_unconfirmed")
                writes += 1
                if inspector(key) != "private":
                    raise S3PrivateAclError("s3_object_acl_still_public")
                if verifier(key) is not True:
                    raise S3PrivateAclError("signed_s3_access_failed")
            conn.rollback()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "writesAttempted": writes,
                "privatizedObjects": writes,
                "selectionMode": report["selectionMode"],
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
    print(json.dumps(run_s3_private_acl_migration(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
