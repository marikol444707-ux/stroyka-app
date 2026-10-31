#!/usr/bin/env python3
"""Expire stale, unconverted public-site leads. Dry-run unless --apply is passed."""

import argparse
import json
import os
import re
from pathlib import Path

from backend.config import load_env_file
from backend.db import get_db
from backend.features.document_access.service import delete_document_local_file
from backend.features.document_access.storage import delete_s3_object


ROOT = Path(__file__).resolve().parents[1]
TENANT_FILE_RE = re.compile(r"^/tenant-files/(\d+)/content$")
CONTRACT_RE = re.compile(r"договор|контракт", re.IGNORECASE)


def _storage_config():
    load_env_file()
    return {
        "backend": os.getenv("STORAGE_BACKEND", "local").strip().lower(),
        "upload_dir": str(ROOT / "uploads"),
        "endpoint_url": (os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT") or "").rstrip("/"),
        "bucket": os.getenv("S3_BUCKET", "").strip(),
        "region": os.getenv("S3_REGION", "ru-central1").strip() or "ru-central1",
        "access_key": (os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "").strip(),
        "secret_key": (os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip(),
    }


def _eligible(cur, lead_id):
    cur.execute(
        """SELECT id,company_id,project_id,estimate_id,stage
             FROM crm_leads
            WHERE id=%s AND public_site_origin IS TRUE
              AND privacy_last_activity_at <= NOW() - INTERVAL '12 months'
              AND project_id IS NULL AND estimate_id IS NULL
              AND COALESCE(stage,'') IN ('Новый','Новая','Новая заявка','На проверке')
            FOR UPDATE""",
        (lead_id,),
    )
    lead = cur.fetchone()
    if not lead:
        return None, "not_eligible"
    cur.execute(
        """SELECT id,file_url,title,doc_type FROM crm_lead_documents
             WHERE lead_id=%s AND company_id=%s AND project_id IS NULL ORDER BY id""",
        (lead_id, lead[1]),
    )
    docs = cur.fetchall()
    cur.execute(
        """SELECT 1 FROM crm_lead_documents
             WHERE lead_id=%s AND (company_id IS DISTINCT FROM %s OR project_id IS NOT NULL)
             LIMIT 1""",
        (lead_id, lead[1]),
    )
    if cur.fetchone():
        return None, "document_owner_conflict"
    if any(CONTRACT_RE.search(" ".join(str(value or "") for value in row[2:])) for row in docs):
        return None, "contract_document_preserved"
    ownership_ids = []
    for _doc_id, file_url, _title, _doc_type in docs:
        url = str(file_url or "").strip()
        if not url:
            continue
        match = TENANT_FILE_RE.fullmatch(url)
        if not match:
            return None, "unmanaged_document_preserved"
        ownership_id = int(match.group(1))
        cur.execute(
            """SELECT id,file_url,storage_key,deletion_status,company_id
                 FROM file_ownership WHERE id=%s AND company_id=%s FOR UPDATE""",
            (ownership_id, lead[1]),
        )
        ownership = cur.fetchone()
        if not ownership:
            return None, "file_owner_missing"
        cur.execute("SELECT COUNT(*) FROM crm_lead_documents WHERE file_url=%s", (url,))
        if cur.fetchone()[0] != 1:
            return None, "shared_file_preserved"
        ownership_ids.append(ownership)
    return {"lead": lead, "docs": docs, "files": ownership_ids}, "ready"


def _remove_file(file_row, storage):
    ownership_id, file_url, storage_key, deletion_status, _company_id = file_row
    retrying = str(deletion_status or "").lower() in ("deleting", "cleanup_failed")
    if storage_key:
        if storage["backend"] != "s3" or not all(storage[k] for k in ("endpoint_url", "bucket", "access_key", "secret_key")):
            raise RuntimeError("s3_not_configured")
        deleted = delete_s3_object(
            key=storage_key, endpoint_url=storage["endpoint_url"], bucket=storage["bucket"],
            region=storage["region"], access_key=storage["access_key"], secret_key=storage["secret_key"],
        )
        if deleted is False and not retrying:
            raise RuntimeError("s3_object_missing")
    else:
        if storage["backend"] == "s3":
            raise RuntimeError("s3_key_missing")
        delete_document_local_file(storage["upload_dir"], file_url, missing_ok=retrying)
    return ownership_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform deletion; default is preview only")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    limit = max(1, min(args.limit, 500))
    storage = _storage_config()
    conn = get_db()
    conn.autocommit = False
    summary = {"mode": "apply" if args.apply else "dry-run", "ageMonths": 12, "limit": limit,
               "eligible": 0, "deleted": 0, "preserved": {}, "storageCleanupFailed": 0}
    lock_acquired = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute("SELECT pg_try_advisory_lock(hashtext('expire_public_site_leads'))")
            if not cur.fetchone()[0]:
                raise RuntimeError("retention_job_already_running")
            lock_acquired = True
            cur.execute(
                """SELECT id FROM crm_leads
                    WHERE public_site_origin IS TRUE
                      AND privacy_last_activity_at <= NOW() - INTERVAL '12 months'
                      AND project_id IS NULL AND estimate_id IS NULL
                      AND COALESCE(stage,'') IN ('Новый','Новая','Новая заявка','На проверке')
                    ORDER BY privacy_last_activity_at,id LIMIT %s""",
                (limit,),
            )
            ids = [row[0] for row in cur.fetchall()]
            conn.commit()

        for lead_id in ids:
            try:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='60s'")
                    candidate, state = _eligible(cur, lead_id)
                    if not candidate:
                        conn.rollback()
                        summary["preserved"][state] = summary["preserved"].get(state, 0) + 1
                        continue
                    summary["eligible"] += 1
                    if not args.apply:
                        conn.rollback()
                        continue

                    file_ids = [row[0] for row in candidate["files"]]
                    if file_ids:
                        cur.execute(
                            "UPDATE file_ownership SET deletion_status='deleting',deletion_error=NULL,deletion_requested_at=NOW() WHERE id=ANY(%s)",
                            (file_ids,),
                        )
                    conn.commit()

                    # Lock the eligible lead again and retain that lock through storage cleanup.
                    # CRM edits and child-record changes therefore cannot race the purge.
                    cur.execute("SET LOCAL statement_timeout='60s'")
                    candidate, state = _eligible(cur, lead_id)
                    if not candidate:
                        conn.rollback()
                        summary["preserved"][state] = summary["preserved"].get(state, 0) + 1
                        continue
                    deleted_files = []
                    try:
                        for file_row in candidate["files"]:
                            deleted_files.append(_remove_file(file_row, storage))
                    except Exception:
                        conn.rollback()
                        summary["storageCleanupFailed"] += 1
                        with conn.cursor() as failed_cur:
                            failed_cur.execute("SET LOCAL statement_timeout='15s'")
                            if file_ids:
                                failed_cur.execute(
                                    "UPDATE file_ownership SET deletion_status='cleanup_failed',deletion_error='retention_storage_cleanup_failed' WHERE id=ANY(%s)",
                                    (file_ids,),
                                )
                        conn.commit()
                        continue

                    if deleted_files:
                        cur.execute(
                            "DELETE FROM file_ownership WHERE id=ANY(%s)", (deleted_files,)
                        )
                    cur.execute("DELETE FROM crm_lead_documents WHERE lead_id=%s", (lead_id,))
                    cur.execute("DELETE FROM crm_lead_tasks WHERE lead_id=%s", (lead_id,))
                    cur.execute("DELETE FROM crm_leads WHERE id=%s", (lead_id,))
                    conn.commit()
                    summary["deleted"] += 1
            except Exception:
                conn.rollback()
                summary["preserved"]["processing_error"] = summary["preserved"].get("processing_error", 0) + 1
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        if summary["storageCleanupFailed"] or summary["preserved"].get("processing_error"):
            raise SystemExit(1)
    finally:
        if lock_acquired:
            try:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtext('expire_public_site_leads'))")
            except Exception:
                pass
        conn.close()


if __name__ == "__main__":
    main()
