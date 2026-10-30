"""Offline evidence evaluation, NOT a search or a server installation command.

stdin is an explicit exported evidence bundle, <=2 MiB. It does not establish
that its author actually visited a site. Live adapters must produce captures via
the protected runner; model-provided JSON is never accepted by the v2 broker.
"""
import json
import sys
from datetime import datetime, timezone

from .model import Candidate, Document, Fact, Profile
from .policy import assess
from .sources import source_registry


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate_field')
        result[key] = value
    return result


def evaluate(bundle, *, now=None):
    if type(bundle) is not dict or set(bundle) != {'format', 'candidates'} or bundle['format'] != 3:
        raise ValueError('commercial_evidence_bundle_required')
    if type(bundle['candidates']) is not list or len(bundle['candidates']) > 100:
        raise ValueError('bounded_candidate_list_required')
    now = now or datetime.now(timezone.utc)
    hosts = {key: source.hosts for key, source in source_registry().items()}
    results = []
    for entry in bundle['candidates']:
        if type(entry) is not dict or set(entry) != {'source', 'number', 'documents', 'facts'}:
            raise ValueError('explicit_candidate_fields_required')
        documents = []
        for raw in entry['documents']:
            if type(raw) is not dict or set(raw) != {'id', 'source', 'url', 'name', 'kind', 'checked_at', 'text'}:
                raise ValueError('explicit_document_fields_required')
            documents.append(Document(**{**raw, 'checked_at': datetime.fromisoformat(raw['checked_at'])}))
        candidate = Candidate(entry['source'], entry['number'], tuple(documents),
                              {name: tuple(Fact(**fact) for fact in facts)
                               for name, facts in entry['facts'].items()})
        results.append(assess(candidate, now, hosts, Profile()))
    return {'format': 3, 'mode': 'offline_supplied_evidence', 'search_executed': False,
            'independent_source_verification': False, 'registry_changed': False,
            'notifications_sent': False, 'results': results}


def main():
    try:
        if sys.argv[1:] != ['evaluate']: raise ValueError('explicit_evaluate_operation_required')
        raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024: raise ValueError('bundle_size_limit')
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_number')))
        print(json.dumps(evaluate(value), ensure_ascii=False, allow_nan=False))
        return 0
    except Exception:
        # Never echo malformed input/tracebacks which can contain credentials.
        print(json.dumps({'ok': False, 'reason': 'invalid_commercial_evidence_bundle',
                          'search_executed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
