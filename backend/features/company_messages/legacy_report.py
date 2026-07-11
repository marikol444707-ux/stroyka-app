"""Read-only diagnostics for legacy company chat ownership."""

import json

import psycopg2.extras


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _company_ids(value):
    if not isinstance(value, (list, tuple, set)):
        return []
    return sorted({company_id for item in value for company_id in [_positive_int(item)] if company_id})


def _classify_candidate(row):
    item = dict(row or {})
    message_id = _positive_int(item.get("message_id"))
    author_id = _positive_int(item.get("author_id"))
    author_found = bool(item.get("author_found"))
    legacy_company_id = _positive_int(item.get("legacy_company_id"))
    active_company_ids = _company_ids(item.get("active_company_ids"))

    if not author_id:
        status = "unresolved"
        reason = "missing_author"
    elif not author_found:
        status = "unresolved"
        reason = "author_not_found"
    elif not legacy_company_id:
        status = "unresolved"
        reason = "missing_legacy_company"
    elif any(company_id != legacy_company_id for company_id in active_company_ids):
        status = "ambiguous"
        reason = "active_membership_conflict"
    else:
        status = "ready"
        reason = "single_company_membership" if active_company_ids else "legacy_company_only"

    return {
        "messageId": message_id,
        "authorId": author_id,
        "proposedCompanyId": legacy_company_id if status == "ready" else None,
        "activeCompanyIds": active_company_ids,
        "status": status,
        "reason": reason,
    }


def build_legacy_message_report(cur):
    cur.execute(
        """SELECT COUNT(*) FILTER (WHERE company_id IS NOT NULL) AS scoped_rows,
                  COUNT(*) FILTER (WHERE company_id IS NULL) AS legacy_rows
             FROM messages
            WHERE chat_type='company'"""
    )
    counts = dict(cur.fetchone() or {})
    cur.execute(
        """SELECT m.id AS message_id,
                  m.author_id,
                  (u.id IS NOT NULL) AS author_found,
                  u.company_id AS legacy_company_id,
                  COALESCE(
                      ARRAY_AGG(DISTINCT membership.company_id)
                          FILTER (WHERE membership.company_id IS NOT NULL),
                      ARRAY[]::INT[]
                  ) AS active_company_ids
             FROM messages m
             LEFT JOIN users u ON u.id=m.author_id
             LEFT JOIN user_company_roles membership
                    ON membership.user_id=m.author_id
                   AND COALESCE(membership.active,TRUE)=TRUE
            WHERE m.chat_type='company'
              AND m.company_id IS NULL
            GROUP BY m.id,m.author_id,u.id,u.company_id
            ORDER BY m.id"""
    )
    candidates = [_classify_candidate(row) for row in cur.fetchall()]
    status_counts = {
        status: sum(1 for candidate in candidates if candidate["status"] == status)
        for status in ("ready", "ambiguous", "unresolved")
    }
    scoped_rows = int(counts.get("scoped_rows") or 0)
    legacy_rows = int(counts.get("legacy_rows") or 0)
    report_consistent = legacy_rows == len(candidates)
    return {
        "ok": True,
        "dryRun": True,
        "table": "messages",
        "writesAttempted": 0,
        "readyForBackfill": report_consistent and not status_counts["ambiguous"] and not status_counts["unresolved"],
        "reportConsistent": report_consistent,
        "summary": {
            "scopedRows": scoped_rows,
            "legacyRows": legacy_rows,
            **status_counts,
        },
        "candidates": candidates,
    }


def run_legacy_message_report(get_db):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            return build_legacy_message_report(cur)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db

    report = run_legacy_message_report(get_db)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
