"""Shared strict identifiers for contractor evidence and explicit selections."""

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
