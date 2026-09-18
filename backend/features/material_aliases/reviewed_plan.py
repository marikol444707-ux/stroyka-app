"""Offline validation of explicit historical ownership reviews; never imports data.

Caller must provide an authorized inventory. Reviewer/evidence fields are audit
references, NOT authentication or proof that a user has authority to apply a plan.
No HTTP route, database connection, assignment inference or executable SQL.
"""
from collections import Counter, defaultdict
import hashlib
import json

from .readiness import _alias_key, _positive_id


def legacy_alias_fingerprint(row):
    fields = ('id', 'active', 'project_name', 'alias_name', 'canonical_name', 'canonical_unit')
    payload = json.dumps({key: row.get(key) for key in fields}, ensure_ascii=False,
                         sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def build_reviewed_alias_plan(company_id, sources, projects, decisions, existing):
    if not _positive_id(company_id):
        raise ValueError('explicit company_id required')
    by_source, by_review = defaultdict(list), defaultdict(list)
    issues = []
    for row in sources:
        if not _positive_id(row.get('id')):
            issues.append({'aliasId': None, 'reasonCode': 'invalid_source_id'})
            continue
        by_source[row.get('id')].append(row)
    for decision in decisions:
        if not _positive_id(decision.get('aliasId')):
            issues.append({'aliasId': None, 'reasonCode': 'invalid_review_id'})
            continue
        by_review[decision.get('aliasId')].append(decision)
    project_owners = defaultdict(list)
    for project in projects:
        if not _positive_id(project.get('id')):
            continue
        project_owners[project.get('id')].append(_positive_id(project.get('company_id')))
    occupied = {(row.get('project_id'), _alias_key(row.get('alias_name')))
                for row in existing if row.get('active') is True and row.get('company_id') == company_id}
    candidates = []
    def issue(alias_id, reason):
        issues.append({'aliasId': _positive_id(alias_id), 'reasonCode': reason})

    for alias_id in dict.fromkeys([*by_source, *by_review]):
        rows, reviews = by_source[alias_id], by_review[alias_id]
        if not _positive_id(alias_id) or len(rows) != 1:
            issue(alias_id, 'unknown_or_duplicate_source')
            continue
        row = rows[0]
        if row.get('active') is not True:
            if reviews:
                issue(alias_id, 'inactive_source')
            continue
        if len(reviews) != 1:
            issue(alias_id, 'duplicate_review' if reviews else 'missing_review')
            continue
        review = reviews[0]
        if review.get('sourceFingerprint') != legacy_alias_fingerprint(row):
            issue(alias_id, 'stale_source')
            continue
        project_id = review.get('projectId')
        if (type(review.get('companyId')) is not int or review['companyId'] != company_id
                or 'projectId' not in review
                or (project_id is not None and (not _positive_id(project_id)
                    or project_owners[project_id] != [company_id]))):
            issue(alias_id, 'invalid_explicit_owner')
            continue
        if not _positive_id(review.get('reviewedById')) or not str(review.get('evidenceRef') or '').strip():
            issue(alias_id, 'missing_review_evidence')
            continue
        key = (project_id, _alias_key(row.get('alias_name')))
        if not key[1] or not str(row.get('canonical_name') or '').strip():
            issue(alias_id, 'invalid_mapping')
            continue
        if key in occupied:
            issue(alias_id, 'existing_owned_key')
            continue
        candidates.append((key, {'aliasId': alias_id, 'companyId': company_id,
                                'projectId': project_id, 'sourceFingerprint': review['sourceFingerprint'],
                                'reviewedById': review['reviewedById']}))
    counts = Counter(key for key, _ in candidates)
    reviewed = []
    for key, candidate in candidates:
        if counts[key] != 1:
            issue(candidate['aliasId'], 'duplicate_target_key')
        else:
            reviewed.append(candidate)
    return {'dryRun': True, 'writesAttempted': 0, 'automaticAssignments': 0,
            'readyForCutover': False, 'companyId': company_id,
            'reviewedCount': len(reviewed), 'reviewed': reviewed,
            'issueCount': len(issues), 'issues': issues}
