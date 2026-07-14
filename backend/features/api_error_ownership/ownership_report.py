"""Read-only tenant ownership diagnostics for legacy api_errors rows."""

import hashlib
import json
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 100
PLATFORM_STAFF_ROLES = {
    "system_owner",
    "platform_admin",
    "platform_support",
    "billing_admin",
}
CLIENT_ACCOUNT_ROLES = {"account_owner", "account_admin"}


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _user_index(rows):
    return {
        user_id: dict(row or {})
        for row in rows or []
        for user_id in [_positive_int((row or {}).get("id"))]
        if user_id
    }


def _membership_index(rows):
    result = defaultdict(set)
    for raw in rows or []:
        row = dict(raw or {})
        if row.get("active") is False:
            continue
        user_id = _positive_int(row.get("user_id"))
        company_id = _positive_int(row.get("company_id"))
        if user_id and company_id:
            result[user_id].add(company_id)
    return result


def _role_scope(role):
    normalized = str(role or "").strip()
    if normalized in PLATFORM_STAFF_ROLES:
        return "platform"
    if normalized in CLIENT_ACCOUNT_ROLES:
        return "account"
    return "company" if normalized else ""


def classify_error_row(row, users_by_id, user_companies):
    item = dict(row or {})
    record_id = _positive_int(item.get("id"))
    user_id = _positive_int(item.get("user_id"))
    result = {
        "recordId": record_id,
        "status": "unresolved",
        "reason": "actor_missing",
        "scope": None,
        "companyId": None,
    }
    if not user_id:
        return result

    user = users_by_id.get(user_id)
    if not user:
        result["reason"] = "actor_not_found"
        return result
    if user.get("active") is False:
        result["reason"] = "actor_inactive"
        return result

    current_role_scope = _role_scope(user.get("role"))
    stored_role_scope = _role_scope(item.get("user_role"))
    if stored_role_scope and current_role_scope and stored_role_scope != current_role_scope:
        result.update(status="mismatched", reason="actor_role_scope_mismatch")
        return result

    role_scope = stored_role_scope or current_role_scope
    if role_scope == "platform":
        result.update(
            status="verified",
            reason="verified_platform_actor",
            scope="platform",
        )
        return result
    if role_scope == "account":
        result["reason"] = "account_scope_not_supported"
        return result

    company_ids = sorted(user_companies.get(user_id, set()))
    if not company_ids:
        result["reason"] = "active_actor_company_missing"
        return result
    if len(company_ids) > 1:
        result.update(status="ambiguous", reason="actor_company_ambiguous")
        return result

    result.update(
        status="verified",
        reason="verified_unique_actor_company",
        scope="company",
        companyId=company_ids[0],
    )
    return result


def review_plan_sha256(items):
    review = [item for item in items or [] if item.get("status") != "verified"]
    plan = [
        {
            "recordId": item.get("recordId"),
            "status": item.get("status"),
            "reason": item.get("reason"),
        }
        for item in sorted(review, key=lambda value: value.get("recordId") or 0)
    ]
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_ownership_rows(rows):
    rows = rows or {}
    errors = [dict(row or {}) for row in rows.get("api_errors", []) or []]
    users_by_id = _user_index(rows.get("users", []))
    user_companies = _membership_index(rows.get("user_company_roles", []))
    return [
        classify_error_row(row, users_by_id, user_companies)
        for row in errors
    ]


def build_report_from_rows(rows):
    rows = rows or {}
    errors = [dict(row or {}) for row in rows.get("api_errors", []) or []]
    classified = classify_ownership_rows(rows)
    counts = Counter(item["status"] for item in classified)
    verified = [item for item in classified if item["status"] == "verified"]
    review = [item for item in classified if item["status"] != "verified"]
    verified_by_company = Counter(
        str(item["companyId"])
        for item in verified
        if item.get("scope") == "company" and item.get("companyId")
    )
    methods = Counter(str(row.get("method") or "(missing)") for row in errors)
    review_reasons = Counter(item["reason"] for item in review)
    review_ids = [item["recordId"] for item in review if item.get("recordId")]
    platform_rows = sum(1 for item in verified if item.get("scope") == "platform")
    company_rows = sum(1 for item in verified if item.get("scope") == "company")
    return {
        "ok": True,
        "dryRun": True,
        "table": "api_errors",
        "writesAttempted": 0,
        "readyForMigration": not review,
        "reportConsistent": len(classified)
        == sum(counts[name] for name in ("verified", "ambiguous", "unresolved", "mismatched")),
        "summary": {
            "totalRows": len(classified),
            "verified": counts["verified"],
            "companyRows": company_rows,
            "platformRows": platform_rows,
            "ambiguous": counts["ambiguous"],
            "unresolved": counts["unresolved"],
            "mismatched": counts["mismatched"],
        },
        "byMethod": dict(sorted(methods.items())),
        "verifiedByCompany": dict(sorted(verified_by_company.items())),
        "reviewCount": len(review),
        "reviewByReason": dict(sorted(review_reasons.items())),
        "reviewIdRange": {
            "first": min(review_ids) if review_ids else None,
            "last": max(review_ids) if review_ids else None,
        },
        "reviewPlanSha256": review_plan_sha256(review),
        "needsReview": review[:PREVIEW_LIMIT],
        "reviewListTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_ownership_rows(cur):
    rows = {}
    cur.execute("SELECT id,user_id,user_role,method,status_code FROM api_errors ORDER BY id")
    rows["api_errors"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute("SELECT id,role,active,platform_account_id FROM users ORDER BY id")
    rows["users"] = [dict(row or {}) for row in (cur.fetchall() or [])]
    cur.execute(
        "SELECT user_id,company_id,active FROM user_company_roles ORDER BY user_id,company_id"
    )
    rows["user_company_roles"] = [dict(row or {}) for row in (cur.fetchall() or [])]
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
