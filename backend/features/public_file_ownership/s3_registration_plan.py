"""Guarded registration plan for legacy accounting files already stored in S3.

The public report contains hashes rather than URLs or object keys.  Only the
two accounting sources whose ownership was previously verified are eligible.
"""

import hashlib
import json
import mimetypes
import os
import posixpath
import re
from collections import Counter, defaultdict
from urllib.parse import quote, unquote, urlsplit

import psycopg2.extras


APPLY_CONFIRMATION = "REGISTER_VERIFIED_ACCOUNTING_S3_FILES"
PREVIEW_LIMIT = 100
VERIFIED_SOURCES = frozenset(("expenses.photo_url", "own_expenses.photo_url"))
HTTP_URL_PATTERN = re.compile(r"https?://[^\s,\"'<>\\]+", re.IGNORECASE)


class S3RegistrationPlanError(RuntimeError):
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


def _safe_http_url(value):
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.path
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    return raw


def _safe_storage_key(value):
    raw = str(value or "").strip()
    if not raw or raw != raw.strip("/") or "\\" in raw or "\x00" in raw:
        return None
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return raw


def _reference_urls(value):
    raw = str(value or "").strip()
    if not raw:
        return []
    matches = [match.group(0) for match in HTTP_URL_PATTERN.finditer(raw)]
    return matches or [raw]


def _known_storage_layout(ownership_rows):
    bases = set()
    registered_urls = set()
    registered_keys = defaultdict(list)
    invalid_rows = 0
    for raw in ownership_rows or []:
        row = dict(raw or {})
        file_url = _safe_http_url(row.get("file_url"))
        storage_key = _safe_storage_key(row.get("storage_key"))
        company_id = _positive_int(row.get("company_id"))
        if not file_url or not storage_key or not company_id:
            invalid_rows += 1
            continue
        encoded_key = quote(storage_key, safe="/")
        if not file_url.endswith("/" + encoded_key):
            invalid_rows += 1
            continue
        bases.add(file_url[: -len(encoded_key)])
        registered_urls.add(file_url)
        registered_keys[storage_key].append({
            "companyId": company_id,
            "projectId": _positive_int(row.get("project_id")),
            "fileUrl": file_url,
        })
    return (
        sorted(bases, key=lambda item: (-len(item), item)),
        registered_urls,
        registered_keys,
        invalid_rows,
    )


def _storage_key_from_url(value, bases):
    file_url = _safe_http_url(value)
    if not file_url:
        return None
    for base in bases:
        if not file_url.startswith(base):
            continue
        encoded_key = file_url[len(base):]
        if not encoded_key:
            continue
        storage_key = _safe_storage_key(unquote(encoded_key))
        if storage_key and quote(storage_key, safe="/") == encoded_key:
            return storage_key
    return None


def _project_index(projects):
    result = {}
    for raw in projects or []:
        row = dict(raw or {})
        project_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        if project_id and company_id:
            result[project_id] = company_id
    return result


def _normalized_storage_prefixes(storage_prefixes):
    result = []
    for raw in storage_prefixes or ():
        prefix = _safe_storage_key(raw)
        if prefix:
            result.append(prefix.split("/"))
    return result


def _storage_context_for_owner(
    storage_key,
    company_id,
    project_id,
    storage_prefixes,
):
    parts = str(storage_key or "").split("/")
    if len(parts) < 4:
        return None
    for prefix_parts in _normalized_storage_prefixes(storage_prefixes):
        index = len(prefix_parts)
        if parts[:index] != prefix_parts or len(parts) <= index + 2:
            continue
        context = parts[index + 1]
        normalized_context = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            context,
        ).strip("-")[:40] or "general"
        if context != normalized_context:
            continue
        if project_id:
            namespace = f"company-{company_id}-project-{project_id}-{context}"
        else:
            namespace = f"company-{company_id}-common-{context}"
        if parts[index] == namespace:
            return context
    return None


def _owner_for_record(record, projects_by_id, company_ids):
    source = str(record.get("source") or "")
    if source not in VERIFIED_SOURCES:
        return None, "unresolved", "source_not_allowlisted"
    if record.get("ownershipVerified") is not True:
        return None, "unresolved", "source_owner_not_verified"
    company_id = _positive_int(record.get("companyId"))
    project_id = _positive_int(record.get("projectId"))
    if not company_id or company_id not in company_ids:
        return None, "unresolved", "company_owner_missing"
    if project_id:
        project_company_id = projects_by_id.get(project_id)
        if not project_company_id:
            return None, "unresolved", "project_not_found"
        if project_company_id != company_id:
            return None, "conflicting", "project_company_mismatch"
    return (company_id, project_id), "ready", "verified_accounting_owner"


def _public_registration(item):
    return {
        "urlSha256": item["urlSha256"],
        "storageKeySha256": item["storageKeySha256"],
        "companyId": item["companyId"],
        "projectId": item["projectId"],
        "sources": item["sources"],
        "recordIds": item["recordIds"],
    }


def _prepare_s3_registration_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    verified_storage_keys,
    storage_prefixes,
):
    bases, registered_urls, registered_keys, invalid_registry_rows = _known_storage_layout(
        ownership_rows
    )
    projects_by_id = _project_index(projects)
    company_ids = {_positive_int(value) for value in (company_ids or set())}
    company_ids.discard(None)
    verified_storage_keys = set(verified_storage_keys or set())
    references = defaultdict(list)

    for raw in records or []:
        record = dict(raw or {})
        owner, status, reason = _owner_for_record(
            record,
            projects_by_id,
            company_ids,
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
    for file_url in sorted(set(references) - already_registered, key=_sha256):
        evidence = references[file_url]
        sources = sorted({item["source"] for item in evidence})
        record_ids = sorted({item["recordId"] for item in evidence if item["recordId"]})
        invalid = [item for item in evidence if item["status"] != "ready"]
        owners = {item["owner"] for item in evidence if item["owner"]}
        reason = None
        status = "unresolved"
        storage_key = None

        if invalid:
            selected = sorted(
                invalid,
                key=lambda item: 0 if item["status"] == "conflicting" else 1,
            )[0]
            status, reason = selected["status"], selected["reason"]
        elif len(owners) != 1:
            status, reason = "conflicting", "owner_conflict"
        else:
            company_id, project_id = next(iter(owners))
            storage_key = _storage_key_from_url(file_url, bases)
            storage_context = None
            if not storage_key:
                reason = "storage_url_not_recognized"
            else:
                storage_context = _storage_context_for_owner(
                    storage_key,
                    company_id,
                    project_id,
                    storage_prefixes,
                )
                if not storage_context:
                    status, reason = "conflicting", "storage_key_owner_mismatch"
                elif storage_key in registered_keys:
                    status, reason = "conflicting", "storage_key_already_registered"
                elif storage_key not in verified_storage_keys:
                    reason = "storage_object_not_verified"

        if reason:
            review.append({
                "urlSha256": _sha256(file_url),
                "storageKeySha256": _sha256(storage_key) if storage_key else None,
                "status": status,
                "reason": reason,
                "sources": sources,
                "recordIds": record_ids,
            })
            continue

        ready.append({
            "fileUrl": file_url,
            "storageKey": storage_key,
            "context": storage_context,
            "urlSha256": _sha256(file_url),
            "storageKeySha256": _sha256(storage_key),
            "companyId": company_id,
            "projectId": project_id,
            "sources": sources,
            "recordIds": record_ids,
        })

    public_ready = [_public_registration(item) for item in ready]
    payload = {
        "ready": public_ready,
        "review": review,
        "alreadyRegistered": sorted(_sha256(url) for url in already_registered),
        "invalidRegistryRows": invalid_registry_rows,
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()
    blockers = sorted({item["reason"] for item in review})
    if invalid_registry_rows:
        blockers.append("invalid_s3_file_registration")
    blockers = sorted(set(blockers))
    review_counts = Counter(item["status"] for item in review)
    report = {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "readyForApply": not blockers,
        "summary": {
            "referenceCount": sum(len(items) for items in references.values()),
            "uniqueFileCount": len(references),
            "alreadyRegisteredUniqueFiles": len(already_registered),
            "readyRegistrations": len(ready),
            "verifiedObjects": len(ready),
            "needsReview": len(review),
            "unresolved": review_counts["unresolved"],
            "conflicting": review_counts["conflicting"],
            "invalidRegistryRows": invalid_registry_rows,
        },
        "blockers": blockers,
        "registrationsPreview": public_ready[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "registrationListTruncated": len(ready) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
        "planSha256": plan_sha256,
    }
    return report, ready


def build_s3_registration_plan(
    records,
    ownership_rows,
    projects,
    company_ids,
    verified_storage_keys,
    storage_prefixes=("uploads",),
):
    report, _ready = _prepare_s3_registration_plan(
        records,
        ownership_rows,
        projects,
        company_ids,
        verified_storage_keys,
        storage_prefixes,
    )
    return report


def _row_dict(row):
    return dict(row) if isinstance(row, dict) else {}


def load_s3_registration_rows(cur):
    """Load only verified accounting photo sources plus S3 layout evidence."""
    cur.execute(
        """SELECT id,company_id,project_id,file_url,COALESCE(storage_key,'') AS storage_key
             FROM public.file_ownership
            WHERE COALESCE(storage_key,'') <> ''
            ORDER BY id"""
    )
    ownership_rows = [_row_dict(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,company_id FROM public.projects ORDER BY id")
    projects = [_row_dict(row) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id FROM public.companies ORDER BY id")
    company_ids = {
        company_id
        for row in (cur.fetchall() or [])
        for company_id in [_positive_int(_row_dict(row).get("id"))]
        if company_id
    }

    records = []
    for table in ("expenses", "own_expenses"):
        cur.execute(
            f"""SELECT id,photo_url,company_id,project_id,company_scope_verified
                   FROM public.{table}
                  WHERE NULLIF(BTRIM(photo_url),'') IS NOT NULL
                  ORDER BY id
                  LIMIT %s""",
            (10001,),
        )
        rows = list(cur.fetchall() or [])
        if len(rows) > 10000:
            raise S3RegistrationPlanError("source_limit_exceeded")
        for raw in rows:
            row = _row_dict(raw)
            records.append({
                "source": table + ".photo_url",
                "recordId": row.get("id"),
                "value": row.get("photo_url"),
                "companyId": row.get("company_id"),
                "projectId": row.get("project_id"),
                "ownershipVerified": row.get("company_scope_verified"),
            })
    return records, ownership_rows, projects, company_ids


def _candidate_storage_keys(
    records,
    ownership_rows,
    projects,
    company_ids,
    storage_prefixes,
):
    bases, registered_urls, _registered_keys, _invalid = _known_storage_layout(
        ownership_rows
    )
    projects_by_id = _project_index(projects)
    normalized_company_ids = {
        company_id
        for value in (company_ids or set())
        for company_id in [_positive_int(value)]
        if company_id
    }
    result = set()
    for raw in records or []:
        record = dict(raw or {})
        owner, status, _reason = _owner_for_record(
            record,
            projects_by_id,
            normalized_company_ids,
        )
        if status != "ready" or not owner:
            continue
        for file_url in _reference_urls(record.get("value")):
            if file_url in registered_urls:
                continue
            storage_key = _storage_key_from_url(file_url, bases)
            if not storage_key:
                continue
            if _storage_context_for_owner(
                storage_key,
                owner[0],
                owner[1],
                storage_prefixes,
            ):
                result.add(storage_key)
    return result


def _verify_s3_storage_key(storage_key):
    from fastapi import HTTPException

    from backend.features.document_access.storage import open_s3_object

    try:
        response, _content_length = open_s3_object(
            key=storage_key,
            endpoint_url=(
                os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT") or ""
            ),
            bucket=os.getenv("S3_BUCKET", ""),
            region=os.getenv("S3_REGION", "ru-central1"),
            access_key=(
                os.getenv("S3_ACCESS_KEY_ID")
                or os.getenv("AWS_ACCESS_KEY_ID")
                or ""
            ),
            secret_key=(
                os.getenv("S3_SECRET_ACCESS_KEY")
                or os.getenv("AWS_SECRET_ACCESS_KEY")
                or ""
            ),
            max_bytes=int(
                os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
            ),
        )
    except HTTPException as error:
        if error.status_code in (404, 413):
            return False
        raise S3RegistrationPlanError("storage_verification_unavailable") from None
    response.close()
    return True


def _verified_storage_keys(
    records,
    ownership_rows,
    projects,
    company_ids,
    storage_prefixes,
    verifier,
):
    verified = set()
    candidates = _candidate_storage_keys(
        records,
        ownership_rows,
        projects,
        company_ids,
        storage_prefixes,
    )
    for storage_key in sorted(candidates, key=_sha256):
        if verifier(storage_key) is True:
            verified.add(storage_key)
    return verified


def _configured_storage_prefixes():
    return tuple(dict.fromkeys(
        value
        for value in (
            os.getenv("S3_PREFIX", "uploads"),
            *os.getenv("S3_LEGACY_PREFIXES", "").split(","),
        )
        if str(value or "").strip()
    ))


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_ready_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise S3RegistrationPlanError("apply_confirmation_invalid")
    if not report["readyForApply"]:
        raise S3RegistrationPlanError("registration_plan_not_ready")
    if _expected_int(expected_ready_count) != report["summary"]["readyRegistrations"]:
        raise S3RegistrationPlanError("ready_count_mismatch")
    if str(expected_plan_sha256 or "") != report["planSha256"]:
        raise S3RegistrationPlanError("plan_sha256_mismatch")


def _file_metadata(storage_key):
    name = unquote(posixpath.basename(storage_key)).strip() or "accounting-file"
    return name, mimetypes.guess_type(name)[0] or "application/octet-stream"


def _apply_registrations(cur, registrations):
    writes = 0
    for item in registrations:
        original_name, content_type = _file_metadata(item["storageKey"])
        cur.execute(
            """INSERT INTO public.file_ownership
                      (company_id,project_id,file_url,storage_key,context,
                       original_name,content_type,uploaded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (file_url) DO NOTHING
               RETURNING id""",
            (
                item["companyId"],
                item["projectId"],
                item["fileUrl"],
                item["storageKey"],
                item["context"],
                original_name,
                content_type,
                "system:verified-accounting-s3-registration",
            ),
        )
        if not cur.fetchone():
            raise S3RegistrationPlanError("concurrent_registration_conflict")
        writes += 1
    return writes


def run_s3_registration_plan(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_ready_count=None,
    expected_plan_sha256="",
    verify_storage_key=None,
):
    verifier = verify_storage_key or _verify_s3_storage_key
    storage_prefixes = _configured_storage_prefixes()
    conn = get_db()
    try:
        if apply:
            conn.set_session(
                readonly=False,
                autocommit=False,
                isolation_level="SERIALIZABLE",
            )
        else:
            conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rows = load_s3_registration_rows(cur)
            verified_keys = _verified_storage_keys(
                *rows,
                storage_prefixes,
                verifier,
            )
            report, registrations = _prepare_s3_registration_plan(
                *rows,
                verified_storage_keys=verified_keys,
                storage_prefixes=storage_prefixes,
            )
            if not apply:
                conn.rollback()
                report["rolledBack"] = True
                return report

            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_ready_count=expected_ready_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute("LOCK TABLE public.file_ownership IN ACCESS EXCLUSIVE MODE")
            cur.execute("LOCK TABLE public.expenses,public.own_expenses IN SHARE MODE")
            cur.execute("LOCK TABLE public.projects,public.companies IN SHARE MODE")
            locked_rows = load_s3_registration_rows(cur)
            locked_report, registrations = _prepare_s3_registration_plan(
                *locked_rows,
                verified_storage_keys=verified_keys,
                storage_prefixes=storage_prefixes,
            )
            _validate_apply_guards(
                locked_report,
                confirm=confirm,
                expected_ready_count=expected_ready_count,
                expected_plan_sha256=expected_plan_sha256,
            )
            writes = _apply_registrations(cur, registrations)
            if writes != locked_report["summary"]["readyRegistrations"]:
                raise S3RegistrationPlanError("write_count_mismatch")
            conn.commit()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "writesAttempted": writes,
                "registeredCount": writes,
                "appliedPlanSha256": locked_report["planSha256"],
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
    print(json.dumps(run_s3_registration_plan(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
