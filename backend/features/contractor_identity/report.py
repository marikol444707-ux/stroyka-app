"""Company-scoped legacy identity audit. No migration or access-grant command."""
import argparse
from collections import Counter
import hashlib
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

from .identity import classify_reference, positive_id
from .evidence import REFERENCE_EVIDENCE_SQL


def collect_report(cur, company_id, *, limit=100, offset=0):
    company_id = positive_id(company_id)
    if type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or not 0 <= offset <= 2147483647:
        raise ValueError('INVALID_PAGE')
    cur.execute('SHOW transaction_read_only')
    if cur.fetchone()['transaction_read_only'] != 'on':
        raise ValueError('READ_ONLY_TRANSACTION_REQUIRED')
    cur.execute('SELECT id,platform_account_id,active FROM companies WHERE id=%s', (company_id,))
    company = cur.fetchone()
    if not company:
        raise ValueError('COMPANY_UNAVAILABLE')
    cur.execute(REFERENCE_EVIDENCE_SQL + ' WHERE bc.company_id=%s ORDER BY bc.id LIMIT %s OFFSET %s',
        (company_id, limit+1, offset))
    rows = [dict(row) for row in cur.fetchall()]
    has_more = len(rows) > limit
    items = [classify_reference(row) for row in rows[:limit]]
    # Hash the exact input, including frozen-party contents and current links,
    # but never disclose names, contacts, banking fields or originals in output.
    evidence = {'company': dict(company), 'rows': rows, 'limit': limit, 'offset': offset}
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False,
                                      separators=(',', ':')).encode()).hexdigest()
    blockers = []
    if company['active'] is not True:
        blockers.append('COMPANY_INACTIVE')
    try:
        positive_id(company['platform_account_id'])
    except ValueError:
        blockers.append('COMPANY_ACCOUNT_UNVERIFIED')
    if has_more:
        blockers.append('PAGE_INCOMPLETE')
    if any(item['status'] == 'blocked' for item in items):
        blockers.append('LEGACY_REFERENCES_REQUIRE_REVIEW')
    return {'reportVersion': 1, 'companyId': company_id, 'scope': 'company_page_only',
            'status': 'blocked' if blockers else 'review_required', 'blockers': blockers,
            'items': items, 'counts': dict(sorted(Counter(item['reason'] for item in items).items())),
            'limit': limit, 'offset': offset, 'hasMore': has_more, 'evidenceSha256': digest,
            'canApply': False, 'accessGranted': False, 'changesMade': False}


def run_audit(get_db, company_id, *, limit=100, offset=0):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='10s'")
            cur.execute("SET LOCAL lock_timeout='2s'")
            report = collect_report(cur, company_id, limit=limit, offset=offset)
        return {**report, 'readOnlyTransaction': True, 'rolledBack': True}
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--company-id', required=True, type=int)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--read-only', required=True, action='store_true')
    parser.add_argument('--dsn-env', default='CONTRACTOR_IDENTITY_AUDIT_DSN')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', args.dsn_env) or not os.environ.get(args.dsn_env):
        parser.error('Set an explicit audit DSN environment variable; .env is not loaded')
    try:
        report = run_audit(lambda: psycopg2.connect(os.environ[args.dsn_env]), args.company_id,
                           limit=args.limit, offset=args.offset)
    except Exception:
        # Connection and schema errors can contain credentials/host metadata.
        print(json.dumps({'status': 'blocked', 'reason': 'AUDIT_UNAVAILABLE', 'canApply': False}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
