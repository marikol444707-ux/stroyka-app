"""Conservative legal-key comparison, never an ownership or access grant.

Only formatting separators are ignored. Letters, punctuation other than a hyphen,
Unicode digits and wrong lengths are not silently converted into an identity.
Historical documents and supplier snapshots are never rewritten here.
"""
import re

SEPARATORS = ' \t\r\n\f\v\u00a0-'
LENGTHS = {'inn': (10, 12), 'ogrn': (13, 15)}


def canonical_legal(value, lengths):
    text = str(value or '')
    if not text.strip(SEPARATORS):
        return ''
    if any(char not in '0123456789' + SEPARATORS for char in text):
        return None
    digits = text.translate(str.maketrans('', '', SEPARATORS))
    return digits if len(digits) in lengths else None


def legal_sql(column, lengths):
    """SQL fragment for trusted internal column names, same semantics as Python."""
    if not re.fullmatch(r'[a-z_][a-z_0-9]*(?:\.[a-z_][a-z_0-9]*)?', column):
        raise ValueError('Expected a trusted SQL column')
    lengths = tuple(int(n) for n in lengths)
    # translate removes exactly the separators above; a digit-only regex then
    # rejects every other character rather than deleting it.
    value = f"translate(COALESCE({column},''), E' \\t\\r\\n\\f\\013\\u00a0-', '')"
    pattern = '^(' + '|'.join('[0-9]{' + str(n) + '}' for n in lengths) + ')$'
    return f"(CASE WHEN {value} ~ '{pattern}' THEN {value} ELSE NULL END)"


def legal_lock_keys(values):
    keys = set()
    for key, value in values:
        raw = str(value or '').strip()
        if raw:
            keys.add(raw)
        normalized = canonical_legal(value, LENGTHS[key])
        if normalized:
            keys.add(normalized)
    return sorted(keys)


def lock_legal_keys(cur, values):
    for key in legal_lock_keys(values):
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                    ('supplier-legal:' + key,))
