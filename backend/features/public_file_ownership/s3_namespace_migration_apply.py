"""Guarded executor for the verified accounting S3 namespace migration.

The read-only planner remains the source of truth.  Applying requires exact
counts plus its SHA-256 and never removes a legacy source object.
"""

import hashlib
import json
import mimetypes
import os
import posixpath
from collections import defaultdict

import psycopg2.extras
from fastapi import HTTPException
from psycopg2 import sql

from backend.features.document_access.storage import open_s3_object, put_s3_object

from .s3_reference_cutover import _rewrite_value
from .s3_namespace_migration_plan import (
    _candidate_source_keys,
    _configured_storage_prefixes,
    _prepare_s3_namespace_migration_plan,
    _verify_s3_storage_key,
    load_s3_registration_rows,
)


APPLY_CONFIRMATION = "MIGRATE_VERIFIED_ACCOUNTING_S3_NAMESPACE"


class S3NamespaceMigrationApplyError(RuntimeError):
    pass


def _storage_config():
    return {
        "endpoint_url": os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT") or "",
        "bucket": os.getenv("S3_BUCKET", ""),
        "region": os.getenv("S3_REGION", "ru-central1"),
        "access_key": (
            os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or ""
        ),
        "secret_key": (
            os.getenv("S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or ""
        ),
        "max_bytes": int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))),
    }


def _read_storage_object(key, *, open_object, storage_config):
    try:
        response, content_length = open_object(key=key, **storage_config)
    except HTTPException:
        raise
    try:
        content = response.read(content_length + 1)
    finally:
        response.close()
    if len(content) != content_length:
        raise S3NamespaceMigrationApplyError("storage_content_length_mismatch")
    if len(content) > storage_config["max_bytes"]:
        raise S3NamespaceMigrationApplyError("storage_object_too_large")
    return content


def _copy_storage_object_verified(
    source_key,
    destination_key,
    *,
    open_object=open_s3_object,
    put_object=put_s3_object,
    storage_config=None,
):
    config = dict(storage_config or _storage_config())
    max_bytes = int(config.get("max_bytes") or 0)
    if max_bytes <= 0:
        raise S3NamespaceMigrationApplyError("storage_size_limit_invalid")
    config["max_bytes"] = max_bytes
    source = _read_storage_object(
        source_key,
        open_object=open_object,
        storage_config=config,
    )
    source_sha256 = hashlib.sha256(source).hexdigest()

    try:
        destination = _read_storage_object(
            destination_key,
            open_object=open_object,
            storage_config=config,
        )
    except HTTPException as error:
        if error.status_code != 404:
            raise S3NamespaceMigrationApplyError(
                "destination_verification_unavailable"
            ) from None
        destination = None

    created = destination is None
    if destination is not None:
        if hashlib.sha256(destination).hexdigest() != source_sha256:
            raise S3NamespaceMigrationApplyError("destination_content_conflict")
    else:
        content_type = (
            mimetypes.guess_type(posixpath.basename(destination_key))[0]
            or "application/octet-stream"
        )
        put_config = {key: value for key, value in config.items() if key != "max_bytes"}
        try:
            put_object(
                key=destination_key,
                content=source,
                content_type=content_type,
                **put_config,
            )
        except HTTPException:
            raise S3NamespaceMigrationApplyError("destination_write_failed") from None
        destination = _read_storage_object(
            destination_key,
            open_object=open_object,
            storage_config=config,
        )
        if hashlib.sha256(destination).hexdigest() != source_sha256:
            raise S3NamespaceMigrationApplyError("destination_verification_failed")

    return {
        "sha256": source_sha256,
        "sizeBytes": len(source),
        "created": created,
    }


def _expected_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _validate_apply_guards(
    report,
    *,
    confirm,
    expected_copy_count,
    expected_affected_cell_count,
    expected_plan_sha256,
):
    if confirm != APPLY_CONFIRMATION:
        raise S3NamespaceMigrationApplyError("apply_confirmation_invalid")
    if not report.get("readyForApply"):
        raise S3NamespaceMigrationApplyError("migration_plan_not_ready")
    summary = report.get("summary") or {}
    if _expected_int(expected_copy_count) != summary.get("readyObjectCopies"):
        raise S3NamespaceMigrationApplyError("copy_count_mismatch")
    if (
        _expected_int(expected_affected_cell_count)
        != summary.get("affectedCells")
    ):
        raise S3NamespaceMigrationApplyError("affected_cell_count_mismatch")
    if str(expected_plan_sha256 or "") != report.get("planSha256"):
        raise S3NamespaceMigrationApplyError("plan_sha256_mismatch")


def _build_cell_updates(records, migrations):
    records_by_cell = {
        (str(record.get("source") or ""), record.get("recordId")): record
        for record in (records or [])
    }
    replacements_by_cell = defaultdict(dict)
    for migration in migrations or []:
        for raw_cell in migration.get("cells") or []:
            cell = tuple(raw_cell)
            replacements_by_cell[cell][migration["sourceUrl"]] = migration[
                "destinationUrl"
            ]

    updates = []
    for cell in sorted(replacements_by_cell):
        record = records_by_cell.get(cell)
        if not record:
            raise S3NamespaceMigrationApplyError("planned_cell_missing")
        old_value = str(record.get("value") or "")
        new_value, reference_count = _rewrite_value(
            old_value,
            replacements_by_cell[cell],
        )
        if reference_count != len(replacements_by_cell[cell]):
            raise S3NamespaceMigrationApplyError("planned_reference_missing")
        if new_value == old_value:
            raise S3NamespaceMigrationApplyError("planned_reference_unchanged")
        updates.append({
            "source": cell[0],
            "recordId": cell[1],
            "oldValue": old_value,
            "newValue": new_value,
            "referenceCount": reference_count,
        })
    return updates


SOURCE_COLUMNS = {
    "expenses.photo_url": ("expenses", "photo_url"),
    "own_expenses.photo_url": ("own_expenses", "photo_url"),
}


def _apply_database_changes(cur, records, migrations):
    registered_files = 0
    protected_migrations = []
    for item in migrations:
        original_name = posixpath.basename(item["destinationKey"]) or "accounting-file"
        content_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
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
                item["destinationUrl"],
                item["destinationKey"],
                item["context"],
                original_name,
                content_type,
                "system:verified-accounting-s3-namespace-migration",
            ),
        )
        inserted = cur.fetchone()
        if not inserted:
            raise S3NamespaceMigrationApplyError("concurrent_registration_conflict")
        file_id = _expected_int(dict(inserted).get("id"))
        if not file_id:
            raise S3NamespaceMigrationApplyError("registered_file_id_invalid")
        protected_migrations.append({
            **item,
            "destinationUrl": f"/tenant-files/{file_id}/content",
        })
        registered_files += 1

    updates = _build_cell_updates(records, protected_migrations)
    updated_cells = 0
    rewritten_references = 0
    for item in updates:
        source = item["source"]
        if source not in SOURCE_COLUMNS:
            raise S3NamespaceMigrationApplyError("source_not_allowlisted")
        table, column = SOURCE_COLUMNS[source]
        query = sql.SQL(
            "UPDATE {table} SET {column}=%s "
            "WHERE id=%s AND {column}=%s RETURNING id"
        ).format(
            table=sql.Identifier("public", table),
            column=sql.Identifier(column),
        )
        cur.execute(
            query,
            (item["newValue"], item["recordId"], item["oldValue"]),
        )
        if not cur.fetchone():
            raise S3NamespaceMigrationApplyError("concurrent_source_change")
        updated_cells += 1
        rewritten_references += item["referenceCount"]
    return updated_cells, rewritten_references, registered_files


def run_s3_namespace_migration_apply(
    get_db,
    *,
    apply=False,
    confirm="",
    expected_copy_count=None,
    expected_affected_cell_count=None,
    expected_plan_sha256="",
    verify_storage_key=None,
    migrate_storage_object=None,
):
    verifier = verify_storage_key or _verify_s3_storage_key
    migrate_object = migrate_storage_object or (
        lambda source_key, destination_key: _copy_storage_object_verified(
            source_key,
            destination_key,
        )
    )
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
            candidate_keys = _candidate_source_keys(*rows, storage_prefixes)
            verified_keys = {
                key
                for key in sorted(candidate_keys, key=lambda value: hashlib.sha256(
                    value.encode("utf-8")
                ).hexdigest())
                if verifier(key) is True
            }
            report, _migrations = _prepare_s3_namespace_migration_plan(
                *rows,
                verified_source_keys=verified_keys,
                storage_prefixes=storage_prefixes,
            )
            if not apply:
                conn.rollback()
                report["applySupported"] = True
                report["rolledBack"] = True
                return report

            _validate_apply_guards(
                report,
                confirm=confirm,
                expected_copy_count=expected_copy_count,
                expected_affected_cell_count=expected_affected_cell_count,
                expected_plan_sha256=expected_plan_sha256,
            )

            # Copy before taking table locks.  A failed later database check can
            # leave only a harmless, deterministic unregistered destination;
            # reruns verify and reuse it.  Legacy sources are never deleted.
            copy_results = []
            for item in _migrations:
                result = dict(migrate_object(
                    item["sourceKey"],
                    item["destinationKey"],
                ) or {})
                digest = str(result.get("sha256") or "")
                if not (
                    len(digest) == 64
                    and all(character in "0123456789abcdef" for character in digest)
                    and _expected_int(result.get("sizeBytes")) is not None
                ):
                    raise S3NamespaceMigrationApplyError("copy_verification_invalid")
                copy_results.append(result)
            if len(copy_results) != report["summary"]["readyObjectCopies"]:
                raise S3NamespaceMigrationApplyError("copy_count_mismatch")

            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("LOCK TABLE public.file_ownership IN ACCESS EXCLUSIVE MODE")
            cur.execute(
                "LOCK TABLE public.expenses,public.own_expenses "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
            cur.execute("LOCK TABLE public.projects,public.companies IN SHARE MODE")

            locked_rows = load_s3_registration_rows(cur)
            locked_report, migrations = _prepare_s3_namespace_migration_plan(
                *locked_rows,
                verified_source_keys=verified_keys,
                storage_prefixes=storage_prefixes,
            )
            _validate_apply_guards(
                locked_report,
                confirm=confirm,
                expected_copy_count=expected_copy_count,
                expected_affected_cell_count=expected_affected_cell_count,
                expected_plan_sha256=expected_plan_sha256,
            )

            if len(copy_results) != locked_report["summary"]["readyObjectCopies"]:
                raise S3NamespaceMigrationApplyError("copy_count_mismatch")

            updates = _build_cell_updates(locked_rows[0], migrations)
            if len(updates) != locked_report["summary"]["affectedCells"]:
                raise S3NamespaceMigrationApplyError("affected_cell_count_mismatch")
            updated_cells, rewritten_references, registered_files = (
                _apply_database_changes(cur, locked_rows[0], migrations)
            )
            if updated_cells != len(updates) or registered_files != len(migrations):
                raise S3NamespaceMigrationApplyError("write_count_mismatch")
            conn.commit()
            return {
                "ok": True,
                "dryRun": False,
                "committed": True,
                "rolledBack": False,
                "objectCopyCount": len(copy_results),
                "newObjectCount": sum(
                    1 for result in copy_results if result.get("created") is True
                ),
                "reusedObjectCount": sum(
                    1 for result in copy_results if result.get("created") is not True
                ),
                "updatedCellCount": updated_cells,
                "rewrittenReferenceCount": rewritten_references,
                "registeredFileCount": registered_files,
                "writesAttempted": updated_cells + registered_files,
                "sourceObjectsDeleted": 0,
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
    from backend.db import get_db

    print(json.dumps(
        run_s3_namespace_migration_apply(get_db),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
