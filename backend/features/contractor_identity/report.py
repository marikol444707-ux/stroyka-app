"""Company-scoped legacy identity audit. No migration or access-grant command."""
import argparse
from collections import Counter
import hashlib
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

from ..contractor_contract_parties.snapshot import snapshot_digest

PERFORMER_ROLES = {'мастер', 'субподрядчик', 'бригадир'}


def positive_id(value):
    if type(value) is not int or not 0 < value <= 2147483647:
        raise ValueError('INVALID_ID')
    return value


def classify_reference(row):
    """Names/emails never disambiguate a historical user/staff ID collision."""
    result = {'contractId': row['id'], 'status': 'blocked', 'reason': '', 'reference': None}

    def finish(reason, reference=None):
        return {**result, 'status': 'review_required' if reference else 'blocked',
                'reason': reason, 'reference': reference}

    if row['project_company_id'] != row['company_id'] or row['project_id'] is None:
        return finish('PROJECT_OWNER_UNVERIFIED')
    if row['contractor_id'] is None:
        return finish('UNLINKED_LEGACY_CONTRACT')
    try:
        user_id = positive_id(row['contractor_id'])
    except ValueError:
        return finish('INVALID_LEGACY_ID')
    if row['user_id'] != user_id:
        return finish('LEGACY_STAFF_REFERENCE_UNVERIFIED' if row['staff_id'] else 'USER_REFERENCE_MISSING')
    if row['user_active'] is not True:
        return finish('USER_INACTIVE')
    if not row['membership_ids']:
        return finish('COMPANY_MEMBERSHIP_UNVERIFIED')
    if not PERFORMER_ROLES.intersection(row['membership_roles']):
        return finish('PERFORMER_ROLE_UNVERIFIED')

    snapshot, digest = row['party_snapshot_json'], row['party_snapshot_hash']
    frozen = snapshot is not None or digest is not None
    if frozen:
        if (not isinstance(snapshot, dict) or type(snapshot.get('schemaVersion')) is not int
                or snapshot.get('schemaVersion') != 1
                or not isinstance(digest, str) or snapshot_digest(snapshot) != digest):
            return finish('FROZEN_IDENTITY_UNVERIFIED')
        for key, expected in (('customer', ('companyId', row['company_id'])),
                              ('contractor', ('userId', user_id)),
                              ('project', ('id', row['project_id'])),
                              ('contract', ('id', row['id']))):
            part = snapshot.get(key)
            if not isinstance(part, dict) or type(part.get(expected[0])) is not int or part[expected[0]] != expected[1]:
                return finish('FROZEN_IDENTITY_CONFLICT')
    elif row['status'] == 'Подписан':
        return finish('SIGNED_IDENTITY_MISSING')
    if not frozen and row['staff_id'] is not None and row['staff_user_ids'] != [user_id]:
        return finish('AMBIGUOUS_USER_STAFF_ID')
    return finish('FROZEN_USER_REFERENCE' if frozen else 'CANDIDATE_USER_REFERENCE',
                  {'type': 'user', 'id': user_id})


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
    cur.execute('''SELECT bc.id,bc.company_id,bc.project_id,bc.contractor_id,bc.status,
            bc.party_snapshot_json,bc.party_snapshot_hash,p.company_id AS project_company_id,
            u.id AS user_id,u.active AS user_active,s.id AS staff_id,
            ARRAY(SELECT m.id FROM user_company_roles m
                WHERE m.user_id=u.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.id) AS membership_ids,
            ARRAY(SELECT DISTINCT m.role FROM user_company_roles m
                WHERE m.user_id=u.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.role) AS membership_roles,
            ARRAY(SELECT DISTINCT m.user_id FROM user_company_roles m
                WHERE m.staff_id=s.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.user_id) AS staff_user_ids
        FROM brigade_contracts bc
        LEFT JOIN projects p ON p.id=bc.project_id
        LEFT JOIN users u ON u.id=bc.contractor_id
        LEFT JOIN staff s ON s.id=bc.contractor_id AND s.company_id=bc.company_id
        WHERE bc.company_id=%s ORDER BY bc.id LIMIT %s OFFSET %s''',
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
