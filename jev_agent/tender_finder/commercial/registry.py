"""Scoped, locked atomic baseline/history. No DB, legacy migration or deletion."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
import stat

from ..state import Scope, RequestConflict, StorageError, _atomic, _directory, _read


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def identity(row):
    # An explicit legal counterparty identity + object identity permits cross-site
    # merge. Names, brands, titles and address similarity do not prove identity.
    return digest(['procedure', row['source'], row['number']])


def aliases(row):
    values = row['values']
    cross_site = ({digest(['canonical', values['counterparty_id'], values['object_id'], values['procedure_id']])}
                  if all(values.get(key) for key in ('counterparty_id', 'object_id', 'procedure_id')) else set())
    return {identity(row)} | cross_site | set(row.get('aliases', ()))


def compare(rows, previous):
    baseline = previous is None
    prior = {} if baseline else previous['records']
    records = deepcopy(prior)
    changes, additions = [], []
    seen = set()
    for row in rows:
        key = identity(row)
        matches = [(old_key, old) for old_key, old in records.items()
                   if aliases(row) & aliases(old)]
        if len(matches) > 1: raise ValueError('ambiguous_procedure_identity')
        old_key, old = matches[0] if matches else (key, None)
        row = deepcopy(row)
        if old:
            row['links'] = sorted(set(old['links']) | set(row['links']))
            row['aliases'] = sorted(aliases(old) | aliases(row))
        if old_key in seen: raise ValueError('duplicate_procedure_in_run')
        seen.add(old_key)
        if old is None:
            if not baseline: additions.append(old_key)
        else:
            last_known = old.get('last_known_values', old['values'])
            for field in sorted(row['values']):
                before, after = last_known.get(field), row['values'][field]
                if before != after:
                    changes.append({'key': old_key, 'number': row['number'], 'field': field,
                                    'before': before, 'after': after,
                                    'evidence': row['evidence'].get(field), 'detected_at': row['checked_at']})
            old_revisions = {(e['url'], e['document']): e['sha256'] for entries in old['evidence'].values()
                             for e in entries if 'sha256' in e}
            revisions = {(e['url'], e['document']): e for entries in row['evidence'].values()
                         for e in entries if 'sha256' in e}
            for doc, evidence in sorted(revisions.items()):
                if doc in old_revisions and old_revisions[doc] != evidence['sha256']:
                    changes.append({'key': old_key, 'number': row['number'], 'field': 'document_revision',
                                    'before': old_revisions[doc], 'after': evidence['sha256'],
                                    'evidence': evidence, 'detected_at': row['checked_at']})
        row['last_known_values'] = {**(old.get('last_known_values', old['values']) if old else {}), **row['values']}
        records[old_key] = row
    return records, additions, changes, baseline


def deduplicate(rows):
    """Only verified canonical procedure/counterparty/object IDs permit merge."""
    result = []
    for incoming in rows:
        matches = [old for old in result if aliases(old) & aliases(incoming)]
        if len(matches) > 1: raise ValueError('ambiguous_procedure_identity')
        if not matches:
            result.append(deepcopy(incoming)); continue
        old = matches[0]
        old['aliases'] = sorted(aliases(old) | aliases(incoming))
        old['links'] = sorted(set(old['links']) | set(incoming['links']))
        old['risks'] = sorted(set(old['risks']) | set(incoming['risks']))
        old['exclusions'] = sorted(set(old['exclusions']) | set(incoming['exclusions']))
        for field, evidence in incoming['evidence'].items():
            old['evidence'].setdefault(field, []).extend(e for e in evidence if e not in old['evidence'][field])
        for field in set(old['values']) | set(incoming['values']):
            if field in old['values'] and field in incoming['values'] and old['values'][field] != incoming['values'][field]:
                old['conflicts'] = sorted(set(old['conflicts']) | {field})
                old['values'].pop(field, None)
            elif field not in old['conflicts'] and field in incoming['values']:
                old['values'][field] = incoming['values'][field]
        if old['conflicts'] or old['bucket'] != incoming['bucket']:
            old['bucket'] = 'unconfirmed'
            old['risks'] = sorted(set(old['risks']) | {'Противоречия публикаций одной процедуры'})
        if old['exclusions']: old['bucket'] = 'excluded'
        old['direct_contract_confirmed'] &= incoming['direct_contract_confirmed']
    return result


@contextmanager
def registry(directory, scope):
    if type(scope) is not Scope: raise StorageError('protected_scope_required')
    key = scope.key()
    fd = _directory(directory, private=True)
    lock = None
    try:
        lock = os.open('commercial-v3.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=fd)
        info = os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            raise StorageError('unsafe_commercial_lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = _read(fd, 'commercial-v3.json', private=True)
        if raw is None and set(os.listdir(fd)) - {'commercial-v3.lock'}:
            raise StorageError('separate_empty_commercial_namespace_required')
        previous = json.loads(raw) if raw else None
        if previous is not None and (previous.get('format') != 3 or previous.get('scope') != key):
            raise RequestConflict('commercial_registry_scope_conflict')
        def save(value):
            _atomic(fd, 'commercial-v3.json', {'format': 3, 'scope': key, **value}, replace=True)
        yield previous, save
    finally:
        if lock is not None: os.close(lock)
        os.close(fd)
