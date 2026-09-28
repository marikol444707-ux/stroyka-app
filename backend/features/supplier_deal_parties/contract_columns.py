"""Suggestions from separated requisites columns, always anchored by exact INN.

No spelling, digit or grammatical repair. Evidence quotes retain original lines.
"""
import re

ROLE = re.compile(r'^\s*(ПОСТАВЩИК|ПОКУПАТЕЛЬ|ПЛАТЕЛЬЩИК)\s*:?\s*$', re.I)
IDENTITY = re.compile(r'(?<!\d)(\d{10}|\d{12})\s*/\s*(\d{9})(?!\d)')
SIDES = {'поставщик': 'supplier', 'покупатель': 'buyer', 'плательщик': 'payer'}
STOP = re.compile(r'^(?:почтов\w*\s+адр|[рpкk]\s*/\s*[сc]|БИК|[ТГ]ел|[ecе]-?mail|ОГР|ИНН)', re.I)


def extract_columns(text, expected, parties):
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.search(r'реквизит\w*.*сторон', line, re.I)]
    if not starts:
        return set()
    start = starts[-1]
    end = min(len(lines), start + 200)
    headers = [(i, SIDES[m[1].lower()]) for i in range(start, end) if lines[i].strip().isupper() and (m := ROLE.fullmatch(lines[i]))]
    blocks = {side: [] for side in expected}
    for position, (begin, side) in enumerate(headers):
        finish = headers[position + 1][0] if position + 1 < len(headers) else end
        hits = [(i, m) for i in range(begin + 1, finish) for m in IDENTITY.finditer(lines[i])]
        if hits:
            blocks[side].append((begin, finish, hits))
    handled = set()
    for side, candidates in blocks.items():
        if not candidates:
            continue
        handled.add(side)
        if len(candidates) != 1 or len(candidates[0][2]) != 1:
            parties[side] = {'status': 'ambiguous', 'fields': {}, 'warnings': ['multiple_column_identities']}
            continue
        begin, finish, [(identity_line, identity)] = candidates[0]
        extra_inns = [m[1] for line in lines[begin+1:finish]
                      if (m := re.match(r'^ИНН\s*:?\s+(\d{10}|\d{12})(?!\d)', line.strip(), re.I))]
        if any(value != identity[1] for value in extra_inns):
            parties[side] = {'status': 'ambiguous', 'fields': {}, 'warnings': ['multiple_column_identities']}
            continue
        if identity[1] != expected[side]:
            parties[side] = {'status': 'identity_mismatch', 'fields': {}, 'warnings': ['inn:does_not_match_selected_party']}
            continue
        fields = {}
        def add(field, value, first, last=None):
            if value:
                fields[field] = {'value': value, 'line': first + 1,
                                 'quote': '\n'.join(lines[first:(last if last is not None else first) + 1])}
        add('inn', identity[1], identity_line)
        add('kpp', identity[2], identity_line)
        patterns = {
            'ogrn': r'^ОГР[НИ](?:ИП)?\s*:?\s*(\d{13}|\d{15})\s*$',
            'rs': r'^[рp]\s*/\s*[сc]\s*:?\s*(\d{20})\s*$',
            'ks': r'^[кk]\s*/\s*[сc]\s*:?\s*(\d{20})\s*$',
            'bik': r'^БИК\s*:?\s*(\d{9})\s*$',
            'phone': r'^[\"\s]*[ТГ]ел\.?\s*(?:/\s*факс)?\s*:?\s*([+\d(][\d\s()+,;-]{5,99})\s*$',
            'email': r'^[ecе]-?mail\s*:\s*([\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})\s*$',
        }
        numeric_labels = {'ogrn': r'^ОГР[НИ]', 'rs': r'^[рp]\s*/\s*[сc]',
                          'ks': r'^[кk]\s*/\s*[сc]', 'bik': r'^БИК'}
        positions = {}
        for field, pattern in patterns.items():
            hits = [(i, m) for i in range(begin + 1, finish) if (m := re.fullmatch(pattern, lines[i].strip(), re.I))]
            labelled = sum(bool(re.match(numeric_labels[field], lines[i].strip(), re.I)) for i in range(begin+1, finish)) if field in numeric_labels else len(hits)
            if len(hits) == labelled and len({m[1] for _, m in hits}) == 1:
                i, match = hits[0]
                add(field, match[1], i)
                positions[field] = i
        names = [(i, lines[i].strip()) for i in range(begin + 1, identity_line)
                 if re.match(r'^(?:ООО|АО|ПАО|ИП|ЗАО|ОАО)\s+[«"]', lines[i].strip())]
        if len(names) == 1:
            add('fullName', names[0][1], names[0][0])
        addresses = [(i, m) for i in range(begin + 1, finish)
                     if (m := re.match(r'^Юридич[еcс]ский\s+адр[еcс]с\s*:\s*(.*)$', lines[i].strip(), re.I))]
        if len(addresses) == 1:
            first, match = addresses[0]
            values = [match[1]] if match[1] else []
            last = first
            for i in range(first + 1, min(finish, first + 7)):
                value = lines[i].strip()
                if STOP.match(value):
                    break
                if value:
                    values.append(value)
                last = i
            value = ' '.join(values)
            if value and len(value) <= 2000:
                add('legalAddress', value, first, last)
        # Only text physically BETWEEN this party's settlement/correspondent
        # accounts can be an unlabelled bank name. Never include contact lines.
        rs, ks = positions.get('rs'), positions.get('ks')
        if rs is not None and ks is not None and 0 < ks - rs <= 7:
            bank = ' '.join(line.strip() for line in lines[rs + 1:ks] if line.strip())
            if bank and len(bank) <= 500 and re.search(r'банк|филиал|ПАО|ООО|АО', bank, re.I) and not any(STOP.match(line.strip()) for line in lines[rs+1:ks]):
                add('bankName', bank, rs + 1, ks - 1)
        parties[side] = {'status': 'matched', 'fields': fields, 'warnings': ['ocr_requisites_require_review']}
        _signer(text, side, fields)
    return handled


def _signer(text, side, fields):
    """Bind a preamble declaration by BOTH role and the column's company name."""
    name = fields.get('fullName', {}).get('value', '')
    quoted = re.search(r'[«"]([^»"]+)[»"]', name)
    if not quoted:
        return
    role = next(k for k, v in SIDES.items() if v == side)
    preamble = text[:6000]
    pattern = re.compile(r'[«"]' + role + r'[»"]\s*,?\s*в\s+лице\s+'
                         r'(?P<position>(?:Генерального\s+)?директора)\s+'
                         r'(?P<name>[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+)\s*,\s*'
                         r'действующ\w*\s+на\s+основании\s+(?P<basis>[^,\n.]{2,150})', re.I)
    matches = []
    for match in pattern.finditer(preamble):
        preceding = preamble[max(0, match.start()-350):match.start()]
        # The nearest quoted organization must agree, not just any earlier name.
        names = re.findall(r'[«"]([^»"\n]+)[»"]', preceding)
        if names and names[-1].casefold() == quoted[1].casefold():
            matches.append(match)
    if len(matches) != 1:
        return
    match = matches[0]
    begin = preamble.rfind('\n', 0, match.start()) + 1
    end = preamble.find('\n', match.end())
    if end < 0:
        end = len(preamble)
    for field, group in [('directorName', 'name'), ('directorPosition', 'position'), ('basis', 'basis')]:
        fields[field] = {'value': ' '.join(match[group].split()), 'line': preamble.count('\n', 0, begin)+1,
                         'quote': preamble[begin:end]}
