"""Conservative offline provenance audit. A candidate is NOT permission to bind it."""
from collections import Counter, defaultdict

JOURNALS = ('material_inspection_journal', 'cable_journal')
SOURCE_FIELDS = {'delivery_id': 'supply_delivery', 'invoice_id': 'warehouse_invoice',
                 'warehouse_history_id': 'warehouse_history'}


def positive_id(value):
    return value if type(value) is int and 0 < value <= 9223372036854775807 else None


def index_rows(rows):
    result = defaultdict(list)
    for row in rows:
        if positive_id(row.get('id')):
            result[row['id']].append(row)
    return result


def classify(row, projects, sources):
    references = {}
    for field, namespace in SOURCE_FIELDS.items():
        value = row.get(field)
        if value is not None:
            if not positive_id(value):
                return 'invalid_source_id', None
            references[namespace] = value
    namespace, source_id = row.get('source_type'), row.get('source_id')
    if namespace == 'project_stock':
        return 'stock_without_primary_document', None
    if namespace or source_id is not None:
        if namespace not in SOURCE_FIELDS.values():
            return 'unsupported_source_type', None
        if not positive_id(source_id):
            return 'invalid_source_id', None
        if namespace in references and references[namespace] != source_id:
            return 'source_reference_conflict', None
        references[namespace] = source_id
    if not references:
        return 'no_source_reference', None
    owners = set()
    for namespace, source_id in references.items():
        found = sources[namespace].get(source_id, [])
        if len(found) != 1:
            return 'source_not_found_or_duplicate', None
        source = found[0]
        company, project = positive_id(source.get('company_id')), positive_id(source.get('project_id'))
        if not company or not project:
            return 'source_owner_incomplete', None
        candidates = projects.get(project, [])
        if len(candidates) != 1 or positive_id(candidates[0].get('company_id')) != company:
            return 'source_project_conflict', None
        owners.add((company, project))
    if len(owners) != 1:
        return 'source_owner_conflict', None
    company, project = next(iter(owners))
    for field, expected in (('company_id', company), ('project_id', project)):
        if row.get(field) is not None and positive_id(row[field]) != expected:
            return 'stored_owner_conflict', None
    return 'exact_sources_require_review', {'companyId': company, 'projectId': project}


def build_quality_ownership_report(journals, projects, sources, *, preview_limit=100):
    """Inputs must be authorized, complete inventories with snake_case DB fields.

    No names, supplier details or document content are emitted. Historical default
    company IDs and source correctness still require human review, even when all
    stored IDs agree. Names never supply a missing immutable project ID.
    """
    if type(preview_limit) is not int or not 0 <= preview_limit <= 1000:
        raise ValueError('preview_limit must be between 0 and 1000')
    if set(journals) != set(JOURNALS) or set(sources) != set(SOURCE_FIELDS.values()):
        raise ValueError('complete journal and source inventories required')
    project_index = index_rows(projects)
    source_indexes = {name: index_rows(rows) for name, rows in sources.items()}
    counts, preview, total = Counter(), [], 0
    for table in JOURNALS:
        rows = journals[table]
        ids = Counter(row.get('id') for row in rows if positive_id(row.get('id')))
        for row in rows:
            journal_id = positive_id(row.get('id'))
            owner = None
            if not journal_id:
                reason = 'invalid_journal_id'
            elif ids[journal_id] > 1:
                reason = 'duplicate_journal_id'
            else:
                reason, owner = classify(row, project_index, source_indexes)
            total += 1
            counts[reason] += 1
            if len(preview) < preview_limit:
                preview.append({'table': table, 'journalId': journal_id, 'reasonCode': reason,
                                'candidateOwner': owner})
    return {'ok': True, 'dryRun': True, 'writesAttempted': 0, 'automaticAssignments': 0,
            'readyForCutover': False, 'totalRows': total, 'reasonCounts': dict(sorted(counts.items())),
            'preview': preview, 'previewTruncated': total > len(preview)}
