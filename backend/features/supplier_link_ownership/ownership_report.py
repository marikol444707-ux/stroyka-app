"""Read-only ownership report for company-to-global-supplier links."""

import hashlib
import json
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _item(record_id, status, reason, company_id=None, supplier_id=None, platform_account_id=None):
    return {
        "table": "company_supplier_links",
        "recordId": _positive_int(record_id),
        "status": status,
        "reason": reason,
        "companyId": _positive_int(company_id),
        "supplierId": _positive_int(supplier_id),
        "platformAccountId": _positive_int(platform_account_id),
    }


def _classify_link(row, platform_account_ids, companies, supplier_ids):
    row = dict(row or {})
    record_id = _positive_int(row.get("id"))
    company_id = _positive_int(row.get("company_id"))
    supplier_id = _positive_int(row.get("supplier_id"))
    account_id = _positive_int(row.get("platform_account_id"))
    if not company_id:
        return _item(record_id, "unresolved", "company_owner_missing", supplier_id=supplier_id)
    company = companies.get(company_id)
    if not company:
        return _item(
            record_id, "unresolved", "company_not_found",
            company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
        )
    if not supplier_id:
        return _item(
            record_id, "unresolved", "supplier_parent_missing",
            company_id=company_id, platform_account_id=account_id,
        )
    if supplier_id not in supplier_ids:
        return _item(
            record_id, "unresolved", "supplier_not_found",
            company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
        )
    if not account_id:
        return _item(
            record_id, "verified", "verified_company_supplier_parents",
            company_id=company_id, supplier_id=supplier_id,
        )
    if account_id not in platform_account_ids:
        return _item(
            record_id, "unresolved", "platform_account_not_found",
            company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
        )
    company_account_id = _positive_int(company.get("platform_account_id"))
    if not company_account_id:
        return _item(
            record_id, "unresolved", "company_platform_account_missing",
            company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
        )
    if company_account_id != account_id:
        return _item(
            record_id, "mismatched", "platform_account_mismatch",
            company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
        )
    return _item(
        record_id, "verified", "verified_company_supplier_account",
        company_id=company_id, supplier_id=supplier_id, platform_account_id=account_id,
    )


def _plan_sha256(classified):
    plan = [
        [
            item["recordId"], item["status"], item["reason"], item["companyId"],
            item["supplierId"], item["platformAccountId"],
        ]
        for item in classified
    ]
    normalized = sorted(
        plan,
        key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")),
    )
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report_from_rows(rows):
    platform_account_ids = {
        account_id
        for row in (rows.get("platform_accounts") or [])
        for account_id in [_positive_int((row or {}).get("id"))]
        if account_id
    }
    companies = {
        company_id: dict(row or {})
        for row in (rows.get("companies") or [])
        for company_id in [_positive_int((row or {}).get("id"))]
        if company_id
    }
    supplier_ids = {
        supplier_id
        for row in (rows.get("suppliers") or [])
        for supplier_id in [_positive_int((row or {}).get("id"))]
        if supplier_id
    }
    classified = [
        _classify_link(row, platform_account_ids, companies, supplier_ids)
        for row in (rows.get("company_supplier_links") or [])
    ]
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "verified"]
    verified = [item for item in classified if item["status"] == "verified"]
    ready_by_company = Counter(str(item["companyId"]) for item in verified)
    return {
        "ok": True,
        "dryRun": True,
        "table": "company_supplier_links",
        "writesAttempted": 0,
        "readyForStrictRuntime": not review,
        "reportConsistent": len(classified) == sum(
            counts[name] for name in ("verified", "unresolved", "mismatched")
        ),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "readyByCompany": dict(sorted(ready_by_company.items())),
        "planSha256": _plan_sha256(classified),
        "verifiedPreview": verified[:PREVIEW_LIMIT],
        "needsReview": review[:PREVIEW_LIMIT],
        "previewTruncated": len(verified) > PREVIEW_LIMIT,
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    rows = {}
    queries = {
        "platform_accounts": "SELECT id FROM platform_accounts ORDER BY id",
        "companies": "SELECT id,platform_account_id FROM companies ORDER BY id",
        "suppliers": "SELECT id FROM suppliers ORDER BY id",
        "company_supplier_links": (
            "SELECT id,company_id,supplier_id,platform_account_id "
            "FROM company_supplier_links ORDER BY id"
        ),
    }
    for table, query in queries.items():
        cur.execute(query)
        rows[table] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows


def run_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_report_from_rows(load_ownership_rows(cur))
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
    print(json.dumps(run_ownership_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
