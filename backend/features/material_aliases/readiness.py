"""Read-only legacy alias audit. Names identify candidates, never proven owners."""
from collections import Counter, defaultdict
import re


def _positive_id(value):
    return value if type(value) is int and value > 0 else None


def _alias_key(value):
    # Mirrors legacy _norm_key_text for collision diagnostics, not authorization.
    return re.sub(r'\s+', ' ', re.sub(r'[.,;:()«»"\'`/\\]+', ' ', str(value or '').lower())).strip()


def build_alias_readiness(projects, aliases, *, preview_limit=100):
    if type(preview_limit) is not int or preview_limit < 0:
        raise ValueError('preview_limit must be a nonnegative integer')
    by_name = defaultdict(list)
    for row in projects:
        # Archived objects can still own historical aliases; never discard them.
        by_name[str(row.get('name') or '')].append(row)
    reasons = Counter()
    issues, groups = [], defaultdict(list)
    active_count = 0
    for row in sorted(aliases, key=lambda r: _positive_id(r.get('id')) or 0):
        if row.get('active') is not True:
            continue
        active_count += 1
        project_name = str(row.get('project_name') or '')
        candidate_rows = by_name.get(project_name, [])
        company_ids = sorted({_positive_id(p.get('company_id')) for p in candidate_rows
                              if _positive_id(p.get('company_id'))})
        project_ids = sorted({_positive_id(p.get('id')) for p in candidate_rows
                              if _positive_id(p.get('id'))})
        if not _positive_id(row.get('id')) or not _alias_key(row.get('alias_name')) or not str(row.get('canonical_name') or '').strip():
            reason = 'invalid_mapping'
        elif not project_name.strip():
            reason = 'global_scope_unowned'
        elif not candidate_rows:
            reason = 'project_not_found'
        elif any(not _positive_id(p.get('company_id')) or not _positive_id(p.get('id')) for p in candidate_rows):
            reason = 'project_owner_invalid'
        elif len(company_ids) > 1:
            reason = 'cross_company_name_collision'
        elif len(project_ids) > 1:
            reason = 'same_company_name_collision'
        else:
            reason = 'candidate_requires_confirmation'
        reasons[reason] += 1
        if len(issues) < preview_limit:
            issue = {'reasonCode': reason, 'aliasId': _positive_id(row.get('id'))}
            if candidate_rows and project_name.strip():
                issue['candidateCompanyIds'] = company_ids[:preview_limit]
                issue['candidateProjectIds'] = project_ids[:preview_limit]
                issue['candidatesTruncated'] = max(len(company_ids), len(project_ids)) > preview_limit
            issues.append(issue)
        groups[(project_name, _alias_key(row.get('alias_name')))].append(row)

    conflict_count, conflicts = 0, []
    for rows in groups.values():
        # Differing units count conservatively; this audit never rewrites units.
        targets = {(str(r.get('canonical_name') or '').strip().lower(),
                    str(r.get('canonical_unit') or '').strip().lower()) for r in rows}
        if len(targets) <= 1:
            continue
        conflict_count += 1
        if len(conflicts) < preview_limit:
            ids = sorted({_positive_id(r.get('id')) for r in rows if _positive_id(r.get('id'))})
            conflicts.append({'reasonCode': 'conflicting_active_targets',
                              'aliasIds': ids[:preview_limit], 'aliasIdsTruncated': len(ids) > preview_limit})
    return {
        'ok': True, 'dryRun': True, 'writesAttempted': 0,
        'automaticAssignments': 0, 'readyForCutover': False,
        'summary': {'projects': len(projects), 'aliases': len(aliases),
                    'activeAliases': active_count, 'inactiveAliases': len(aliases) - active_count},
        'issueCount': sum(reasons.values()), 'reasonCounts': dict(sorted(reasons.items())),
        'issues': issues, 'issuesTruncated': sum(reasons.values()) > len(issues),
        'conflictCount': conflict_count, 'conflicts': conflicts,
        'conflictsTruncated': conflict_count > len(conflicts),
    }
