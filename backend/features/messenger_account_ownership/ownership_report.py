"""Read-only ownership diagnostics for shared messenger identities."""

import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
SUPPORTED_PROVIDERS = {"max", "telegram"}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _identity_duplicates(accounts, field):
    grouped = defaultdict(list)
    for raw in accounts or []:
        row = dict(raw or {})
        provider = str(row.get("provider") or "").strip().lower()
        value = str(row.get(field) or "").strip()
        account_id = _positive_int(row.get("id"))
        if provider and value and account_id:
            grouped[(provider, value)].append(account_id)
    return {
        account_id
        for account_ids in grouped.values()
        if len(account_ids) > 1
        for account_id in account_ids
    }


def _classification(row, status, reason, company_ids=()):
    item = dict(row or {})
    user_id = _positive_int(item.get("user_id"))
    staff_id = _positive_int(item.get("staff_id"))
    return {
        "recordId": _positive_int(item.get("id")),
        "provider": str(item.get("provider") or "").strip().lower(),
        "enabled": item.get("enabled") is not False,
        "targetType": "user" if user_id and not staff_id else "staff" if staff_id and not user_id else "",
        "targetId": user_id if user_id and not staff_id else staff_id if staff_id and not user_id else None,
        "companyIds": sorted({_positive_int(value) for value in company_ids if _positive_int(value)}),
        "status": status,
        "reason": reason,
    }


def _classify_account(row, users, user_companies, staff, duplicate_external, duplicate_chat):
    item = dict(row or {})
    account_id = _positive_int(item.get("id"))
    provider = str(item.get("provider") or "").strip().lower()
    user_id = _positive_int(item.get("user_id"))
    staff_id = _positive_int(item.get("staff_id"))

    if not provider:
        return _classification(item, "unresolved", "provider_missing")
    if provider not in SUPPORTED_PROVIDERS:
        return _classification(item, "unresolved", "provider_unsupported")
    if user_id and staff_id:
        return _classification(item, "unresolved", "multiple_employee_targets")
    if not user_id and not staff_id:
        return _classification(item, "unresolved", "employee_target_missing")
    if not str(item.get("external_user_id") or "").strip() and not str(item.get("chat_id") or "").strip():
        return _classification(item, "unresolved", "messenger_identity_missing")

    if user_id:
        user = users.get(user_id)
        if not user:
            return _classification(item, "unresolved", "user_not_found")
        if user.get("active") is False:
            return _classification(item, "unresolved", "user_inactive")
        company_ids = sorted(user_companies.get(user_id, set()))
        if not company_ids:
            return _classification(item, "unresolved", "active_user_company_missing")
    else:
        employee = staff.get(staff_id)
        if not employee:
            return _classification(item, "unresolved", "staff_not_found")
        company_id = _positive_int(employee.get("company_id"))
        if not company_id:
            return _classification(item, "unresolved", "staff_company_missing")
        company_ids = [company_id]

    if account_id in duplicate_external:
        return _classification(item, "ambiguous", "duplicate_external_identity", company_ids)
    if account_id in duplicate_chat:
        return _classification(item, "ambiguous", "duplicate_chat_identity", company_ids)
    return _classification(item, "verified", "verified_employee_companies", company_ids)


def build_report_from_rows(rows):
    accounts = [dict(row or {}) for row in (rows.get("messenger_accounts", []) or [])]
    users = {
        user_id: dict(row or {})
        for row in (rows.get("users", []) or [])
        for user_id in [_positive_int((row or {}).get("id"))]
        if user_id
    }
    user_companies = defaultdict(set)
    for raw in rows.get("user_company_roles", []) or []:
        row = dict(raw or {})
        if row.get("active") is False:
            continue
        user_id = _positive_int(row.get("user_id"))
        company_id = _positive_int(row.get("company_id"))
        if user_id and company_id:
            user_companies[user_id].add(company_id)
    staff = {
        staff_id: dict(row or {})
        for row in (rows.get("staff", []) or [])
        for staff_id in [_positive_int((row or {}).get("id"))]
        if staff_id
    }

    duplicate_external = _identity_duplicates(accounts, "external_user_id")
    duplicate_chat = _identity_duplicates(accounts, "chat_id")
    classified = [
        _classify_account(
            row,
            users,
            user_companies,
            staff,
            duplicate_external,
            duplicate_chat,
        )
        for row in accounts
    ]
    counts = Counter(item["status"] for item in classified)
    review = [item for item in classified if item["status"] != "verified"]
    verified_by_company = Counter(
        str(company_id)
        for item in classified
        if item["status"] == "verified"
        for company_id in item["companyIds"]
    )
    provider_counts = Counter(item["provider"] or "(missing)" for item in classified)
    enabled_counts = Counter("enabled" if item["enabled"] else "disabled" for item in classified)
    shared_accounts = sum(
        1 for item in classified if item["status"] == "verified" and len(item["companyIds"]) > 1
    )
    return {
        "ok": True,
        "dryRun": True,
        "table": "messenger_accounts",
        "writesAttempted": 0,
        "readyForRuntime": not review,
        "reportConsistent": len(classified)
        == sum(counts[name] for name in ("verified", "ambiguous", "unresolved", "mismatched")),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "sharedAccounts": shared_accounts,
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byProvider": dict(sorted(provider_counts.items())),
        "byState": dict(sorted(enabled_counts.items())),
        "verifiedByCompany": dict(sorted(verified_by_company.items())),
        "needsReview": review[:PREVIEW_LIMIT],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    rows = {}
    cur.execute(
        "SELECT id,provider,user_id,staff_id,external_user_id,chat_id,enabled "
        "FROM messenger_accounts ORDER BY id"
    )
    rows["messenger_accounts"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,active FROM users ORDER BY id")
    rows["users"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        "SELECT user_id,company_id,active FROM user_company_roles ORDER BY user_id,company_id"
    )
    rows["user_company_roles"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,company_id FROM staff ORDER BY id")
    rows["staff"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows


def run_ownership_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_report_from_rows(load_ownership_rows(cur))
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
