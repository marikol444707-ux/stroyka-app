"""Conservative text-only suggestions, not OCR, authorization or legal verification.

Only contiguous, explicitly labelled requisites blocks are supported. Unknown
lines end a block: guessing their relationship could attach another party's bank
account. Callers must authorize the source and obtain expected INNs themselves.
This module performs no I/O and is deliberately not wired to a public endpoint.
"""
import re


SIDES = {'покупатель': 'buyer', 'плательщик': 'payer', 'поставщик': 'supplier'}
LABELS = {
    'наименование': 'fullName', 'инн': 'inn', 'кпп': 'kpp', 'огрн': 'ogrn',
    'юридический адрес': 'legalAddress', 'банк': 'bankName', 'бик': 'bik',
    'р/с': 'rs', 'расчетный счет': 'rs', 'расчётный счёт': 'rs',
    'к/с': 'ks', 'корреспондентский счет': 'ks', 'корреспондентский счёт': 'ks',
    'подписант': 'directorName', 'должность подписанта': 'directorPosition',
    'основание полномочий': 'basis', 'телефон': 'phone', 'email': 'email',
}
LENGTHS = {
    'fullName': 500, 'legalAddress': 2000, 'bankName': 500, 'directorName': 255,
    'directorPosition': 255, 'basis': 1000, 'phone': 100, 'email': 255,
}
DIGITS = {'inn': (10, 12), 'kpp': (9,), 'ogrn': (13, 15), 'bik': (9,), 'rs': (20,), 'ks': (20,)}
HEADER = re.compile(r'^(покупатель|плательщик|поставщик)\s*:?$', re.IGNORECASE)
FIELD = re.compile(r'^(' + '|'.join(re.escape(k) for k in LABELS) + r')\s*:\s*(.*)$', re.IGNORECASE)
EMBEDDED_LABEL = re.compile(r'(?:' + '|'.join(re.escape(k) for k in LABELS) + r')\s*:', re.IGNORECASE)


def _valid_value(field, value):
    if not value or EMBEDDED_LABEL.search(value):
        return False
    if field in DIGITS:
        return bool(re.fullmatch(r'[0-9]+', value)) and len(value) in DIGITS[field]
    return len(value) <= LENGTHS[field] and not any(ord(char) < 32 for char in value)


def _parse_block(lines, expected_inn):
    candidates, warnings, invalid = {}, [], set()
    for line_number, quote, match in lines:
        field, value = LABELS[match[1].lower()], match[2].strip()
        if not _valid_value(field, value):
            invalid.add(field)
            warnings.append(field + ':invalid_value')
            continue
        candidates.setdefault(field, []).append({'value': value, 'line': line_number, 'quote': quote})
    fields = {}
    for field, values in candidates.items():
        if len({item['value'] for item in values}) > 1:
            warnings.append(field + ':conflicting_values')
        elif field not in invalid:
            fields[field] = values[0]
    status = 'matched'
    if 'inn' not in fields:
        status = 'ambiguous'
        warnings.append('inn:missing_or_ambiguous')
    elif fields['inn']['value'] != expected_inn:
        status = 'identity_mismatch'
        warnings.append('inn:does_not_match_selected_party')
    return {'status': status, 'fields': fields if status == 'matched' else {},
            'warnings': list(dict.fromkeys(warnings))}


def extract_contract_parties(text, expected_inns):
    """Return unconfirmed suggestions with 1-based lines in the supplied text.

    Accepts <=64,000 characters and exactly three server-resolved INN strings.
    Matching means literal agreement only, not tax-registry/checksum validation.
    Quotes are untrusted plain text, not HTML. No payer=buyer inference is made.
    Oversized or invalid inputs raise a generic ValueError without source data.
    """
    if not isinstance(text, str) or len(text) > 64000:
        raise ValueError('Invalid contract text (maximum 64000 characters)')
    if (not isinstance(expected_inns, dict) or set(expected_inns) != set(SIDES.values())
            or any(not isinstance(value, str) or not re.fullmatch(r'(?:[0-9]{10}|[0-9]{12})', value)
                   for value in expected_inns.values())):
        raise ValueError('Three valid selected-party INNs are required')
    blocks = {side: [] for side in SIDES.values()}
    active = None
    warnings = []
    for line_number, quote in enumerate(text.splitlines(), 1):
        line = quote.strip()
        if not line:
            continue
        header = HEADER.fullmatch(line)
        if header:
            active = []
            blocks[SIDES[header[1].lower()]].append(active)
            continue
        match = FIELD.fullmatch(line)
        if active is not None and match:
            active.append((line_number, quote, match))
        else:
            if active is not None:
                warnings.append('unrecognized_line_ends_block:' + str(line_number))
            active = None
    parties = {}
    for side, side_blocks in blocks.items():
        if len(side_blocks) == 1:
            parties[side] = _parse_block(side_blocks[0], expected_inns[side])
        else:
            parties[side] = {
                'status': 'ambiguous' if side_blocks else 'missing', 'fields': {},
                'warnings': ['multiple_party_blocks' if side_blocks else 'party_block_not_found'],
            }
    return {'source': 'labelled_text', 'parties': parties, 'warnings': warnings,
            'reviewConfirmed': False, 'appliedToAccounting': False}
