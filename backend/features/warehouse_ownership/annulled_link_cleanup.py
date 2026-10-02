"""Dry-run-first cleanup for live warehouse links to annulled supplier invoices."""

import argparse
import hashlib
import json
import re

import psycopg2.extensions
import psycopg2.extras


APPLY_CONFIRMATION = "APPLY_ANNULLED_WAREHOUSE_LINK_CLEANUP"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def classify_rows(rows):
    """Return a bounded, identifier-only classification of stale reverse links."""
    classified = []
    for raw in rows or []:
        row = dict(raw or {})
        warehouse_id = _positive_int(row.get("warehouse_invoice_id"))
        warehouse_company_id = _positive_int(row.get("warehouse_company_id"))
        supplier_id = _positive_int(row.get("supplier_invoice_id"))
        supplier_company_id = _positive_int(row.get("supplier_company_id"))
        if not warehouse_id or not warehouse_company_id or not supplier_id:
            classified.append({
                "warehouseInvoiceId": warehouse_id,
                "supplierInvoiceId": supplier_id,
                "companyId": warehouse_company_id,
                "status": "review",
                "reason": "link_identity_missing",
            })
            continue
        if supplier_company_id != warehouse_company_id:
            status, reason = "review", "company_mismatch"
        elif str(row.get("supplier_status") or "") != "Аннулирован":
            status, reason = "verified", "linked_supplier_invoice_active"
        elif str(row.get("warehouse_status") or "") == "Аннулирована":
            status, reason = "verified", "both_documents_inactive"
        elif bool(row.get("warehouse_payment_registered")):
            status, reason = "review", "warehouse_payment_document_registered"
        else:
            status, reason = "ready", "annulled_supplier_reverse_link"
        classified.append({
            "warehouseInvoiceId": warehouse_id,
            "supplierInvoiceId": supplier_id,
            "companyId": warehouse_company_id,
            "status": status,
            "reason": reason,
        })
    return classified


def _plan_sha256(ready):
    payload = sorted([
        [item["warehouseInvoiceId"], item["supplierInvoiceId"], item["companyId"]]
        for item in ready
    ])
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_report(rows):
    classified = classify_rows(rows)
    ready = [item for item in classified if item["status"] == "ready"]
    review = [item for item in classified if item["status"] == "review"]
    verified = [item for item in classified if item["status"] == "verified"]
    return {
        "ok": True,
        "dryRun": True,
        "totalLinkedRows": len(classified),
        "verifiedCount": len(verified),
        "readyCount": len(ready),
        "reviewCount": len(review),
        "readyForStrictRuntime": not ready and not review,
        "planSha256": _plan_sha256(ready),
        "cleanupPreview": ready[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "writesAttempted": 0,
        "updatedRows": 0,
        "rolledBack": False,
        "complete": False,
    }


def load_rows(cur):
    cur.execute(
        """SELECT w.id AS warehouse_invoice_id,
                  w.company_id AS warehouse_company_id,
                  COALESCE(w.status,'') AS warehouse_status,
                  w.supplier_invoice_id,
                  s.company_id AS supplier_company_id,
                  COALESCE(s.status,'') AS supplier_status,
                  EXISTS(
                    SELECT 1 FROM supplier_payment_documents d
                     WHERE d.company_id=w.company_id
                       AND d.document_kind='warehouse'
                       AND d.document_id=w.id
                  ) AS warehouse_payment_registered
             FROM warehouse_invoices w
             LEFT JOIN supplier_invoices s ON s.id=w.supplier_invoice_id
            WHERE w.supplier_invoice_id IS NOT NULL
            ORDER BY w.id"""
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def run_cleanup(conn, *, apply=False, expected_ready_count=None, expected_plan_sha256=None):
    if apply and (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("Apply requires a non-negative expected_ready_count")
    expected_sha = str(expected_plan_sha256 or "").strip().lower()
    if apply and not SHA_RE.fullmatch(expected_sha):
        raise ValueError("Apply requires a valid expected_plan_sha256")
    session = {"readonly": not apply, "autocommit": False}
    if apply:
        # Supplier-payment integrity triggers intentionally require the shared
        # company advisory lock and READ COMMITTED used by every ledger writer.
        session["isolation_level"] = psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED
    conn.set_session(**session)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if apply:
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute(
                """SELECT DISTINCT company_id
                     FROM warehouse_invoices
                    WHERE supplier_invoice_id IS NOT NULL
                    ORDER BY company_id"""
            )
            company_ids = [
                _positive_int((row or {}).get("company_id"))
                for row in (cur.fetchall() or [])
            ]
            if any(company_id is None for company_id in company_ids):
                raise RuntimeError("Linked warehouse company is missing")
            for company_id in company_ids:
                cur.execute(
                    "SELECT public.supplier_allocation_lock(%s)",
                    (company_id,),
                )
            cur.execute("LOCK TABLE supplier_invoices IN SHARE MODE")
            cur.execute("LOCK TABLE supplier_payment_documents IN SHARE MODE")
            cur.execute("LOCK TABLE warehouse_invoices IN SHARE ROW EXCLUSIVE MODE")
        rows = load_rows(cur)
        report = build_report(rows)
        report["dryRun"] = not apply
        if not apply:
            conn.rollback()
            report["rolledBack"] = True
            return report
        if (
            report["readyCount"] != expected_ready_count
            or report["planSha256"] != expected_sha
        ):
            raise RuntimeError("Cleanup plan changed; rerun dry-run")
        ready = [item for item in classify_rows(rows) if item["status"] == "ready"]
        report["writesAttempted"] = len(ready)
        for item in ready:
            cur.execute(
                """UPDATE warehouse_invoices
                      SET supplier_invoice_id=NULL
                    WHERE id=%s AND company_id=%s AND supplier_invoice_id=%s
                      AND COALESCE(status,'') <> 'Аннулирована'
                      AND EXISTS (
                        SELECT 1 FROM supplier_invoices s
                         WHERE s.id=%s AND s.company_id=%s
                           AND s.status='Аннулирован'
                      )
                      AND NOT EXISTS (
                        SELECT 1 FROM supplier_payment_documents d
                         WHERE d.company_id=%s AND d.document_kind='warehouse'
                           AND d.document_id=%s
                      )""",
                (
                    item["warehouseInvoiceId"], item["companyId"],
                    item["supplierInvoiceId"], item["supplierInvoiceId"],
                    item["companyId"], item["companyId"],
                    item["warehouseInvoiceId"],
                ),
            )
            report["updatedRows"] += int(cur.rowcount or 0)
        if report["updatedRows"] != len(ready):
            raise RuntimeError("Cleanup write conflict")
        post = build_report(load_rows(cur))
        if post["readyCount"] or post["reviewCount"]:
            raise RuntimeError("Cleanup post-check is not strict-ready")
        conn.commit()
        report["complete"] = True
        report["postcheck"] = {
            "totalLinkedRows": post["totalLinkedRows"],
            "readyForStrictRuntime": post["readyForStrictRuntime"],
        }
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Clean live warehouse reverse links to annulled supplier invoices"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=int)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("Choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error("--apply requires --confirm " + APPLY_CONFIRMATION)
    if args.apply and (
        args.expected_ready_count is None
        or not SHA_RE.fullmatch(str(args.expected_plan_sha256 or ""))
    ):
        parser.error("--apply requires exact count and SHA from dry-run")
    from backend.db import get_db
    conn = get_db()
    try:
        result = run_cleanup(
            conn,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
